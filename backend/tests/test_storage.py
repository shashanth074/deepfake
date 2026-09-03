"""Upload validation, hashing and path safety."""

from __future__ import annotations

import hashlib
import io

import pytest
from app.models import MediaType
from app.storage import (
    UploadValidationError,
    media_type_for_extension,
    sanitize_filename,
    save_upload,
    sha256_file,
    sniff_media_type,
)


class TestFilenameHandling:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("../../etc/passwd.png", "passwd.png"),
            ("C:\\Users\\evil\\shell.jpg", "shell.jpg"),
            ("normal name.mp4", "normal name.mp4"),
            ("", "upload"),
        ],
    )
    def test_strips_directory_components(self, raw, expected):
        assert sanitize_filename(raw) == expected

    def test_replaces_shell_metacharacters(self):
        assert ";" not in sanitize_filename("a;rm -rf.png")
        assert "$" not in sanitize_filename("a$(id).png")


class TestMediaTypeDetection:
    @pytest.mark.parametrize(
        "filename,expected",
        [
            ("photo.JPG", MediaType.IMAGE),
            ("clip.mp4", MediaType.VIDEO),
            ("voice.WAV", MediaType.AUDIO),
        ],
    )
    def test_maps_extension_to_media_type(self, filename, expected):
        assert media_type_for_extension(filename) is expected

    def test_rejects_unsupported_extension(self):
        with pytest.raises(UploadValidationError, match="Unsupported file extension"):
            media_type_for_extension("payload.exe")

    @pytest.mark.parametrize(
        "header,expected",
        [
            (b"\xff\xd8\xff\xe0", MediaType.IMAGE),
            (b"\x89PNG\r\n\x1a\n", MediaType.IMAGE),
            (b"RIFF\x00\x00\x00\x00WEBP", MediaType.IMAGE),
            (b"RIFF\x00\x00\x00\x00WAVE", MediaType.AUDIO),
            (b"RIFF\x00\x00\x00\x00AVI ", MediaType.VIDEO),
            (b"ID3\x04", MediaType.AUDIO),
            (b"\x00\x00\x00\x20ftypmp42", MediaType.VIDEO),
            (b"\x1a\x45\xdf\xa3", MediaType.VIDEO),
        ],
    )
    def test_sniffs_magic_numbers(self, header, expected):
        assert sniff_media_type(header) is expected

    def test_returns_none_for_unknown_bytes(self):
        assert sniff_media_type(b"not a real header") is None


class TestSaveUpload:
    def test_stores_file_and_computes_hash(self, tmp_path, png_bytes):
        stored = save_upload(
            io.BytesIO(png_bytes), "photo.png", "image/png", "job1", destination_dir=tmp_path
        )
        assert stored.path.exists()
        assert stored.size_bytes == len(png_bytes)
        assert stored.media_type is MediaType.IMAGE
        assert stored.sha256 == hashlib.sha256(png_bytes).hexdigest()

    def test_preserves_bytes_exactly(self, tmp_path, png_bytes):
        """Chain of custody depends on the stored file being byte-identical."""
        stored = save_upload(
            io.BytesIO(png_bytes), "photo.png", "image/png", "job2", destination_dir=tmp_path
        )
        assert stored.path.read_bytes() == png_bytes
        assert sha256_file(stored.path) == stored.sha256

    def test_rejects_content_not_matching_extension(self, tmp_path):
        """An MP3 renamed to .png must not be accepted as an image."""
        with pytest.raises(UploadValidationError, match="does not match"):
            save_upload(
                io.BytesIO(b"ID3\x04" + b"\x00" * 100),
                "disguised.png",
                "image/png",
                "job3",
                destination_dir=tmp_path,
            )
        assert list(tmp_path.iterdir()) == [], "rejected upload must not be left on disk"

    def test_rejects_oversized_file_without_writing_it_all(self, tmp_path):
        payload = b"\x89PNG\r\n\x1a\n" + b"\x00" * 5000
        with pytest.raises(UploadValidationError, match="exceeds"):
            save_upload(
                io.BytesIO(payload),
                "big.png",
                "image/png",
                "job4",
                max_bytes=1024,
                destination_dir=tmp_path,
            )
        assert list(tmp_path.iterdir()) == []

    def test_rejects_empty_file(self, tmp_path):
        with pytest.raises(UploadValidationError, match="empty"):
            save_upload(io.BytesIO(b""), "empty.png", "image/png", "job5", destination_dir=tmp_path)

    def test_uses_job_id_for_stored_name(self, tmp_path, png_bytes):
        """Stored names come from the job id, so a hostile filename cannot pick the path."""
        stored = save_upload(
            io.BytesIO(png_bytes),
            "../../evil.png",
            "image/png",
            "job6",
            destination_dir=tmp_path,
        )
        assert stored.path.name == "job6.png"
        assert stored.path.parent == tmp_path
