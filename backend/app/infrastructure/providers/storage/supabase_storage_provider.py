from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote

import httpx

from app.core.exceptions import ApplicationError
from app.knowledge_engine.contracts.storage import StorageContract


@dataclass(slots=True)
class SupabaseStorageProvider(StorageContract):
    settings: object

    def _normalize_path(
        self,
        path: str | None,
    ) -> str:
        if path is None:
            raise ApplicationError(
                message="Storage path is required.",
                code="storage_path_required",
                status_code=422,
            )

        normalized_path = path.strip().lstrip("/")

        if not normalized_path:
            raise ApplicationError(
                message="Storage path is required.",
                code="storage_path_required",
                status_code=422,
            )

        if normalized_path.lower() in {"null", "none"}:
            raise ApplicationError(
                message="Storage path is invalid.",
                code="storage_path_invalid",
                status_code=422,
            )

        return normalized_path

    def _object_url(
        self,
        storage_path: str,
    ) -> str:
        normalized_path = self._normalize_path(
            storage_path,
        )

        encoded_path = quote(
            normalized_path,
            safe="/",
        )

        return (
            f"{self.settings.supabase_url.rstrip('/')}"
            f"/storage/v1/object/"
            f"{self.settings.supabase_bucket_name}/"
            f"{encoded_path}"
        )

    def _headers(
        self,
        content_type: str | None = None,
        *,
        upsert: bool = False,
    ) -> dict[str, str]:
        headers = {
            "apikey": (
                self.settings.supabase_service_role_key
            ),
            "Authorization": (
                "Bearer "
                f"{self.settings.supabase_service_role_key}"
            ),
        }

        if content_type:
            headers["Content-Type"] = content_type

        headers["x-upsert"] = (
            "true" if upsert else "false"
        )

        return headers

    def upload(
        self,
        *,
        path: str,
        content: bytes,
        content_type: str | None,
    ) -> str:
        normalized_path = self._normalize_path(path)

        url = self._object_url(
            normalized_path,
        )

        headers = self._headers(
            content_type or "application/octet-stream",
            upsert=False,
        )

        try:
            response = httpx.post(
                url,
                headers=headers,
                content=content,
                timeout=(
                    self.settings.provider_timeout_seconds
                ),
            )
            response.raise_for_status()

        except httpx.HTTPStatusError as exc:
            raise ApplicationError(
                message=(
                    "File upload failed with status "
                    f"{exc.response.status_code}."
                ),
                code="storage_upload_failed",
                status_code=502,
            ) from exc

        except httpx.HTTPError as exc:
            raise ApplicationError(
                message="File upload failed.",
                code="storage_upload_failed",
                status_code=502,
            ) from exc

        # This is important. The uploaded object path must
        # be returned to the application service.
        return normalized_path

    def upload_bytes(
        self,
        storage_path: str,
        content_bytes: bytes,
    ) -> str:
        return self.upload(
            path=storage_path,
            content=content_bytes,
            content_type="application/octet-stream",
        )

    def download_bytes(
        self,
        source_path: str,
    ) -> bytes:
        normalized_path = self._normalize_path(
            source_path,
        )

        url = self._object_url(
            normalized_path,
        )

        headers = self._headers()

        try:
            response = httpx.get(
                url,
                headers=headers,
                timeout=(
                    self.settings.provider_timeout_seconds
                ),
            )
            response.raise_for_status()

        except httpx.HTTPStatusError as exc:
            raise ApplicationError(
                message=(
                    "Storage download failed with status "
                    f"{exc.response.status_code}."
                ),
                code="storage_download_failed",
                status_code=502,
            ) from exc

        except httpx.HTTPError as exc:
            raise ApplicationError(
                message="Storage download failed.",
                code="storage_download_failed",
                status_code=502,
            ) from exc

        return response.content

    def delete(self, storage_path: str) -> None:
        normalized_path = self._normalize_path(storage_path)
        try:
            response = httpx.delete(
                self._object_url(normalized_path),
                headers=self._headers(),
                timeout=self.settings.provider_timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return
            raise ApplicationError(
                message="Uploaded file cleanup failed.",
                code="storage_delete_failed",
                status_code=502,
            ) from exc
        except httpx.HTTPError as exc:
            raise ApplicationError(
                message="Uploaded file cleanup failed.",
                code="storage_delete_failed",
                status_code=502,
            ) from exc

    def download_text(
        self,
        storage_path: str,
    ) -> str:
        content = self.download_bytes(
            storage_path,
        )

        try:
            return content.decode("utf-8")

        except UnicodeDecodeError as exc:
            raise ApplicationError(
                message="Stored file is not valid UTF-8 text.",
                code="storage_text_decode_failed",
                status_code=422,
            ) from exc