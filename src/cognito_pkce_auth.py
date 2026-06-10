"""
Cognito OAuth2 Authorization Code + PKCE (headless hosted UI login).

Requires env:
  COGNITO_USER_POOL_ID, COGNITO_CLIENT_ID, COGNITO_REDIRECT_URI,
  COGNITO_SCOPES, COGNITO_USERNAME, COGNITO_PASSWORD
Optional:
  COGNITO_REGION, COGNITO_DOMAIN, COGNITO_CLIENT_SECRET
"""
from __future__ import annotations

import base64
import hashlib
import logging
import os
import re
import secrets
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
from urllib.parse import parse_qs, urljoin, urlparse

import requests

logger = logging.getLogger(__name__)

TIMEOUT = 30
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _make_verifier() -> str:
    return _b64url(os.urandom(32))


def _make_challenge(verifier: str) -> str:
    return _b64url(hashlib.sha256(verifier.encode("ascii")).digest())


@dataclass(frozen=True)
class CognitoPkceConfig:
    user_pool_id: str
    region: str
    client_id: str
    redirect_uri: str
    scopes: str
    username: str
    password: str
    client_secret: str = ""
    domain: str = ""

    @classmethod
    def from_env(cls) -> "CognitoPkceConfig":
        pool_id = os.environ.get("COGNITO_USER_POOL_ID", "").strip()
        region = os.environ.get("COGNITO_REGION", "").strip()
        if not region and "_" in pool_id:
            region = pool_id.split("_", 1)[0]
        return cls(
            user_pool_id=pool_id,
            region=region,
            client_id=os.environ.get("COGNITO_CLIENT_ID", "").strip(),
            redirect_uri=os.environ.get("COGNITO_REDIRECT_URI", "").strip(),
            scopes=os.environ.get(
                "COGNITO_SCOPES",
                "openid profile adminscope/allaccessscope email",
            ).strip(),
            username=os.environ.get("COGNITO_USERNAME", "").strip(),
            password=os.environ.get("COGNITO_PASSWORD", "").strip(),
            client_secret=os.environ.get("COGNITO_CLIENT_SECRET", "").strip(),
            domain=os.environ.get("COGNITO_DOMAIN", "").strip().rstrip("/"),
        )

    def validate(self) -> None:
        missing = [
            name
            for name, val in (
                ("COGNITO_USER_POOL_ID", self.user_pool_id),
                ("COGNITO_CLIENT_ID", self.client_id),
                ("COGNITO_REDIRECT_URI", self.redirect_uri),
                ("COGNITO_SCOPES", self.scopes),
                ("COGNITO_USERNAME", self.username),
                ("COGNITO_PASSWORD", self.password),
            )
            if not val
        ]
        if missing:
            raise ValueError(
                "Cognito PKCE auth missing required environment variables: "
                + ", ".join(missing)
            )
        if not self.region:
            raise ValueError(
                "Cognito PKCE auth requires COGNITO_REGION or a valid COGNITO_USER_POOL_ID"
            )


def discover_domain(config: CognitoPkceConfig, session: requests.Session) -> str:
    if config.domain:
        return config.domain
    url = (
        f"https://cognito-idp.{config.region}.amazonaws.com/"
        f"{config.user_pool_id}/.well-known/openid-configuration"
    )
    response = session.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    auth_endpoint = response.json().get("authorization_endpoint")
    if not auth_endpoint:
        raise RuntimeError(
            "No authorization_endpoint in OIDC discovery document; "
            "hosted UI domain is not configured on this user pool."
        )
    return auth_endpoint.rsplit("/oauth2/authorize", 1)[0]


def _find_form(html: str, base_url: str) -> Optional[Tuple[str, Dict[str, str]]]:
    match = re.search(
        r'<form\b[^>]*action="([^"]*)"[^>]*>(.*?)</form>',
        html,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None
    action_url = urljoin(base_url, match.group(1).replace("&amp;", "&"))
    body = match.group(2)
    fields: Dict[str, str] = {}
    for inp in re.findall(r"<input\b[^>]*>", body, re.IGNORECASE):
        name_match = re.search(r'\bname="([^"]*)"', inp)
        if not name_match:
            continue
        value_match = re.search(r'\bvalue="([^"]*)"', inp)
        fields[name_match.group(1)] = value_match.group(1) if value_match else ""
    return action_url, fields


def _follow_redirects(
    session: requests.Session,
    response: requests.Response,
) -> requests.Response:
    page = response
    while page.status_code in _REDIRECT_STATUSES:
        location = page.headers.get("Location")
        if not location:
            break
        page = session.get(
            urljoin(page.url, location),
            timeout=TIMEOUT,
            allow_redirects=False,
        )
    return page


def _authorize_error(location: str) -> Optional[str]:
    if "error=" not in location:
        return None
    query = parse_qs(urlparse(location).query)
    error = query.get("error", ["?"])[0]
    description = query.get("error_description", [""])[0]
    return f"{error} - {description}"


def fetch_tokens_pkce(
    config: Optional[CognitoPkceConfig] = None,
    *,
    session: Optional[requests.Session] = None,
) -> Dict[str, object]:
    """
    Run Authorization Code + PKCE and return Cognito token JSON
    (access_token, id_token, refresh_token, expires_in, ...).
    """
    cfg = config or CognitoPkceConfig.from_env()
    cfg.validate()

    http = session or requests.Session()
    http.headers.setdefault("User-Agent", "Mozilla/5.0")

    domain = discover_domain(cfg, http)
    logger.info("Cognito PKCE: using domain %s", domain)

    verifier = _make_verifier()
    challenge = _make_challenge(verifier)
    state = secrets.token_urlsafe(16)

    authorize_url = f"{domain}/oauth2/authorize"
    authorize_params = {
        "response_type": "code",
        "client_id": cfg.client_id,
        "redirect_uri": cfg.redirect_uri,
        "scope": cfg.scopes,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }

    page = http.get(
        authorize_url,
        params=authorize_params,
        timeout=TIMEOUT,
        allow_redirects=False,
    )
    location = page.headers.get("Location", "")
    auth_error = _authorize_error(location)
    if auth_error:
        raise RuntimeError(f"Cognito rejected authorize request: {auth_error}")

    page = _follow_redirects(http, page)

    code: Optional[str] = None
    for step in range(1, 6):
        parsed = _find_form(page.text, page.url)
        if not parsed:
            raise RuntimeError(
                f"Cognito login step {step}: no HTML form found (url={page.url}). "
                "Possible MFA, CAPTCHA, or unsupported Managed Login UI."
            )
        action, fields = parsed

        if "username" in fields:
            fields["username"] = cfg.username
        if "password" in fields:
            fields["password"] = cfg.password

        if "username" not in fields and "password" not in fields:
            raise RuntimeError(
                f"Cognito login step {step}: form has no username/password fields "
                "(MFA, passkey, or confirmation screen)."
            )

        headers = {
            "Origin": domain,
            "Referer": page.url,
            "Content-Type": "application/x-www-form-urlencoded",
        }
        resp = http.post(
            action,
            data=fields,
            headers=headers,
            timeout=TIMEOUT,
            allow_redirects=False,
        )
        logger.info(
            "Cognito PKCE login step %d -> HTTP %s",
            step,
            resp.status_code,
        )

        loc = resp.headers.get("Location")
        if loc:
            qs = parse_qs(urlparse(loc).query)
            if "code" in qs:
                code = qs["code"][0]
                break
            login_error = _authorize_error(loc)
            if login_error:
                raise RuntimeError(f"Cognito login error: {login_error}")
            page = http.get(urljoin(action, loc), timeout=TIMEOUT, allow_redirects=False)
            page = _follow_redirects(http, page)
            continue

        if resp.status_code == 200:
            page = resp
            continue

        raise RuntimeError(
            f"Cognito login step {step}: HTTP {resp.status_code} without redirect."
        )

    if not code:
        raise RuntimeError(
            "Cognito PKCE login completed without an authorization code."
        )

    token_data = {
        "grant_type": "authorization_code",
        "client_id": cfg.client_id,
        "code": code,
        "redirect_uri": cfg.redirect_uri,
        "code_verifier": verifier,
    }
    auth = (cfg.client_id, cfg.client_secret) if cfg.client_secret else None

    token_resp = http.post(
        f"{domain}/oauth2/token",
        data=token_data,
        auth=auth,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=TIMEOUT,
    )
    if token_resp.status_code != 200:
        raise RuntimeError(
            f"Cognito token exchange failed (HTTP {token_resp.status_code}): "
            f"{token_resp.text[:500]}"
        )

    tokens = token_resp.json()
    if not tokens.get("access_token"):
        raise RuntimeError("Cognito token response missing access_token")
    return tokens


def fetch_access_token_pkce(
    config: Optional[CognitoPkceConfig] = None,
    *,
    session: Optional[requests.Session] = None,
) -> Tuple[str, int]:
    """Return (access_token, expires_in_seconds)."""
    tokens = fetch_tokens_pkce(config, session=session)
    access_token = str(tokens["access_token"])
    expires_in = int(tokens.get("expires_in", 3600))
    return access_token, expires_in
