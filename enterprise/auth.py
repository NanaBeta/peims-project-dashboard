"""OIDC JWT verification: access tokens only, validated issuer/audience/signature.
No demo bypass or hardcoded credentials are available in the deployed API.
"""
from dataclasses import dataclass
from functools import lru_cache
import os
from urllib.parse import urlparse
import jwt
from jwt import PyJWKClient
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

@dataclass(frozen=True)
class Identity:
    sub: str

bearer = HTTPBearer(auto_error=False)

@lru_cache(maxsize=4)
def jwks_client(url: str):
    return PyJWKClient(url, cache_jwk_set=True, lifespan=300, timeout=4)


def verify_access_token(token: str) -> Identity:
    issuer = os.environ.get('PEIMS_OIDC_ISSUER','').strip()
    audience = os.environ.get('PEIMS_OIDC_AUDIENCE','').strip()
    url = os.environ.get('PEIMS_OIDC_JWKS_URL','').strip()
    if not (issuer and audience and url and urlparse(url).scheme == 'https' and urlparse(url).hostname):
        raise HTTPException(status_code=503, detail='OIDC verification is not configured')
    try:
        key = jwks_client(url).get_signing_key_from_jwt(token).key
        claims = jwt.decode(token, key=key, algorithms=['RS256'], audience=audience,
                            issuer=issuer, leeway=30,
                            options={'require':['sub','iss','aud','exp','iat']})
        subject = claims.get('sub')
        if not isinstance(subject, str) or not subject or len(subject) > 255:
            raise jwt.InvalidTokenError('Invalid subject')
        return Identity(sub=subject)
    except Exception as ex:
        # No JWT, key material or provider response is ever returned to the caller.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail='Invalid or expired bearer token',
                            headers={'WWW-Authenticate':'Bearer'}) from ex


def get_identity(auth: HTTPAuthorizationCredentials | None = Depends(bearer)) -> Identity:
    if auth is None or auth.scheme.lower() != 'bearer':
        raise HTTPException(status_code=401, detail='Bearer access token required',
                            headers={'WWW-Authenticate':'Bearer'})
    return verify_access_token(auth.credentials)
