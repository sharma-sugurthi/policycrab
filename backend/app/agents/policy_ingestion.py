"""
Agent 1: Policy Ingestion — Two-phase pipeline for full-document RAG indexing
and structured profile extraction.

Phase 1 — RAG Indexing (NEW):
  Chunks the full policy PDF page-by-page using LangChain's splitter.
  Embeds each chunk with Gemini Embedding and stores it in Supabase.
  This enables the Policy Analyzer Agent to later perform exact page-cited
  semantic searches against the patient's specific policy document.

Phase 2 — Profile Extraction (ENHANCED):
  Extracts the high-level PolicyProfile (deductibles, plan type, etc.)
  by summarizing only the first 10 pages. This prevents LLM context
  overflow on 100+ page documents while still capturing the SBC fields.
"""

import json
import logging
import re
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.agents.state import AgentState
from app.services.llm_router import get_llm, TaskType, embed_document_chunks
from app.services.supabase_client import insert_policy_chunks, save_policy_session
from app.models.policy import PolicyProfile

logger = logging.getLogger(__name__)

# Chunk settings — tuned for insurance policy language
CHUNK_SIZE = 800        # ~600-800 tokens; insurance clauses are dense
CHUNK_OVERLAP = 150     # Preserve context across clause boundaries

POLICY_EXTRACTION_PROMPT = """You are a US health insurance policy analyst. Extract structured 
policy information from the provided document text (SBC, EOB, or policy summary).

CRITICAL RULE: If a field is not explicitly stated in the document, you MUST return null.
DO NOT guess, assume, or fabricate reasonable defaults based on industry norms.

Required fields:
- plan_name: The name of the insurance plan
- carrier_name: The insurance company name
- plan_type: One of "HMO", "PPO", "EPO", "POS"
- legal_classification: One of "FULLY_INSURED", "SELF_FUNDED_ERISA", "MEDICARE_ADVANTAGE", 
  "MEDICARE_ORIGINAL", "MEDICAID_MANAGED", "INDIVIDUAL_ACA"
  (Hint: If the document mentions "marketplace" or "exchange", use INDIVIDUAL_ACA.
   If it mentions an employer with 500+ employees, likely SELF_FUNDED_ERISA.
   If it mentions a specific state DOI, likely FULLY_INSURED.)
- state: 2-letter US state code
- in_network_deductible_individual: Annual in-network individual deductible ($)
- in_network_oop_max_individual: Annual in-network individual OOP maximum ($)
- in_network_coinsurance: Patient coinsurance rate as decimal (e.g., 0.20 for 80/20)
- out_of_network_deductible_individual: OON deductible (null if no OON coverage)
- out_of_network_oop_max_individual: OON OOP max (null if no OON coverage)
- out_of_network_coinsurance: OON coinsurance rate (null if no OON coverage)
- copay_schedule: Object with primary_care, specialist, urgent_care, emergency_room, 
  generic_rx, preferred_brand_rx, specialty_rx (all in $)
- is_hsa_eligible: Boolean
- requires_pcp_referral: Boolean (true for HMO and POS)
- prior_auth_required_categories: List of service categories requiring prior auth
- excluded_services: List of explicitly excluded services

Important: For list fields, return [] when no items are explicitly stated.
If the plan state is not obvious, return the two-letter code when present in the document,
or "XX" as a last-resort placeholder.

Respond ONLY with a valid JSON object matching the schema above. No explanations."""


STATE_CODE_PATTERN = re.compile(r"(?im)^(?:state|jurisdiction)\s*[:\-]?\s*([A-Z]{2})\b")


def _infer_state_code(raw_text: str) -> str:
    """Best-effort state inference from the raw policy text."""
    if not raw_text:
        return "XX"

    match = STATE_CODE_PATTERN.search(raw_text)
    if match:
        return match.group(1).upper()

    fallback_match = re.search(r"\b(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)\b", raw_text)
    if fallback_match:
        return fallback_match.group(1).upper()

    return "XX"


def _normalize_policy_data(policy_data: dict, raw_text: str) -> tuple[dict, list[str]]:
    """Fill in safe defaults for fields Gemini may omit or return as null."""
    normalized = dict(policy_data)
    warnings: list[str] = []

    if not normalized.get("state"):
        inferred_state = _infer_state_code(raw_text)
        normalized["state"] = inferred_state
        warnings.append(f"State was missing from the extraction; inferred '{inferred_state}'.")

    if normalized.get("plan_name") is None:
        normalized["plan_name"] = "Unknown Plan"
        warnings.append("Plan name was missing from the extraction; using a placeholder.")

    if normalized.get("carrier_name") is None:
        normalized["carrier_name"] = "Unknown Carrier"
        warnings.append("Carrier name was missing from the extraction; using a placeholder.")

    if normalized.get("copay_schedule") is None:
        normalized["copay_schedule"] = {}

    for field_name in ("prior_auth_required_categories", "excluded_services"):
        if normalized.get(field_name) is None:
            normalized[field_name] = []

    return normalized, warnings



# ── Section Heading Detection ─────────────────────────────────────
# Maps detected heading text → canonical section tag stored in Supabase.
# Checked in order — first match wins.
_SECTION_KEYWORD_MAP: list[tuple[tuple[str, ...], str]] = [
    (("exclusion", "not covered", "limitation", "non-covered", "noncovered"), "EXCLUSIONS"),
    (("appeal", "grievance", "dispute", "complaint", "internal review", "external review", "your rights"), "APPEALS"),
    (("definition", "key term", "meaning", "glossary"), "DEFINITIONS"),
    (("covered service", "covered benefit", "what we cover", "benefit"), "BENEFITS"),
    (("prior auth", "preauthorization", "pre-authorization", "precertification"), "PRIOR_AUTH"),
    (("emergency", "urgent care", "emtala"), "EMERGENCY"),
    (("deductible", "out-of-pocket", "oop max", "coinsurance", "copay", "cost sharing"), "COST_SHARING"),
    (("network", "in-network", "out-of-network", "provider directory"), "NETWORK"),
]


def _classify_heading(text: str) -> str | None:
    """
    Map a heading line to a canonical section tag, or return None if unrecognised.

    Detection is case-insensitive. Returns the canonical tag (e.g. 'EXCLUSIONS')
    or None for headings that don't match any known insurance section vocabulary.
    """
    lower = text.lower().strip()
    for keywords, tag in _SECTION_KEYWORD_MAP:
        if any(kw in lower for kw in keywords):
            return tag
    # Unknown heading — store its text so it can be searched later
    # Truncate to 80 chars to avoid bloating the column
    return f"OTHER:{text.strip()[:80]}"


def _detect_heading_in_line(line: str) -> str | None:
    """
    Detect whether a line is a section heading.

    Three detection strategies (in priority order):
    1. Markdown heading (## or ###) — reliable output from pymupdf4llm
    2. ALL CAPS short line (< 70 chars) — common in insurance PDFs
    3. Title Case short line with known keywords — fallback

    Returns the heading text (stripped) or None if not a heading.
    """
    stripped = line.strip()
    if not stripped:
        return None

    # Strategy 1: Markdown heading prefix (## Heading or ### Heading)
    md_match = __import__("re").match(r"^#{1,4}\s+(.+)$", stripped)
    if md_match:
        return md_match.group(1).strip()

    # Strategy 2: ALL CAPS line, short enough to be a heading
    if len(stripped) <= 70 and stripped == stripped.upper() and any(c.isalpha() for c in stripped):
        return stripped

    return None


def _build_page_chunks(pages: list[dict]) -> list[dict]:
    """
    Split page texts into overlapping chunks using LangChain's RecursiveCharacterTextSplitter.

    NEW (Option A): Each chunk is tagged with the `section_heading` of the most
    recent detected heading above it in the document. This enables the Policy
    Analyzer to do structural anchor retrieval (e.g., always fetch EXCLUSIONS
    section chunks) without relying on semantic similarity.

    Returns:
        List of dicts with keys: page_number, chunk_index, chunk_text, section_heading
        section_heading is None for chunks that precede any detected heading.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    all_chunks = []
    current_section: str | None = None  # Tracks the active section heading

    for page in pages:
        page_text = page["text"]
        page_num = page["page_number"]

        # Scan page lines to find headings BEFORE chunking.
        # The heading detected here will be applied to all chunks on this page
        # (unless a later heading overrides it within the page).
        lines = page_text.split("\n")
        page_dominant_heading = current_section  # Inherit from previous page

        for line in lines:
            heading_text = _detect_heading_in_line(line)
            if heading_text:
                canonical = _classify_heading(heading_text)
                if canonical:
                    page_dominant_heading = canonical
                    current_section = canonical  # Propagate to subsequent pages
                    logger.debug(
                        f"Agent 1 (chunker): Page {page_num} — heading '{heading_text}' "
                        f"→ section '{canonical}'"
                    )
                break  # First heading on the page sets the section for all its chunks

        raw_chunks = splitter.split_text(page_text)
        for i, chunk_text in enumerate(raw_chunks):
            if chunk_text.strip():
                # For each chunk, re-scan for a heading within the chunk itself
                # to handle cases where a page has multiple sections.
                chunk_section = page_dominant_heading
                for chunk_line in chunk_text.split("\n"):
                    h = _detect_heading_in_line(chunk_line)
                    if h:
                        new_section = _classify_heading(h)
                        if new_section:
                            chunk_section = new_section
                            current_section = new_section
                        break

                all_chunks.append({
                    "page_number": page_num,
                    "chunk_index": i,
                    "chunk_text":  chunk_text.strip(),
                    "section_heading": chunk_section,
                })

    # Log section distribution for observability
    from collections import Counter
    section_counts = Counter(
        c["section_heading"].split(":")[0] if c["section_heading"] else "UNTAGGED"
        for c in all_chunks
    )
    logger.info(f"Agent 1 (chunker): Section distribution: {dict(section_counts)}")

    return all_chunks




async def policy_ingestion_node(state: AgentState) -> dict:
    """
    Two-phase policy ingestion:
      1. Chunk, embed, and store the full document in Supabase.
      2. Extract structured PolicyProfile from a first-pages summary.
    """
    logger.info("Agent 1 (Policy Ingestion): Starting two-phase pipeline")

    raw_text = state.get("raw_policy_text", "")
    if not raw_text:
        return {
            "errors": state.get("errors", []) + ["No policy text provided for ingestion"],
            "current_phase": "ingestion",
        }

    # Determine session_id (required for scoping the vector store)
    session_id = state.get("session_id")
    if not session_id:
        # Fall back to a hash of the raw text as a stable identifier
        import hashlib
        session_id = hashlib.sha256(raw_text[:500].encode()).hexdigest()[:16]
        logger.warning(f"Agent 1: No session_id in state, derived '{session_id}' from text hash")

    # ── Phase 1: Parse pages from raw text ───────────────────────────
    # The raw_policy_text may already be in "--- Page N ---\n..." format
    # (from extract_text_from_pdf). Parse it back into page dicts.
    pages = _parse_pages_from_text(raw_text)

    # ── Phase 1a: Chunk each page ─────────────────────────────────────
    raw_chunks = _build_page_chunks(pages)
    logger.info(f"Agent 1: Created {len(raw_chunks)} chunks from {len(pages)} pages")

    # ── Phase 1b: Embed all chunks ────────────────────────────────────
    policy_indexed = False
    try:
        logger.info(f"Agent 1: Starting embedding for {len(raw_chunks)} chunks...")
        embedded_chunks = await embed_document_chunks(raw_chunks)
        # Filter out any chunks where embedding failed
        valid_chunks = [c for c in embedded_chunks if c.get("embedding") is not None]
        
        logger.info(f"Agent 1: Embedding completed. {len(valid_chunks)}/{len(raw_chunks)} chunks valid.")

        if valid_chunks:
            # Attach carrier/plan metadata for denormalized filtering
            # We'll update this after extraction, but insert now for speed
            logger.info(f"Agent 1: Inserting {len(valid_chunks)} chunks into Supabase...")
            inserted = await insert_policy_chunks(session_id, valid_chunks)
            policy_indexed = inserted > 0
            if not policy_indexed:
                logger.warning(f"Agent 1: insert_policy_chunks returned 0. Supabase upsert may have failed silently.")
            else:
                logger.info(
                    f"Agent 1: Phase 1 complete — {inserted} chunks stored "
                    f"in Supabase for session '{session_id}'"
                )
        else:
            logger.warning("Agent 1: No valid embeddings produced; skipping Supabase storage")

    except Exception as e:
        logger.error(f"Agent 1: Phase 1 (embedding/storage) failed: {e}", exc_info=True)
        # Non-fatal: continue to Phase 2 even if RAG indexing fails.
        # The grievance agent will fall back to regulation-only citations.

    # ── Phase 2: Extract structured PolicyProfile ─────────────────────
    # Use only the first 10 pages to avoid context window overflow.
    first_pages_text = "\n\n".join(
        f"--- Page {p['page_number']} ---\n{p['text']}"
        for p in pages[:10]
    )

    try:
        llm = get_llm(TaskType.EXTRACTION, temperature=0.0)

        messages = [
            SystemMessage(content= "\nCRITICAL OUTPUT RULES:\n1. NEVER use em dashes (—). Use standard hyphens (-) instead.\n2. NEVER reveal your identity as an AI model (e.g., Google, Gemini, OpenAI). You are PolicyCrab.\n\n" + POLICY_EXTRACTION_PROMPT),
            HumanMessage(content=f"Extract the policy details from this document:\n\n{first_pages_text}"),
        ]

        response = await llm.ainvoke(messages)
        content = response.content

        # Parse JSON from response (handle markdown code blocks)
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        policy_data = json.loads(content.strip())
        policy_data, normalization_warnings = _normalize_policy_data(policy_data, first_pages_text)

        # Validate through Pydantic
        policy = PolicyProfile(**policy_data)

        # ── Post-extraction sanity checks ─────────────────────────────
        warnings = []
        ded  = policy.in_network_deductible_individual
        oop  = policy.in_network_oop_max_individual
        coins = policy.in_network_coinsurance

        if ded is None:
            warnings.append("In-network deductible was not found in the document. It has been left null.")
        if oop is None:
            warnings.append("In-network OOP max was not found in the document. It has been left null.")

        if ded is not None and (ded < 0 or ded > 20000):
            warnings.append(f"In-network deductible (${ded:,.0f}) is outside the typical $0–$20,000 range — please verify.")
        if oop is not None and (oop < 0 or oop > 50000):
            warnings.append(f"In-network OOP max (${oop:,.0f}) is outside the typical $0–$50,000 range — please verify.")
        if ded is not None and oop is not None and oop < ded:
            warnings.append(f"OOP max (${oop:,.0f}) is less than deductible (${ded:,.0f}) — this is unusual. Please verify.")
        if coins is not None and (coins < 0 or coins > 1):
            warnings.append(f"Coinsurance ({coins}) should be between 0.0 and 1.0 — please verify.")

        copay = policy.copay_schedule
        if copay:
            for field_name, val in [
                ("primary_care", copay.primary_care),
                ("specialist", copay.specialist),
                ("emergency_room", copay.emergency_room),
            ]:
                if val is not None and val > 1000:
                    warnings.append(f"Copay for {field_name} (${val:,.0f}) seems high — please verify.")

        confidence = "HIGH" if len(warnings) == 0 else ("MEDIUM" if len(warnings) <= 2 else "LOW")
        if warnings:
            logger.warning(f"Agent 1: Extraction warnings ({confidence}): {warnings}")

        if normalization_warnings:
            warnings.extend(normalization_warnings)
            confidence = "MEDIUM" if confidence == "HIGH" else confidence
            logger.warning(f"Agent 1: Normalization warnings: {normalization_warnings}")

        logger.info(
            f"Agent 1: Phase 2 complete — Policy: {policy.plan_name} ({policy.carrier_name}), "
            f"Pages indexed: {len(pages)}, Chunks: {len(raw_chunks)}, "
            f"Policy indexed in Supabase: {policy_indexed}"
        )

        # ── Phase 3: Persist PolicyProfile for returning users ────────────
        # After successful extraction, save the profile to policy_sessions so
        # future claim evaluations can skip this LLM call entirely.
        user_id = state.get("user_id")
        if user_id and policy_indexed:
            try:
                await save_policy_session(session_id, user_id, policy.model_dump())
                logger.info(f"Agent 1: PolicyProfile persisted for session '{session_id}'")
            except Exception as e:
                logger.warning(f"Agent 1: Failed to persist PolicyProfile (non-fatal): {e}")

        return {
            "policy_profile":        policy.model_dump(),
            "session_id":            session_id,
            "policy_indexed":        policy_indexed,
            "policy_page_count":     len(pages),
            "extraction_warnings":   warnings,
            "extraction_confidence": confidence,
            "current_phase":         "ingestion",
            "errors":                state.get("errors", []),
        }

    except json.JSONDecodeError as e:
        error_msg = f"Agent 1: Failed to parse LLM response as JSON: {e}"
        logger.error(error_msg)
        return {
            "errors":         state.get("errors", []) + [error_msg],
            "session_id":     session_id,
            "policy_indexed": policy_indexed,
            "current_phase":  "ingestion",
        }
    except Exception as e:
        error_msg = f"Agent 1: Policy extraction failed: {e}"
        logger.error(error_msg)
        return {
            "errors":         state.get("errors", []) + [error_msg],
            "session_id":     session_id,
            "policy_indexed": policy_indexed,
            "current_phase":  "ingestion",
        }


def _parse_pages_from_text(raw_text: str) -> list[dict]:
    """
    Parse "--- Page N ---\\n..." formatted text back into page dicts.
    Falls back to treating the entire text as page 1 if no markers found.
    """
    import re
    page_pattern = re.compile(r"--- Page (\d+) ---\n(.*?)(?=--- Page \d+ ---|$)", re.DOTALL)
    matches = page_pattern.findall(raw_text)

    if matches:
        return [{"page_number": int(num), "text": text.strip()} for num, text in matches if text.strip()]

    # Fallback: treat entire document as single page
    logger.warning("Agent 1: No page markers found in raw text; treating as single page")
    return [{"page_number": 1, "text": raw_text.strip()}]


