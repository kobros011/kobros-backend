import os
from typing import Any, Optional

import httpx


class ClerkApiError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class ClerkClient:
    BASE_URL = "https://api.clerk.com/v1"

    def __init__(self, secret_key: Optional[str] = None):
        self._secret_key = secret_key or os.getenv("CLERK_SECRET_KEY", "")

    @property
    def configured(self) -> bool:
        return bool(self._secret_key)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._secret_key}"}

    def _parse_error(self, resp: httpx.Response) -> str:
        try:
            data = resp.json()
            errors = data.get("errors") or []
            if errors:
                return errors[0].get("long_message") or errors[0].get("message") or resp.text
        except Exception:
            pass
        return resp.text or "Error desconocido en Clerk"

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Optional[dict] = None,
        expected: tuple[int, ...] = (200, 201),
    ) -> dict[str, Any]:
        if not self.configured:
            raise ClerkApiError("CLERK_SECRET_KEY no configurada", 500)

        url = f"{self.BASE_URL}{path}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.request(method, url, headers=self._headers(), json=json)

        if resp.status_code not in expected:
            raise ClerkApiError(self._parse_error(resp), resp.status_code)

        if resp.status_code == 204 or not resp.content:
            return {}
        return resp.json()

    async def create_user(
        self,
        *,
        username: str,
        password: str,
        full_name: str,
        type_user_code: str,
        email: Optional[str] = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "username": username,
            "password": password,
            "first_name": full_name,
            "public_metadata": {"type_user": type_user_code},
            "skip_password_checks": False,
        }
        if email:
            body["email_address"] = [email]

        return await self._request("POST", "/users", json=body, expected=(200, 201))

    async def update_user(
        self,
        clerk_user_id: str,
        *,
        username: Optional[str] = None,
        password: Optional[str] = None,
        type_user_code: Optional[str] = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {}
        if username is not None:
            body["username"] = username
        if password is not None:
            body["password"] = password
        if type_user_code is not None:
            body["public_metadata"] = {"type_user": type_user_code}
        if not body:
            return {}
        return await self._request("PATCH", f"/users/{clerk_user_id}", json=body)

    async def get_user(self, clerk_user_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/users/{clerk_user_id}")

    async def find_user_by_username(self, username: str) -> Optional[dict[str, Any]]:
        data = await self._request("GET", f"/users?username={username}&limit=1")
        if isinstance(data, list):
            users = data
        elif isinstance(data, dict):
            users = data.get("data") or data.get("users") or []
        else:
            users = []
        return users[0] if users else None

    async def delete_user(self, clerk_user_id: str) -> None:
        await self._request("DELETE", f"/users/{clerk_user_id}", expected=(200, 204))

    async def ban_user(self, clerk_user_id: str) -> None:
        await self._request("POST", f"/users/{clerk_user_id}/ban", expected=(200, 201))

    async def unban_user(self, clerk_user_id: str) -> None:
        await self._request("POST", f"/users/{clerk_user_id}/unban", expected=(200, 201))

    async def send_password_reset_email(self, clerk_user_id: str) -> None:
        await self._request(
            "POST",
            f"/users/{clerk_user_id}/send_reset_password_email",
            expected=(200, 201),
        )

    async def sync_email(self, clerk_user_id: str, email: Optional[str]) -> None:
        """Alinea el correo en Clerk con el valor de Kobros (None = sin correo)."""
        user_data = await self.get_user(clerk_user_id)
        existing = user_data.get("email_addresses") or []

        target = email.strip().lower() if email else None
        current_primary = None
        for entry in existing:
            if entry.get("id") and entry.get("email_address"):
                addr = entry["email_address"].lower()
                if entry.get("primary") or not current_primary:
                    current_primary = addr

        if target and current_primary == target:
            return

        for entry in existing:
            email_id = entry.get("id")
            if email_id:
                await self._request(
                    "DELETE",
                    f"/email_addresses/{email_id}",
                    expected=(200, 204),
                )

        if target:
            await self._request(
                "POST",
                "/email_addresses",
                json={
                    "user_id": clerk_user_id,
                    "email_address": target,
                    "verified": True,
                    "primary": True,
                },
                expected=(200, 201),
            )
