"""Test fixtures: an isolated database and storage tree per test session.

The environment is configured at import time, before ``app.config`` is imported
anywhere. Settings are read once at import and cached, so setting them from
inside a fixture would be too late — the app would already have opened the
developer's real database.
"""

from __future__ import annotations

import io
import math
import os
import struct
import tempfile
import wave
from pathlib import Path

import pytest

TEST_ROOT = Path(tempfile.mkdtemp(prefix="deepfake-test-"))

os.environ.update(
    {
        "DATABASE_URL": f"sqlite:///{TEST_ROOT / 'test.db'}",
        "STORAGE_DIR": str(TEST_ROOT / "uploads"),
        "EVIDENCE_DIR": str(TEST_ROOT / "evidence"),
        "REPORT_DIR": str(TEST_ROOT / "reports"),
        "CHECKPOINT_DIR": str(TEST_ROOT / "checkpoints"),
        "CELERY_BROKER_URL": "",  # eager mode: no Redis needed
        "CELERY_RESULT_BACKEND": "",
        "JWT_SECRET_KEY": "test-secret-key-not-for-production",
        "MAX_UPLOAD_MB": "5",
        "UPLOAD_RATE_LIMIT_PER_HOUR": "50",
        "GUEST_RATE_LIMIT_PER_HOUR": "50",
    }
)


@pytest.fixture(scope="session")
def test_root() -> Path:
    """Root of this session's isolated storage tree."""
    return TEST_ROOT


@pytest.fixture(scope="session", autouse=True)
def _cleanup_test_root():
    yield
    import shutil

    shutil.rmtree(TEST_ROOT, ignore_errors=True)


@pytest.fixture(scope="session")
def client():
    """FastAPI test client with the app's lifespan (and table creation) run."""
    from app.main import app
    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_headers(client):
    """Register a fresh user and return its Authorization header."""
    import uuid

    email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "correct-horse-battery", "full_name": "Test User"},
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture(scope="session")
def png_bytes() -> bytes:
    """A small valid PNG."""
    pytest.importorskip("PIL")
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (128, 128), (120, 90, 70)).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture(scope="session")
def wav_bytes() -> bytes:
    """A 2-second 16 kHz mono PCM WAV containing a 440 Hz tone."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(
            b"".join(
                struct.pack("<h", int(10000 * math.sin(2 * math.pi * 440 * i / 16000)))
                for i in range(32000)
            )
        )
    return buffer.getvalue()


@pytest.fixture
def torch_available() -> bool:
    try:
        import torch  # noqa: F401
    except ImportError:
        return False
    return True


def requires_torch():
    """Skip marker for tests that need the inference stack installed."""
    return pytest.mark.skipif(
        __import__("importlib").util.find_spec("torch") is None,
        reason="PyTorch is not installed (pip install -r requirements-ml.txt)",
    )


@pytest.fixture(scope="session")
def face_photo():
    """A real photograph containing a detectable face.

    scikit-image bundles this sample, so the face-detection path can be tested
    without shipping a photo of a real person in this repository.
    """
    skimage_data = pytest.importorskip("skimage.data", reason="scikit-image not installed")
    from PIL import Image

    return Image.fromarray(skimage_data.astronaut())


@pytest.fixture(scope="session")
def face_photo_bytes(face_photo) -> bytes:
    buffer = io.BytesIO()
    face_photo.save(buffer, format="PNG")
    return buffer.getvalue()
