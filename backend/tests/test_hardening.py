"""Security and robustness guarantees.

Each test here pins a defect that was found by probing the running service.
"""

from __future__ import annotations

import io

import pytest
from app.config import INSECURE_JWT_SECRET, InsecureConfigurationError, Settings


class TestProductionConfiguration:
    """A production deployment must refuse to start when configured unsafely.

    Booting with the placeholder signing key is an authentication bypass:
    the value is published in this repository, so anyone could mint tokens.
    """

    def _settings(self, **overrides):
        base = {
            "environment": "production",
            "debug": False,
            "jwt_secret_key": "x" * 48,
            "cors_origins": ["https://example.com"],
        }
        base.update(overrides)
        return Settings(**base)

    def test_rejects_the_placeholder_secret(self):
        with pytest.raises(InsecureConfigurationError, match="placeholder"):
            self._settings(jwt_secret_key=INSECURE_JWT_SECRET)

    def test_rejects_a_short_secret(self):
        with pytest.raises(InsecureConfigurationError, match="at least"):
            self._settings(jwt_secret_key="tooshort")

    def test_rejects_debug_in_production(self):
        with pytest.raises(InsecureConfigurationError, match="DEBUG"):
            self._settings(debug=True)

    def test_rejects_wildcard_cors(self):
        with pytest.raises(InsecureConfigurationError, match="CORS"):
            self._settings(cors_origins=["*"])

    def test_accepts_a_sound_production_configuration(self):
        assert self._settings().environment == "production"

    def test_development_is_unaffected(self):
        """The guard must not make local development harder."""
        settings = Settings(
            environment="development", debug=True, jwt_secret_key=INSECURE_JWT_SECRET
        )
        assert settings.debug is True


class TestSecurityHeaders:
    """The API is often exposed directly, so it sets its own headers."""

    @pytest.mark.parametrize(
        "header,expected",
        [
            ("X-Content-Type-Options", "nosniff"),
            ("X-Frame-Options", "DENY"),
            ("Referrer-Policy", "strict-origin-when-cross-origin"),
        ],
    )
    def test_sets_defensive_headers(self, client, header, expected):
        assert client.get("/api/health").headers[header] == expected

    def test_sets_a_restrictive_content_security_policy(self, client):
        policy = client.get("/api/health").headers["Content-Security-Policy"]
        assert "default-src 'none'" in policy
        assert "frame-ancestors 'none'" in policy


class TestRequestCorrelation:
    def test_every_response_carries_a_request_id(self, client):
        assert client.get("/api/health").headers["X-Request-ID"]

    def test_ids_differ_between_requests(self, client):
        first = client.get("/api/health").headers["X-Request-ID"]
        second = client.get("/api/health").headers["X-Request-ID"]
        assert first != second

    def test_an_upstream_id_is_preserved(self, client):
        """A trace must survive the reverse-proxy hop."""
        response = client.get("/api/health", headers={"X-Request-ID": "trace-abc-123"})
        assert response.headers["X-Request-ID"] == "trace-abc-123"

    def test_errors_report_the_request_id(self, client):
        body = client.get("/api/jobs/does-not-exist/status").json()
        assert body["detail"] == "Job not found."
        assert body["request_id"]


class TestValidationErrors:
    def test_reports_fields_without_echoing_the_body(self, client):
        response = client.post(
            "/api/auth/register", json={"email": "not-an-email", "password": "short"}
        )
        assert response.status_code == 422
        body = response.json()
        assert body["detail"] == "Request validation failed."
        assert {error["field"] for error in body["errors"]} == {"email", "password"}


class TestRateLimiting:
    def test_rejected_uploads_still_count(self, client):
        """A malformed upload consumed real work and must be counted.

        Previously the attempt was recorded but only committed alongside a
        successfully created job, so invalid uploads were unlimited.

        The request carries its own X-Forwarded-For so this test gets a fresh
        rate-limit bucket and does not depend on what the rest of the suite
        uploaded first.
        """
        from app.config import settings

        headers = {"X-Forwarded-For": "203.0.113.77"}
        attempts = settings.guest_rate_limit_per_hour + 2

        statuses = [
            client.post(
                "/api/upload",
                files={"file": ("bad.exe", io.BytesIO(b"MZ\x00\x00"), "application/exe")},
                headers=headers,
            ).status_code
            for _ in range(attempts)
        ]

        assert statuses[0] == 400, "an invalid file should be rejected on its own merits"
        assert 429 in statuses, "rejected uploads must consume the rate-limit budget"
        assert statuses.count(400) == settings.guest_rate_limit_per_hour, (
            "exactly the budgeted number of attempts should be processed before limiting"
        )


class TestCheckpointLoading:
    """Checkpoints are untrusted input: the documented workflow copies a .pt
    file from Colab onto the server that holds user media. Full pickle would
    make that remote code execution."""

    @pytest.fixture
    def torch_module(self):
        return pytest.importorskip("torch", reason="inference stack not installed")

    def test_loads_a_plain_state_dict_checkpoint(self, torch_module, tmp_path):
        from app.ml.checkpoints import extract_metadata, extract_state_dict, load_checkpoint

        path = tmp_path / "model.pt"
        torch_module.save(
            {"state_dict": {"w": torch_module.zeros(2)}, "version": "v1.2", "val_auc": 0.94},
            path,
        )

        payload = load_checkpoint(path)
        assert extract_metadata(payload) == {"version": "v1.2", "val_auc": 0.94}
        assert "w" in extract_state_dict(payload)

    def test_refuses_a_pickled_object_without_opt_in(self, torch_module, tmp_path, monkeypatch):
        from app.ml.checkpoints import UnsafeCheckpointError, load_checkpoint

        monkeypatch.delenv("ALLOW_UNSAFE_CHECKPOINTS", raising=False)

        path = tmp_path / "unsafe.pt"
        torch_module.save({"state_dict": {}, "obj": _ArbitraryObject()}, path)

        with pytest.raises(UnsafeCheckpointError, match="execute code"):
            load_checkpoint(path)

    def test_opt_in_allows_it(self, torch_module, tmp_path, monkeypatch):
        from app.ml.checkpoints import load_checkpoint

        monkeypatch.setenv("ALLOW_UNSAFE_CHECKPOINTS", "true")

        path = tmp_path / "unsafe.pt"
        torch_module.save({"state_dict": {}, "obj": _ArbitraryObject()}, path)
        assert "obj" in load_checkpoint(path)


class _ArbitraryObject:
    """Stands in for any non-tensor object a third-party checkpoint might carry."""
