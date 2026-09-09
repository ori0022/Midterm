import hashlib
try:
    import bcrypt
except ImportError:
    bcrypt = None

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
