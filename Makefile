# Deepfake Detection Platform — common tasks.
#   make help          list targets
#   make install       install backend + frontend dependencies
#   make dev           run API and frontend together
#   make train-all     preprocess, train and evaluate both detectors
#   make verify        check which checkpoints the backend will load

SHELL := /bin/bash
PY    ?= python3
DATA  ?= data
PROC  ?= $(DATA)/processed
EPOCHS_IMAGE ?= 15
EPOCHS_AUDIO ?= 20
BACKBONE ?= efficientnet_b0

.DEFAULT_GOAL := help
.PHONY: help install install-backend install-frontend hooks dev api web worker \
        test test-frontend coverage lint lint-frontend format typecheck build check audit \
        migrate migration migrate-down datasets data-faces data-audio \
        train-image train-audio train-all evaluate evaluate-image evaluate-audio \
        verify clean clean-data

help:  ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------- setup
install: install-backend install-frontend  ## Install all dependencies

install-backend:  ## Install Python dependencies (includes PyTorch, ~2 GB)
	$(PY) -m pip install -r backend/requirements-ml.txt -r backend/requirements-dev.txt

install-frontend:  ## Install frontend dependencies
	cd frontend && npm install

hooks:  ## Install pre-commit hooks (runs CI's gates before each commit)
	$(PY) -m pip install pre-commit && pre-commit install

# ---------------------------------------------------------------- run
dev:  ## Run API and frontend together (Ctrl-C stops both)
	@echo "API  -> http://localhost:8000/docs"
	@echo "Web  -> http://localhost:5173"
	@trap 'kill 0' EXIT INT TERM; \
	 (cd backend && uvicorn app.main:app --reload) & \
	 (cd frontend && npm run dev) & \
	 wait

api:  ## Run only the API
	cd backend && uvicorn app.main:app --reload

web:  ## Run only the frontend
	cd frontend && npm run dev

worker:  ## Run a Celery worker (needs CELERY_BROKER_URL and a running Redis)
	cd backend && celery -A app.worker.celery_app.celery_app worker --loglevel=info

# ---------------------------------------------------------------- quality
test:  ## Run the backend test suite
	cd backend && $(PY) -m pytest

test-frontend:  ## Run the frontend test suite
	cd frontend && npm run test -- --run

coverage:  ## Backend tests with a coverage report
	cd backend && $(PY) -m pytest --cov=app --cov-report=term-missing

lint:  ## Lint Python
	$(PY) -m ruff check backend ml scripts
	$(PY) -m ruff format --check backend ml scripts

lint-frontend:  ## Lint the frontend
	cd frontend && npm run lint

format:  ## Auto-format Python
	$(PY) -m ruff check --fix backend ml scripts
	$(PY) -m ruff format backend ml scripts

audit:  ## Dependency and static security scan (as CI runs it)
	$(PY) -m pip install --quiet pip-audit bandit
	$(PY) -m pip_audit -r backend/requirements.txt --strict || true
	$(PY) -m bandit -r backend/app ml scripts -ll

build:  ## Build the production frontend bundle
	cd frontend && npm run build

check: lint lint-frontend test test-frontend build  ## Everything CI would run

# ---------------------------------------------------------------- database
migrate:  ## Apply migrations up to head
	cd backend && $(PY) -m alembic upgrade head

migration:  ## Autogenerate a migration (make migration M="what changed")
	@test -n "$(M)" || { echo 'usage: make migration M="what changed"'; exit 1; }
	cd backend && $(PY) -m alembic revision --autogenerate -m "$(M)"

migrate-down:  ## Roll back one migration
	cd backend && $(PY) -m alembic downgrade -1

# ---------------------------------------------------------------- data
datasets:  ## List datasets that download without an approval process
	$(PY) scripts/fetch_datasets.py --list

data-faces:  ## Build the face-crop dataset (set REAL_DIR and FAKE_DIR)
	@test -n "$(REAL_DIR)" -a -n "$(FAKE_DIR)" || \
	  { echo "usage: make data-faces REAL_DIR=... FAKE_DIR=..."; exit 1; }
	$(PY) ml/preprocessing/build_face_dataset.py \
	  --real-dir $(REAL_DIR) --fake-dir $(FAKE_DIR) --output $(PROC)/faces

data-audio:  ## Build the audio-window dataset (set BONAFIDE_DIR and SPOOF_DIR)
	@test -n "$(BONAFIDE_DIR)" -a -n "$(SPOOF_DIR)" || \
	  { echo "usage: make data-audio BONAFIDE_DIR=... SPOOF_DIR=..."; exit 1; }
	$(PY) ml/preprocessing/build_audio_dataset.py \
	  --bonafide-dir $(BONAFIDE_DIR) --spoof-dir $(SPOOF_DIR) --output $(PROC)/audio

# ---------------------------------------------------------------- training
train-image:  ## Train the image/video detector
	$(PY) ml/training/train_image.py --data $(PROC)/faces \
	  --backbone $(BACKBONE) --epochs $(EPOCHS_IMAGE)

train-audio:  ## Train the audio detector
	$(PY) ml/training/train_audio.py --data $(PROC)/audio --epochs $(EPOCHS_AUDIO)

train-all: train-image train-audio evaluate verify  ## Train both, evaluate, then verify

evaluate-image:  ## Evaluate the image detector on its held-out test split
	$(PY) ml/evaluation/evaluate.py --model image --data $(PROC)/faces \
	  --backbone $(BACKBONE) --checkpoint checkpoints/image_detector.pt

evaluate-audio:  ## Evaluate the audio detector on its held-out test split
	$(PY) ml/evaluation/evaluate.py --model audio --data $(PROC)/audio \
	  --checkpoint checkpoints/audio_detector.pt

evaluate: evaluate-image evaluate-audio  ## Evaluate both detectors

verify:  ## Report which checkpoints the backend will load
	$(PY) scripts/verify_checkpoints.py

# ---------------------------------------------------------------- cleanup
clean:  ## Remove build artefacts and caches
	find . -name __pycache__ -type d -not -path "./frontend/node_modules/*" \
	  -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache backend/.pytest_cache frontend/dist

clean-data:  ## Remove processed datasets (raw downloads are kept)
	rm -rf $(PROC)
