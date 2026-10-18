"""PIN-Hash: HMAC-SHA256(pin_key, PIN), erste 32 Hex-Zeichen. Der Atom rechnet identisch (esphome/adnet_access.h),
damit die PIN nie im Klartext übertragen oder gespeichert wird."""
import hashlib
import hmac
import secrets


def pin_hash(key: str, pin: str) -> str:
    return hmac.new(key.encode(), pin.encode(), hashlib.sha256).hexdigest()[:32]


def new_token() -> str:
    return secrets.token_urlsafe(24)
