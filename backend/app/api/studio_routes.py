"""
Studio API Routes
Exposes the AI Co-Pilot revision engine and deterministic dossier compiler
to the frontend.
"""

from fastapi import APIRouter, Depends, HTTPException, Body
from app.api.auth import get_current_user

from app.models.studio import RevisionRequest, RevisionResponse, DossierPackage
from app.services.studio_engine import apply_revision, compile_dossier
from app.services.llm_router import LLMRateLimitError
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/studio", tags=["studio"])


@router.post("/revise", response_model=RevisionResponse)
async def revise_letter(
    request: RevisionRequest = Body(...),
    current_user: dict = Depends(get_current_user)
) -> RevisionResponse:
    """
    Apply a one-click AI revision (e.g., assertive, simplify) to the current draft.
    Rate limited by standard FastAPI limits if configured, but also handles
    LLM API rate limits gracefully via the FallbackChatModel logic.
    """
    try:
        response = await apply_revision(request)
        if not response.success:
            # We still return 200 with success=False so the frontend can
            # gracefully display the failure state and keep the draft intact.
            pass
        return response
    except LLMRateLimitError as e:
        logger.warning(f"Rate limited during revision for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=503,
            detail="AI traffic is currently very high. Please wait a few moments and try your revision again."
        )
    except Exception as e:
        logger.error(f"Unexpected error in /revise: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred while processing your revision.")


@router.post("/dossier", response_model=DossierPackage)
def build_dossier(
    payload: dict = Body(...),
    current_user: dict = Depends(get_current_user)
) -> DossierPackage:
    """
    Deterministically compile evidence into a structured dossier package for PDF generation.
    Does not use an LLM.
    """
    try:
        # Extract fields from the generic payload
        letter_text = payload.get("letter_text", "")
        if not letter_text:
            raise HTTPException(status_code=400, detail="Missing letter_text in payload")

        claim_case = payload.get("claim_case")
        policy_profile = payload.get("policy_profile")
        cost_breakdown = payload.get("cost_breakdown")
        appeal_output = payload.get("appeal_output")
        eob_highlights = payload.get("eob_highlights")

        # Map to proper models where appropriate if studio_engine doesn't just take dicts
        # Looking at studio_engine.py, it takes models for claim_case and policy_profile
        from app.models.claim_case import ClaimCase
        from app.models.policy import PolicyProfile
        
        claim_case_obj = ClaimCase(**claim_case) if claim_case else None
        policy_profile_obj = PolicyProfile(**policy_profile) if policy_profile else None

        dossier = compile_dossier(
            letter_text=letter_text,
            claim_case=claim_case_obj,
            policy_profile=policy_profile_obj,
            cost_breakdown=cost_breakdown,
            appeal_output=appeal_output,
            eob_highlights=eob_highlights
        )
        return dossier

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Failed to compile dossier: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred while compiling your dossier.")
