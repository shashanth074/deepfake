"""Detection pipelines and their preprocessing."""

from __future__ import annotations

import numpy as np
import pytest

torch = pytest.importorskip("torch", reason="inference stack not installed")

from app.ml.base import AnalysisResult, classify  # noqa: E402
from app.ml.preprocessing import (  # noqa: E402
    log_mel_spectrogram,
    normalize_waveform,
    preprocess_image,
    segment_waveform,
)
from app.models import Verdict  # noqa: E402


class TestVerdictClassification:
    @pytest.mark.parametrize(
        "probability,expected",
        [
            (0.02, Verdict.AUTHENTIC),
            (0.30, Verdict.AUTHENTIC),
            (0.50, Verdict.INCONCLUSIVE),
            (0.55, Verdict.INCONCLUSIVE),
            (0.70, Verdict.MANIPULATED),
            (0.99, Verdict.MANIPULATED),
        ],
    )
    def test_maps_probability_to_verdict(self, probability, expected):
        assert classify(probability) is expected

    def test_borderline_scores_are_never_forced_into_a_binary_call(self):
        """The uncertain band is the honesty guarantee — it must not collapse."""
        assert classify(0.48) is Verdict.INCONCLUSIVE
        assert classify(0.52) is Verdict.INCONCLUSIVE

    def test_confidence_is_zero_at_the_midpoint(self):
        result = AnalysisResult(0.5, "m", "v", "trained")
        assert result.confidence == 0.0

    def test_confidence_is_maximal_at_the_extremes(self):
        assert AnalysisResult(1.0, "m", "v", "trained").confidence == 1.0
        assert AnalysisResult(0.0, "m", "v", "trained").confidence == 1.0


class TestImagePreprocessing:
    def test_produces_a_normalised_batch_tensor(self):
        from PIL import Image

        tensor = preprocess_image(Image.new("RGB", (500, 300), (128, 128, 128)))
        assert tensor.shape == (1, 3, 224, 224)
        assert tensor.dtype == torch.float32
        # Mid-grey normalises to roughly zero under ImageNet statistics.
        assert abs(float(tensor.mean())) < 0.5

    def test_converts_greyscale_input(self):
        from PIL import Image

        assert preprocess_image(Image.new("L", (100, 100), 200)).shape == (1, 3, 224, 224)





class TestImagePipeline:
    def test_scores_an_image_and_writes_a_heatmap(self, tmp_path, png_bytes):
        from app.ml.image_pipeline import analyze_image

        source = tmp_path / "input.png"
        source.write_bytes(png_bytes)

        result = analyze_image(source, tmp_path / "evidence", "job-img")
        assert 0.0 <= result.fake_probability <= 1.0
        assert result.evidence["media"] == "image"
        assert (tmp_path / "evidence" / result.evidence["heatmap_file"]).exists()

    def test_flags_an_untrained_deployment_in_its_notes(self, tmp_path, png_bytes):
        from app.ml.image_pipeline import analyze_image

        source = tmp_path / "input2.png"
        source.write_bytes(png_bytes)
        result = analyze_image(source, tmp_path / "evidence", "job-img2")

        assert result.weights_status == "untrained-backbone"
        assert any("NOT valid evidence" in note for note in result.evidence["notes"])





class TestFaceDetection:
    """The face-crop path, exercised on a real photograph.

    Deepfake artefacts concentrate in the face, so a detector that silently
    analyses whole frames is a materially weaker detector. These tests fail if
    face detection regresses to the whole-image fallback.
    """

    def test_detects_a_face_and_crops_to_it(self, face_photo):
        pytest.importorskip("facenet_pytorch", reason="face detector not installed")
        from app.ml.faces import extract_faces

        crops = extract_faces(face_photo)
        assert len(crops) >= 1

        crop = crops[0]
        assert crop.box is not None, "fell back to the whole image"
        assert crop.confidence is not None and crop.confidence > 0.9

        x1, y1, x2, y2 = crop.box
        assert 0 <= x1 < x2 <= face_photo.size[0]
        assert 0 <= y1 < y2 <= face_photo.size[1]
        # The crop must be a region, not the entire frame.
        assert (x2 - x1) * (y2 - y1) < face_photo.size[0] * face_photo.size[1]

    def test_faceless_image_falls_back_to_the_whole_frame(self):
        pytest.importorskip("facenet_pytorch", reason="face detector not installed")
        from app.ml.faces import extract_faces
        from PIL import Image

        crops = extract_faces(Image.new("RGB", (256, 256), (40, 90, 140)))
        assert len(crops) == 1
        assert crops[0].box is None, "a blank image must not yield a face box"

    def test_pipeline_analyses_the_face_region(self, tmp_path, face_photo_bytes):
        pytest.importorskip("facenet_pytorch", reason="face detector not installed")
        from app.ml.image_pipeline import analyze_image

        source = tmp_path / "portrait.png"
        source.write_bytes(face_photo_bytes)
        result = analyze_image(source, tmp_path / "evidence", "face-job")

        evidence = result.evidence
        assert evidence["faces_detected"] >= 1
        assert evidence["analysed_region"] is not None, "scored the whole image, not the face"
        assert not any("No face was detected" in note for note in evidence["notes"])
