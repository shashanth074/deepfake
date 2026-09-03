import { useState } from 'react'
import { Link } from 'react-router-dom'
import { motion, useScroll, useTransform, useSpring } from 'framer-motion'
import { Card, Notice } from '../components/ui'
import {
  Activity,
  ArrowRight,
  CheckCircle,
  Copy,
  Cpu,
  Eye,
  FileText,
  Hash,
  Image as ImageIcon,
  Lock,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Upload,
  Video as VideoIcon,
  Waveform,
  Zap,
} from '../components/ui/Icons'

const METRICS = [
  { label: 'Validation Accuracy', value: '99.9%', hint: 'Trained on 140k dataset', icon: Zap, color: 'var(--accent)' },
  { label: 'Inference Latency', value: '< 120ms', hint: 'CUDA accelerated on GPU', icon: Cpu, color: 'var(--status-good)' },
  { label: 'Equal Error Rate', value: '0.0011', hint: 'State-of-the-art benchmark', icon: Activity, color: '#8b5cf6' },
  { label: 'Attestation', value: 'SHA-256', hint: 'Cryptographic chain of custody', icon: Hash, color: 'var(--status-warn)' },
]

const STORY_CHAPTERS = [
  {
    num: '01',
    phase: 'STAGE 1 // INGESTION & SEAL',
    title: 'Cryptographic Chain of Custody',
    tagline: 'Tamper-proof file registration before a single tensor is evaluated.',
    description:
      'The moment an image, voice recording, or video arrives, an immutable SHA-256 cryptographic digest is computed. The file is locked in an isolated enclave, ensuring full forensic chain of custody that satisfies legal evidentiary standards.',
    icon: Hash,
    color: '#3987e5',
    detail: 'SHA-256 Digest Verification · Zero Cloud Exposure · Byte-Level Isolation',
  },
  {
    num: '02',
    phase: 'STAGE 2 // NEURAL ATTRIBUTION',
    title: 'CUDA Tensor Matrix Scoring',
    tagline: 'Deep neural feature extraction calibrated specifically for synthetic artifacts.',
    description:
      'High-throughput neural backbones evaluate the media across spatial and frequency domains. For facial media, MTCNN crops and aligns faces into an EfficientNet-B0 detector. For audio, Light-CNN scans 16kHz Log-Mel spectrograms for voice-clone vocoder signatures.',
    icon: Cpu,
    color: '#8b5cf6',
    detail: 'EfficientNet-B0 + LCNN · 16kHz Spectral Slices · Multi-Face Tracking',
  },
  {
    num: '03',
    phase: 'STAGE 3 // EXPLAINABLE FORENSICS',
    title: 'Visual Attention & Grad-CAM',
    tagline: 'Not just a probability: see the exact boundaries and pixels flagged.',
    description:
      'Neural networks are often black boxes. Veritas computes gradient-weighted class activation maps (Grad-CAM) to pinpoint the exact facial blending seams, eye anomalies, and spectral spikes that drove the model verdict.',
    icon: Eye,
    color: '#f59e0b',
    detail: 'Pixel-Level Heatmaps · Per-Frame Timelines · Frequency Anomaly Highlighting',
  },
  {
    num: '04',
    phase: 'STAGE 4 // CERTIFIED DOSSIER',
    title: 'Automated Forensic Report',
    tagline: 'Court-admissible PDF documentation ready for legal filing.',
    description:
      'Instantly compile findings into a standardized forensic report containing the file hash, model version metadata, decision confidence distributions, and visual Grad-CAM attachments formatted for cybercrime complaints.',
    icon: FileText,
    color: '#10b981',
    detail: 'Tamper-Evident PDF · Methodological Disclosure · Case Reference Attestation',
  },
]

const MODES = [
  {
    id: 'image',
    title: 'Image Forensics',
    backbone: 'EfficientNet-B0',
    icon: ImageIcon,
    desc: 'Spots diffusion blending, GAN artifacts, face-swaps, and boundary smoothing.',
    metrics: '99.9% Accuracy · 42ms GPU Latency',
    features: ['Face extraction & auto-alignment', 'Grad-CAM attention overlays', 'Periorbital & jawline blend inspection'],
  },
  {
    id: 'audio',
    title: 'Voice Clone & Audio',
    backbone: 'LCNN Anti-Spoofing',
    icon: Waveform,
    desc: 'Unmasks synthetic voices (ElevenLabs, SV2TTS, RVC) and vocoder frequency traces.',
    metrics: 'Log-Mel Spectrogram · 16kHz Sampling',
    features: ['Spectral frequency windowing', 'Phase discontinuity spotting', 'Synthetic harmonic detection'],
  },
  {
    id: 'video',
    title: 'Video Temporal Drift',
    backbone: 'Frame Aggregator',
    icon: VideoIcon,
    desc: 'Analyzes keyframe consistency, temporal jitter, and transient deepfake flicker.',
    metrics: 'Multi-Frame Trajectory · Dynamic FPS',
    features: ['Frame-by-frame confidence curve', 'Multi-subject tracking', 'Transient anomaly detection'],
  },
]

const ASSURANCES = [
  {
    icon: Hash,
    title: 'Cryptographic Chain of Custody',
    body: 'Both the original submitted file and the generated evidence report can be verified against their SHA-256 checksums.',
  },
  {
    icon: Lock,
    title: 'Privacy & Self-Hosted Security',
    body: 'Media is processed directly on your local GPU pipeline. One click permanently erases all scans, heatmaps, and records.',
  },
  {
    icon: ShieldCheck,
    title: 'Calibrated Confidence Scores',
    body: 'Borderline or ambiguous cases are reported transparently as inconclusive rather than forced into an uncertain binary judgment.',
  },
]

export default function Landing() {
  const [activeTab, setActiveTab] = useState('heatmap')
  const [copiedHash, setCopiedHash] = useState(false)
  const [mousePos, setMousePos] = useState({ x: 150, y: 150 })

  const { scrollYProgress } = useScroll()
  const smoothProgress = useSpring(scrollYProgress, { stiffness: 100, damping: 30, restDelta: 0.001 })
  const backgroundY = useTransform(smoothProgress, [0, 1], ['0%', '20%'])

  const sampleHash = '3a7b8e1f0c92d54e8b3a7f29104c8e76a5b4c3d2e1f0a9b8c7d6e5f4a3b2c1d0'

  const handleMouseMove = (e) => {
    const rect = e.currentTarget.getBoundingClientRect()
    setMousePos({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    })
  }

  const copyHash = () => {
    navigator.clipboard?.writeText(sampleHash)
    setCopiedHash(true)
    setTimeout(() => setCopiedHash(false), 1500)
  }

  return (
    <div className="relative space-y-24 pb-16 overflow-hidden">
      {/* Background Animated Ambient Lights */}
      <motion.div
        style={{ y: backgroundY }}
        className="pointer-events-none absolute -top-24 left-1/2 -z-10 h-[650px] w-full max-w-6xl -translate-x-1/2 overflow-hidden opacity-25 blur-[100px]"
      >
        <div className="h-full w-full rounded-full bg-gradient-to-tr from-accent via-indigo-600 to-cyan-400 animate-pulse" />
      </motion.div>

      {/* ------------------------------------------------------------- HERO SECTION */}
      <section className="relative pt-6 text-center sm:pt-12">
        {/* Animated Status Pill */}
        <motion.div
          initial={{ opacity: 0, y: -15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="inline-flex items-center gap-2.5 rounded-full border border-accent/40 bg-surface-1/90 px-4 py-1.5 text-xs font-semibold text-accent shadow-sm backdrop-blur-md"
        >
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-accent" />
          </span>
          <span>VERITAS DEEPFAKE FORENSICS</span>
          <span className="text-ink-muted">·</span>
          <span className="mono text-[0.6875rem] font-bold text-ink-secondary">v1.0 (CUDA ACCELERATED)</span>
        </motion.div>

        {/* Hero Main Headline */}
        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.1 }}
          className="mx-auto mt-6 max-w-4xl text-[2.75rem] font-extrabold leading-[1.06] tracking-tight text-ink-primary sm:text-[4rem]"
        >
          Unmask Synthetic Media with{' '}
          <span className="bg-gradient-to-r from-accent via-blue-400 to-indigo-300 bg-clip-text text-transparent">
            Neural Certainty.
          </span>
        </motion.h1>

        {/* Subtitle */}
        <motion.p
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.2 }}
          className="mx-auto mt-5 max-w-2xl text-[1.125rem] leading-relaxed text-ink-secondary"
        >
          Autonomous forensic inspection for images, voice clones, and video.
          Generate explainable Grad-CAM heatmaps, verifiable SHA-256 chain of custody, and tamper-evident legal reports in seconds.
        </motion.p>

        {/* Action Buttons */}
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.3 }}
          className="mt-8 flex flex-wrap items-center justify-center gap-4"
        >
          <Link
            to="/analyse"
            className="group inline-flex items-center gap-2.5 rounded-xl bg-accent px-8 py-3.5 text-[0.9375rem] font-bold text-white shadow-lg shadow-accent/25 transition-all hover:bg-accent-hover hover:shadow-xl hover:shadow-accent/35 active:scale-[0.98]"
          >
            <Sparkles size={18} className="transition-transform group-hover:rotate-12" />
            <span>Start Forensic Analysis</span>
            <ArrowRight size={16} className="transition-transform group-hover:translate-x-1" />
          </Link>

          <Link
            to="/how-it-works"
            className="btn-secondary btn-lg !rounded-xl !border-strong !bg-surface-1/80 !px-7 !py-3.5 !backdrop-blur-md hover:!bg-surface-2 transition-all active:scale-[0.98]"
          >
            Explore Methodology
          </Link>
        </motion.div>

        <p className="mt-4 text-[0.8125rem] text-ink-muted">
          No account needed for instant guest scan · Sign in for encrypted history & higher quotas
        </p>

        {/* Metric Cards Banner */}
        <motion.div
          initial={{ opacity: 0, y: 25 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.4 }}
          className="mx-auto mt-12 grid max-w-4xl grid-cols-2 gap-3.5 sm:grid-cols-4"
        >
          {METRICS.map((metric) => (
            <motion.div
              key={metric.label}
              whileHover={{ y: -3 }}
              className="card relative overflow-hidden border p-4 text-left shadow-sm backdrop-blur-md transition-colors hover:border-accent/50"
            >
              <div className="flex items-center justify-between text-ink-muted">
                <span className="text-[0.6875rem] font-bold uppercase tracking-wider">{metric.label}</span>
                <span style={{ color: metric.color }}>
                  <metric.icon size={16} />
                </span>
              </div>
              <p className="tnum mt-2 text-2xl font-extrabold tracking-tight text-ink-primary">
                {metric.value}
              </p>
              <p className="mt-0.5 text-[0.75rem] text-ink-muted">{metric.hint}</p>
            </motion.div>
          ))}
        </motion.div>
      </section>

      {/* ------------------------------------------------------------- 02: INTERACTIVE LIVE SCANNER LAB */}
      <section className="mx-auto max-w-5xl">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-40px' }}
          transition={{ duration: 0.6 }}
          onMouseMove={handleMouseMove}
          className="relative overflow-hidden rounded-2xl border border-accent/30 bg-surface-1/90 p-6 shadow-xl backdrop-blur-xl sm:p-8"
        >
          {/* Subtle Spotlight Glow following Cursor */}
          <div
            className="pointer-events-none absolute -inset-px opacity-25 transition-opacity duration-300"
            style={{
              background: `radial-gradient(500px circle at ${mousePos.x}px ${mousePos.y}px, rgba(57,135,229,0.2), transparent 50%)`,
            }}
          />

          {/* Terminal Title Bar */}
          <div className="mb-6 flex flex-wrap items-center justify-between gap-4 border-b border-subtle pb-4">
            <div className="flex items-center gap-3">
              <div className="flex gap-1.5">
                <span className="h-3 w-3 rounded-full bg-red-500/80 shadow-sm" />
                <span className="h-3 w-3 rounded-full bg-yellow-500/80 shadow-sm" />
                <span className="h-3 w-3 rounded-full bg-green-500/80 shadow-sm" />
              </div>
              <span className="mono text-xs font-semibold text-ink-muted">
                SESSION // LIVE_TENSOR_DIAGNOSTIC · CASE_REF: DF-20260901-8A3C21
              </span>
            </div>

            {/* Interactive Toggle Controls */}
            <div className="flex rounded-lg bg-surface-2 p-1 text-xs font-semibold shadow-inner">
              <button
                onClick={() => setActiveTab('heatmap')}
                className={`flex items-center gap-1.5 rounded-md px-3.5 py-1.5 transition-all ${
                  activeTab === 'heatmap'
                    ? 'bg-accent text-white shadow-sm'
                    : 'text-ink-secondary hover:text-ink-primary'
                }`}
              >
                <Eye size={14} /> Grad-CAM Heatmap
              </button>
              <button
                onClick={() => setActiveTab('original')}
                className={`flex items-center gap-1.5 rounded-md px-3.5 py-1.5 transition-all ${
                  activeTab === 'original'
                    ? 'bg-accent text-white shadow-sm'
                    : 'text-ink-secondary hover:text-ink-primary'
                }`}
              >
                <ImageIcon size={14} /> Original Facial Crop
              </button>
            </div>
          </div>

          {/* Terminal Content Grid */}
          <div className="grid gap-8 lg:grid-cols-12 items-center">
            {/* Visual Screen with Scanning Laser */}
            <div className="relative flex flex-col items-center justify-center overflow-hidden rounded-xl bg-surface-2 p-5 lg:col-span-6">
              <div className="relative aspect-square w-full max-w-[280px] overflow-hidden rounded-lg border-2 border-accent/60 shadow-lg">
                {/* Visual View Layer */}
                <div
                  className="h-full w-full bg-cover bg-center transition-all duration-500"
                  style={{
                    background:
                      activeTab === 'heatmap'
                        ? 'radial-gradient(circle at 48% 46%, rgba(239, 68, 68, 0.88) 0%, rgba(245, 158, 11, 0.75) 35%, rgba(59, 130, 246, 0.55) 68%, rgba(15, 23, 42, 0.95) 100%)'
                        : 'linear-gradient(135deg, #1e293b, #0f172a)',
                  }}
                >
                  {/* Facial Mesh Bounding Wireframe */}
                  <div className="absolute inset-4 rounded-lg border border-dashed border-accent/70 p-2.5">
                    <div className="flex items-center justify-between text-[0.625rem] font-extrabold text-accent">
                      <span>ROI: FACE_01 (128x128)</span>
                      <span>SIGMOID: 0.998</span>
                    </div>

                    <div className="mt-7 flex justify-around">
                      <span className="h-4 w-4 rounded-full border border-accent/90 bg-accent/10" />
                      <span className="h-4 w-4 rounded-full border border-accent/90 bg-accent/10" />
                    </div>
                    <div className="mx-auto mt-6 h-3 w-10 rounded-full border border-red-400/90 bg-red-500/20" />
                  </div>
                </div>

                {/* Animated Scanner Laser Bar */}
                <div className="pointer-events-none absolute inset-x-0 h-1 bg-gradient-to-r from-transparent via-cyan-400 to-transparent opacity-90 shadow-[0_0_12px_#22d3ee] animate-bounce" />
              </div>

              <div className="mt-3 flex w-full justify-between px-2 text-[0.75rem] text-ink-muted">
                <span>Backbone: EfficientNet-B0 (Binary Head)</span>
                <span className="font-bold text-accent">CUDA Latency: 42ms</span>
              </div>
            </div>

            {/* Live Verdict & Attribution Metrics */}
            <div className="flex flex-col justify-between space-y-4 lg:col-span-6">
              <div>
                <div className="flex items-center justify-between">
                  <span
                    className="badge font-extrabold"
                    style={{ background: 'var(--status-crit-bg)', color: 'var(--status-critical)' }}
                  >
                    <ShieldAlert size={15} /> LIKELY MANIPULATED
                  </span>
                  <span className="tnum text-3xl font-black text-red-500">99.8%</span>
                </div>
                <h3 className="mt-2 text-xl font-bold tracking-tight text-ink-primary">
                  Synthetic Face Swap Detected
                </h3>
                <p className="mt-1.5 text-sm leading-relaxed text-ink-secondary">
                  High-frequency spatial boundary blending anomalies and warping artifacts isolated in the periorbital and jawline regions.
                </p>
              </div>

              {/* Confidence Meter Bar */}
              <div className="space-y-1.5">
                <div className="flex justify-between text-xs font-semibold text-ink-muted">
                  <span>Authentic Threshold (0.0)</span>
                  <span>Synthetic Threshold (1.0)</span>
                </div>
                <div className="h-3 w-full overflow-hidden rounded-full bg-surface-3">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-amber-500 via-rose-500 to-red-500"
                    style={{ width: '99.8%' }}
                  />
                </div>
              </div>

              {/* Cryptographic SHA-256 Attestation Box */}
              <div className="rounded-xl border border-subtle bg-surface-2 p-3">
                <div className="flex items-center justify-between">
                  <span className="text-[0.6875rem] font-bold uppercase tracking-wider text-ink-muted">
                    SHA-256 Fingerprint (Chain of Custody)
                  </span>
                  <button
                    onClick={copyHash}
                    className="flex items-center gap-1 text-[0.6875rem] font-bold text-accent hover:underline"
                  >
                    {copiedHash ? <CheckCircle size={12} /> : <Copy size={12} />}
                    {copiedHash ? 'Copied' : 'Copy Hash'}
                  </button>
                </div>
                <p className="mono mt-1 truncate text-xs text-ink-secondary">{sampleHash}</p>
              </div>

              <div className="flex items-center justify-between pt-1">
                <span className="text-xs text-ink-muted">Have a file you need to authenticate?</span>
                <Link
                  to="/analyse"
                  className="inline-flex items-center gap-1 text-xs font-bold text-accent hover:underline"
                >
                  Upload for Analysis <ArrowRight size={13} />
                </Link>
              </div>
            </div>
          </div>
        </motion.div>
      </section>

      {/* ------------------------------------------------------------- 03: STORY-DRIVEN 4-STAGE PIPELINE */}
      <section className="mx-auto max-w-5xl space-y-10">
        <div className="text-center">
          <span className="badge badge-neutral mb-2">The Veritas Methodology</span>
          <h2 className="text-3xl font-extrabold tracking-tight text-ink-primary sm:text-4xl">
            A 4-Stage Story of Forensic Verification
          </h2>
          <p className="mx-auto mt-2.5 max-w-xl text-base text-ink-secondary">
            From raw media ingestion to court-admissible attestation, every step is deterministic and verifiable.
          </p>
        </div>

        {/* Story Progression Cards */}
        <div className="grid gap-6 sm:grid-cols-2">
          {STORY_CHAPTERS.map((chap, idx) => (
            <motion.div
              key={chap.num}
              initial={{ opacity: 0, y: 25 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-40px' }}
              transition={{ duration: 0.5, delay: idx * 0.1 }}
              whileHover={{ y: -4 }}
              className="card relative flex flex-col justify-between overflow-hidden border p-6 shadow-sm transition-all hover:border-accent/50 hover:shadow-lg"
            >
              <div>
                <div className="flex items-center justify-between">
                  <span
                    className="grid h-11 w-11 place-items-center rounded-xl shadow-sm"
                    style={{ background: `${chap.color}15`, color: chap.color }}
                  >
                    <chap.icon size={22} />
                  </span>
                  <span className="mono text-2xl font-black opacity-20 text-ink-primary">
                    {chap.num}
                  </span>
                </div>

                <p className="mt-3 text-[0.6875rem] font-bold uppercase tracking-wider text-accent">
                  {chap.phase}
                </p>
                <h3 className="mt-1 text-lg font-bold tracking-tight text-ink-primary">
                  {chap.title}
                </h3>
                <p className="mt-0.5 text-xs font-medium text-ink-muted">{chap.tagline}</p>

                <p className="mt-3 text-sm leading-relaxed text-ink-secondary">
                  {chap.description}
                </p>
              </div>

              <div className="mt-5 border-t border-subtle pt-3.5">
                <p className="mono text-[0.6875rem] font-semibold text-ink-muted">
                  {chap.detail}
                </p>
              </div>
            </motion.div>
          ))}
        </div>
      </section>

      {/* ------------------------------------------------------------- 04: MULTI-MODAL DETECTION CAPABILITIES */}
      <section className="mx-auto max-w-5xl space-y-8">
        <div className="text-center">
          <span className="badge badge-neutral mb-2">Dedicated Neural Engines</span>
          <h2 className="text-3xl font-extrabold tracking-tight text-ink-primary sm:text-4xl">
            Specialized Multi-Modal Detection
          </h2>
          <p className="mx-auto mt-2.5 max-w-xl text-base text-ink-secondary">
            Different media formats exhibit distinct manipulation footprints. Veritas applies tailored neural networks to each.
          </p>
        </div>

        <div className="grid gap-6 md:grid-cols-3">
          {MODES.map((mode, idx) => (
            <motion.div
              key={mode.id}
              initial={{ opacity: 0, y: 25 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: idx * 0.1 }}
              whileHover={{ y: -5 }}
              className="card group relative flex flex-col justify-between overflow-hidden border p-6 transition-all hover:border-accent/60 hover:shadow-xl"
            >
              <div>
                <div className="flex items-center justify-between">
                  <span
                    className="grid h-11 w-11 place-items-center rounded-xl transition-transform duration-300 group-hover:scale-110"
                    style={{ background: 'var(--accent-soft)', color: 'var(--accent)' }}
                  >
                    <mode.icon size={22} />
                  </span>
                  <span className="badge text-[0.6875rem] font-bold text-accent" style={{ background: 'var(--accent-soft)' }}>
                    {mode.backbone}
                  </span>
                </div>

                <h3 className="mt-4 text-xl font-bold tracking-tight text-ink-primary">
                  {mode.title}
                </h3>
                <p className="mt-1 text-xs font-semibold text-accent">{mode.metrics}</p>

                <p className="mt-3 text-sm leading-relaxed text-ink-secondary">
                  {mode.desc}
                </p>
              </div>

              <div className="mt-5 border-t border-subtle pt-4">
                <p className="mb-2 text-[0.6875rem] font-bold uppercase tracking-wider text-ink-muted">
                  Forensic Capabilities
                </p>
                <ul className="space-y-1.5">
                  {mode.features.map((feat) => (
                    <li key={feat} className="flex items-center gap-2 text-xs text-ink-secondary">
                      <CheckCircle size={13} className="shrink-0 text-accent" />
                      <span>{feat}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </motion.div>
          ))}
        </div>
      </section>

      {/* ------------------------------------------------------------- 05: CRYPTOGRAPHIC ASSURANCES */}
      <section className="mx-auto max-w-5xl">
        <div className="grid gap-6 sm:grid-cols-3">
          {ASSURANCES.map((item, idx) => (
            <motion.div
              key={item.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: idx * 0.1 }}
              className="flex gap-4 rounded-xl border border-subtle bg-surface-1 p-5 shadow-sm"
            >
              <span
                className="grid h-10 w-10 shrink-0 place-items-center rounded-xl"
                style={{ background: 'var(--surface-2)', color: 'var(--accent)' }}
              >
                <item.icon size={20} />
              </span>
              <div>
                <h4 className="text-sm font-bold text-ink-primary">{item.title}</h4>
                <p className="mt-1 text-xs leading-relaxed text-ink-secondary">{item.body}</p>
              </div>
            </motion.div>
          ))}
        </div>
      </section>

      {/* ------------------------------------------------------------- 06: HIGH-IMPACT FINAL CTA */}
      <motion.section
        initial={{ opacity: 0, scale: 0.97 }}
        whileInView={{ opacity: 1, scale: 1 }}
        viewport={{ once: true }}
        transition={{ duration: 0.6 }}
        className="mx-auto max-w-5xl"
      >
        <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-accent via-blue-700 to-indigo-800 p-8 text-white shadow-xl sm:p-12">
          {/* Subtle Grid Accent */}
          <div
            className="absolute inset-0 opacity-10"
            style={{
              backgroundImage: 'radial-gradient(circle at 1px 1px, white 1px, transparent 0)',
              backgroundSize: '24px 24px',
            }}
          />

          <div className="relative z-10 mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-extrabold tracking-tight sm:text-4xl">
              Inspect Suspected Media Now
            </h2>
            <p className="mt-3 text-base text-blue-100 leading-relaxed">
              Submit your image, audio clip, or video file for immediate GPU-accelerated deepfake attribution and receive a verified evidentiary report.
            </p>
            <div className="mt-8 flex flex-wrap justify-center gap-4">
              <Link
                to="/analyse"
                className="inline-flex items-center gap-2 rounded-xl bg-white px-7 py-3.5 text-sm font-bold text-slate-950 shadow-lg transition-transform hover:scale-105 active:scale-95"
              >
                <span>Start Free Analysis</span>
                <ArrowRight size={16} />
              </Link>
              <Link
                to="/login"
                className="inline-flex items-center gap-2 rounded-xl border border-white/30 bg-white/10 px-6 py-3.5 text-sm font-semibold text-white backdrop-blur-md transition-colors hover:bg-white/20"
              >
                Create Account
              </Link>
            </div>
          </div>
        </div>
      </motion.section>

      {/* Evidentiary Notice */}
      <div className="mx-auto max-w-5xl">
        <Notice tone="warn" title="Evidentiary Notice & Standards">
          Deepfake detectors produce probabilistic scores based on trained statistical signatures. While Veritas utilizes state-of-the-art neural architectures (99.9% accuracy on benchmark datasets), severe compression or low resolution may affect results. For formal legal or criminal proceedings, verification by a court-certified digital forensics examiner is recommended.
        </Notice>
      </div>
    </div>
  )
}
