import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.core.exceptions import AppException

SAS_TTL = timedelta(hours=1)


class StorageNotConfigured(AppException):
    def __init__(self):
        super().__init__("El almacenamiento de archivos (Azure) no está configurado", status_code=503)


class StorageMisconfigured(AppException):
    def __init__(self):
        super().__init__(
            "AZURE_STORAGE_CONNECTION_STRING no tiene el formato correcto "
            "(debe incluir AccountName= y AccountKey=, no solo la clave). "
            "Copia la 'Cadena de conexión' completa desde Azure Portal → Claves de acceso, "
            "o usa AZURE_STORAGE_ACCOUNT_NAME + AZURE_STORAGE_ACCOUNT_KEY por separado.",
            status_code=503,
        )


class AzureBlobStorage:
    """Acceso mínimo a un contenedor privado de Azure Blob Storage.

    Credenciales por variables de entorno:
      AZURE_STORAGE_CONNECTION_STRING  (o AZURE_STORAGE_ACCOUNT_NAME + AZURE_STORAGE_ACCOUNT_KEY)
      AZURE_STORAGE_CONTAINER
    """

    def __init__(self):
        self.container = os.getenv("AZURE_STORAGE_CONTAINER", "").strip()
        self.connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "").strip()
        self.account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME", "").strip()
        self.account_key = os.getenv("AZURE_STORAGE_ACCOUNT_KEY", "").strip()

    @property
    def is_configured(self) -> bool:
        has_credentials = bool(self.connection_string) or bool(self.account_name and self.account_key)
        return bool(self.container) and has_credentials

    def _credentials(self) -> tuple[Optional[str], Optional[str]]:
        """(account_name, account_key); (None, None) si la cadena de conexión no trae ambos valores."""
        if self.connection_string:
            # Parseo manual en vez de BlobServiceClient.from_connection_string: ese método lanza un
            # KeyError sin controlar (500) si falta AccountName/AccountKey — aquí devolvemos None y
            # dejamos que el llamador levante un error claro (ver StorageMisconfigured).
            parts = dict(p.split("=", 1) for p in self.connection_string.split(";") if "=" in p)
            return parts.get("AccountName"), parts.get("AccountKey")
        return self.account_name or None, self.account_key or None

    def _service_client(self):
        from azure.storage.blob.aio import BlobServiceClient

        account_name, account_key = self._credentials()
        if not account_name or not account_key:
            raise StorageMisconfigured()
        return BlobServiceClient(
            account_url=f"https://{account_name}.blob.core.windows.net",
            credential=account_key,
        )

    async def upload(self, blob_name: str, data: bytes, content_type: str) -> None:
        if not self.is_configured:
            raise StorageNotConfigured()
        from azure.storage.blob import ContentSettings

        async with self._service_client() as service:
            blob = service.get_blob_client(container=self.container, blob=blob_name)
            await blob.upload_blob(
                data,
                overwrite=True,
                content_settings=ContentSettings(
                    content_type=content_type,
                    cache_control="private, max-age=3600",
                ),
            )

    async def delete(self, blob_name: str) -> None:
        """Borra el blob; ignora errores (limpieza best effort)."""
        if not self.is_configured or not blob_name:
            return
        try:
            async with self._service_client() as service:
                blob = service.get_blob_client(container=self.container, blob=blob_name)
                await blob.delete_blob()
        except Exception:
            pass

    def url_for(self, blob_name: Optional[str]) -> Optional[str]:
        """URL de lectura firmada (SAS) de corta vida; None si no hay blob o no hay configuración."""
        if not blob_name or not self.is_configured:
            return None
        from azure.storage.blob import BlobSasPermissions, generate_blob_sas

        account_name, account_key = self._credentials()
        if not account_name or not account_key:
            return None
        token = generate_blob_sas(
            account_name=account_name,
            container_name=self.container,
            blob_name=blob_name,
            account_key=account_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.now(timezone.utc) + SAS_TTL,
        )
        return f"https://{account_name}.blob.core.windows.net/{self.container}/{blob_name}?{token}"


def get_storage() -> AzureBlobStorage:
    return AzureBlobStorage()
