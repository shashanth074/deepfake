# Deepfake Detection System

Image, audio and video forensic analysis platform. Upload suspected media, get a
confidence score with visual evidence, and download a timestamped PDF forensic
report suitable for attaching to a cybercrime complaint.

Built as a final-year project following the ten-phase development guide in
[`docs/project-guide.pdf`](docs/project-guide.pdf).

> **This platform produces an automated technical assessment, not a certified
> forensic opinion, and it does not file complaints with any authority.** It
> generates the evidence document a complainant can submit themselves.

---

## What it does

| Media | Detects | Evidence produced |
|---|---|---|
| **Image** | Face swaps, GAN faces, diffusion-generated imagery | Grad-CAM heatmap over the analysed region |
| **Audio** | Voice cloning, TTS-synthesised speech | Log-Mel spectrogram with flagged windows outlined |
| **Video** | Face-swap deepfakes, temporal inconsistency | Per-frame confidence curve + heatmap of the worst frame |

Every result is a probability with an explicit uncertain band — scores near the
threshold are reported as **inconclusive** rather than forced into a yes or no.

## Architecture

```
      Browser (React + Tailwind)
              │  HTTPS
              ▼
      Nginx  ──►  FastAPI  ──►  PostgreSQL      (users, jobs, report register)
                    │
                    ├──►  Object/file storage   (originals kept byte-identical)
                    │
                    └──►  Redis queue  ──►  Celery worker
                                              ├── image pipeline  (EfficientNet/Xception + Grad-CAM)
                                              ├── audio pipeline  (LCNN over log-Mel)
                                              └── video pipeline  (frame sampling + aggregation)
                                                        │
                                                        ▼
                                              ReportLab  ──►  forensic PDF
```

Inference runs in a separate worker process because a 30-second video is far
past an acceptable HTTP request. Models load once per worker at startup, not
per request.

## Quick start

### Docker (everything at once)

```bash
cp .env.example .env
# set JWT_SECRET_KEY and POSTGRES_PASSWORD, then:
docker compose up --build
```

Frontend on <http://localhost:8080>, API docs on <http://localhost:8000/docs>.

### Local development

```bash
# --- backend ---
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements-ml.txt      # or requirements.txt for API only
cd backend && uvicorn app.main:app --reload

# --- frontend (second terminal) ---
cd frontend && npm install && npm run dev
```

With no `CELERY_BROKER_URL` set, analysis runs inline — no Redis, no worker, no
PostgreSQL needed. SQLite and the local filesystem are the defaults.

To run a real queue locally:

```bash
celery -A app.worker.celery_app.celery_app worker --loglevel=info
```

## Training the models

**The API ships with no trained checkpoints, and none are committed to this
repository.** Until you train or install them, every result is labelled
`untrained-backbone` and flagged as non-evidential in the UI *and* in the
generated PDF. That is deliberate: a demo build must never be mistaken for a
forensic one, least of all by a police officer reading the report.

Trained weights cannot ship here for a further reason — FaceForensics++,
Celeb-DF, DFDC and ASVspoof are released under academic-use agreements signed by
a named researcher at a named institution. That signature has to be yours.

Train on a GPU. [`notebooks/train_on_colab.ipynb`](notebooks/train_on_colab.ipynb)
runs the whole pipeline on a Colab GPU and exports the checkpoints to Drive;
that is the fastest route if you have no GPU of your own.

```bash
# 0. What downloads without an approval process
python scripts/fetch_datasets.py --list
python scripts/fetch_datasets.py faces-140k        # needs a Kaggle API token

# 1. Prepare data (splits by source video / speaker, never by frame)
make data-faces REAL_DIR=data/raw/faces-140k/real FAKE_DIR=data/raw/faces-140k/fake
make data-audio BONAFIDE_DIR=... SPOOF_DIR=...

# 2. Train, evaluate and verify in one go
make train-all
```

Add `--face-detection off` when your images are already cropped faces (the 140k
dataset is); leave it on for full scenes and video frames.

Then confirm the handoff:

```bash
make verify        # reports exactly what the UI and the PDF will say
```

`make verify` also catches a trap worth knowing about: a model can reach an
excellent validation AUC and still return **the same score for every input**
once switched to eval mode, because BatchNorm's running statistics converge much
more slowly than the weights. It looks like a serving bug and is not one — it
means train longer, on more data.

Checkpoints land in `checkpoints/` (gitignored — they are large binaries), and
the backend loads them at the next API/worker start. See `ml/README.md` for the
full workflow and `docs/datasets.md` for dataset access.

## API

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/auth/register`, `/api/auth/login` | POST | Account creation and JWT login |
| `/api/upload` | POST | Accept media, hash it, create a job |
| `/api/jobs/{id}/status` | GET | Poll: queued / processing / done / failed |
| `/api/jobs/{id}/result` | GET | Verdict, confidence, evidence |
| `/api/jobs/{id}/evidence/{kind}` | GET | Heatmap or spectrogram image |
| `/api/jobs/{id}/report` | POST / GET | Generate / download the forensic PDF |
| `/api/reports/{ref}/verify` | GET | **Public**: the registered SHA-256 of a report |
| `/api/history` | GET | A user's past scans |
| `/api/history/{id}` | DELETE | Erase a scan and all its files |

Interactive documentation at `/docs`.

## Chain of custody

1. The SHA-256 of every upload is computed **during** the streaming write and
   stored with the job. The original bytes are never modified.
2. That hash is printed in the report, so a recipient can confirm the analysed
   file is the one they hold.
3. The finished PDF is itself hashed, and that value is published by the public
   `/api/reports/{ref}/verify` endpoint. A document cannot contain its own hash,
   so the report points at the register rather than printing a value that could
   never reproduce.

Both checks use ordinary tools:

```bash
shasum -a 256 evidence.mp4     # must equal the hash printed in the report
shasum -a 256 report.pdf       # must equal the hash the verify endpoint returns
```

## Testing

```bash
make check          # lint + tests + frontend build
make test           # 111 backend tests
make verify         # which checkpoints the backend will load
```

`make help` lists every target.

Tests run against an isolated temporary database and storage tree; they never
touch your real data. Pipeline tests skip automatically when PyTorch is absent.

## Repository layout

```
backend/          FastAPI app, ML pipelines, Celery worker, report generator
  app/ml/         image, audio and video detection + Grad-CAM
  app/report/     ReportLab forensic PDF
  tests/          pytest suite
ml/               offline training: preprocessing, training, evaluation
frontend/         React + Vite + Tailwind SPA
scripts/          dataset download, checkpoint verification
notebooks/        Colab GPU training notebook
docs/             architecture, datasets, legal & ethics, project phases
```

## Documentation

- [`docs/architecture.md`](docs/architecture.md) — components, data flow, schema
- [`docs/datasets.md`](docs/datasets.md) — dataset access and citations
- [`docs/legal-and-ethics.md`](docs/legal-and-ethics.md) — chain of custody, data protection, limitations
- [`docs/project-phases.md`](docs/project-phases.md) — the ten build phases and timeline
- [`docs/deployment.md`](docs/deployment.md) — production deployment and hardening

## Limitations

Detection accuracy drops sharply on recompressed and low-resolution media, and
on manipulation techniques absent from the training data. Real uploads are
overwhelmingly authentic, so the false-positive rate matters more than headline
accuracy — an authentic file wrongly flagged is a person wrongly accused. These
limitations are stated in the UI and reproduced in every generated report.
