import hashlib
from pathlib import Path
from app.core.config import settings

MAX_UPLOAD_BYTES = settings.MAX_UPLOAD_MB * 1024 * 1024  # 10MB default

ALLOWED_MIME_TYPES = {
    "image/jpeg": [".jpg", ".jpeg"],
    "image/png": [".png"],
    "image/webp": [".webp"],
}

DISALLOWED_EXTENSIONS = {
    ".exe",
    ".bat",
    ".cmd",
    ".sh",
    ".php",
    ".py",
    ".js",
    ".ts",
    ".dll",
    ".so",
    ".dylib",
    ".vbs",
    ".ps1",
    ".jar",
    ".msi",
    ".html",
    ".htm",
}


def detect_mime_type(header_bytes: bytes) -> str | None:
    """Inspects binary header magic bytes to detect true image format."""
    if len(header_bytes) >= 3 and header_bytes[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if len(header_bytes) >= 8 and header_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if len(header_bytes) >= 12 and header_bytes[:4] == b"RIFF" and header_bytes[8:12] == b"WEBP":
        return "image/webp"
    return None


def calculate_sha256(data: bytes) -> str:
    """Computes SHA-256 checksum string of binary content."""
    return hashlib.sha256(data).hexdigest()


def get_local_storage_file_path(storage_key: str) -> Path:
    """Resolves target local storage path on disk."""
    base_dir = Path(settings.LOCAL_STORAGE_PATH)
    target_path = (base_dir / storage_key).resolve()
    base_resolved = base_dir.resolve()

    # Prevent directory traversal
    if not str(target_path).startswith(str(base_resolved)):
        raise ValueError("Invalid storage key path")

    return target_path


def save_file_to_local_storage(storage_key: str, content: bytes) -> Path:
    """Saves binary content to local disk storage."""
    file_path = get_local_storage_file_path(storage_key)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "wb") as f:
        f.write(content)
    return file_path


def read_file_from_local_storage(storage_key: str) -> bytes:
    """Reads binary content from local disk storage."""
    file_path = get_local_storage_file_path(storage_key)
    if not file_path.exists():
        raise FileNotFoundError(f"File '{storage_key}' not found in local storage.")
    with open(file_path, "rb") as f:
        return f.read()


def file_exists_in_storage(storage_key: str) -> bool:
    """Checks whether stored file exists on disk."""
    try:
        file_path = get_local_storage_file_path(storage_key)
        return file_path.exists()
    except Exception:
        return False
