"""
Provider API Routes - search US clinicians/facilities and estimate network status.

Provider identity comes from the official CMS NPPES NPI Registry. Plan network
status is not publicly available at national scale, so the current checker is a
stable estimate that must be verified against the payer's provider directory.
"""

import logging
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.auth import get_current_user
from app.tools.network_status import NetworkStatusTool
from app.security.rate_limit import rate_limit

logger = logging.getLogger(__name__)
PROVIDER_SEARCH_RATE_LIMIT = rate_limit("providers:search", max_requests=30, window_seconds=60)
PROVIDER_NETWORK_RATE_LIMIT = rate_limit("providers:network", max_requests=30, window_seconds=60)

router = APIRouter(prefix="/api/providers", tags=["Providers"])


class ProviderSearchRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = Field(None, min_length=2, max_length=2)
    taxonomy_description: Optional[str] = None
    is_facility: bool = False
    limit: int = Field(5, ge=1, le=10)


class NetworkStatusRequest(BaseModel):
    npi: str = Field(..., min_length=10, max_length=10)
    plan_name: str = Field(..., min_length=2)


def _provider_name(item: dict) -> str:
    basic = item.get("basic", {})
    if basic.get("organization_name"):
        return basic["organization_name"]
    return " ".join(
        part for part in [basic.get("first_name"), basic.get("middle_name"), basic.get("last_name")]
        if part
    ).strip() or "Unknown Provider"


def _primary_address(item: dict) -> dict | None:
    for address in item.get("addresses", []):
        if address.get("address_purpose") == "LOCATION":
            return {
                "address_1": address.get("address_1", ""),
                "address_2": address.get("address_2", ""),
                "city": address.get("city", ""),
                "state": address.get("state", ""),
                "postal_code": address.get("postal_code", ""),
                "telephone_number": address.get("telephone_number", ""),
            }
    return None


def _primary_specialty(item: dict) -> str:
    taxonomies = item.get("taxonomies", [])
    for taxonomy in taxonomies:
        if taxonomy.get("primary"):
            return taxonomy.get("desc") or "Unknown Specialty"
    if taxonomies:
        return taxonomies[0].get("desc") or "Unknown Specialty"
    return "Unknown Specialty"


@router.post("/search")
async def search_providers(
    request: ProviderSearchRequest,
    user: dict = Depends(get_current_user),
    _: None = Depends(PROVIDER_SEARCH_RATE_LIMIT),
):
    if not any([
        request.first_name,
        request.last_name,
        request.city,
        request.state,
        request.taxonomy_description,
    ]):
        raise HTTPException(status_code=400, detail="Provide a name, city, state, or specialty.")

    params = {
        "version": "2.1",
        "limit": 100,
        "enumeration_type": "NPI-2" if request.is_facility else "NPI-1",
    }
    if request.first_name:
        params["first_name"] = request.first_name
    if request.last_name:
        params["last_name"] = request.last_name
    if request.city:
        params["city"] = request.city
    if request.state:
        params["state"] = request.state.upper()

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("https://npiregistry.cms.hhs.gov/api/", params=params)
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        logger.error("NPPES provider search failed: %s", exc)
        raise HTTPException(status_code=502, detail="Provider registry search failed.") from exc

    results = []
    taxonomy_filter = (request.taxonomy_description or "").lower().strip()
    for item in data.get("results", []):
        specialties = [t.get("desc") or "" for t in item.get("taxonomies", [])]
        if taxonomy_filter and not any(taxonomy_filter in specialty.lower() for specialty in specialties):
            continue

        results.append({
            "npi": str(item.get("number", "")),
            "name": _provider_name(item),
            "entity_type": "facility" if request.is_facility else "individual",
            "primary_specialty": _primary_specialty(item),
            "address": _primary_address(item),
            "all_specialties": [s for s in specialties if s],
        })
        if len(results) >= request.limit:
            break

    return {
        "source": "CMS NPPES NPI Registry",
        "results": results,
        "disclaimer": (
            "NPI data identifies real US providers and facilities, but it does not prove plan network status. "
            "Verify network status with the insurer's provider directory before non-emergency care."
        ),
    }


@router.post("/network-status")
async def check_network_status(
    request: NetworkStatusRequest,
    user: dict = Depends(get_current_user),
    _: None = Depends(PROVIDER_NETWORK_RATE_LIMIT),
):
    result = NetworkStatusTool().invoke({"npi": request.npi, "plan_name": request.plan_name})
    return {
        "npi": request.npi,
        "plan_name": request.plan_name,
        "result": result,
        "is_estimate": True,
        "regulatory_note": (
            "For emergency services and certain out-of-network services at in-network facilities, "
            "the No Surprises Act may limit patient cost-sharing to in-network amounts. "
            "For planned non-emergency care, verify in-network status in advance."
        ),
    }
