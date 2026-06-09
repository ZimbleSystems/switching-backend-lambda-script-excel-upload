"""
Thin API Gateway client with dependency-aware lookups and AWS Cognito auth.
Replaces the old MongoWriter for direct DB access.
"""
from __future__ import annotations

import os
import time
import requests
import logging
from typing import Dict, Optional, Any

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

class ApiGatewayClient:
    def __init__(
        self,
        api_gateway_url: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ):
        self.api_gateway_url = (api_gateway_url or os.environ.get("API_GATEWAY_URL", "")).rstrip("/")
        self.tenant_id = tenant_id or os.environ.get("TENANT_ID", "default-tenant")
        
        # Cognito Configuration
        self.client_id = os.environ.get("COGNITO_CLIENT_ID", "")
        self.client_secret = os.environ.get("COGNITO_CLIENT_SECRET", "")
        self.token_url = os.environ.get("COGNITO_TOKEN_URL", "")
        
        self.session = requests.Session()
        self._access_token = None
        self._token_expires_at = 0

    def _get_token(self) -> str:
        """Fetch or refresh the OAuth2 JWT from Cognito using client credentials."""
        if not self.token_url or not self.client_id or not self.client_secret:
            logger.warning("Cognito credentials missing. Bypassing token fetch (local dev).")
            return "dummy-token"

        now = time.time()
        if self._access_token and now < self._token_expires_at:
            return self._access_token

        logger.info("Fetching new JWT token from Cognito...")
        auth = (self.client_id, self.client_secret)
        data = {"grant_type": "client_credentials"}
        
        response = self.session.post(self.token_url, auth=auth, data=data, timeout=10)
        response.raise_for_status()
        
        token_data = response.json()
        self._access_token = token_data.get("access_token")
        # Refresh 1 minute before actual expiration
        self._token_expires_at = now + token_data.get("expires_in", 3600) - 60
        
        return self._access_token

    def _get_headers(self) -> Dict[str, str]:
        token = self._get_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            # Passing tenant_id as a claim/header might be required depending on setup
            "X-Tenant-Id": self.tenant_id,
        }

    def _get_endpoint(self, sheet_name: str) -> str:
        path = SHEET_TO_API_PATH.get(sheet_name)
        if not path:
            raise ValueError(f"Unknown API path mapping for sheet {sheet_name!r}")
        return f"{self.api_gateway_url}{path}"

    def exists(self, sheet_name: str, id_field: str, id_value: str) -> bool:
        """
        Check if a record exists.
        Expects downstream APIs to support `GET /v1/{id}`.
        """
        endpoint = self._get_endpoint(sheet_name)
        url = f"{endpoint}{id_value}"
        
        try:
            response = self.session.get(url, headers=self._get_headers(), timeout=10)
            if response.status_code == 200:
                return True
            if response.status_code == 404:
                return False
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            logger.error(f"Error checking exists for {sheet_name} ({id_value}): {exc}")
            # If the backend is unreachable or doesn't support GET, default to False or raise
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
            
        endpoint = self._get_endpoint(sheet_name)
        id_value = document[id_field]
        
        # We will default to a POST request to the base endpoint or PUT to the ID endpoint
        # The specific HTTP method can be tailored to the exact microservice contract.
        url = endpoint  # Assuming POST to base creates/upserts
        
        try:
            # Added tenant_id to document body if required by downstream
            document_payload = {**document}
            if "tenantId" not in document_payload:
                document_payload["tenantId"] = self.tenant_id

            response = self.session.post(
                url, 
                headers=self._get_headers(), 
                json=document_payload, 
                timeout=15
            )
            
            # If the service returns 405 Method Not Allowed, it might require a PUT /id instead.
            if response.status_code == 405:
                url = f"{endpoint}{id_value}"
                response = self.session.put(
                    url,
                    headers=self._get_headers(),
                    json=document_payload,
                    timeout=15
                )

            response.raise_for_status()
            
            # Simulated Mongo upsert response to keep orchestrator compatible
            return {
                "matched": 1,
                "modified": 1,
                "upserted_id": str(id_value),
                "api_status_code": response.status_code
            }
            
        except requests.exceptions.HTTPError as exc:
            raise ValueError(f"API HTTP Error while writing to {sheet_name}: {exc.response.text}") from exc
        except requests.exceptions.RequestException as exc:
            raise ValueError(f"API connection error while writing to {sheet_name}: {exc}") from exc

    def close(self) -> None:
        self.session.close()
