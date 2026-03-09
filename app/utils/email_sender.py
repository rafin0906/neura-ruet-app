from __future__ import annotations

import os
from typing import Iterable, Sequence

from app.utils.logger import logger


def get_default_from_address() -> str:
   
    return "auth@neuraruet.tech"


def _normalize_from_address(from_address: str) -> str:
    from_address = (from_address or "").strip()
    if not from_address:
        from_address = get_default_from_address()

    # Resend accepts either "Name <email@domain>" or "email@domain".
    # If caller gives a bare email, add a neutral display name.
    if "<" not in from_address and ">" not in from_address and "@" in from_address:
        return f"NeuraRUET <{from_address}>"

    return from_address


def _normalize_to(to: str | Sequence[str]) -> list[str]:
    if isinstance(to, str):
        emails = [to]
    else:
        emails = list(to)

    normalized: list[str] = []
    for e in emails:
        e = (e or "").strip()
        if e:
            normalized.append(e)

    return normalized


def send_text_email(
    *,
    to: str | Sequence[str],
    subject: str,
    text: str,
    from_address: str | None = None,
) -> dict | None:
    """Send a plaintext email using Resend when configured.

    Returns Resend API response dict on success.
    Returns None when RESEND_API_KEY is not configured.

    Raises on send failures so callers can decide how to respond.
    """

    resend_api_key = (os.getenv("RESEND_API_KEY") or "").strip()
    if not resend_api_key:
        logger.info(
            "RESEND_API_KEY not set; skipping email send (to=%s subject=%s)",
            _normalize_to(to),
            subject,
        )
        return None

    # Local import so app can boot without the optional dependency.
    import resend  # type: ignore

    resend.api_key = resend_api_key

    payload = {
        "from": _normalize_from_address(from_address or get_default_from_address()),
        "to": _normalize_to(to),
        "subject": subject,
        "text": text,
    }

    try:
        resp = resend.Emails.send(payload)
        # Resend SDK typically returns a dict like {"id": "..."}
        logger.info(
            "Resend email sent (to=%s subject=%s resp=%s)",
            payload["to"],
            subject,
            resp,
        )
        return resp if isinstance(resp, dict) else {"response": resp}
    except Exception as exc:
        # Try to extract useful bits without leaking secrets.
        logger.exception(
            "Resend send failed (to=%s subject=%s from=%s): %s",
            payload.get("to"),
            subject,
            payload.get("from"),
            str(exc),
        )
        raise
