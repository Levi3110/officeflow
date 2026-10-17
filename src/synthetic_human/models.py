from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

Role = Literal["supervisor", "browser", "office"]


class Persona(BaseModel):
    seed: int = 17
    characters_per_second: float = Field(default=7, gt=0)
    typo_probability: float = Field(default=0.018, ge=0, le=0.1)
    pause_scale: float = Field(default=1, ge=0)


class Settings(BaseModel):
    backend: Literal["simulation", "macos"] = "simulation"
    browser_app: str = "Google Chrome"
    office_app: str = "LibreOffice"
    persona: Persona = Field(default_factory=Persona)
    action_timeout: float = Field(default=240, ge=1, le=300)
    lease_seconds: float = Field(default=300, ge=5, le=600)
    max_retries: int = Field(default=1, ge=0, le=3)
    max_handoffs: int = Field(default=12, ge=1)
    max_no_progress: int = Field(default=3, ge=1)
    max_recoveries: int = Field(default=2, ge=0, le=5)
    screenshot_on_checkpoint: bool = True
    model_url: str | None = None
    model_name: str = "qwen3:8b"
    model_timeout: float = Field(default=30, gt=0, le=120)
    sample_interval: float = Field(default=0.5, ge=0.1)

    @model_validator(mode="after")
    def time_budget(self):
        if self.lease_seconds <= self.action_timeout + 5:
            raise ValueError("lease_seconds must exceed action_timeout + 5 seconds")
        return self


class Product(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    price: float = Field(gt=0, le=1_000_000)
    currency: Literal["USD"] = "USD"
    warranty_months: int | None = Field(default=None, ge=0, le=120)
    source_url: str
    evidence_id: str
    version: int = Field(default=1, ge=1)


class Action(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    owner: Role
    epoch: int
    kind: Literal[
        "navigate",
        "follow_link",
        "read_page",
        "scroll",
        "open_file",
        "set_cell",
        "set_cells",
        "write_document",
    ]
    target: str
    payload: dict[str, Any] = Field(default_factory=dict)
    expected: dict[str, Any] = Field(default_factory=dict)
    goal: str


class Handoff(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    sender: Role
    receiver: Role
    reason: str = Field(min_length=1)
    next_task: str = Field(min_length=1)
    data_version: int = Field(ge=0)
    completion: list[str] = Field(min_length=1)
    checkpoint_id: str
    resume_at: str
    authority_epoch: int = Field(ge=0)

    @model_validator(mode="after")
    def distinct(self):
        if self.sender == self.receiver:
            raise ValueError("handoff requires different roles")
        return self


class Observation(BaseModel):
    timestamp: float
    application: str
    title: str = ""
    document_uri: str = ""
    focus: str = ""
    accessibility: str = ""
    screenshot: str | None = None
    error: str | None = None


class Primitive(BaseModel):
    kind: Literal["hotkey", "key", "text", "scroll", "move", "click", "launch", "pause"]
    value: Any
    allow_typo: bool = False
    hold_seconds: float = Field(default=0, ge=0, le=0.5)
    onset_interval_seconds: float | None = Field(default=None, ge=0)
