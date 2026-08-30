"""The contract handed from the Interviewer agent to the Builder agent.

This is the 'decided contract': the Interviewer gathers requirements in free
conversation and, once the user confirms, emits exactly this structure. The
Builder takes it from here and never talks to the user."""
from __future__ import annotations
from typing import List, Literal
from pydantic import BaseModel, Field


class Scale(BaseModel):
    accounts: int = Field(1000, description="How many card accounts to generate")
    cycles: int = Field(24, description="How many monthly billing cycles per account")


class Contract(BaseModel):
    """Finalized requirements for a synthetic credit-card dataset."""
    purpose: str = Field(..., description="Plain-language reason the user needs this data")
    use_case: Literal["model_training", "pipeline_testing", "demo", "validation", "other"] = Field(
        "other", description="The primary use of the data")
    scale: Scale = Field(default_factory=Scale)
    revolver_mix: Literal["mostly_revolvers", "mostly_transactors", "mixed"] = Field(
        "mixed", description="Whether accounts tend to carry a balance month to month")
    behaviors: List[Literal["grace_period", "fees", "cash_advances", "minimum_payment"]] = Field(
        default_factory=list, description="Billing behaviours the user wants modelled")
    notes: str = Field("", description="Anything else worth recording from the conversation")
