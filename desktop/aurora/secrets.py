"""Credential storage: Windows Credential Manager via `keyring`.
If no keyring backend exists the secret is kept in the local database as a fallback (logged)."""
import logging
log = logging.getLogger(__name__)
SERVICE = "91 TV"

try:
    import keyring
    from keyring.errors import KeyringError, NoKeyringError
    _backend_name = type(keyring.get_keyring()).__name__
    _ok = "fail" not in _backend_name.lower() and "null" not in _backend_name.lower()
except Exception as e:  # pragma: no cover
    log.warning("keyring unavailable: %s", e); keyring = None; _ok = False; _backend_name = "none"


def _disable(e):
    global _ok
    if "NoKeyring" in type(e).__name__ or "No recommended" in str(e):
        _ok = False


def available() -> bool:
    return _ok


def backend() -> str:
    return _backend_name


def set_secret(name: str, value: str) -> bool:
    if not _ok:
        return False
    try:
        keyring.set_password(SERVICE, name, value); return True
    except Exception as e:
        log.warning("keyring write failed (using local fallback): %s", type(e).__name__); _disable(e); return False


def get_secret(name: str):
    if not _ok:
        return None
    try:
        return keyring.get_password(SERVICE, name)
    except Exception as e:
        _disable(e); return None


def delete_secret(name: str):
    if _ok:
        try:
            keyring.delete_password(SERVICE, name)
        except Exception:
            pass
