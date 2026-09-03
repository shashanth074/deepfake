# System Architecture

## Why the system is decoupled

Inference is slow and bursty: a 30-second video at one frame per second means 30
forward passes, which is far past an acceptable HTTP request. Splitting the
system into an API and a worker keeps the site responsive while heavy models
run, and lets the two scale independently — the API is I/O-bound, the worker is
compute-bound.

## Components

| Layer | Responsibility | Technology |
|---|---|---|
| Frontend | Upload UI, result dashboard, report download, auth | React 18, Vite, Tailwind, Recharts |
| API | Auth, upload validation, job creation, result serving | FastAPI, Pydantic v2, SQLAlchemy 2 |
| Worker | Runs the detection pipelines | Celery + Redis, PyTorch |
| Database | Users, jobs, evidence metadata, report register | PostgreSQL (SQLite in dev) |
| Storage | Original media, evidence images, generated PDFs | Local volume (S3-compatible in production) |
| Reporting | Forensic PDF assembly | ReportLab + Matplotlib |
| Edge | TLS, static assets, API proxy | Nginx |

## Data flow

```
1. Client uploads a file
2. API validates extension AND magic numbers, streams it to disk,
   computes SHA-256 in the same pass, enforces the size limit mid-stream
3. API creates a Job row (status=queued) and pushes a task to Redis
4. Worker picks it up, sets status=processing, runs the pipeline for that
   media type, writes evidence images to the shared volume
5. Worker writes the score, verdict, model version and evidence JSON back,
   sets status=done
6. Frontend polls /status, then fetches /result
7. User requests a report; the API renders the PDF, hashes it, and records
   the hash in the report register
8. User downloads the PDF and attaches it to their own complaint
```

Steps 2 and 7 are the chain-of-custody spine: hash on arrival, hash on issue.

## Database schema

```
users                      jobs                          reports
─────                      ────                          ───────
id (PK)              ┌────>id (PK)               ┌──────>id (PK)
email (unique)       │     case_reference (uniq) │       job_id (FK) ──┐
full_name            │     user_id (FK) ─────────┘       report_reference (uniq)
hashed_password      │     original_filename             file_path
is_active            │     stored_path                   sha256
created_at           │     media_type                    generated_at
                     │     content_type                                │
                     │     file_size_bytes        <──────────────────── ┘
upload_events        │     sha256          ← hash recorded at upload
─────────────        │     uploaded_at
id (PK)              │     status                (queued/processing/done/failed)
user_id ─────────────┘     started_at, finished_at, error_message
client_ip                  verdict                (authentic/manipulated/inconclusive)
created_at                 fake_probability, confidence
                           model_name, model_version, weights_status
                           processing_ms
                           evidence (JSON: frame/segment scores, heatmap file, notes)
```

`upload_events` exists separately from `jobs` so rate limiting still counts
rejected uploads and survives a user deleting their history.

## Verdict model

A single probability drives a three-way verdict:

```
        0.0 ─────────── 0.35 ────── 0.65 ─────────── 1.0
        │  likely authentic │ inconclusive │ likely manipulated │
```

The band is `FAKE_THRESHOLD ± UNCERTAIN_BAND`. Confidence is reported separately
as `|p − 0.5| × 2`, so a score of 0.5 shows as zero confidence rather than as a
coin-flip verdict presented with certainty.

## Aggregation for video and audio

Both aggregate per-unit scores as **the mean of the top-scoring 25%**, not a
plain mean. A face swap often affects only part of a clip; averaging every frame
would dilute a genuine localised manipulation into noise. The full per-unit
curve is kept and plotted so a reviewer can see where the peak is.

## Model loading

`backend/app/ml/registry.py` caches each model per process behind a lock, and the Celery
`worker_process_init` signal warms them at startup. When no checkpoint file is
present the model still loads, but is tagged `untrained-backbone`, which
propagates to the API response, the UI banner, and a red warning block in the
PDF.

## Failure handling

| Failure | Behaviour |
|---|---|
| Corrupt/undecodable media | Job marked `failed` with a user-facing message; not retried |
| Missing PyTorch | `DetectorUnavailableError`; job fails with an actionable message |
| Missing face detector | Falls back to whole-frame analysis, records a note in the evidence. MTCNN weights ship inside the `facenet-pytorch` wheel, so detection works offline once installed — no model download is needed. |
| Missing librosa/soundfile | Falls back to the stdlib WAV reader |
| Grad-CAM failure | Report is still produced; the numeric score is unaffected |
| Worker dies mid-task | `task_acks_late` redelivers the job |
