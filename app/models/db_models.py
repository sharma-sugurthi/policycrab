from sqlalchemy import Column, String, DateTime, JSON, Text, ForeignKey
from sqlalchemy.sql import func
from app.database import Base
import uuid

class UserPolicy(Base):
    __tablename__ = "user_policies"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, index=True, nullable=False) # Auth user ID
    policy_profile_json = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class UserClaim(Base):
    __tablename__ = "user_claims"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, index=True, nullable=False)
    policy_id = Column(String, ForeignKey("user_policies.id"), nullable=True)
    claim_description = Column(Text, nullable=False)
    cost_breakdown_json = Column(JSON, nullable=True)
    appeal_output_json = Column(JSON, nullable=True)
    route_decision = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
