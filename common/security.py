import hashlib
import bcrypt


def hash_password(password: str) -> str:
    sha = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return bcrypt.hashpw(sha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    sha = hashlib.sha256(plain_password.encode("utf-8")).hexdigest()
    return bcrypt.checkpw(sha.encode("utf-8"), hashed_password.encode("utf-8"))
