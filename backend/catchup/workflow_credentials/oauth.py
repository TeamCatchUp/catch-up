from __future__ import annotations

from urllib.parse import parse_qsl
from urllib.parse import urlencode
from urllib.parse import urlsplit
from urllib.parse import urlunsplit

from catchup.configs.config import auth_settings
from catchup.utils.redis import consume_oauth_state_payload

DEFAULT_REDIRECT_AFTER = "/settings/credentials"


def sanitize_redirect_after(redirect_after: str | None) -> str:
    if not redirect_after:
        return DEFAULT_REDIRECT_AFTER

    candidate = redirect_after.strip()
    if not candidate.startswith("/") or candidate.startswith("//"):
        return DEFAULT_REDIRECT_AFTER

    parsed = urlsplit(candidate)
    if parsed.scheme or parsed.netloc:
        return DEFAULT_REDIRECT_AFTER

    return urlunsplit(("", "", parsed.path or DEFAULT_REDIRECT_AFTER, parsed.query, ""))


def split_oauth_scopes(scope_value: str | None) -> list[str]:
    if not scope_value:
        return []
    return [scope for scope in scope_value.replace(",", " ").split() if scope]


def build_oauth_completion_redirect(
    *,
    vendor: str,
    success: bool,
    redirect_after: str | None,
    reason: str | None = None,
) -> str:
    internal_path = sanitize_redirect_after(redirect_after)
    parsed = urlsplit(internal_path)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.update(
        {
            "credential_connected": "true" if success else "false",
            "vendor": vendor,
            "status": "success" if success else "error",
        }
    )
    if reason:
        query["reason"] = reason

    path_with_query = urlunsplit(("", "", parsed.path, urlencode(query), ""))
    return f"{auth_settings.FRONTEND_BASE_URL.rstrip('/')}{path_with_query}"


async def consume_workflow_redirect_after(
    *,
    provider: str,
    state: str | None,
) -> str | None:
    if not state:
        return None

    payload = await consume_oauth_state_payload(provider=provider, state=state)
    if payload is None or payload.get("purpose") != "workflow_personal":
        return None
    return payload.get("redirect_after")
