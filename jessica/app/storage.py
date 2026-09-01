"""Private file storage. 'supabase' for real deployments, 'local' for development."""
from pathlib import Path

import httpx

from app.config import settings


class Storage:
    def put(self, path: str, data: bytes, mime: str) -> None: ...
    def get(self, path: str) -> bytes: ...
    def delete(self, path: str) -> None: ...


class LocalStorage(Storage):
    def __init__(self, root: str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _p(self, path: str) -> Path:
        p = (self.root / path).resolve()
        if self.root.resolve() not in p.parents:
            raise ValueError("bad path")
        return p

    def put(self, path: str, data: bytes, mime: str) -> None:
        p = self._p(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def get(self, path: str) -> bytes:
        return self._p(path).read_bytes()

    def delete(self, path: str) -> None:
        p = self._p(path)
        if p.exists():
            p.unlink()


class SupabaseStorage(Storage):
    """Uses the Storage REST API with the service key. Bucket must be private."""

    def __init__(self):
        self.base = f"{settings.SUPABASE_URL}/storage/v1/object/{settings.STORAGE_BUCKET}"
        self.headers = {"Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}"}

    def put(self, path: str, data: bytes, mime: str) -> None:
        r = httpx.post(
            f"{self.base}/{path}",
            content=data,
            headers={**self.headers, "Content-Type": mime, "x-upsert": "true"},
            timeout=60,
        )
        r.raise_for_status()

    def get(self, path: str) -> bytes:
        r = httpx.get(f"{self.base}/{path}", headers=self.headers, timeout=60)
        r.raise_for_status()
        return r.content

    def delete(self, path: str) -> None:
        httpx.delete(f"{self.base}/{path}", headers=self.headers, timeout=30)


def get_storage() -> Storage:
    if settings.STORAGE_BACKEND == "supabase":
        return SupabaseStorage()
    return LocalStorage(settings.LOCAL_STORAGE_DIR)


storage = get_storage()
