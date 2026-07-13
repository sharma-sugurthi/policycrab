import httpx
import logging
from typing import Optional, Type
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class ProviderSearchInput(BaseModel):
    first_name: Optional[str] = Field(None, description="First name of the doctor.")
    last_name: Optional[str] = Field(None, description="Last name of the doctor.")
    city: Optional[str] = Field(None, description="City where the provider is located (e.g., 'Chicago').")
    state: Optional[str] = Field(None, description="2-letter State abbreviation (e.g., 'IL').")
    taxonomy_description: Optional[str] = Field(None, description="Optional. Medical specialty (e.g., 'Cardiology', 'Pediatrics'). It will substring match.")
    is_facility: bool = Field(False, description="Set to True if searching for a hospital/clinic instead of an individual doctor.")
    limit: int = Field(5, description="Number of results to return. Max 10.")

class ProviderSearchTool(BaseTool):
    name: str = "search_us_healthcare_providers"
    description: str = (
        "Searches the official US Government NPI Registry (NPPES) for real doctors and hospitals. "
        "Use this tool to find providers by name, city, state, or medical specialty. "
        "Returns their NPI (National Provider Identifier), name, addresses, and specialties."
    )
    args_schema: Type[BaseModel] = ProviderSearchInput

    def _run(
        self,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        city: Optional[str] = None,
        state: Optional[str] = None,
        taxonomy_description: Optional[str] = None,
        is_facility: bool = False,
        limit: int = 5
    ) -> str:
        """Execute the search against the NPPES API."""
        if not any([first_name, last_name, city, state, taxonomy_description]):
            return "Error: You must provide at least one search parameter (name, city, state, or specialty)."

        base_url = "https://npiregistry.cms.hhs.gov/api/"
        params = {
            "version": "2.1", 
            "limit": 100, # Fetch up to 100 so we have enough to filter locally
            "enumeration_type": "NPI-2" if is_facility else "NPI-1"
        } 
        
        if first_name: params["first_name"] = first_name
        if last_name: params["last_name"] = last_name
        if city: params["city"] = city
        if state: params["state"] = state.upper()

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(base_url, params=params)
                response.raise_for_status()
                data = response.json()

            if "results" not in data or not data["results"]:
                return "No providers found matching those criteria in the US NPI Registry."

            results = []
            for item in data["results"]:
                # Get primary specialty
                taxonomies = item.get("taxonomies", [])
                primary_specialty = "Unknown Specialty"
                matches_taxonomy = False
                for tax in taxonomies:
                    desc = tax.get("desc") or ""
                    if taxonomy_description and taxonomy_description.lower() in desc.lower():
                        matches_taxonomy = True
                    if tax.get("primary"):
                        primary_specialty = desc or "Unknown Specialty"
                
                # If a taxonomy filter is applied and it didn't match, skip this provider
                if taxonomy_description and not matches_taxonomy:
                    continue

                if len(results) >= limit:
                    break
                npi = item.get("number")
                basic = item.get("basic", {})
                
                # Determine provider name
                if basic.get("organization_name"):
                    name = basic.get("organization_name")
                else:
                    name = f"{basic.get('first_name', '')} {basic.get('last_name', '')}".strip()
                
                # Get primary address
                addresses = item.get("addresses", [])
                primary_address = "Unknown Address"
                for addr in addresses:
                    if addr.get("address_purpose") == "LOCATION":
                        primary_address = f"{addr.get('address_1', '')}, {addr.get('city', '')}, {addr.get('state', '')} {addr.get('postal_code', '')}"
                        break
                
                results.append(
                    f"- Provider: {name}\n"
                    f"  NPI: {npi}\n"
                    f"  Specialty: {primary_specialty}\n"
                    f"  Address: {primary_address}\n"
                )

            if not results:
                return f"Found providers in {city}, but none matched the specialty '{taxonomy_description}'."

            return "Here are the real providers found in the US Government Registry:\n\n" + "\n".join(results)
        except Exception as e:
            logger.error(f"NPPES API Error: {e}")
            return f"Failed to search provider registry: {str(e)}"
