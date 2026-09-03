# Datasets

You do not need to create deepfakes yourself. Use the established, citable
research datasets below.

Most require an academic-use request form signed with an institutional email,
and approval can take days — **start these requests in week 1.**

## Image and video

| Dataset | Content | Access |
|---|---|---|
| FaceForensics++ | 1000 real + manipulated videos (DeepFakes, Face2Face, FaceSwap, NeuralTextures) | [github.com/ondyari/FaceForensics](https://github.com/ondyari/FaceForensics) — academic email required |
| Celeb-DF (v2) | 590 real + 5,639 high-quality celebrity deepfakes | [github.com/yuezunli/celeb-deepfakeforensics](https://github.com/yuezunli/celeb-deepfakeforensics) |
| DFDC | ~128,000 videos (Meta/AWS/Microsoft) | Kaggle: "Deepfake Detection Challenge" |
| WildDeepfake | Real-world deepfakes scraped from the internet — harder and more diverse | GitHub: deepfakeinthewild |
| 140k Real and Fake Faces | StyleGAN-generated vs real faces | Kaggle, open access |
| DFFD | GAN synthesis, face swap, expression manipulation | cvlab.cse.msu.edu (request) |

## Audio

| Dataset | Content | Access |
|---|---|---|
| ASVspoof 2019 / 2021 | Bonafide vs spoofed (TTS/VC) speech — the standard benchmark | [asvspoof.org](https://www.asvspoof.org) — free registration |
| WaveFake | Audio from 6 neural vocoders (MelGAN, WaveGlow, …) | Zenodo, open access |
| In-The-Wild Audio Deepfake | Real-world cloned celebrity/politician speech | deepfake-total.com |
| FoR (Fake or Real) | Large TTS vs human speech corpus | Kaggle |

## If access does not arrive in time

- **Kaggle-hosted subsets** (140k Real/Fake Faces, the DFDC sample set, FoR)
  download instantly with no request process — enough for a working prototype.
- **Pretrained weights** released alongside these datasets can be fine-tuned on
  whatever subset you can access. This is normal practice.
- **Document exactly what you trained yourself versus what you inherited.**
  Examiners respect that far more than a vague claim of full training.

## Expected layout

The preprocessing scripts take two directories per modality:

```
data/raw/
├── real/          → --real-dir       (authentic videos or images)
├── fake/          → --fake-dir       (manipulated videos or images)
├── bonafide/      → --bonafide-dir   (genuine speech)
└── spoof/         → --spoof-dir      (TTS / voice-converted speech)
```

Filenames matter: the source file stem becomes the *group* used to keep an
identity entirely inside one split. For ASVspoof-style corpora the speaker is
taken from the filename prefix (`LA_0079_…`); pass `--speaker-from parent` when
your layout uses one directory per speaker instead.

## Citations

- Rössler et al., *FaceForensics++: Learning to Detect Manipulated Facial Images*, ICCV 2019
- Li et al., *Celeb-DF: A Large-Scale Challenging Dataset for DeepFake Forensics*, CVPR 2020
- Dolhansky et al., *The DeepFake Detection Challenge (DFDC) Dataset*, 2020
- Zi et al., *WildDeepfake: A Challenging Real-World Dataset for Deepfake Detection*, ACM MM 2020
- Todisco et al., *ASVspoof 2019: A Large-Scale Public Database of Synthesized, Converted and Replayed Speech*, 2019
- Frank & Schönherr, *WaveFake: A Data Set to Facilitate Audio Deepfake Detection*, 2021
- Chollet, *Xception: Deep Learning with Depthwise Separable Convolutions*, CVPR 2017
- Tak et al., *End-to-End Anti-Spoofing with RawNet2*, ICASSP 2021
- Selvaraju et al., *Grad-CAM: Visual Explanations from Deep Networks via Gradient-based Localization*, ICCV 2017
