import os
import re
import time
import json
import base64
import hmac
import hashlib
from typing import Optional, Dict, Any

try:
    import bcrypt
except ImportError:
    bcrypt = None

JWT_SECRET = os.getenv("JWT_SECRET") or os.getenv("BANK_API_KEY") or "haovdim_bank_jwt_secret_signing_key_secure_2026"

def hash_password(password: str) -> str:
    """
    Hash a password using salted bcrypt.
    Raises RuntimeError if bcrypt is not installed to prevent insecure silent downgrade to SHA-256.
    """
    if bcrypt is None:
        raise RuntimeError(
            "bcrypt is required for password hashing but is not installed. "
            "Insecure fallback to unsalted SHA-256 is disabled for security."
        )
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against a stored hash.
    Supports bcrypt ($2b$, $2a$, $2y$) and legacy unsalted SHA-256.
    """
    if not hashed_password or not plain_password:
        return False

    # Check for bcrypt format
    if hashed_password.startswith("$2b$") or hashed_password.startswith("$2a$") or hashed_password.startswith("$2y$"):
        if bcrypt is not None:
            try:
                return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
            except Exception:
                return False
        return False

    # Fallback to legacy SHA-256
    legacy_hash = hashlib.sha256(plain_password.encode("utf-8")).hexdigest()
    return legacy_hash == hashed_password

def validate_israeli_id(id_number: str) -> bool:
    """
    Validates an Israeli National ID (Teudat Zehut) using the official
    Luhn Modulo 10 check digit algorithm.
    Accepts numbers with optional hyphens or spaces, up to 9 digits (padded with leading zeros).
    """
    if not id_number:
        return False
    clean = re.sub(r'\D', '', str(id_number).strip())
    if not clean or len(clean) > 9 or int(clean) == 0:
        return False
    clean = clean.zfill(9)
    total = 0
    for i, char in enumerate(clean):
        val = int(char) * ((i % 2) + 1)
        total += val if val < 10 else (val - 9)
    return total % 10 == 0

def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('utf-8')

def _base64url_decode(data_str: str) -> bytes:
    rem = len(data_str) % 4
    if rem > 0:
        data_str += '=' * (4 - rem)
    return base64.urlsafe_b64decode(data_str.encode('utf-8'))

def create_access_token(data: Dict[str, Any], expires_delta: Optional[int] = 3600, secret: Optional[str] = None) -> str:
    """
    Generate a signed HS256 JWT access token.
    data typically contains {"sub": customer_id, "role": "customer"}.
    """
    key = (secret or JWT_SECRET).encode('utf-8')
    header = {"alg": "HS256", "typ": "JWT"}
    payload = dict(data)
    now = int(time.time())
    payload["iat"] = now
    if expires_delta:
        payload["exp"] = now + expires_delta
    
    header_b64 = _base64url_encode(json.dumps(header, separators=(',', ':')).encode('utf-8'))
    payload_b64 = _base64url_encode(json.dumps(payload, separators=(',', ':')).encode('utf-8'))
    signing_input = f"{header_b64}.{payload_b64}".encode('utf-8')
    sig = hmac.new(key, signing_input, hashlib.sha256).digest()
    sig_b64 = _base64url_encode(sig)
    return f"{header_b64}.{payload_b64}.{sig_b64}"

def verify_access_token(token: str, secret: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Verify a signed HS256 JWT access token.
    Returns the decoded payload dict if valid and not expired, else None.
    """
    if not token or not isinstance(token, str):
        return None
    parts = token.split('.')
    if len(parts) != 3:
        return None
    header_b64, payload_b64, sig_b64 = parts
    key = (secret or JWT_SECRET).encode('utf-8')
    signing_input = f"{header_b64}.{payload_b64}".encode('utf-8')
    expected_sig = hmac.new(key, signing_input, hashlib.sha256).digest()
    try:
        actual_sig = _base64url_decode(sig_b64)
        if not hmac.compare_digest(actual_sig, expected_sig):
            return None
        payload_bytes = _base64url_decode(payload_b64)
        payload = json.loads(payload_bytes.decode('utf-8'))
        exp = payload.get("exp")
        if exp and int(time.time()) > int(exp):
            return None
        return payload
    except Exception:
        return None
