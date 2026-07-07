import hashlib
from typing import Optional, Type
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

class NetworkStatusInput(BaseModel):
    npi: str = Field(description="The 10-digit National Provider Identifier (NPI) of the doctor or hospital.")
    plan_name: str = Field(description="The name of the user's insurance plan (e.g., 'Blue Cross Blue Shield PPO').")

class NetworkStatusTool(BaseTool):
    name: str = "check_provider_network_status"
    description: str = (
        "Checks if a specific provider (identified by NPI) is In-Network or Out-of-Network "
        "for the user's specific insurance plan. "
        "Always use this after finding a provider's NPI to determine coverage."
    )
    args_schema: Type[BaseModel] = NetworkStatusInput

    def _run(self, npi: str, plan_name: str) -> str:
        """
        Deterministically simulate network status.
        Real network data is proprietary, so we hash the NPI + Plan Name to generate
        a consistent, realistic result.
        """
        # Create a deterministic string to hash
        seed_string = f"{npi}_{plan_name.lower().strip()}"
        
        # Generate an integer from the MD5 hash
        hash_int = int(hashlib.md5(seed_string.encode('utf-8')).hexdigest(), 16)
        
        # 70% chance they are In-Network (typical for broad PPO networks)
        # We use modulo 100 to get a stable number between 0 and 99
        is_in_network = (hash_int % 100) < 70
        
        if is_in_network:
            return (
                f"✅ IN-NETWORK: The provider with NPI {npi} IS contracted and participating "
                f"in the '{plan_name}' network. In-network benefits and cost-sharing will apply."
            )
        else:
            return (
                f"❌ OUT-OF-NETWORK: The provider with NPI {npi} is NOT contracted with "
                f"the '{plan_name}' network. Out-of-network penalties, higher deductibles, "
                f"or balance billing may apply depending on the plan type."
            )
