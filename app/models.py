from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.json_schema import SkipJsonSchema

from app.rbac import Role
from app.security import MIN_PASSWORD_LENGTH

ACTIVE_STATUSES = frozenset({"queued", "transcribing", "diarizing", "analyzing"})
REVIEWABLE_STATUSES = frozenset({"ready", "approved"})
ActionStatus = Literal["open", "in_progress", "done"]
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class Word(BaseModel):
    word: str
    start: float = Field(ge=0)
    end: float = Field(ge=0)

    @model_validator(mode="after")
    def check_interval(self):
        if self.end < self.start:
            raise ValueError("Invalid word interval")
        return self


class Segment(BaseModel):
    id: str
    text: str
    start: float | None = None
    end: float | None = None
    speaker: str | None = None


class Action(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=2000)
    owner: str | None = Field(default=None, max_length=200)
    deadline_text: str | None = Field(default=None, max_length=300)
    due_date: date | None = None
    evidence: str = Field(min_length=1, max_length=4000)
    segment_ids: list[str] = Field(default_factory=list)
    status: ActionStatus = "open"
    needs_review: bool = True
    # Internal fields. SkipJsonSchema keeps them out of the schema sent to the LLM,
    # and validate_evidence overwrites whatever the model returns for them.
    id: SkipJsonSchema[str | None] = Field(default=None, max_length=64)
    assignee_id: SkipJsonSchema[str | None] = Field(default=None, max_length=64)


class Analysis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(max_length=10000)
    decisions: list[str] = Field(default_factory=list, max_length=100)
    actions: list[Action] = Field(default_factory=list, max_length=200)
    warnings: list[str] = Field(default_factory=list, max_length=100)


class Review(BaseModel):
    version: int = Field(ge=1)
    analysis: Analysis
    speaker_names: dict[str, str] = Field(default_factory=dict, max_length=100)


class Approval(BaseModel):
    version: int = Field(ge=1)


class ActionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: ActionStatus


class People(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chair_id: str | None = Field(default=None, max_length=64)
    participant_ids: list[str] = Field(default_factory=list, max_length=200)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=200)


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(max_length=254, pattern=EMAIL_PATTERN)
    name: str = Field(min_length=1, max_length=200)
    role: Role
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=200)


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=200)
    role: Role | None = None
    active: bool | None = None
    password: str | None = Field(default=None, min_length=MIN_PASSWORD_LENGTH, max_length=200)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=200)
