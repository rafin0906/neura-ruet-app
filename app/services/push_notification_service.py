from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import threading
import time
from typing import Any

import httpx
from google.oauth2 import service_account
from google.auth.transport.requests import Request as GoogleAuthRequest

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.device_token_models import DeviceToken, DeviceOwnerRole
from app.models.notice_models import Notice
from app.models.teacher_models import Teacher
from app.models.cr_models import CR
from app.services.device_token_service import deactivate_token

logger = logging.getLogger(__name__)

FIREBASE_MESSAGING_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"


_token_lock = threading.Lock()
_cached_access_token: str | None = None
_cached_access_token_expiry_ts: float = 0.0
_cached_project_id: str | None = None
_cached_service_account_info: dict[str, Any] | None = None


_logged_firebase_creds_source: bool = False


def _log_firebase_creds_source_once() -> None:
    """Log which Firebase credentials source is used (safe: no secrets).

    This is mainly for production debugging (e.g., Render env var not set / wrong key deployed).
    """

    global _logged_firebase_creds_source
    if _logged_firebase_creds_source:
        return
    _logged_firebase_creds_source = True

    try:
        info = _service_account_info()
        if info:
            logger.info(
                "Firebase creds source=env project_id=%s client_email=%s private_key_id=%s",
                str(info.get("project_id") or ""),
                str(info.get("client_email") or ""),
                str(info.get("private_key_id") or ""),
            )
            return

        path = _service_account_file()
        logger.info("Firebase creds source=file path=%s", path)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            logger.info(
                "Firebase creds file project_id=%s client_email=%s private_key_id=%s",
                str(data.get("project_id") or ""),
                str(data.get("client_email") or ""),
                str(data.get("private_key_id") or ""),
            )
        except Exception:
            # Don't fail push due to logging.
            logger.info("Firebase creds file could not be read for diagnostics")
    except Exception:
        # Best-effort diagnostics only.
        return


def _normalize_service_account_info(info: dict[str, Any]) -> dict[str, Any]:
    """Normalize common deployment formatting issues.

    Most common production issue for "invalid_grant: Invalid JWT Signature" is that
    the service account private_key is injected via env var with literal "\\n"
    instead of real newlines.
    """

    if not isinstance(info, dict):
        return info

    pk = info.get("private_key")
    if isinstance(pk, str):
        pk_str = pk.strip().strip('"')
        # If the key contains literal backslash-n sequences, convert to newlines.
        if "\\n" in pk_str and "\n" not in pk_str:
            pk_str = pk_str.replace("\\n", "\n")
        info["private_key"] = pk_str

    return info


def _service_account_info() -> dict[str, Any] | None:
    """Return service account JSON loaded from env vars, if provided.

    Supported env vars:
    - FIREBASE_SERVICE_ACCOUNT_JSON: raw JSON string
    - FIREBASE_SERVICE_ACCOUNT_JSON_B64: base64-encoded JSON string (safer for multi-line values)

    If neither is set, returns None and callers can fall back to file-based loading.
    """

    global _cached_service_account_info
    if _cached_service_account_info is not None:
        return _cached_service_account_info

    raw_b64 = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON_B64", "").strip()
    raw = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()

    try:
        if raw_b64:
            decoded = base64.b64decode(raw_b64).decode("utf-8")
            _cached_service_account_info = _normalize_service_account_info(
                json.loads(decoded)
            )
            return _cached_service_account_info

        if raw:
            _cached_service_account_info = _normalize_service_account_info(
                json.loads(raw)
            )
            return _cached_service_account_info
    except Exception as e:
        raise RuntimeError(
            "Invalid Firebase service account JSON in FIREBASE_SERVICE_ACCOUNT_JSON(_B64)"
        ) from e

    _cached_service_account_info = None
    return None


def _service_account_file() -> str:
    # Default: backend/service_account_key.json
    default_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "service_account_key.json",
    )
    return (
        os.getenv("FIREBASE_SERVICE_ACCOUNT_FILE")
        or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        or default_path
    )


def _get_project_id() -> str:
    global _cached_project_id
    if _cached_project_id:
        return _cached_project_id

    _log_firebase_creds_source_once()

    info = _service_account_info()
    if info:
        project_id = info.get("project_id")
        if not project_id:
            raise RuntimeError("Firebase service account JSON missing project_id")
        _cached_project_id = str(project_id)
        return _cached_project_id

    path = _service_account_file()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError as e:
        raise RuntimeError(
            "Firebase service account credentials not configured. "
            "Set FIREBASE_SERVICE_ACCOUNT_JSON_B64 (preferred) or FIREBASE_SERVICE_ACCOUNT_JSON, "
            "or set FIREBASE_SERVICE_ACCOUNT_FILE/GOOGLE_APPLICATION_CREDENTIALS to a readable JSON file path."
        ) from e
    project_id = data.get("project_id")
    if not project_id:
        raise RuntimeError("Firebase service account JSON missing project_id")
    _cached_project_id = str(project_id)
    return _cached_project_id


def _get_access_token() -> str:
    global _cached_access_token, _cached_access_token_expiry_ts

    _log_firebase_creds_source_once()

    now = time.time()
    # Refresh a bit early.
    if _cached_access_token and (_cached_access_token_expiry_ts - 60) > now:
        return _cached_access_token

    with _token_lock:
        now = time.time()
        if _cached_access_token and (_cached_access_token_expiry_ts - 60) > now:
            return _cached_access_token

        info = _service_account_info()
        if info:
            credentials = service_account.Credentials.from_service_account_info(
                info,
                scopes=[FIREBASE_MESSAGING_SCOPE],
            )
        else:
            path = _service_account_file()
            try:
                credentials = service_account.Credentials.from_service_account_file(
                    path,
                    scopes=[FIREBASE_MESSAGING_SCOPE],
                )
            except FileNotFoundError as e:
                raise RuntimeError(
                    "Firebase service account credentials not configured. "
                    "Set FIREBASE_SERVICE_ACCOUNT_JSON_B64 (preferred) or FIREBASE_SERVICE_ACCOUNT_JSON, "
                    "or set FIREBASE_SERVICE_ACCOUNT_FILE/GOOGLE_APPLICATION_CREDENTIALS to a readable JSON file path."
                ) from e
        try:
            credentials.refresh(GoogleAuthRequest())
        except Exception as e:
            # Surface the most common causes with an actionable message.
            msg = str(e)
            if "invalid_grant" in msg.lower() or "invalid jwt signature" in msg.lower():
                raise RuntimeError(
                    "Firebase credentials refresh failed (invalid_grant / Invalid JWT Signature). "
                    "This usually means the service account key is wrong/revoked OR the private_key is misformatted "
                    "(common when injected via env vars with literal \\n instead of real newlines). "
                    "Prefer setting FIREBASE_SERVICE_ACCOUNT_JSON_B64 to the exact service-account JSON, or set "
                    "GOOGLE_APPLICATION_CREDENTIALS/FIREBASE_SERVICE_ACCOUNT_FILE to a JSON file path."
                ) from e
            raise

        if not credentials.token or not credentials.expiry:
            raise RuntimeError("Failed to obtain Firebase access token")

        _cached_access_token = credentials.token
        _cached_access_token_expiry_ts = credentials.expiry.timestamp()
        return _cached_access_token


def _normalize_section(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip()
    if cleaned == "" or cleaned.lower() in {"none", "null"}:
        return None
    upper = cleaned.upper()
    return upper if upper in {"A", "B", "C"} else None


def _normalize_sender_role(value: object) -> str:
    # created_by_role is stored as an Enum (SenderRole). In many places
    # `str(enum)` becomes like 'SenderRole.cr', so we normalize robustly.
    if value is None:
        return ""
    role_value = getattr(value, "value", None)
    if isinstance(role_value, str):
        return role_value.strip().lower()
    return str(value).strip().lower().split(".")[-1]


def _select_recipient_tokens_for_notice(db: Session, notice: Notice) -> list[str]:
    dept = str(notice.dept)
    series = str(notice.series)
    sec = _normalize_section(notice.sec)

    sender_role = _normalize_sender_role(notice.created_by_role)

    tokens: list[str] = []

    # Teacher notice -> students + CR
    if sender_role == "teacher":
        q_students = db.query(DeviceToken.token).filter(
            DeviceToken.is_active.is_(True),
            DeviceToken.platform == "android",
            DeviceToken.owner_role == DeviceOwnerRole.student,
            DeviceToken.dept == dept,
            DeviceToken.series == series,
        )
        if sec is not None:
            q_students = q_students.filter(DeviceToken.sec == sec)

        q_crs = db.query(DeviceToken.token).filter(
            DeviceToken.is_active.is_(True),
            DeviceToken.platform == "android",
            DeviceToken.owner_role == DeviceOwnerRole.cr,
            DeviceToken.dept == dept,
            DeviceToken.series == series,
        )
        if sec is not None:
            q_crs = q_crs.filter(DeviceToken.sec == sec)

        tokens.extend([t[0] for t in q_students.all()])
        tokens.extend([t[0] for t in q_crs.all()])

    # CR notice -> students
    elif sender_role == "cr":
        q_students = db.query(DeviceToken.token).filter(
            DeviceToken.is_active.is_(True),
            DeviceToken.platform == "android",
            DeviceToken.owner_role == DeviceOwnerRole.student,
            DeviceToken.dept == dept,
            DeviceToken.series == series,
        )
        if sec is not None:
            q_students = q_students.filter(DeviceToken.sec == sec)
        tokens.extend([t[0] for t in q_students.all()])

    return list(dict.fromkeys(tokens))


def _shorten(text: str, max_len: int) -> str:
    cleaned = (text or "").strip()
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max(0, max_len - 1)].rstrip() + "…"


def _get_notice_sender_name(db: Session, notice: Notice) -> str:
    role = _normalize_sender_role(notice.created_by_role)
    try:
        if role == "teacher" and getattr(notice, "created_by_teacher_id", None):
            name = (
                db.query(Teacher.full_name)
                .filter(Teacher.id == str(notice.created_by_teacher_id))
                .scalar()
            )
            return str(name).strip() if name else "Teacher"

        if role == "cr" and getattr(notice, "created_by_cr_id", None):
            row = (
                db.query(CR.full_name, CR.roll_no)
                .filter(CR.id == str(notice.created_by_cr_id))
                .first()
            )
            if not row:
                return "CR"
            full_name, roll_no = row
            if full_name and str(full_name).strip():
                return str(full_name).strip()
            if roll_no and str(roll_no).strip():
                return f"CR ({str(roll_no).strip()})"
            return "CR"
    except Exception:
        # Best-effort only; never break push sending due to missing profile.
        return ""

    return ""


async def _send_fcm_message(
    token: str, *, title: str, body: str, data: dict[str, str]
) -> bool | None:
    project_id = _get_project_id()
    url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
    access_token = _get_access_token()

    payload: dict[str, Any] = {
        "message": {
            "token": token,
            "notification": {"title": title, "body": body},
            "data": data,
            "android": {
                "priority": "high",
                # Ensure notifications route to an existing channel on Android 8+.
                # The app creates this channel via Notifee (id: 'default').
                "notification": {"channel_id": "default"},
            },
        }
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=utf-8",
    }

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, headers=headers, json=payload)

    if 200 <= resp.status_code < 300:
        return True

    text = resp.text or ""
    lowered = text.lower()

    # UNREGISTERED / invalid token -> allow caller to deactivate.
    if (
        ("unregistered" in lowered)
        or ("registration token" in lowered)
        or ("notregistered" in lowered)
    ):
        logger.info("FCM token unregistered/invalid; will deactivate")
        return False

    # Auth/config issues: do NOT deactivate tokens.
    if resp.status_code in {401, 403}:
        logger.error(
            "FCM auth/permission error status=%s body=%s",
            resp.status_code,
            (text[:2000] + "…") if len(text) > 2000 else text,
        )
        return None

    # For all other errors, return False so callers can treat it as failure and we log the reason.
    # This helps diagnose common issues like SENDER_ID_MISMATCH / PROJECT_NOT_PERMITTED.
    logger.warning(
        "FCM send failed status=%s body=%s",
        resp.status_code,
        (text[:2000] + "…") if len(text) > 2000 else text,
    )
    return None


async def _send_notice_push_async(db: Session, notice: Notice) -> None:
    tokens = _select_recipient_tokens_for_notice(db, notice)
    logger.info(
        "Push: notice_id=%s role=%s dept=%s series=%s sec=%s tokens=%s",
        str(notice.id),
        str(notice.created_by_role),
        str(notice.dept),
        str(notice.series),
        str(notice.sec) if notice.sec is not None else None,
        len(tokens),
    )
    if not tokens:
        return

    sender_name = _get_notice_sender_name(db, notice)
    notice_title = _shorten(str(notice.title), 80)
    notice_desc = _shorten(str(getattr(notice, "notice_message", "") or ""), 200)

    # Receiver format: "{sender}: {title}" and body = description.
    base_title = notice_title if notice_title else "New Notice"
    title = f"{sender_name}: {base_title}" if sender_name else base_title
    body = notice_desc

    data = {
        "type": "notice",
        "notice_id": str(notice.id),
        "screen": "Notifications",
        "sender_name": sender_name,
        "notice_title": notice_title,
        "notice_description": notice_desc,
        "dept": str(notice.dept),
        "series": str(notice.series),
        "sec": str(notice.sec) if notice.sec is not None else "",
        "created_by_role": _normalize_sender_role(notice.created_by_role),
    }

    semaphore = asyncio.Semaphore(20)

    async def _send_one(t: str) -> None:
        async with semaphore:
            result = await _send_fcm_message(t, title=title, body=body, data=data)
            if result is False:
                logger.info(
                    "Push: deactivating token prefix=%s",
                    (t[:20] + "...") if isinstance(t, str) else "<non-str>",
                )
                deactivate_token(db, t)

    await asyncio.gather(*[_send_one(t) for t in tokens])


async def _send_notice_push_by_id_async(notice_id: str) -> None:
    db = SessionLocal()
    try:
        notice = db.query(Notice).filter(Notice.id == str(notice_id)).first()
        if not notice:
            return
        await _send_notice_push_async(db, notice)
    finally:
        db.close()


def _log_task_result(task: asyncio.Task[None]) -> None:
    try:
        task.result()
    except Exception:
        logger.exception("Failed to send notice push")


def send_notice_push_by_id(notice_id: str) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is None:
        try:
            asyncio.run(_send_notice_push_by_id_async(notice_id))
        except Exception:
            logger.exception("Failed to send notice push")
        return

    task = loop.create_task(_send_notice_push_by_id_async(notice_id))
    task.add_done_callback(_log_task_result)
