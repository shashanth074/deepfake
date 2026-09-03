# Deployment

## Docker Compose (recommended)

```bash
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"   # JWT_SECRET_KEY
# set JWT_SECRET_KEY and POSTGRES_PASSWORD in .env
docker compose up --build -d
```

Services: `frontend` (Nginx, :8080), `api` (:8000), `worker`, `db`, `redis`.
The API and worker share a `media` volume — the API writes uploads, the worker
reads them and writes evidence back, so both must mount it.

Checkpoints are mounted read-only from `./checkpoints`. Put your trained
`image_detector.pt` and `audio_detector.pt` there before deploying; without them
every result is flagged non-evidential.

## Secrets

Never commit `.env`. `JWT_SECRET_KEY` and `POSTGRES_PASSWORD` have no defaults
in `docker-compose.yml` — the stack refuses to start without them, which is
preferable to silently booting with a known-insecure default.

Rotating `JWT_SECRET_KEY` invalidates every issued token, which is exactly what
you want after a suspected compromise.

## HTTPS

Terminate TLS at a reverse proxy in front of the `frontend` service:

```bash
sudo certbot --nginx -d yourdomain.example
```

Then set `CORS_ORIGINS=https://yourdomain.example` and restart the API. Uploaded
media is sensitive personal data; do not run this over plain HTTP.

## CPU vs GPU inference

The backend image installs the CPU build of PyTorch, which is right for a
student deployment. GPU hosting is expensive and inference on a handful of
sampled frames is tolerable on CPU.

To trade accuracy for speed, set `IMAGE_MODEL_BACKBONE=efficientnet_b0` (the
default) rather than `efficientnet_b4` or `xception`, and mention that trade-off
explicitly in your report as a scalability consideration.

For GPU inference: base the worker image on `nvidia/cuda`, install the matching
torch build, set `DEVICE=cuda`, and give the container `--gpus all`. Only the
worker needs the GPU — the API never runs a model.

## Scaling

- Add worker replicas (`docker compose up --scale worker=3`). Redis distributes
  tasks and `worker_prefetch_multiplier=1` stops one worker hoarding the queue.
- The API is stateless behind the shared database and volume, so it scales
  horizontally too.
- Move media to S3-compatible object storage before running more than one host —
  the shared local volume is the limiting factor.

## Monitoring

- `GET /api/health` reports version, queue mode and per-model checkpoint status;
  it is wired to the container `HEALTHCHECK`.
- Jobs record `started_at`, `finished_at`, `processing_ms` and `error_message`,
  so failures are queryable without log spelunking.
- Have the logs of a running worker to hand during a live demo; a model that
  fails to load is otherwise silent until the first upload.

## Pre-deployment checklist

- [ ] `JWT_SECRET_KEY` and `POSTGRES_PASSWORD` set to generated values
- [ ] `DEBUG=false`, `ENVIRONMENT=production`
- [ ] `CORS_ORIGINS` restricted to your real frontend origin
- [ ] Trained checkpoints present in `./checkpoints`
- [ ] TLS terminating in front of the frontend
- [ ] `client_max_body_size` in `nginx.conf` ≥ `MAX_UPLOAD_MB`
- [ ] Storage volume encrypted at rest, with a published retention policy
- [ ] Database backups configured
