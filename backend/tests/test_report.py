"""Forensic PDF report generation and its integrity guarantees."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest
from app.models import Job, JobStatus, MediaType, Verdict
from app.report.generator import generate_report, verify_report_hash


def make_job(**overrides) -> Job:
    """A completed job, detached from any session (the generator only reads it)."""
    defaults = dict(
        id="job-test",
        case_reference="DF-20260101-ABC123",
        original_filename="suspect_clip.mp4",
        stored_path="/tmp/suspect_clip.mp4",
        media_type=MediaType.VIDEO,
        content_type="video/mp4",
        file_size_bytes=4_582_912,
        sha256="a" * 64,
        status=JobStatus.DONE,
        verdict=Verdict.MANIPULATED,
        fake_probability=0.87,
        confidence=0.74,
        model_name="efficientnet_b0-binary-head+frame-aggregation",
        model_version="image-detector-v1.0.0/video-frame-agg-v1.0.0",
        weights_status="trained",
        processing_ms=4210,
        uploaded_at=datetime.now(UTC),
        evidence={
            "media": "video",
            "frames_analysed": 12,
            "flagged_frames": 5,
            "frame_scores": [
                {
                    "index": i,
                    "timestamp": float(i),
                    "fake_probability": 0.3 + 0.05 * i,
                    "face_detected": True,
                }
                for i in range(12)
            ],
            "notes": ["A face was found in 10 of 12 sampled frames."],
        },
    )
    defaults.update(overrides)
    return Job(**defaults)


def pdf_text(path) -> str:
    """Extract the document's text so assertions can inspect what it says."""
    pypdf = pytest.importorskip("pypdf")
    reader = pypdf.PdfReader(str(path))
    return "\n".join(page.extract_text() for page in reader.pages)


class TestGeneration:
    def test_writes_a_valid_pdf(self, tmp_path):
        artifacts = generate_report(make_job(), output_dir=tmp_path, evidence_dir=tmp_path)
        assert artifacts.path.exists()
        assert artifacts.path.read_bytes().startswith(b"%PDF-")
        assert artifacts.report_reference == "DFR-DF-20260101-ABC123"

    def test_hash_matches_the_delivered_file(self, tmp_path):
        """A recipient running `shasum -a 256` must get the registered value."""
        artifacts = generate_report(make_job(), output_dir=tmp_path, evidence_dir=tmp_path)
        on_disk = hashlib.sha256(artifacts.path.read_bytes()).hexdigest()
        assert artifacts.sha256 == on_disk
        assert verify_report_hash(artifacts.path, artifacts.sha256)

    def test_verification_fails_after_tampering(self, tmp_path):
        artifacts = generate_report(make_job(), output_dir=tmp_path, evidence_dir=tmp_path)
        with open(artifacts.path, "ab") as handle:
            handle.write(b"% appended by an editor\n")
        assert not verify_report_hash(artifacts.path, artifacts.sha256)

    def test_verification_fails_for_a_missing_file(self, tmp_path):
        assert not verify_report_hash(tmp_path / "nothing.pdf", "0" * 64)


class TestRequiredSections:
    @pytest.fixture(scope="class")
    def text(self, tmp_path_factory):
        directory = tmp_path_factory.mktemp("report")
        artifacts = generate_report(make_job(), output_dir=directory, evidence_dir=directory)
        return pdf_text(artifacts.path)

    def test_contains_every_required_section(self, text):
        for heading in (
            "Submitted File Details",
            "Analysis Summary",
            "Detailed Findings",
            "Methodology",
            "Limitations and Disclaimer",
            "Report Integrity",
        ):
            assert heading in text, f"missing report section: {heading}"

    def test_prints_the_analysed_file_hash(self, text):
        assert "a" * 64 in text.replace("\n", "")

    def test_states_the_verdict_and_score(self, text):
        assert "LIKELY MANIPULATED" in text
        assert "87.0%" in text

    def test_identifies_the_model_and_version(self, text):
        assert "image-detector-v1.0.0" in text

    def test_carries_the_limitations_disclaimer(self, text):
        assert "not" in text and "certified forensic" in text
        assert "false positives" in text

    def test_explains_it_does_not_file_complaints(self, text):
        """Claiming legal authority would be the project's biggest liability."""
        assert "does not file" in text

    def test_explains_how_to_verify_the_hashes(self, text):
        assert "shasum" in text or "certutil" in text


class TestUntrainedWarning:
    def test_untrained_model_is_called_out_prominently(self, tmp_path):
        job = make_job(weights_status="untrained-backbone")
        artifacts = generate_report(job, output_dir=tmp_path, evidence_dir=tmp_path)
        text = pdf_text(artifacts.path)
        assert "MODEL NOT TRAINED" in text
        assert "no evidentiary value" in text

    def test_trained_model_shows_no_warning(self, tmp_path):
        artifacts = generate_report(make_job(), output_dir=tmp_path, evidence_dir=tmp_path)
        assert "MODEL NOT TRAINED" not in pdf_text(artifacts.path)


class TestMediaVariants:
    def test_audio_report_uses_the_audio_methodology(self, tmp_path):
        job = make_job(
            media_type=MediaType.AUDIO,
            original_filename="call.wav",
            verdict=Verdict.AUTHENTIC,
            fake_probability=0.12,
            evidence={
                "media": "audio",
                "duration_seconds": 12.0,
                "segments_analysed": 3,
                "flagged_segments": 0,
                "segment_scores": [
                    {
                        "index": i,
                        "start": i * 4.0,
                        "end": (i + 1) * 4.0,
                        "fake_probability": 0.1 + 0.01 * i,
                    }
                    for i in range(3)
                ],
                "notes": [],
            },
        )
        text = pdf_text(generate_report(job, output_dir=tmp_path, evidence_dir=tmp_path).path)
        assert "spectrogram" in text.lower()
        assert "LIKELY AUTHENTIC" in text

    def test_image_report_renders_without_a_timeline(self, tmp_path):
        job = make_job(
            media_type=MediaType.IMAGE,
            original_filename="photo.jpg",
            verdict=Verdict.INCONCLUSIVE,
            fake_probability=0.52,
            evidence={
                "media": "image",
                "faces_detected": 1,
                "face_scores": [
                    {
                        "index": 0,
                        "box": [10, 10, 90, 90],
                        "detection_confidence": 0.99,
                        "fake_probability": 0.52,
                    }
                ],
                "notes": [],
            },
        )
        text = pdf_text(generate_report(job, output_dir=tmp_path, evidence_dir=tmp_path).path)
        assert "INCONCLUSIVE" in text
