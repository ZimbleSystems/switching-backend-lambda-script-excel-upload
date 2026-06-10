"""

Thin API Gateway client with dependency-aware lookups and AWS Cognito auth.

Replaces the old MongoWriter for direct DB access.

"""

from __future__ import annotations



import json

import logging

import os

import time

from typing import Any, Dict, Optional



import requests

from cognito_pkce_auth import fetch_access_token_pkce
from defaults import normalize_demographic_id

logger = logging.getLogger(__name__)



# Map internal sheet names to their API Gateway paths

SHEET_TO_API_PATH = {

    "demographic": "/auth/demographic/v1/",

    "merchant_criteria": "/config/merchant-criteria/v1/",

    "instrument_criteria": "/config/instrument-criteria/v1/",

    "connector": "/config/connector-properties/v1/",

    "chain": "/auth/chain/v1/",

    "connector_table": "/auth/connectorTable/v1/",

    "merchant": "/auth/merchant/v1/",

    "store": "/auth/store/v1/",

}

# GET by-id path segment appended after the sheet base path (before {id})
SHEET_GET_ID_PATH_SEGMENT = {
    "demographic": "demographicId/",
}

_ALREADY_PRESENT_HINTS = (
    "already present",
    "cannot add",
    "already exists",
)


class AlreadyPresentError(Exception):
    """Raised when the API reports the record already exists (treat as skip, not failure)."""

    def __init__(self, sheet_name: str, id_value: Any, response_body: str) -> None:
        self.sheet_name = sheet_name
        self.id_value = id_value
        self.response_body = response_body
        super().__init__(response_body)


def _is_already_present_message(text: str) -> bool:
    lower = (text or "").lower()
    return any(hint in lower for hint in _ALREADY_PRESENT_HINTS)


def _extract_upserted_id(
    sheet_name: str,
    id_field: str,
    id_value: Any,
    response: requests.Response,
) -> str:
    """Prefer API-returned id (e.g. demographic lowercased) over request value."""
    try:
        data = response.json()
    except (json.JSONDecodeError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}

    if sheet_name == "demographic":
        returned = data.get("demographic_id") or data.get(id_field)
        if returned:
            return normalize_demographic_id(returned)

    for key in (id_field, "id"):
        if data.get(key) is not None:
            return str(data[key])

    if sheet_name == "demographic":
        return normalize_demographic_id(id_value)
    return str(id_value)



_TRUTHY = frozenset({"1", "true", "yes", "on"})





def _is_truthy(value: Optional[str]) -> bool:

    return (value or "").strip().lower() in _TRUTHY





def _api_debug_enabled() -> bool:

    """Toggle via env API_DEBUG_LOG=true|false (default false)."""

    return _is_truthy(os.environ.get("API_DEBUG_LOG", ""))





def _api_debug_log_file() -> Optional[str]:

    """Optional NDJSON file; set API_DEBUG_LOG_FILE or leave unset for CloudWatch only."""

    path = os.environ.get("API_DEBUG_LOG_FILE", "").strip()

    return path or None





def _redact_headers(headers: Dict[str, str]) -> Dict[str, str]:

    safe = dict(headers)

    if "Authorization" in safe:

        safe["Authorization"] = "Bearer ***"

    return safe





def _api_debug_log(event: str, data: Dict[str, Any]) -> None:

    """Structured API debug logging (CloudWatch + optional file). No-op when disabled."""

    if not _api_debug_enabled():

        return



    entry = {

        "event": event,

        "timestamp": int(time.time() * 1000),

        **data,

    }

    payload = json.dumps(entry, default=str)



    logger.info("API_DEBUG %s", payload)



    log_file = _api_debug_log_file()

    if log_file:

        try:

            with open(log_file, "a", encoding="utf-8") as fh:

                fh.write(payload + "\n")

        except OSError as exc:

            logger.warning("API_DEBUG could not write to %s: %s", log_file, exc)





class ApiGatewayClient:

    def __init__(

        self,

        api_gateway_url: Optional[str] = None,

    ):

        self.api_gateway_url = (api_gateway_url or os.environ.get("API_GATEWAY_URL", "")).rstrip("/")

        self.session = requests.Session()
        self._auth_session = requests.Session()
        self._access_token: Optional[str] = None
        self._token_expires_at = 0.0



        if _api_debug_enabled():

            logger.info(

                "API_DEBUG enabled (API_DEBUG_LOG=true); log_file=%s",

                _api_debug_log_file() or "(CloudWatch only)",

            )



    def _get_token(self) -> str:
        """Fetch or refresh JWT via Cognito Authorization Code + PKCE."""
        now = time.time()
        if self._access_token and now < self._token_expires_at:
            return self._access_token

        logger.info("Fetching Cognito access token via Authorization Code + PKCE...")
        access_token, expires_in = fetch_access_token_pkce(session=self._auth_session)
        self._access_token = access_token
        self._token_expires_at = now + expires_in - 60
        return self._access_token



    def _get_headers(self) -> Dict[str, str]:

        token = self._get_token()

        return {

            "Authorization": f"Bearer {token}",

            "Content-Type": "application/json",

            "Accept": "application/json",

        }



    def _get_endpoint(self, sheet_name: str) -> str:

        path = SHEET_TO_API_PATH.get(sheet_name)

        if not path:

            raise ValueError(f"Unknown API path mapping for sheet {sheet_name!r}")

        return f"{self.api_gateway_url}{path}"



    def _get_by_id_url(self, sheet_name: str, id_value: Any) -> str:

        endpoint = self._get_endpoint(sheet_name)

        segment = SHEET_GET_ID_PATH_SEGMENT.get(sheet_name, "")

        return f"{endpoint}{segment}{id_value}"



    def _put_by_id_url(self, sheet_name: str, id_value: Any) -> str:

        endpoint = self._get_endpoint(sheet_name)

        return f"{endpoint}{id_value}"



    def _log_request(

        self,

        *,

        operation: str,

        sheet_name: str,

        method: str,

        url: str,

        api_path: str,

        headers: Dict[str, str],

        body: Optional[Dict[str, Any]] = None,

        id_field: Optional[str] = None,

        id_value: Optional[Any] = None,

    ) -> None:

        _api_debug_log(

            "api_request",

            {

                "operation": operation,

                "sheet_name": sheet_name,

                "method": method,

                "url": url,

                "api_gateway_base": self.api_gateway_url,

                "api_path": api_path,

                "id_field": id_field,

                "id_value": str(id_value) if id_value is not None else None,

                "headers": _redact_headers(headers),

                "request_body": body,

            },

        )



    def _log_response(

        self,

        *,

        operation: str,

        sheet_name: str,

        method: str,

        url: str,

        status_code: int,

        response_body: str,

        elapsed_ms: Optional[int] = None,

    ) -> None:

        _api_debug_log(

            "api_response",

            {

                "operation": operation,

                "sheet_name": sheet_name,

                "method": method,

                "url": url,

                "status_code": status_code,

                "elapsed_ms": elapsed_ms,

                "response_body": response_body[:4000] if response_body else "",

            },

        )



    def exists(self, sheet_name: str, id_field: str, id_value: str) -> bool:

        """

        Check if a record exists.

        Demographic GET: `/auth/demographic/v1/demographicId/{demographicId}`.

        Other sheets default to `{base_path}{id}` unless configured in SHEET_GET_ID_PATH_SEGMENT.

        """

        api_path = SHEET_TO_API_PATH.get(sheet_name, "")

        lookup_id = (
            normalize_demographic_id(id_value) if sheet_name == "demographic" else id_value
        )

        url = self._get_by_id_url(sheet_name, lookup_id)

        headers = self._get_headers()



        self._log_request(

            operation="exists",

            sheet_name=sheet_name,

            method="GET",

            url=url,

            api_path=api_path,

            headers=headers,

            id_field=id_field,

            id_value=id_value,

        )



        started = time.time()

        try:

            response = self.session.get(url, headers=headers, timeout=10)

            elapsed_ms = int((time.time() - started) * 1000)

            self._log_response(

                operation="exists",

                sheet_name=sheet_name,

                method="GET",

                url=url,

                status_code=response.status_code,

                response_body=response.text,

                elapsed_ms=elapsed_ms,

            )

            if response.status_code == 200:

                return True

            if response.status_code == 404:

                return False

            response.raise_for_status()

        except requests.exceptions.RequestException as exc:

            elapsed_ms = int((time.time() - started) * 1000)

            _api_debug_log(

                "api_error",

                {

                    "operation": "exists",

                    "sheet_name": sheet_name,

                    "method": "GET",

                    "url": url,

                    "elapsed_ms": elapsed_ms,

                    "error": str(exc),

                },

            )

            logger.error("Error checking exists for %s (%s): %s", sheet_name, id_value, exc)

            return False



        return False



    def upsert(

        self,

        sheet_name: str,

        id_field: str,

        document: Dict,

    ) -> Dict:

        """

        Upsert a document via API Gateway.

        Expects downstream APIs to handle POST or PUT appropriately.

        """

        if id_field not in document:

            raise ValueError(

                f"Document missing id field {id_field!r} for sheet {sheet_name!r}"

            )



        api_path = SHEET_TO_API_PATH.get(sheet_name, "")

        endpoint = self._get_endpoint(sheet_name)

        id_value = document[id_field]

        url = endpoint



        document_payload = {**document}

        try:

            headers = self._get_headers()

            self._log_request(

                operation="upsert",

                sheet_name=sheet_name,

                method="POST",

                url=url,

                api_path=api_path,

                headers=headers,

                body=document_payload,

                id_field=id_field,

                id_value=id_value,

            )



            started = time.time()

            response = self.session.post(

                url,

                headers=headers,

                json=document_payload,

                timeout=15,

            )

            elapsed_ms = int((time.time() - started) * 1000)

            self._log_response(

                operation="upsert",

                sheet_name=sheet_name,

                method="POST",

                url=url,

                status_code=response.status_code,

                response_body=response.text,

                elapsed_ms=elapsed_ms,

            )



            if response.status_code == 405:

                url = self._put_by_id_url(sheet_name, id_value)

                self._log_request(

                    operation="upsert",

                    sheet_name=sheet_name,

                    method="PUT",

                    url=url,

                    api_path=api_path,

                    headers=headers,

                    body=document_payload,

                    id_field=id_field,

                    id_value=id_value,

                )

                started = time.time()

                response = self.session.put(

                    url,

                    headers=headers,

                    json=document_payload,

                    timeout=15,

                )

                elapsed_ms = int((time.time() - started) * 1000)

                self._log_response(

                    operation="upsert",

                    sheet_name=sheet_name,

                    method="PUT",

                    url=url,

                    status_code=response.status_code,

                    response_body=response.text,

                    elapsed_ms=elapsed_ms,

                )



            response.raise_for_status()



            upserted_id = _extract_upserted_id(sheet_name, id_field, id_value, response)

            return {

                "matched": 1,

                "modified": 1,

                "upserted_id": upserted_id,

                "api_status_code": response.status_code,

            }



        except requests.exceptions.HTTPError as exc:

            _api_debug_log(

                "api_error",

                {

                    "operation": "upsert",

                    "sheet_name": sheet_name,

                    "url": url,

                    "status_code": exc.response.status_code if exc.response is not None else None,

                    "response_body": (exc.response.text[:4000] if exc.response is not None else ""),

                    "request_body": document_payload,

                },

            )

            response_body = exc.response.text if exc.response is not None else ""

            if _is_already_present_message(response_body):

                raise AlreadyPresentError(sheet_name, id_value, response_body) from exc

            raise ValueError(

                f"API HTTP Error while writing to {sheet_name}: {response_body}"

            ) from exc

        except requests.exceptions.RequestException as exc:

            _api_debug_log(

                "api_error",

                {

                    "operation": "upsert",

                    "sheet_name": sheet_name,

                    "url": url,

                    "error": str(exc),

                    "request_body": document_payload,

                },

            )

            raise ValueError(f"API connection error while writing to {sheet_name}: {exc}") from exc



    def close(self) -> None:
        self.session.close()
        self._auth_session.close()


