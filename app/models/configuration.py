"""Pydantic models for scenario configuration files."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProtocolConfig(StrictModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    scenario_id: str = Field(min_length=1)
    instructions: list[str] = Field(min_length=1)
    version: str = Field(min_length=1)
    approval_status: Literal["approved", "unapproved"]
    approving_authority: str | None
    review_date: date | None

    @model_validator(mode="after")
    def require_approval_metadata(self):
        if self.approval_status == "approved" and (not self.approving_authority or not self.review_date):
            raise ValueError("Approved protocols require an authority and review date")
        if self.approval_status == "unapproved" and self.approving_authority:
            raise ValueError("Unapproved protocols cannot name an approving authority")
        return self


class NodeConfig(StrictModel):
    id: str = Field(min_length=1)
    type: Literal["decision", "terminal"]
    question: str | None = None
    yes: str | None = None
    no: str | None = None
    protocol_id: str | None = None

    @model_validator(mode="after")
    def validate_shape(self):
        if self.type == "decision":
            if not self.question or not self.yes or not self.no or self.protocol_id:
                raise ValueError("Decision nodes require question, yes, and no references only")
        elif self.question or self.yes or self.no or not self.protocol_id:
            raise ValueError("Terminal nodes require a protocol_id and no branches")
        return self


class ScenarioConfig(StrictModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    root_id: str = Field(min_length=1)
    nodes: list[NodeConfig] = Field(min_length=1)
    protocols: list[ProtocolConfig] = Field(min_length=1)
