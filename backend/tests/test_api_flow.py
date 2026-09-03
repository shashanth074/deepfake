"""End-to-end API behaviour: upload, poll, result, report, history."""

from __future__ import annotations

import hashlib

import pytest

torch = pytest.importorskip("torch", reason="inference stack not installed")


@pytest.fixture(scope="module")
def completed_job(client, png_bytes):
    """Upload an image and run it through to completion (eager mode)."""
    response = client.post("/api/upload", files={"file": ("evidence.png", png_bytes, "image/png")})
    assert response.status_code == 202, response.text
    return response.json()


class TestUpload:
    def test_returns_202_with_case_reference_and_hash(self, completed_job, png_bytes):
        assert completed_job["status"] in {"queued", "processing", "done"}
        assert completed_job["case_reference"].startswith("DF-")
        assert completed_job["sha256"] == hashlib.sha256(png_bytes).hexdigest()
        assert completed_job["media_type"] == "image"

    def test_hash_is_recorded_at_upload_time(self, client, png_bytes):
        """The report's chain-of-custody claim rests on this."""
        first = client.post("/api/upload", files={"file": ("a.png", png_bytes, "image/png")})
        second = client.post("/api/upload", files={"file": ("b.png", png_bytes, "image/png")})
        assert first.json()["sha256"] == second.json()["sha256"]

    def test_rejects_unsupported_extension(self, client):
        response = client.post(
            "/api/upload", files={"file": ("malware.exe", b"MZ\x90\x00", "application/exe")}
        )
        assert response.status_code == 400
        assert "Unsupported file extension" in response.json()["detail"]

    def test_rejects_content_disguised_by_extension(self, client, wav_bytes):
        response = client.post(
            "/api/upload", files={"file": ("disguised.png", wav_bytes, "image/png")}
        )
        assert response.status_code == 400
        assert "does not match" in response.json()["detail"]

    def test_rejects_empty_file(self, client):
        response = client.post("/api/upload", files={"file": ("empty.png", b"", "image/png")})
        assert response.status_code == 400

    def test_limits_endpoint_describes_constraints(self, client):
        limits = client.get("/api/upload/limits").json()
        assert limits["max_upload_mb"] == 5
        assert ".png" in limits["allowed_extensions"]["image"]
        assert ".mp4" in limits["allowed_extensions"]["video"]


class TestJobLifecycle:
    def test_status_reports_done(self, client, completed_job):
        status = client.get(f"/api/jobs/{completed_job['id']}/status").json()
        assert status["status"] == "done"
        assert status["case_reference"] == completed_job["case_reference"]

    def test_result_contains_verdict_and_evidence(self, client, completed_job):
        result = client.get(f"/api/jobs/{completed_job['id']}/result").json()
        assert result["verdict"] in {"likely_authentic", "likely_manipulated", "inconclusive"}
        assert 0.0 <= result["fake_probability"] <= 1.0
        assert 0.0 <= result["confidence"] <= 1.0
        assert result["model_name"] and result["model_version"]
        assert "disclaimer" in result and "not a certified forensic opinion" in result["disclaimer"]

    def test_untrained_deployment_is_flagged_in_the_result(self, client, completed_job):
        """A demo build must never look like an evidential one."""
        result = client.get(f"/api/jobs/{completed_job['id']}/result").json()
        assert result["weights_status"] == "untrained-backbone"
        notes = " ".join(result["evidence"].get("notes", []))
        assert "NOT valid evidence" in notes

    def test_evidence_image_is_served(self, client, completed_job):
        result = client.get(f"/api/jobs/{completed_job['id']}/result").json()
        url = result["evidence"]["heatmap_url"]
        response = client.get(url)
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"

    def test_unknown_evidence_type_is_404(self, client, completed_job):
        assert client.get(f"/api/jobs/{completed_job['id']}/evidence/secrets").status_code == 404

    def test_unknown_job_is_404(self, client):
        assert client.get("/api/jobs/does-not-exist/status").status_code == 404


class TestOwnership:
    def test_another_user_cannot_read_your_job(self, client, auth_headers, png_bytes):
        owned = client.post(
            "/api/upload",
            files={"file": ("mine.png", png_bytes, "image/png")},
            headers=auth_headers,
        ).json()

        other = client.post(
            "/api/auth/register",
            json={"email": "intruder@example.com", "password": "password12345"},
        ).json()
        intruder_headers = {"Authorization": f"Bearer {other['access_token']}"}

        response = client.get(f"/api/jobs/{owned['id']}/result", headers=intruder_headers)
        assert response.status_code == 404, "must not confirm the job even exists"

    def test_anonymous_cannot_read_an_owned_job(self, client, auth_headers, png_bytes):
        owned = client.post(
            "/api/upload",
            files={"file": ("mine2.png", png_bytes, "image/png")},
            headers=auth_headers,
        ).json()
        assert client.get(f"/api/jobs/{owned['id']}/result").status_code == 404

    def test_guest_can_read_their_own_unowned_job(self, client, completed_job):
        assert client.get(f"/api/jobs/{completed_job['id']}/result").status_code == 200

    def test_owner_can_load_their_evidence_image_with_a_token(
        self, client, auth_headers, png_bytes
    ):
        """Evidence for an owned job needs the header a plain <img> cannot send.

        The browser must fetch these with the Authorization header (see
        AuthedImage on the frontend); without it the request is anonymous and
        correctly refused.
        """
        job = client.post(
            "/api/upload",
            files={"file": ("owned.png", png_bytes, "image/png")},
            headers=auth_headers,
        ).json()
        url = client.get(f"/api/jobs/{job['id']}/result", headers=auth_headers).json()["evidence"][
            "heatmap_url"
        ]

        assert client.get(url, headers=auth_headers).status_code == 200
        assert client.get(url).status_code == 404, "anonymous access must stay refused"


class TestReports:
    def test_generates_a_pdf_whose_hash_is_registered(self, client, completed_job):
        job_id = completed_job["id"]
        created = client.post(f"/api/jobs/{job_id}/report").json()
        assert created["report_reference"].startswith("DFR-")

        download = client.get(f"/api/jobs/{job_id}/report")
        assert download.status_code == 200
        assert download.headers["content-type"] == "application/pdf"
        assert download.content.startswith(b"%PDF-")
        # The recipient must be able to reproduce this with `shasum -a 256`.
        assert hashlib.sha256(download.content).hexdigest() == created["sha256"]

    def test_regenerating_keeps_one_record_and_a_matching_hash(self, client, completed_job):
        job_id = completed_job["id"]
        first = client.post(f"/api/jobs/{job_id}/report").json()
        second = client.post(f"/api/jobs/{job_id}/report").json()
        assert first["id"] == second["id"]

        download = client.get(f"/api/jobs/{job_id}/report")
        assert hashlib.sha256(download.content).hexdigest() == second["sha256"]

    def test_public_verify_endpoint_needs_no_account(self, client, completed_job):
        created = client.post(f"/api/jobs/{completed_job['id']}/report").json()
        verification = client.get(f"/api/reports/{created['report_reference']}/verify")
        assert verification.status_code == 200

        body = verification.json()
        assert body["report_sha256"] == created["sha256"]
        assert body["stored_copy_intact"] is True
        # It must not leak the verdict or who submitted the media.
        assert "verdict" not in body and "user" not in body

    def test_verify_unknown_reference_is_404(self, client):
        assert client.get("/api/reports/DFR-nope/verify").status_code == 404


class TestHistory:
    def test_lists_only_your_own_scans(self, client, auth_headers, png_bytes):
        client.post(
            "/api/upload", files={"file": ("h1.png", png_bytes, "image/png")}, headers=auth_headers
        )
        history = client.get("/api/history", headers=auth_headers).json()
        assert history["total"] == 1
        assert history["items"][0]["original_filename"] == "h1.png"

    def test_requires_authentication(self, client):
        assert client.get("/api/history").status_code == 401

    def test_delete_removes_the_scan_and_its_files(self, client, auth_headers, png_bytes):
        from pathlib import Path

        job = client.post(
            "/api/upload",
            files={"file": ("delete-me.png", png_bytes, "image/png")},
            headers=auth_headers,
        ).json()
        client.post(f"/api/jobs/{job['id']}/report", headers=auth_headers)

        from app.database import SessionLocal
        from app.models import Job

        with SessionLocal() as session:
            stored_path = Path(session.get(Job, job["id"]).stored_path)
        assert stored_path.exists()

        assert client.delete(f"/api/history/{job['id']}", headers=auth_headers).status_code == 204
        assert not stored_path.exists(), "media must be erased, not just unlinked from the record"
        assert client.get(f"/api/jobs/{job['id']}/status", headers=auth_headers).status_code == 404

    def test_cannot_delete_another_users_scan(self, client, auth_headers, png_bytes):
        job = client.post(
            "/api/upload",
            files={"file": ("theirs.png", png_bytes, "image/png")},
            headers=auth_headers,
        ).json()
        other = client.post(
            "/api/auth/register",
            json={"email": "thief@example.com", "password": "password12345"},
        ).json()
        response = client.delete(
            f"/api/history/{job['id']}",
            headers={"Authorization": f"Bearer {other['access_token']}"},
        )
        assert response.status_code == 404


class TestHealth:
    def test_reports_model_and_queue_status(self, client):
        health = client.get("/api/health").json()
        assert health["status"] == "ok"
        assert health["queue_enabled"] is False  # eager mode in tests
        assert set(health["models"]) == {"image", "audio", "video"}
