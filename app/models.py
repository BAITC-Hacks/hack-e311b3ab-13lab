from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    status: Literal["open", "in_progress", "done"] = "open"
    needs_review: bool = True


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
