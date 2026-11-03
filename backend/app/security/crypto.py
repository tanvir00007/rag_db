from pathlib import Path

from cryptography.fernet import Fernet

from app.core.settings import settings


def _key_path() -> Path:
    settings.configs_dir.mkdir(parents=True, exist_ok=True)
    return settings.configs_dir / ".local_secret.key"


def _fernet() -> Fernet:
    path = _key_path()
    if not path.exists():
        path.write_bytes(Fernet.generate_key())
    return Fernet(path.read_bytes())


def encrypt_text(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_text(value: str) -> str:
    return _fernet().decrypt(value.encode("utf-8")).decode("utf-8")

