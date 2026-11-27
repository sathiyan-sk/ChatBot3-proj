from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.parse import quote

import httpx

from app.config.settings import StorageSettings
from app.core.exceptions import ApplicationError
from app.knowledge_engine.contracts.storage import StorageContract

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SupabaseStorageProvider(StorageContract):
    settings: StorageSettings

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

    def _object_list_url(self) -> str:
        bucket_name = quote(
            self.settings.supabase_bucket_name,
            safe="",
        )
        return (
            f"{self.settings.supabase_url.rstrip('/')}"
            f"/storage/v1/object/list/{bucket_name}"
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
        storage_path: str,
    ) -> bytes:
        normalized_path = self._normalize_path(
            storage_path,
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
        self._delete_paths([normalized_path])

    def list_prefix(self, prefix: str) -> list[str]:
        normalized_prefix = self._normalize_path(prefix).rstrip("/")
        pending_prefixes = [normalized_prefix]
        visited_prefixes: set[str] = set()
        object_paths: set[str] = set()

        while pending_prefixes:
            current_prefix = pending_prefixes.pop()
            if current_prefix in visited_prefixes:
                continue
            visited_prefixes.add(current_prefix)

            offset = 0
            while True:
                try:
                    response = httpx.post(
                        self._object_list_url(),
                        headers=self._headers("application/json"),
                        json={
                            "prefix": current_prefix,
                            "limit": 1000,
                            "offset": offset,
                        },
                        timeout=self.settings.provider_timeout_seconds,
                    )
                    response.raise_for_status()
                    try:
                        entries = response.json()
                    except ValueError as exc:
                        raise ApplicationError(
                            message="Storage returned an invalid object listing.",
                            code="storage_list_invalid",
                            status_code=502,
                        ) from exc
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code == 404:
                        entries = []
                    else:
                        raise ApplicationError(
                            message="Stored files could not be enumerated for deletion.",
                            code="storage_list_failed",
                            status_code=502,
                            details={
                                "upstream_status": exc.response.status_code,
                            },
                        ) from exc
                except httpx.HTTPError as exc:
                    raise ApplicationError(
                        message="Stored files could not be enumerated for deletion.",
                        code="storage_list_failed",
                        status_code=502,
                    ) from exc

                if not isinstance(entries, list):
                    raise ApplicationError(
                        message="Storage returned an invalid object listing.",
                        code="storage_list_invalid",
                        status_code=502,
                    )

                for entry in entries:
                    name = entry.get("name") if isinstance(entry, dict) else None
                    if (
                        not isinstance(name, str)
                        or not name
                        or name in {".", ".."}
                        or "/" in name
                        or "\\" in name
                    ):
                        raise ApplicationError(
                            message="Storage returned an invalid object path.",
                            code="storage_list_invalid",
                            status_code=502,
                        )

                    object_path = f"{current_prefix}/{name}"
                    if entry.get("id") is None:
                        pending_prefixes.append(object_path)
                    else:
                        object_paths.add(object_path)

                if len(entries) < 1000:
                    break
                offset += len(entries)

        return sorted(object_paths)

    def delete_prefix(self, prefix: str) -> int:
        paths = self.list_prefix(prefix)
        for start in range(0, len(paths), 100):
            self._delete_paths(paths[start : start + 100])
        return len(paths)

    def _delete_paths(self, storage_paths: list[str]) -> None:
        if not storage_paths:
            return
        try:
            response = httpx.request(
                "DELETE",
                (
                    f"{self.settings.supabase_url.rstrip('/')}"
                    f"/storage/v1/object/"
                    f"{self.settings.supabase_bucket_name}"
                ),
                headers=self._headers(),
                json={"prefixes": storage_paths},
                timeout=self.settings.provider_timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return
            logger.warning(
                "Supabase Storage object deletion failed",
                extra={
                    "upstream_status": exc.response.status_code,
                    "storage_paths": storage_paths,
                },
            )
            raise ApplicationError(
                message="Uploaded file cleanup failed.",
                code="storage_delete_failed",
                status_code=502,
                details={
                    "upstream_status": exc.response.status_code,
                    "object_count": len(storage_paths),
                },
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