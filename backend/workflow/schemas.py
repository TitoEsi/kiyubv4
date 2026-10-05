from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


class LoginBody(BaseModel):
    email: str
    password: str


class RegisterBody(BaseModel):
    email: str
    password: str
    role: str = "CLIENT"
    invitation_token: str | None = None
    full_name: str | None = None
    accept_terms: bool = False
    accept_privacy: bool = False


class ProjectCreate(BaseModel):
    name: str
    client_id: str | None = None
    architect_id: str | None = None


class ProjectAssign(BaseModel):
    client_id: str | None = None
    architect_id: str | None = None


class BriefBody(BaseModel):
    questionnaire: dict[str, Any]
    specification: dict[str, Any] = Field(default_factory=dict)


class PreferencesBody(BaseModel):
    measurement_unit: Literal["m", "ft", "cm", "mm", "in"]


class CommentBody(BaseModel):
    body: str
    revision_id: str | None = None
    object_id: str | None = None
    stage: str | None = None
    x: float | None = None
    y: float | None = None
    parent_id: str | None = None


class CommentResolveBody(BaseModel):
    resolved: bool = True
    note: str | None = None


class CommentPatch(BaseModel):
    body: str | None = None
    object_id: str | None = None
    x: float | None = None
    y: float | None = None


class WorkingDesignBody(BaseModel):
    scene_document: dict[str, Any]


class SubmitReviewBody(BaseModel):
    scene_document: dict[str, Any] | None = None
    floor_plan: dict[str, Any] | None = None


class PublishBody(BaseModel):
    scene_document: dict[str, Any] | None = None
    floor_plan: dict[str, Any] | None = None


class AccountPatch(BaseModel):
    approved: bool | None = None
    role: str | None = None
    suspended: bool | None = None


class InvitationCreate(BaseModel):
    email: str
    project_name: str | None = None
    resend: bool = False


class InquiryCreate(BaseModel):
    name: str
    email: str
    message: str


class ArchitectApplicationCreate(BaseModel):
    email: str
    full_name: str
    information: str | None = None


class ArchitectApplicationReject(BaseModel):
    reason: str | None = None


class ArchitectApplicationComplete(BaseModel):
    password: str
    role: str | None = None
    accept_terms: bool = False
    accept_privacy: bool = False
