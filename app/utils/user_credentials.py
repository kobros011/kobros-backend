import re
from typing import Optional

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Alineado con Clerk: letras, números, guión, guión bajo; punto solo si está permitido en el dashboard
USERNAME_RE = re.compile(r"^[a-zA-Z0-9._-]{4,64}$")


def normalize_email(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    return trimmed.lower()


def validate_username(username: str) -> Optional[str]:
    if not username or len(username) < 4 or len(username) > 64:
        return "El usuario debe tener entre 4 y 64 caracteres"
    if not USERNAME_RE.match(username):
        return "Use solo letras, números, punto (.), guión (-) y guión bajo (_)"
    return None


def validate_password(password: str) -> Optional[str]:
    if not password or len(password) < 8:
        return "La contraseña debe tener al menos 8 caracteres"
    return None


def validate_email_optional(email: Optional[str]) -> Optional[str]:
    normalized = normalize_email(email)
    if normalized is None:
        return None
    if not EMAIL_RE.match(normalized):
        return "El correo no tiene un formato válido"
    return None


def clerk_username(username: str) -> str:
    """Clerk no acepta '.' en username; Kobros sí. Misma regla que sync_users_to_clerk."""
    return username.replace(".", "_")
