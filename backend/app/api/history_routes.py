from fastapi import APIRouter, Depends, HTTPException

from app.api.auth import get_current_user
from app.services.user_data import (
    list_user_claims,
    list_user_policies,
    delete_user_policy,
    list_user_documents,
    delete_user_document,
    list_user_audits,
    delete_user_audit,
)

router = APIRouter(prefix="/api/history", tags=["History"])


@router.get("/policies")
async def get_user_policies(user: dict = Depends(get_current_user)):
    """Get all policies uploaded by the current user."""
    return [
        {
            "id": policy["id"],
            "session_id": policy.get("session_id"),
            "policy_profile": policy.get("policy_profile_json"),
            "created_at": policy.get("created_at"),
        }
        for policy in list_user_policies(user["id"])
    ]


@router.get("/claims")
async def get_user_claims(user: dict = Depends(get_current_user)):
    """Get all claim evaluations run by the current user."""
    return [
        {
            "id": claim["id"],
            "claim_description": claim.get("claim_description"),
            "cost_breakdown": claim.get("cost_breakdown_json"),
            "appeal_output": claim.get("appeal_output_json"),
            "route_decision": claim.get("route_decision"),
            "created_at": claim.get("created_at"),
        }
        for claim in list_user_claims(user["id"])
    ]


@router.delete("/policies/{policy_id}")
async def remove_user_policy(policy_id: str, user: dict = Depends(get_current_user)):
    """Delete a saved policy by ID (scoped to current user)."""
    deleted = delete_user_policy(user["id"], policy_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Policy not found or not owned by you.")
    return {"success": True, "deleted_id": policy_id}


@router.get("/documents")
async def get_user_documents(user: dict = Depends(get_current_user)):
    """Get all saved documents for the current user."""
    return list_user_documents(user["id"])


@router.delete("/documents/{document_id}")
async def remove_user_document(document_id: str, user: dict = Depends(get_current_user)):
    """Delete a saved document by ID (scoped to current user)."""
    deleted = delete_user_document(user["id"], document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found or not owned by you.")
    return {"success": True, "deleted_id": document_id}


@router.get("/audits")
async def get_user_audits(user: dict = Depends(get_current_user)):
    """Get all saved bill audits for the current user."""
    return list_user_audits(user["id"])


@router.delete("/audits/{audit_id}")
async def remove_user_audit(audit_id: str, user: dict = Depends(get_current_user)):
    """Delete a saved bill audit by ID (scoped to current user)."""
    deleted = delete_user_audit(user["id"], audit_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Audit report not found or not owned by you.")
    return {"success": True, "deleted_id": audit_id}

