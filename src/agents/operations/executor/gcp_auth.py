"""
GCP Authentication module.

Provides Workload Identity Federation (AWS OIDC -> GCP Service Account)
and Service Account JSON Key fallback.
"""

from __future__ import annotations

import base64
import json
import os
import urllib.parse
from typing import Any

import boto3
import requests
import structlog
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

logger = structlog.get_logger(__name__)


def get_gcp_access_token() -> str:
    """
    Get a GCP access token.
    1. Try GCP Workload Identity Federation (WIF) if env variables are configured.
    2. Try Service Account Key JSON from GCP_SERVICE_ACCOUNT_KEY env var or AWS Secrets Manager.
    3. Try google-auth library default credentials if installed.
    """
    # 1. Try Workload Identity Federation (OIDC)
    project_number = os.getenv("GCP_PROJECT_NUMBER")
    pool_id = os.getenv("GCP_WORKLOAD_POOL_ID", "aws-pool")
    provider_id = os.getenv("GCP_WORKLOAD_PROVIDER_ID", "aws-provider")
    sa_email = os.getenv("GCP_SERVICE_ACCOUNT_EMAIL")

    if project_number and sa_email:
        try:
            logger.info("gcp_auth.try_wif", sa_email=sa_email)
            return _get_token_via_wif(project_number, pool_id, provider_id, sa_email)
        except Exception as e:
            logger.error("gcp_auth.wif_failed", error=str(e))

    # 2. Try Service Account Key JSON
    sa_key_json = os.getenv("GCP_SERVICE_ACCOUNT_KEY")
    if not sa_key_json:
        # Check AWS Secrets Manager for GCP key
        secret_id = os.getenv("GCP_SECRET_ID")
        if secret_id:
            try:
                logger.info("gcp_auth.secrets_manager_lookup", secret_id=secret_id)
                client = boto3.client("secretsmanager", region_name=os.getenv("AWS_REGION", "us-east-1"))
                resp = client.get_secret_value(SecretId=secret_id)
                sa_key_json = resp.get("SecretString", "")
            except Exception as e:
                logger.error("gcp_auth.secrets_manager_failed", error=str(e))

    if sa_key_json:
        try:
            logger.info("gcp_auth.try_sa_key")
            return _get_token_via_sa_key(sa_key_json)
        except Exception as e:
            logger.error("gcp_auth.sa_key_failed", error=str(e))

    # 3. Try google-auth default credentials (local/dev fallback)
    try:
        import google.auth
        import google.auth.transport.requests
        credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        request = google.auth.transport.requests.Request()
        credentials.refresh(request)
        if credentials.token:
            logger.info("gcp_auth.google_auth_default_success")
            return str(credentials.token)
    except ImportError:
        pass
    except Exception as e:
        logger.error("gcp_auth.google_auth_default_failed", error=str(e))

    raise RuntimeError("No valid GCP authentication method available")


def _get_token_via_wif(project_number: str, pool_id: str, provider_id: str, sa_email: str) -> str:
    """
    Exchange AWS OIDC / STS credentials for GCP Service Account access token.
    Ref: https://cloud.google.com/iam/docs/workload-identity-federation
    """
    # Create AWS STS GetCallerIdentity assertion
    assertion = _get_aws_sts_assertion()

    # Step 1: Exchange AWS STS assertion for GCP federated token
    audience = f"//iam.googleapis.com/projects/{project_number}/locations/global/workloadIdentityPools/{pool_id}/providers/{provider_id}"
    
    sts_url = "https://sts.googleapis.com/v1/token"
    sts_payload = {
        "audience": audience,
        "grantType": "urn:ietf:params:oauth:grant-type:token-exchange",
        "requestedTokenType": "urn:ietf:params:oauth:token-type:access_token",
        "subjectTokenType": "urn:ietf:params:oauth:token-type:aws-request",
        "subjectToken": assertion,
    }
    
    resp = requests.post(sts_url, json=sts_payload, timeout=10)
    if resp.status_code != 200:
        raise RuntimeError(f"GCP STS exchange failed (HTTP {resp.status_code}): {resp.text}")
    
    fed_token = resp.json()["access_token"]

    # Step 2: Exchange federated token for GCP Service Account access token
    iam_url = f"https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/{sa_email}:generateAccessToken"
    headers = {
        "Authorization": f"Bearer {fed_token}",
        "Content-Type": "application/json",
    }
    iam_payload = {
        "scope": ["https://www.googleapis.com/auth/cloud-platform"]
    }
    
    resp = requests.post(iam_url, json=iam_payload, headers=headers, timeout=10)
    if resp.status_code != 200:
        raise RuntimeError(f"GCP Service Account token generation failed (HTTP {resp.status_code}): {resp.text}")
        
    return str(resp.json()["accessToken"])


def _get_aws_sts_assertion() -> str:
    """Generate a signed AWS STS GetCallerIdentity request serialized as Base64 JSON."""
    session = boto3.Session()
    credentials = session.get_credentials()
    if not credentials:
        raise RuntimeError("No AWS credentials available for STS OIDC signing")
    frozen_creds = credentials.get_frozen_credentials()
    
    region = session.region_name or "us-east-1"
    url = "https://sts.amazonaws.com/?Action=GetCallerIdentity&Version=2011-06-15"
    
    request = AWSRequest(
        method="POST",
        url=url,
        headers={
            "Host": "sts.amazonaws.com",
            "Content-Type": "application/x-www-form-urlencoded"
        },
        data="Action=GetCallerIdentity&Version=2011-06-15"
    )
    
    SigV4Auth(frozen_creds, "sts", region).add_auth(request)
    
    # Structure matching GCP expectations for aws-request type
    serialized = {
        "url": request.url,
        "method": request.method,
        "headers": [{"key": k, "value": v} for k, v in request.headers.items()]
    }
    return base64.b64encode(json.dumps(serialized).encode("utf-8")).decode("utf-8")


def _get_token_via_sa_key(key_json_str: str) -> str:
    """Generate GCP Access token from Service Account key JSON file."""
    # Simple JWT token creator for GCP without external google-auth libs
    # Uses standard python hashlib & cryptography if available,
    # or fallbacks to google-auth if installed.
    try:
        from google.oauth2 import service_account
        import google.auth.transport.requests
        info = json.loads(key_json_str)
        credentials = service_account.Credentials.from_service_account_info(
            info, scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        request = google.auth.transport.requests.Request()
        credentials.refresh(request)
        return str(credentials.token)
    except ImportError:
        pass

    # Basic fallback: parsing key and calling oauth endpoint if library is missing
    # (For pure lambda bundle efficiency, google-auth might not be present)
    raise RuntimeError("google-auth package is required to sign service account keys")
