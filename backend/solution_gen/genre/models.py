from __future__ import annotations

from pydantic import BaseModel, Field


class BriefSlot(BaseModel):
    key: str
    label: str
    required: bool = False
    question: str = ""


class ChapterTemplate(BaseModel):
    key: str
    title: str
    words: int
    writing: str
    required: bool = True
    when: str | None = None
    diagram: bool = False
    nest_modules: bool = False


class GenreContract(BaseModel):
    """Doc-type grammar: slots, chapters, writing patterns. No industry content."""

    doc_type: str
    name: str
    slots: list[BriefSlot] = Field(default_factory=list)
    chapters: list[ChapterTemplate] = Field(default_factory=list)
    default_diagrams: list[str] = Field(default_factory=list)


class WorkPackage(BaseModel):
    id: str
    title: str
    unit: str


class PackModule(BaseModel):
    id: str
    title: str
    kind: str
    package: str
    default: bool = True
    implies_civil: bool = False
    brief: str = ""


class IndustryPack(BaseModel):
    """Industry fill-ins for a genre contract. Swap this file to add a new industry."""

    id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    work_packages: list[WorkPackage] = Field(default_factory=list)
    modules: list[PackModule] = Field(default_factory=list)
    scenes: list[str] = Field(default_factory=list)
    terms: list[str] = Field(default_factory=list)
    term_aliases: dict[str, str] = Field(default_factory=dict)
