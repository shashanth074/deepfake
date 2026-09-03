# Project Phases and Timeline

The ten build phases from the project guide, and where each one lives in this
repository.

| Phase | Weeks | Deliverable | Where it lives |
|---|---|---|---|
| 1. Planning & requirements | 1 | Scope, roles, non-functional requirements, ER diagram | `docs/architecture.md`, this file |
| 2. Dataset collection | 2–3 | Access to FF++, Celeb-DF, DFDC, ASVspoof, WaveFake | `docs/datasets.md` |
| 3. Preprocessing | 4 | Frame sampling, face cropping, audio windowing, splits | `ml/preprocessing/`, `backend/app/ml/preprocessing.py` |
| 4. Model training | 5–8 | Trained image and audio detectors | `ml/training/` |
| 5. Evaluation | 9 | Accuracy, P/R/F1, AUC-ROC, EER, confusion matrix | `ml/evaluation/` |
| 6. Backend API | 9–10 | Auth, upload, job queue, results | `backend/app/routers/`, `backend/app/worker/` |
| 7. Frontend | 10–12 | Landing, upload, dashboard, report, history | `frontend/src/pages/` |
| 8. Forensic report | 12–13 | Seven-section PDF with hashes and disclaimers | `backend/app/report/` |
| 9. Integration & testing | 13–14 | Unit + integration tests, UX polish | `backend/tests/` |
| 10. Deployment | 15 | Docker, compose, Nginx, HTTPS | `docker-compose.yml`, `docs/deployment.md` |
| Documentation | 16 | Report, slides, viva preparation | `docs/` |

## Scope

**In scope.** Face-swap, GAN and diffusion-generated images; TTS and
voice-cloned audio; face-swap and lip-sync video. Single-file analysis with a
downloadable report.

**Out of scope.** Deepfake *generation*; filing complaints with any authority;
live stream analysis; identifying *who* created a manipulation; provenance
metadata standards such as C2PA (a good extension); text-based misinformation.

**User roles.** Guests get a limited number of scans per hour and can view their
own results by unguessable link. Registered users get a higher limit, scan
history, and the erasure endpoint.

**Non-functional requirements.** Uploads up to 100 MB; jpg/png/webp/bmp,
wav/mp3/flac/m4a/ogg, mp4/mov/avi/mkv/webm; images analysed in a few seconds,
video roughly one second per sampled frame on CPU; strict file-type validation
including magic-number checks; rate limiting per account and per IP.

## Evaluation checklist for the viva

- [ ] Per-model accuracy, precision, recall, F1 and AUC-ROC on the held-out test split
- [ ] Confusion matrix per model (`ml/evaluation/evaluate.py` renders these)
- [ ] Architecture comparison table (EfficientNet vs Xception — both are implemented)
- [ ] Qualitative examples: real and fake samples with scores and Grad-CAM heatmaps side by side
- [ ] End-to-end processing time per media type
- [ ] Results on samples generated yourself and never seen in training — this
      demonstrates real generalisation far more convincingly than in-dataset accuracy
- [ ] Explicit statement of which weights you trained and which you inherited

## Pitfalls this codebase already guards against

| Pitfall | Guard |
|---|---|
| Data leakage across splits | `split_by_group()` splits by source video/speaker, never by frame |
| Overfitting to one dataset | Augmentation includes JPEG recompression and blur; test on WildDeepfake too |
| Ignoring class imbalance | `--balance` on the preprocessing scripts, `pos_weight` in training, false-positive rate reported |
| Treating output as certainty | Three-way verdict with an uncertain band; confidence reported separately |
| Slow video processing | Frames sampled at 1 fps with a hard cap, not decoded exhaustively |
| Skipping the legal framing | Disclaimers in the UI, the API response and the PDF |
