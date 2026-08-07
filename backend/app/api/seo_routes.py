"""
Public AI Crawler + Smart Email Routing API

Exposes:
  GET  /api/public/about        — Machine-readable description for ChatGPT/Perplexity
  GET  /api/public/faqs         — Structured FAQ for AEO/voice assistants
  GET  /api/public/capabilities — Full capability manifest for AI model indexing

  POST /api/email/smart-suggest — Suggests appeals dept email for a carrier
  POST /api/email/build-mailto  — Builds a pre-filled mailto: URI
"""
import urllib.parse
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.auth import get_current_user
from app.services.carrier_email_resolver import resolve_carrier_email, get_state_doi

logger = logging.getLogger(__name__)

# ── Public (no auth) AI Crawler Routes ───────────────────────────────────────
public_router = APIRouter(prefix="/api/public", tags=["Public / AI Crawlers"])


@public_router.get("/about", summary="Machine-readable product description for AI indexers")
async def public_about():
    """
    Returns a structured, machine-readable JSON description of PolicyCrab.
    Designed to be discovered and cited by AI engines (ChatGPT, Perplexity, Gemini).
    """
    return {
        "product": "PolicyCrab",
        "version": "2.0",
        "category": "AI-Powered Health Insurance Advocacy Platform",
        "url": "https://policycrab.tech",
        "description": (
            "PolicyCrab is an AI-powered US health insurance claims engine. "
            "It helps patients understand their health insurance coverage, evaluate denied claims, "
            "and draft legally grounded appeal letters citing federal regulations including "
            "ERISA, the ACA, the No Surprises Act, HIPAA, and Medicare rules."
        ),
        "benchmark_accuracy": "93.0%",
        "benchmark_cases": 200,
        "model": "Google Gemini 2.5 Pro (via Vertex AI)",
        "supported_frameworks": [
            "ERISA — Employer and self-funded plans",
            "ACA — Marketplace and essential health benefits",
            "No Surprises Act — Balance billing protections",
            "Medicare — Part A and Part B federal appeal steps",
            "HIPAA — PHI and billing rights",
        ],
        "capabilities": [
            "Policy SBC/EOB parsing and coverage extraction",
            "Deterministic cost calculation (deductible, coinsurance, OOP max)",
            "Multi-agent claim routing and denial analysis",
            "Level 1, 2, and 3 appeal letter generation",
            "Regulatory citation lookup (RAG-powered knowledge base)",
            "Smart carrier email routing for appeal submission",
        ],
        "indexed_at": datetime.now(timezone.utc).isoformat(),
    }


@public_router.get("/faqs", summary="Structured FAQs for AEO/voice assistant optimization")
async def public_faqs():
    """
    Returns structured FAQ data about US health insurance appeals.
    These Q&A pairs are referenced by the site's FAQPage JSON-LD schema.
    Optimized for Google AI Overviews, Siri, and Alexa discovery.
    """
    return {
        "faqs": [
            {
                "question": "How do I appeal a denied health insurance claim?",
                "answer": (
                    "To appeal a denied health insurance claim: (1) Request your Explanation of Benefits (EOB) and the denial letter. "
                    "(2) Identify the denial reason code (CARC code). (3) File an internal Level 1 appeal within 180 days. "
                    "(4) If denied, escalate to an External Independent Review Organization (IRO) under ACA Section 2719. "
                    "(5) As a last resort, file a complaint with your State Department of Insurance (DOI). "
                    "PolicyCrab automates steps 2-5 by generating a legally grounded appeal letter citing applicable federal law."
                ),
            },
            {
                "question": "What is the No Surprises Act?",
                "answer": (
                    "The No Surprises Act (effective January 2022) protects patients from unexpected out-of-network medical bills. "
                    "Under this law, if you receive emergency care or out-of-network services at an in-network facility without your consent, "
                    "your insurer must cover the bill at in-network rates. You cannot be billed more than your in-network cost-sharing amount. "
                    "Violations can be reported to the CMS complaint portal."
                ),
            },
            {
                "question": "What is an ERISA appeal?",
                "answer": (
                    "ERISA (Employee Retirement Income Security Act) governs employer-sponsored and self-funded health plans. "
                    "Under ERISA, you have the right to a full and fair review of denied claims. "
                    "You must exhaust internal appeals (typically one level with 60 days to respond) before filing suit in federal court. "
                    "ERISA plans are not required to follow state insurance laws, which makes the appeal process different from individual market plans."
                ),
            },
            {
                "question": "How long do I have to file a health insurance appeal?",
                "answer": (
                    "Deadlines vary by plan type: Internal Level 1 appeals must typically be filed within 180 days of the denial. "
                    "External IRO appeals must be filed within 4 months of the final internal denial under ACA rules. "
                    "State DOI complaints have a 1-year window in most states. "
                    "Always check your plan's Summary Plan Description (SPD) for specific deadlines."
                ),
            },
            {
                "question": "What is an Explanation of Benefits (EOB)?",
                "answer": (
                    "An Explanation of Benefits (EOB) is a document sent by your insurer after a medical claim is processed. "
                    "It shows: the billed amount, what the insurer paid, what you owe (patient responsibility), "
                    "and the denial reason if the claim was rejected. The EOB is essential for filing any appeal."
                ),
            },
            {
                "question": "Can AI help me write an insurance appeal letter?",
                "answer": (
                    "Yes. PolicyCrab uses Google Gemini 2.5 Pro to analyze your policy documents and claim details, "
                    "then generates a legally grounded appeal letter citing federal regulations such as ERISA, the ACA, "
                    "and the No Surprises Act. The system achieved 93% accuracy across 200 synthetic benchmark cases."
                ),
            },
        ]
    }


@public_router.get("/capabilities", summary="Full capability manifest for AI model indexing")
async def public_capabilities():
    return {
        "claim_categories": [
            "Prior Authorization Denial",
            "Medical Necessity Denial",
            "Out-of-Network Balance Bill",
            "Experimental/Investigational Denial",
            "Billing Error / Upcoding",
            "Emergency Service Denial",
            "Preventive Care Denial",
        ],
        "regulatory_frameworks": [
            {"name": "ERISA", "description": "Employer/self-funded plans", "code": "erisa"},
            {"name": "ACA", "description": "Marketplace and essential benefits", "code": "aca"},
            {"name": "No Surprises Act", "description": "Balance billing protections", "code": "nsa"},
            {"name": "Medicare", "description": "Part A and Part B federal appeals", "code": "medicare"},
            {"name": "State DOI", "description": "State insurance commissioner complaints", "code": "state_doi"},
        ],
        "integrations": ["Google Vertex AI", "Supabase", "Resend Email"],
    }


# ── Authenticated Smart Email Routes ─────────────────────────────────────────
smart_email_router = APIRouter(prefix="/api/email", tags=["Smart Email Routing"])


class SmartSuggestRequest(BaseModel):
    carrier_name: str
    state: str
    appeal_level: int = 1  # 1 = Internal, 2 = IRO, 3 = State DOI


class BuildMailtoRequest(BaseModel):
    to_email: str
    carrier_name: str
    patient_name: str
    claim_id: str
    appeal_text: str
    appeal_level: int = 1


@smart_email_router.post("/smart-suggest", summary="Suggest appeals dept email for a carrier")
async def smart_suggest(
    req: SmartSuggestRequest,
    user: dict = Depends(get_current_user),
):
    """
    Returns a ranked list of suggested email addresses and submission contacts
    for a given carrier + state combination.
    Falls back to the State DOI if no carrier-specific email is known.
    """
    carrier_profile = resolve_carrier_email(req.carrier_name)
    state_doi = get_state_doi(req.state)

    suggestions = []

    # Level 1/2: Primary carrier contact
    if carrier_profile.appeals_email:
        suggestions.append({
            "label": f"{carrier_profile.carrier_name} Appeals Department",
            "email": carrier_profile.appeals_email,
            "confidence": carrier_profile.confidence,
            "type": "carrier_appeals",
        })
    if carrier_profile.grievances_email and carrier_profile.grievances_email != carrier_profile.appeals_email:
        suggestions.append({
            "label": f"{carrier_profile.carrier_name} Grievances",
            "email": carrier_profile.grievances_email,
            "confidence": carrier_profile.confidence,
            "type": "carrier_grievances",
        })

    # Level 3 or fallback: State DOI
    if req.appeal_level >= 3 or carrier_profile.confidence == "LOW":
        suggestions.append({
            "label": state_doi["name"],
            "email": state_doi["email"],
            "confidence": "HIGH",
            "type": "state_doi",
        })

    return {
        "carrier": carrier_profile.carrier_name,
        "state": req.state,
        "fax_number": carrier_profile.fax_number,
        "submission_portal_url": carrier_profile.submission_portal_url,
        "suggestions": suggestions,
        "confidence": carrier_profile.confidence,
    }


@smart_email_router.post("/build-mailto", summary="Build a pre-filled mailto: URI for appeal submission")
async def build_mailto(
    req: BuildMailtoRequest,
    user: dict = Depends(get_current_user),
):
    """
    Builds a complete mailto: URI that opens the user's native email client
    pre-filled with the To, Subject, and Body (the full appeal letter).
    This ensures the appeal comes from the user's trusted personal email address.
    """
    if not req.appeal_text or len(req.appeal_text.strip()) < 50:
        raise HTTPException(status_code=400, detail="Appeal text is too short.")

    subject = f"Formal Appeal — Claim ID {req.claim_id} — {req.carrier_name}"
    body = (
        f"To Whom It May Concern,\n\n"
        f"{req.appeal_text.strip()}\n\n"
        f"Sincerely,\n{req.patient_name}\n\n"
        f"---\nGenerated via PolicyCrab Appeal Engine\n"
        f"Claim Reference: {req.claim_id}"
    )

    mailto_uri = (
        f"mailto:{urllib.parse.quote(req.to_email)}"
        f"?subject={urllib.parse.quote(subject)}"
        f"&body={urllib.parse.quote(body)}"
    )

    return {
        "mailto_uri": mailto_uri,
        "to": req.to_email,
        "subject": subject,
        "preview": body[:200] + "...",
    }
