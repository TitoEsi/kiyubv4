"""Outbound Auth emails. Memory/pytest skips live send. Never log tokens or passwords."""
from __future__ import annotations

import logging
import os
from typing import Any
from urllib.parse import urlparse

from fastapi import HTTPException, status

from .db import supabase_enabled

logger = logging.getLogger(__name__)

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def public_app_url() -> str:
    raw = (os.environ.get("PUBLIC_APP_URL") or "").strip()
    if raw:
        return raw.rstrip("/")
    if supabase_enabled():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Invitation email is not configured.",
        )
    return "http://localhost:5173"


def require_public_app_url() -> str:
    """Return the public site URL. Live Supabase must not use a localhost fallback."""
    raw = (os.environ.get("PUBLIC_APP_URL") or "").strip().rstrip("/")
    if not supabase_enabled():
        return raw or "http://localhost:5173"
    if not raw:
        logger.error("PUBLIC_APP_URL is required when Supabase is enabled")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Invitation email is not configured.",
        )
    host = (urlparse(raw).hostname or "").lower()
    if host in _LOCAL_HOSTS:
        logger.error("PUBLIC_APP_URL must not be localhost when Supabase is enabled")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Invitation email is not configured.",
        )
    return raw


def send_auth_invite(email: str, redirect_to: str, metadata: dict[str, Any] | None = None) -> str | None:
    if not supabase_enabled():
        return None
    from supabase.auth import invite_user_by_email

    return invite_user_by_email(email, redirect_to, metadata)


def send_application_rejection(email: str, full_name: str | None = None, reason: str | None = None) -> bool:
    """Send the architect rejection email. Memory/tests: no-op success. Live: Edge Function."""
    if not supabase_enabled():
        return True
    secret = (os.environ.get("REJECTION_MAIL_SECRET") or "").strip()
    if not secret:
        logger.error("REJECTION_MAIL_SECRET is not configured")
        return False
    payload = {
        "email": email,
        "full_name": full_name or "",
        "rejection_reason": reason,
        "status": "REJECTED",
    }
    try:
        from supabase.client import get_service_client

        client = get_service_client()
        headers = {"x-rejection-secret": secret} if secret else {}
        result = client.functions.invoke("architect-rejection", invoke_options={"body": payload, "headers": headers})
        error = getattr(result, "error", None)
        if error:
            logger.error("architect rejection email function returned an error")
            return False
        return True
    except Exception:
        logger.error("architect rejection email function failed")
        return False


def invite_failed(exc: Exception) -> HTTPException:
    if isinstance(exc, HTTPException):
        if exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
            return exc
        return HTTPException(status.HTTP_502_BAD_GATEWAY, "Unable to send invitation. Please try again.")
    return HTTPException(status.HTTP_502_BAD_GATEWAY, "Unable to send invitation. Please try again.")
