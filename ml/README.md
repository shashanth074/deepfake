# Training & Evaluation Pipeline

Everything in this directory is offline tooling: dataset preparation, model
training, and evaluation. The API in `backend/` only *serves* the checkpoints
these scripts produce.

Preprocessing transforms are imported from `backend/app/ml/preprocessing.py`, so
training and serving cannot silently drift apart.

## 0. Get data

```bash
python scripts/fetch_datasets.py --list      # what downloads without approval
python scripts/fetch_datasets.py faces-140k  # needs a Kaggle API token
```

Datasets behind an academic-use agreement (FaceForensics++, Celeb-DF, DFDC,
WildDeepfake, ASVspoof) must be requested by you — no script can accept those
terms on your behalf. See `docs/datasets.md`.

## 1. Prepare data

Videos → sampled frames → cropped faces:

```bash
python ml/preprocessing/build_face_dataset.py \
    --real-dir  data/raw/ff++/original \
    --fake-dir  data/raw/ff++/manipulated \
    --output    data/processed/faces \
    --fps 1.0 --max-frames 32
```

Audio → fixed-length windows:

```bash
python ml/preprocessing/build_audio_dataset.py \
    --bonafide-dir data/raw/asvspoof/bonafide \
    --spoof-dir    data/raw/asvspoof/spoof \
    --output       data/processed/audio
```

Add `--face-detection off` when the images are already cropped faces (as in the
140k Real and Fake Faces dataset); leave detection on for full scenes and video
frames. Without `facenet-pytorch` installed, the script says so and falls back to
whole images rather than silently producing an empty dataset.

Both scripts split **by source video / speaker, never by frame or window**. This
is the single most common way to inflate deepfake-detection accuracy: frames
from the same video landing in both train and test make the model look far
better than it is.

## 2. Train

```bash
python ml/training/train_image.py --data data/processed/faces \
    --backbone efficientnet_b0 --epochs 15 --batch-size 32 --lr 1e-4

python ml/training/train_audio.py --data data/processed/audio \
    --epochs 20 --batch-size 64 --lr 1e-4
```

Checkpoints are written to `checkpoints/image_detector.pt` and
`checkpoints/audio_detector.pt` — the exact paths the backend loads. Training
curves are written as CSV alongside them for your report.

## 3. Evaluate

```bash
python ml/evaluation/evaluate.py --model image --data data/processed/faces \
    --checkpoint checkpoints/image_detector.pt --output reports/eval_image
```

Produces accuracy, precision, recall, F1, AUC-ROC, EER, a confusion matrix, and
ROC/PR curve images — the exact figures the project report and viva slides need.

## Dataset sources

See `docs/datasets.md` for access links and request procedures for
FaceForensics++, Celeb-DF, DFDC, WildDeepfake, ASVspoof and WaveFake.
