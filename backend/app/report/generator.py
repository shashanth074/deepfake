"""Forensic PDF report generation (ReportLab).

The report follows the seven sections the project guide specifies for an
evidentiary document:

  1. Header — title, case/report reference, generation timestamp, platform name
  2. Submitted file details — filename, type, size, SHA-256, upload timestamp
  3. Analysis summary — media type, models + versions, verdict, confidence
  4. Detailed findings — heatmap / spectrogram, per-frame or per-segment chart
  5. Methodology note — plain language, written for a non-technical reader
  6. Limitations disclaimer
  7. Report integrity hash — the SHA-256 of the finished PDF

A document cannot contain its own hash, so section 7 does not try to print one.
The PDF is rendered once and then hashed; that hash is stored in the platform's
report register (the ``reports`` table) and served by the verification endpoint.
Anyone holding the PDF can therefore run ``shasum -a 256`` on it and compare the
result against the registered value — a check that actually reproduces, which a
self-referential hash printed inside the file never could.
"""

from __future__ import annotations

import contextlib
import hashlib
import platform
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app import __version__ as app_version
from app.config import settings
from app.models import Job, Verdict
from app.report.charts import confidence_gauge, confidence_timeline

PAGE_WIDTH, PAGE_HEIGHT = A4
CONTENT_WIDTH = PAGE_WIDTH - 40 * mm

ACCENT = colors.HexColor("#1f4e79")
MUTED = colors.HexColor("#5b6670")
LIGHT = colors.HexColor("#eef2f6")

VERDICT_STYLING: dict[Verdict, tuple[str, colors.Color]] = {
    Verdict.AUTHENTIC: ("LIKELY AUTHENTIC", colors.HexColor("#2e7d32")),
    Verdict.MANIPULATED: ("LIKELY MANIPULATED", colors.HexColor("#c62828")),
    Verdict.INCONCLUSIVE: ("INCONCLUSIVE", colors.HexColor("#f9a825")),
}

DISCLAIMER = (
    "This report is an automated technical assessment produced by a machine-learning "
    "system. It is <b>not</b> a certified forensic or legal determination, and it has not "
    "been reviewed by a qualified forensic examiner. Automated deepfake detectors produce "
    "both false positives (authentic media flagged as manipulated) and false negatives "
    "(manipulated media reported as authentic), and their accuracy degrades on "
    "compression, low resolution, and manipulation techniques not represented in their "
    "training data. For legal proceedings, verification by a certified forensic expert or "
    "an accredited government forensic laboratory is recommended. The findings here "
    "should be treated as an investigative lead, not as conclusive proof."
)

METHODOLOGY: dict[str, str] = {
    "image": (
        "The submitted image was scanned for human faces. Each detected face was cropped, "
        "resized, and passed through a convolutional neural network trained to tell apart "
        "authentic photographs from images produced or altered by face-swap, GAN, and "
        "diffusion-based generators. The network outputs a probability between 0 and 1 that "
        "the region is manipulated. The accompanying heatmap highlights, in warmer colours, "
        "the areas of the image that most influenced that decision — commonly the blending "
        "boundary of a swapped face, or inconsistent skin and eye texture."
    ),
    "video": (
        "Frames were sampled from the submitted video at regular intervals rather than "
        "analysing every frame, which keeps processing time practical. In each sampled "
        "frame the largest face was located and cropped, then scored by the same neural "
        "network used for still images. The per-frame scores are plotted over time, so a "
        "manipulation affecting only part of the clip remains visible instead of being "
        "averaged away. The overall video score is the mean of the highest-scoring quarter "
        "of frames."
    ),
    "audio": (
        "The submitted audio was converted to a standard 16 kHz mono signal, silence was "
        "trimmed, and the clip was divided into short consecutive windows. Each window was "
        "transformed into a log-Mel spectrogram — a visual representation of how the sound's "
        "frequency content changes over time — and scored by a neural network trained on "
        "the ASVspoof anti-spoofing benchmark to distinguish genuine human speech from "
        "text-to-speech and voice-cloned speech. Synthetic speech typically leaves "
        "artefacts in the higher frequency bands that are hard to hear but measurable. "
        "The spectrogram in this report marks the flagged windows in red."
    ),
}


@dataclass
class ReportArtifacts:
    path: Path
    sha256: str
    report_reference: str
    generated_at: datetime


def generate_report(
    job: Job,
    output_dir: str | Path | None = None,
    *,
    evidence_dir: str | Path | None = None,
    requester: str | None = None,
) -> ReportArtifacts:
    """Render the forensic PDF for a completed job.

    Returns the file path, the SHA-256 printed inside the document, and the
    unique report reference.
    """
    output_dir = Path(output_dir or settings.report_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    evidence_dir = Path(evidence_dir or settings.evidence_dir)

    generated_at = datetime.now(UTC)
    report_reference = _build_report_reference(job)
    output_path = output_dir / f"{report_reference}.pdf"

    charts = _render_charts(job, evidence_dir, report_reference)

    _build_pdf(job, output_path, report_reference, generated_at, charts, requester)
    document_hash = _sha256_file(output_path)

    return ReportArtifacts(
        path=output_path,
        sha256=document_hash,
        report_reference=report_reference,
        generated_at=generated_at,
    )


def verify_report_hash(pdf_path: str | Path, expected_hash: str) -> bool:
    """True when the PDF on disk still hashes to the registered value.

    This is the same comparison a recipient performs by hand with
    ``shasum -a 256``, so a report that verifies here verifies for them too.
    """
    try:
        return _sha256_file(pdf_path) == expected_hash
    except OSError:
        return False


# --------------------------------------------------------------------------- internals
def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _build_report_reference(job: Job) -> str:
    """One canonical report reference per case, e.g. ``DFR-DF-20260831-8A3C21``.

    Regenerating a report for the same case reuses this reference and replaces
    the stored PDF, so the register always names exactly one current document
    per case rather than accumulating near-identical references.
    """
    return f"DFR-{job.case_reference}"


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title", parent=base["Title"], fontSize=19, leading=23, textColor=ACCENT, spaceAfter=2
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            parent=base["Normal"],
            fontSize=9.5,
            leading=13,
            textColor=MUTED,
            alignment=1,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            fontSize=12.5,
            leading=15,
            textColor=ACCENT,
            spaceBefore=12,
            spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "body", parent=base["BodyText"], fontSize=9.5, leading=13.5, alignment=TA_JUSTIFY
        ),
        "small": ParagraphStyle(
            "small", parent=base["BodyText"], fontSize=8, leading=11, textColor=MUTED
        ),
        "mono": ParagraphStyle(
            "mono", parent=base["BodyText"], fontName="Courier", fontSize=8, leading=11
        ),
        "cell": ParagraphStyle("cell", parent=base["BodyText"], fontSize=8.5, leading=11),
        "cellmono": ParagraphStyle(
            "cellmono", parent=base["BodyText"], fontName="Courier", fontSize=8, leading=10.5
        ),
    }


def _build_pdf(
    job: Job,
    output_path: Path,
    report_reference: str,
    generated_at: datetime,
    charts: dict[str, Path],
    requester: str | None,
) -> None:
    styles = _styles()
    document = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=20 * mm,
        title=f"Forensic Analysis Report {report_reference}",
        author=settings.app_name,
        subject="Automated media authenticity analysis",
    )

    story: list[Any] = []
    story += _section_header(job, report_reference, generated_at, requester, styles)
    story += _section_file_details(job, styles)
    story += _section_analysis_summary(job, charts, styles)
    story += _section_findings(job, charts, styles)
    story += _section_methodology(job, styles)
    story += _section_disclaimer(styles)
    story += _section_integrity(job, report_reference, generated_at, styles)

    document.build(
        story,
        onFirstPage=lambda canvas, doc: _draw_page_furniture(canvas, doc, report_reference),
        onLaterPages=lambda canvas, doc: _draw_page_furniture(canvas, doc, report_reference),
    )


def _draw_page_furniture(canvas, document, report_reference: str) -> None:
    """Footer with the case reference and page number on every page."""
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(20 * mm, 12 * mm, f"{settings.app_name} · Report {report_reference}")
    canvas.drawRightString(PAGE_WIDTH - 20 * mm, 12 * mm, f"Page {document.page}")
    canvas.setStrokeColor(colors.HexColor("#d4dae0"))
    canvas.setLineWidth(0.4)
    canvas.line(20 * mm, 15 * mm, PAGE_WIDTH - 20 * mm, 15 * mm)
    canvas.restoreState()


def _kv_table(
    rows: list[tuple[str, Any]],
    styles: dict[str, ParagraphStyle],
    mono_keys: set[str] | None = None,
) -> Table:
    mono_keys = mono_keys or set()
    data = [
        [
            Paragraph(f"<b>{label}</b>", styles["cell"]),
            Paragraph(str(value), styles["cellmono"] if label in mono_keys else styles["cell"]),
        ]
        for label, value in rows
    ]
    table = Table(data, colWidths=[52 * mm, CONTENT_WIDTH - 52 * mm])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (0, -1), LIGHT),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d4dae0")),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


# --------------------------------------------------------------------- section 1
def _section_header(job, report_reference, generated_at, requester, styles) -> list[Any]:
    return [
        Paragraph("FORENSIC MEDIA AUTHENTICITY REPORT", styles["title"]),
        Paragraph(
            f"{settings.app_name} — automated deepfake analysis<br/>"
            f"Report reference <b>{report_reference}</b> · Case reference "
            f"<b>{job.case_reference}</b>",
            styles["subtitle"],
        ),
        Spacer(1, 4),
        HRFlowable(width="100%", thickness=1.1, color=ACCENT, spaceAfter=8),
        _kv_table(
            [
                ("Report reference", report_reference),
                ("Case reference", job.case_reference),
                ("Generated at (UTC)", generated_at.strftime("%Y-%m-%d %H:%M:%S UTC")),
                ("Requested by", requester or "Anonymous / guest submission"),
                ("Platform version", f"{settings.app_name} v{app_version}"),
                ("Runtime", f"Python {platform.python_version()} on {platform.system()}"),
            ],
            styles,
        ),
    ]


# --------------------------------------------------------------------- section 2
def _section_file_details(job, styles) -> list[Any]:
    uploaded = job.uploaded_at.strftime("%Y-%m-%d %H:%M:%S UTC") if job.uploaded_at else "—"
    return [
        Paragraph("1. Submitted File Details", styles["h2"]),
        Paragraph(
            "The file described below was received and stored without modification. Its "
            "SHA-256 cryptographic hash was computed at the moment of upload; recomputing "
            "that hash on the original file will yield the same value if, and only if, the "
            "file has not been altered since submission.",
            styles["body"],
        ),
        Spacer(1, 5),
        _kv_table(
            [
                ("Original filename", job.original_filename),
                ("Media type", job.media_type.value.capitalize()),
                ("Declared content type", job.content_type),
                (
                    "File size",
                    f"{job.file_size_bytes:,} bytes ({job.file_size_bytes / (1024 * 1024):.2f} MB)",
                ),
                ("SHA-256 of submitted file", job.sha256),
                ("Received at (UTC)", uploaded),
            ],
            styles,
            mono_keys={"SHA-256 of submitted file"},
        ),
    ]


# --------------------------------------------------------------------- section 3
def _section_analysis_summary(job, charts, styles) -> list[Any]:
    label, colour = VERDICT_STYLING.get(job.verdict, ("NOT ANALYSED", MUTED))
    probability = job.fake_probability if job.fake_probability is not None else 0.0
    confidence = job.confidence if job.confidence is not None else 0.0

    verdict_table = Table(
        [
            [
                Paragraph(
                    f'<font color="white"><b>{label}</b></font>',
                    ParagraphStyle(
                        "v", fontSize=13, leading=16, alignment=1, textColor=colors.white
                    ),
                ),
                Paragraph(
                    f"<b>P(manipulated) = {probability * 100:.1f}%</b><br/>"
                    f"<font size=8>Decision confidence {confidence * 100:.1f}% · "
                    f"threshold {settings.fake_threshold:.2f} "
                    f"± {settings.uncertain_band:.2f} uncertain band</font>",
                    ParagraphStyle("vd", fontSize=10, leading=13, alignment=1),
                ),
            ]
        ],
        colWidths=[CONTENT_WIDTH * 0.42, CONTENT_WIDTH * 0.58],
    )
    verdict_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), colour),
                ("BACKGROUND", (1, 0), (1, 0), LIGHT),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#d4dae0")),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ]
        )
    )

    evidence = job.evidence or {}
    rows: list[tuple[str, Any]] = [
        ("Media analysed", job.media_type.value.capitalize()),
        ("Model", job.model_name or "—"),
        ("Model version", job.model_version or "—"),
        ("Weights status", _weights_label(job.weights_status)),
        (
            "Decision threshold",
            f"{settings.fake_threshold:.2f} (± {settings.uncertain_band:.2f} inconclusive band)",
        ),
        ("Processing time", f"{job.processing_ms} ms" if job.processing_ms else "—"),
    ]
    if job.media_type.value == "video":
        rows.append(("Frames analysed", evidence.get("frames_analysed", "—")))
        rows.append(("Frames above threshold", evidence.get("flagged_frames", "—")))
    elif job.media_type.value == "audio":
        rows.append(("Duration", f"{evidence.get('duration_seconds', '—')} s"))
        rows.append(
            (
                "Windows above threshold",
                f"{evidence.get('flagged_segments', '—')} of "
                f"{evidence.get('segments_analysed', '—')}",
            )
        )
    else:
        rows.append(("Faces detected", evidence.get("faces_detected", 0)))

    story: list[Any] = [
        Paragraph("2. Analysis Summary", styles["h2"]),
        verdict_table,
        Spacer(1, 7),
    ]
    gauge = charts.get("gauge")
    if gauge and gauge.exists():
        story += [
            Image(str(gauge), width=CONTENT_WIDTH, height=CONTENT_WIDTH * 1.15 / 7.2),
            Spacer(1, 6),
        ]
    story.append(_kv_table(rows, styles))

    if job.weights_status and job.weights_status != "trained":
        story += [
            Spacer(1, 6),
            _callout(
                "MODEL NOT TRAINED — RESULT IS NOT EVIDENCE",
                "This analysis ran on a network with no trained checkpoint loaded. The score "
                "above is the output of an untrained model and carries no evidentiary value "
                "whatsoever. Do not submit this report in support of a complaint.",
                colors.HexColor("#c62828"),
                styles,
            ),
        ]
    return story


def _weights_label(status: str | None) -> str:
    if status == "trained":
        return "Trained checkpoint loaded"
    if status == "untrained-backbone":
        return "<b>UNTRAINED — demonstration only, not evidential</b>"
    return status or "—"


def _callout(title: str, body: str, colour: colors.Color, styles) -> Table:
    table = Table(
        [
            [
                Paragraph(
                    f'<font color="white"><b>{title}</b></font><br/>'
                    f'<font color="white" size=8.5>{body}</font>',
                    ParagraphStyle("callout", fontSize=9, leading=12),
                )
            ]
        ],
        colWidths=[CONTENT_WIDTH],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colour),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return table


# --------------------------------------------------------------------- section 4
def _section_findings(job, charts, styles) -> list[Any]:
    evidence = job.evidence or {}
    story: list[Any] = [PageBreak(), Paragraph("3. Detailed Findings", styles["h2"])]

    heatmap = charts.get("heatmap")
    if heatmap and heatmap.exists():
        story += [
            Paragraph(
                "<b>3.1 Manipulation heatmap (Grad-CAM)</b><br/>Warmer regions contributed most "
                "strongly to the model's decision. On a face-swap these commonly appear along "
                "the jawline, hairline, or the boundary where a synthetic face was blended "
                "into the original frame.",
                styles["body"],
            ),
            Spacer(1, 5),
            _fitted_image(heatmap, max_width=110 * mm, max_height=95 * mm),
            Spacer(1, 9),
        ]

    spectrogram = charts.get("spectrogram")
    if spectrogram and spectrogram.exists():
        story += [
            Paragraph(
                "<b>3.1 Spectrogram evidence</b><br/>The log-Mel spectrogram of the submitted "
                "audio. Windows the model flagged as synthetic are outlined in red.",
                styles["body"],
            ),
            Spacer(1, 5),
            _fitted_image(spectrogram, max_width=CONTENT_WIDTH, max_height=60 * mm),
            Spacer(1, 9),
        ]

    timeline = charts.get("timeline")
    if timeline and timeline.exists():
        unit = "frame" if job.media_type.value == "video" else "window"
        story += [
            Paragraph(
                f"<b>3.2 Per-{unit} confidence</b><br/>Manipulation probability for each "
                f"analysed {unit}. Points above the dashed threshold line were flagged. A "
                f"manipulation confined to part of the media shows here as a localised peak "
                f"rather than a uniformly raised curve.",
                styles["body"],
            ),
            Spacer(1, 5),
            _fitted_image(timeline, max_width=CONTENT_WIDTH, max_height=52 * mm),
            Spacer(1, 9),
        ]

    detail_table = _findings_table(job, evidence, styles)
    if detail_table is not None:
        story += [
            Paragraph("<b>3.3 Highest-scoring segments</b>", styles["body"]),
            Spacer(1, 4),
            detail_table,
            Spacer(1, 8),
        ]

    notes = evidence.get("notes") or []
    if notes:
        bullets = "".join(f"<br/>• {note}" for note in notes)
        story.append(Paragraph(f"<b>3.4 Analysis notes</b>{bullets}", styles["body"]))

    return story


def _findings_table(job, evidence: dict, styles) -> Table | None:
    """Table of the highest-scoring frames/windows/faces."""
    media = job.media_type.value
    if media == "video":
        rows = sorted(
            evidence.get("frame_scores", []),
            key=lambda item: item["fake_probability"],
            reverse=True,
        )[:10]
        header = ["Frame", "Timestamp (s)", "Face found", "P(manipulated)"]
        body = [
            [
                str(row["index"]),
                f"{row['timestamp']:.2f}",
                "yes" if row.get("face_detected") else "no",
                f"{row['fake_probability'] * 100:.1f}%",
            ]
            for row in rows
        ]
    elif media == "audio":
        rows = sorted(
            evidence.get("segment_scores", []),
            key=lambda item: item["fake_probability"],
            reverse=True,
        )[:10]
        header = ["Window", "Start (s)", "End (s)", "P(manipulated)"]
        body = [
            [
                str(row["index"]),
                f"{row['start']:.2f}",
                f"{row['end']:.2f}",
                f"{row['fake_probability'] * 100:.1f}%",
            ]
            for row in rows
        ]
    else:
        rows = sorted(
            evidence.get("face_scores", []), key=lambda item: item["fake_probability"], reverse=True
        )[:10]
        if not rows:
            return None
        header = ["Region", "Bounding box (x1,y1,x2,y2)", "Detection conf.", "P(manipulated)"]
        body = [
            [
                f"Face {row['index'] + 1}",
                ",".join(str(v) for v in row["box"]) if row.get("box") else "whole image",
                f"{row['detection_confidence'] * 100:.1f}%"
                if row.get("detection_confidence")
                else "—",
                f"{row['fake_probability'] * 100:.1f}%",
            ]
            for row in rows
        ]

    if not body:
        return None

    data = [[Paragraph(f"<b>{cell}</b>", styles["cell"]) for cell in header]]
    data += [[Paragraph(cell, styles["cell"]) for cell in row] for row in body]
    table = Table(
        data, colWidths=[CONTENT_WIDTH * w for w in (0.18, 0.34, 0.24, 0.24)], repeatRows=1
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d4dae0")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 3.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
            ]
        )
    )
    return table


def _fitted_image(path: Path, max_width: float, max_height: float) -> Image:
    """Scale an image to fit a box while preserving its aspect ratio."""
    from PIL import Image as PILImage

    with PILImage.open(path) as opened:
        width, height = opened.size
    scale = min(max_width / width, max_height / height)
    return Image(str(path), width=width * scale, height=height * scale)


# --------------------------------------------------------------------- section 5
def _section_methodology(job, styles) -> list[Any]:
    return [
        Paragraph("4. Methodology", styles["h2"]),
        Paragraph(METHODOLOGY.get(job.media_type.value, ""), styles["body"]),
        Spacer(1, 5),
        Paragraph(
            "The probability reported in section 2 is the model's own confidence, not a "
            "measured error rate. It should be read together with the detection accuracy "
            "figures published for the model version named above.",
            styles["small"],
        ),
    ]


# --------------------------------------------------------------------- section 6
def _section_disclaimer(styles) -> list[Any]:
    return [
        Paragraph("5. Limitations and Disclaimer", styles["h2"]),
        _callout(
            "AUTOMATED ASSESSMENT — NOT A CERTIFIED FORENSIC OPINION",
            DISCLAIMER,
            colors.HexColor("#455a64"),
            styles,
        ),
        Spacer(1, 6),
        Paragraph(
            "This platform produces a technical evidence report only. It does not file, "
            "register, or transmit any complaint to a police service or cybercrime authority, "
            "and it holds no investigative or legal authority. Complaint procedures differ by "
            "jurisdiction; the recipient should confirm the current process with their local "
            "cybercrime unit or national reporting portal before submission.",
            styles["body"],
        ),
    ]


# --------------------------------------------------------------------- section 7
def _section_integrity(job, report_reference, generated_at, styles) -> list[Any]:
    return [
        Paragraph("6. Report Integrity and Chain of Custody", styles["h2"]),
        Paragraph(
            "Two hashes secure this report. The first covers the media that was analysed and "
            "is printed below. The second covers this PDF itself: a document cannot contain "
            "its own hash, so that value is held in the platform's report register against "
            "the reference below and is published by the verification endpoint. Either hash "
            "changes completely if a single byte of the corresponding file is altered.",
            styles["body"],
        ),
        Spacer(1, 5),
        KeepTogether(
            _kv_table(
                [
                    ("SHA-256 of analysed file", job.sha256),
                    ("Report reference", report_reference),
                    ("Generated at (UTC)", generated_at.strftime("%Y-%m-%d %H:%M:%S UTC")),
                    ("Report hash register", f"GET /api/reports/{report_reference}/verify"),
                ],
                styles,
                mono_keys={"SHA-256 of analysed file", "Report hash register"},
            )
        ),
        Spacer(1, 6),
        Paragraph(
            "<b>How to verify.</b> Compute the SHA-256 of a file with "
            "<font face='Courier'>shasum -a 256 &lt;file&gt;</font> on Linux or macOS, or "
            "<font face='Courier'>certutil -hashfile &lt;file&gt; SHA256</font> on Windows. "
            "Run it on the original media and confirm the result equals the value printed "
            "above. Run it on this PDF and confirm the result equals the hash the register "
            f"endpoint returns for report <b>{report_reference}</b>. Both checks must pass "
            "for the report and the media it describes to be considered unaltered.",
            styles["small"],
        ),
        Spacer(1, 4),
        Paragraph(
            "This report is not cryptographically signed. Hashes detect accidental or casual "
            "alteration; they are not a substitute for a digital signature issued by a "
            "recognised certifying authority, and the register value is only as trustworthy "
            "as the platform that publishes it.",
            styles["small"],
        ),
    ]


# --------------------------------------------------------------------- charts
def _render_charts(job: Job, evidence_dir: Path, report_reference: str) -> dict[str, Path]:
    """Render/collect every image the report embeds."""
    evidence = job.evidence or {}
    charts: dict[str, Path] = {}
    chart_dir = evidence_dir / "report_charts"

    if job.fake_probability is not None:
        # Charts are supporting evidence: a rendering failure must not block
        # the report, which still carries the score, hashes and disclaimers.
        with contextlib.suppress(Exception):
            charts["gauge"] = confidence_gauge(
                job.fake_probability, chart_dir / f"{report_reference}_gauge.png"
            )

    for key, filename in (
        ("heatmap", evidence.get("heatmap_file")),
        ("spectrogram", evidence.get("spectrogram_file")),
    ):
        if filename:
            candidate = evidence_dir / filename
            if candidate.exists():
                charts[key] = candidate

    points = evidence.get("frame_scores") or evidence.get("segment_scores")
    if points and len(points) > 1:
        is_video = bool(evidence.get("frame_scores"))
        with contextlib.suppress(Exception):
            charts["timeline"] = confidence_timeline(
                points,
                chart_dir / f"{report_reference}_timeline.png",
                x_key="timestamp" if is_video else "start",
                x_label="Time (seconds)",
                title="Per-frame manipulation probability"
                if is_video
                else "Per-window synthetic-speech probability",
            )

    return charts
