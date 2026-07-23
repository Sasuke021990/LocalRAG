"""
Google Sign-In via the standard OAuth 2.0 Authorization Code flow,
implemented with direct REST calls (``requests``, already a dependency)
rather than a dedicated OAuth library — see .plan/task_plan.md KTD 9.
"""

import logging
from urllib.parse import urlencode

import requests
from fastapi import HTTPException

from utils.config import config

logger = logging.getLogger(__name__)

AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v3/userinfo"


def build_authorization_url(state: str) -> str:
    params = {
        "client_id": config.GOOGLE_CLIENT_ID,
        "redirect_uri": config.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
    }
    return f"{AUTHORIZATION_ENDPOINT}?{urlencode(params)}"


def exchange_code_for_userinfo(code: str) -> dict:
    """
    Exchanges an authorization code for Google user info.
    Returns {"sub": <google user id>, "email": <email>, "name": <display name, may be "">}.
    ``name`` comes from the ``profile`` scope already requested above; falls
    back to "" (caller derives a username from the email) if Google omits it.
    Raises HTTPException(400) if the exchange or userinfo fetch fails.
    """
    token_resp = requests.post(
        TOKEN_ENDPOINT,
        data={
            "code": code,
            "client_id": config.GOOGLE_CLIENT_ID,
            "client_secret": config.GOOGLE_CLIENT_SECRET,
            "redirect_uri": config.GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        },
        timeout=10,
    )
    if token_resp.status_code != 200:
        # Status only at error level -- the response body is logged at debug
        # only (normally disabled in production), since Google's error
        # payload is attacker-influenced (via the `code` we forwarded) and
        # not something that belongs in aggregated logs by default.
        logger.error(f"Google token exchange failed: HTTP {token_resp.status_code}")
        logger.debug(f"Google token exchange error body: {token_resp.text}")
        raise HTTPException(status_code=400, detail="Google OAuth exchange failed")

    access_token = token_resp.json().get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="Google OAuth exchange failed")

    userinfo_resp = requests.get(
        USERINFO_ENDPOINT,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    if userinfo_resp.status_code != 200:
        logger.error(f"Google userinfo fetch failed: HTTP {userinfo_resp.status_code}")
        logger.debug(f"Google userinfo error body: {userinfo_resp.text}")
        raise HTTPException(status_code=400, detail="Failed to fetch Google userinfo")

    data = userinfo_resp.json()
    if "sub" not in data or "email" not in data:
        raise HTTPException(status_code=400, detail="Failed to fetch Google userinfo")

    return {"sub": data["sub"], "email": data["email"], "name": data.get("name", "")}
