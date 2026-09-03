"""Upload validation, hashing and on-disk storage.

The uploaded file is written once, byte-for-byte unmodified, and its SHA-256 is
computed during the same streaming pass. Preserving the original bytes and
recording the hash at upload time is what supports the chain-of-custody claim in
the generated forensic report.
"""

from __future__ import annotations

import hashlib
import shutil
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from app.config import settings
from app.models import MediaType

CHUNK_SIZE = 1024 * 1024  # 1 MiB

# Accepted extensions per media type (Phase 1 non-functional requirements).
ALLOWED_EXTENSIONS: dict[MediaType, set[str]] = {
    MediaType.IMAGE: {".jpg", ".jpeg", ".png", ".webp", ".bmp"},
    MediaType.AUDIO: {".wav", ".mp3", ".flac", ".ogg", ".m4a"},
    MediaType.VIDEO: {".mp4", ".mov", ".avi", ".mkv", ".webm"},
}

# Magic-number signatures used to confirm the bytes match the claimed extension.
_MAGIC_SIGNATURES: list[tuple[bytes, int, MediaType]] = [
    (b"\xff\xd8\xff", 0, MediaType.IMAGE),   # JPEG
    (b"\x89PNG\r\n\x1a\n", 0, MediaType.IMAGE),  # PNG
    (b"BM", 0, MediaType.IMAGE),              # BMP
    (b"RIFF", 0, MediaType.IMAGE),            # WEBP (checked via RIFF+WEBP fourcc)
    # Audio
    (b"RIFF", 0, MediaType.AUDIO),            # WAV  (RIFF+WAVE fourcc)
    (b"ID3", 0, MediaType.AUDIO),             # MP3 with ID3 tag
    (b"\xff\xfb", 0, MediaType.AUDIO),        # MP3 raw frame
    (b"\xff\xf3", 0, MediaType.AUDIO),        # MP3 raw frame variant
    (b"fLaC", 0, MediaType.AUDIO),            # FLAC
    (b"OggS", 0, MediaType.AUDIO),            # OGG
    # Video
    (b"\x00\x00\x00", 0, MediaType.VIDEO),   # MP4/MOV (ftyp box, permissive)
    (b"RIFF", 0, MediaType.VIDEO),            # AVI (RIFF+AVI fourcc)
    (b"\x1aE\xdf\xa3", 0, MediaType.VIDEO),  # MKV/WEBM EBML header
]


class UploadValidationError(ValueError):
    """Raised when an upload fails type, extension or size validation."""


@dataclass(frozen=True)
class StoredFile:
    path: Path
    sha256: str
    size_bytes: int
    media_type: MediaType
    original_filename: str
    content_type: str


def sha256_file(path: str | Path) -> str:
    """SHA-256 of a file on disk, streamed so large videos do not load into RAM."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sanitize_filename(filename: str) -> str:
    """Strip directory components and unsafe characters from a client filename."""
    name = unicodedata.normalize("NFKD", filename or "upload")
    name = Path(name.replace("\\", "/")).name
    safe = "".join(ch if (ch.isalnum() or ch in "._- ") else "_" for ch in name).strip()
    return safe[:200] or "upload"


def media_type_for_extension(filename: str) -> MediaType:
    """Map a filename extension to a supported media type."""
    suffix = Path(sanitize_filename(filename)).suffix.lower()
    for media_type, extensions in ALLOWED_EXTENSIONS.items():
        if suffix in extensions:
            return media_type
    supported = sorted(ext for exts in ALLOWED_EXTENSIONS.values() for ext in exts)
    raise UploadValidationError(
        f"Unsupported file extension '{suffix or 'none'}'. Supported: {', '.join(supported)}"
    )


def sniff_media_type(header: bytes) -> MediaType | None:
    """Best-effort media type from magic numbers; ``None`` when unrecognised."""
    if not header:
        return None

    # RIFF container — disambiguate by the fourcc at bytes 8-12.
    if len(header) >= 12 and header[:4] == b"RIFF":
        fourcc = header[8:12]
        if fourcc == b"WEBP":
            return MediaType.IMAGE
        if fourcc == b"WAVE":
            return MediaType.AUDIO
        if fourcc[:3] == b"AVI":
            return MediaType.VIDEO
        return None

    # MP4 / MOV: 'ftyp' box at offset 4.
    if len(header) >= 8 and header[4:8] == b"ftyp":
        return MediaType.VIDEO

    # MKV / WEBM EBML header.
    if header[:4] == b"\x1aE\xdf\xa3":
        return MediaType.VIDEO

    # Walk the simple signature table for everything else.
    for signature, offset, media_type in _MAGIC_SIGNATURES:
        if len(header) >= offset + len(signature) and header[offset: offset + len(signature)] == signature:
            return media_type
    return None



def save_upload(
    fileobj: BinaryIO,
    original_filename: str,
    content_type: str,
    job_id: str,
    *,
    max_bytes: int | None = None,
    destination_dir: Path | None = None,
) -> StoredFile:
    """Validate and persist an upload, returning its metadata and SHA-256.

    The size limit is enforced while streaming so an oversized upload never
    fully lands on disk.
    """
    max_bytes = max_bytes or settings.max_upload_bytes
    safe_name = sanitize_filename(original_filename)
    declared_type = media_type_for_extension(safe_name)

    destination_dir = Path(destination_dir or settings.storage_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)
    target = destination_dir / f"{job_id}{Path(safe_name).suffix.lower()}"

    digest = hashlib.sha256()
    size = 0
    header = b""

    try:
        with open(target, "wb") as out:
            while chunk := fileobj.read(CHUNK_SIZE):
                size += len(chunk)
                if size > max_bytes:
                    raise UploadValidationError(
                        f"File exceeds the {max_bytes // (1024 * 1024)} MB upload limit."
                    )
                if len(header) < 32:
                    header += chunk[: 32 - len(header)]
                digest.update(chunk)
                out.write(chunk)
    except Exception:
        target.unlink(missing_ok=True)
        raise

    if size == 0:
        target.unlink(missing_ok=True)
        raise UploadValidationError("Uploaded file is empty.")

    sniffed = sniff_media_type(header)
    if sniffed is not None and sniffed is not declared_type:
        target.unlink(missing_ok=True)
        raise UploadValidationError(
            f"File content ({sniffed.value}) does not match its '{Path(safe_name).suffix}' extension."
        )

    return StoredFile(
        path=target,
        sha256=digest.hexdigest(),
        size_bytes=size,
        media_type=declared_type,
        original_filename=safe_name,
        content_type=content_type or "application/octet-stream",
    )


def delete_job_artifacts(*paths: str | Path | None) -> None:
    """Remove stored media/evidence for a job (data-retention policy support)."""
    for path in paths:
        if not path:
            continue
        target = Path(path)
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
        else:
            target.unlink(missing_ok=True)
