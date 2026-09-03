/**
 * Inline SVG icons.
 *
 * Status is never carried by colour alone — each verdict pairs its colour with
 * one of these glyphs and a text label, which is what keeps the result readable
 * for colour-blind users and in forced-colours mode.
 */
const base = {
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.75,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
}

function Svg({ size = 18, children, ...rest }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" {...base} {...rest}>
      {children}
    </svg>
  )
}

export const ShieldCheck = (p) => (
  <Svg {...p}>
    <path d="M12 3l7.5 3v5.5c0 4.6-3.2 8-7.5 9.5-4.3-1.5-7.5-4.9-7.5-9.5V6z" />
    <path d="M9 12l2.2 2.2L15.5 10" />
  </Svg>
)

export const ShieldAlert = (p) => (
  <Svg {...p}>
    <path d="M12 3l7.5 3v5.5c0 4.6-3.2 8-7.5 9.5-4.3-1.5-7.5-4.9-7.5-9.5V6z" />
    <path d="M12 8.5v4" />
    <circle cx="12" cy="15.8" r=".9" fill="currentColor" stroke="none" />
  </Svg>
)

export const ShieldQuestion = (p) => (
  <Svg {...p}>
    <path d="M12 3l7.5 3v5.5c0 4.6-3.2 8-7.5 9.5-4.3-1.5-7.5-4.9-7.5-9.5V6z" />
    <path d="M10.4 10a1.7 1.7 0 113 1c-.6.5-1.4.9-1.4 2" />
    <circle cx="12" cy="15.9" r=".85" fill="currentColor" stroke="none" />
  </Svg>
)

export const Upload = (p) => (
  <Svg {...p}>
    <path d="M12 15V4" />
    <path d="M8.5 7.5L12 4l3.5 3.5" />
    <path d="M4.5 14v3.5a2 2 0 002 2h11a2 2 0 002-2V14" />
  </Svg>
)

export const FileText = (p) => (
  <Svg {...p}>
    <path d="M14 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V8z" />
    <path d="M14 3v5h5M9 13h6M9 17h4" />
  </Svg>
)

export const Download = (p) => (
  <Svg {...p}>
    <path d="M12 4v11" />
    <path d="M8.5 11.5L12 15l3.5-3.5" />
    <path d="M5 19h14" />
  </Svg>
)

export const History = (p) => (
  <Svg {...p}>
    <path d="M3.5 12a8.5 8.5 0 108.5-8.5 8.4 8.4 0 00-6 2.5L3.5 8" />
    <path d="M3.5 4v4h4M12 7.5V12l3 1.8" />
  </Svg>
)

export const Image = (p) => (
  <Svg {...p}>
    <rect x="3.5" y="4.5" width="17" height="15" rx="2" />
    <circle cx="9" cy="10" r="1.6" />
    <path d="M20 16l-4.5-4.5L5 20" />
  </Svg>
)

export const Waveform = (p) => (
  <Svg {...p}>
    <path d="M3.5 12h2M8 7v10M12 4.5v15M16 8.5v7M20.5 11v2" />
  </Svg>
)

export const Video = (p) => (
  <Svg {...p}>
    <rect x="3" y="6" width="13" height="12" rx="2" />
    <path d="M16 10.5l5-2.8v8.6l-5-2.8z" />
  </Svg>
)

export const Sun = (p) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2.5v2M12 19.5v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M2.5 12h2M19.5 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4" />
  </Svg>
)

export const Moon = (p) => (
  <Svg {...p}>
    <path d="M20 13.5A8 8 0 1110.5 4a6.5 6.5 0 009.5 9.5z" />
  </Svg>
)

export const Lock = (p) => (
  <Svg {...p}>
    <rect x="4.5" y="10.5" width="15" height="9.5" rx="2" />
    <path d="M8 10.5V7.8a4 4 0 018 0v2.7" />
  </Svg>
)

export const Hash = (p) => (
  <Svg {...p}>
    <path d="M9 3.5L7.5 20.5M16.5 3.5L15 20.5M3.5 8.5h17M3 15.5h17" />
  </Svg>
)

export const Check = (p) => (
  <Svg {...p}>
    <path d="M4.5 12.5l5 5 10-11" />
  </Svg>
)

export const Copy = (p) => (
  <Svg {...p}>
    <rect x="9" y="9" width="11" height="11" rx="2" />
    <path d="M5 15V6a2 2 0 012-2h9" />
  </Svg>
)

export const Trash = (p) => (
  <Svg {...p}>
    <path d="M4 7h16M9.5 7V5.5a1.5 1.5 0 011.5-1.5h2a1.5 1.5 0 011.5 1.5V7" />
    <path d="M6.5 7l.9 12a2 2 0 002 1.9h5.2a2 2 0 002-1.9l.9-12" />
  </Svg>
)

export const ArrowRight = (p) => (
  <Svg {...p}>
    <path d="M4.5 12h15M13.5 6l6 6-6 6" />
  </Svg>
)

export const Alert = (p) => (
  <Svg {...p}>
    <path d="M12 4.5l8.5 15h-17z" />
    <path d="M12 10v4" />
    <circle cx="12" cy="16.8" r=".9" fill="currentColor" stroke="none" />
  </Svg>
)

export const Info = (p) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M12 11.5v5" />
    <circle cx="12" cy="8.3" r=".9" fill="currentColor" stroke="none" />
  </Svg>
)

export const Spinner = ({ size = 18, className = '' }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" className={`animate-spin ${className}`}
       aria-hidden="true" fill="none">
    <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity=".15" />
    <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" 
            strokeDasharray="62" strokeDashoffset="45" />
  </svg>
)

export const Cpu = (p) => (
  <Svg {...p}>
    <rect x="4" y="4" width="16" height="16" rx="2" />
    <rect x="9" y="9" width="6" height="6" />
    <path d="M9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 14h3M1 9h3M1 14h3" />
  </Svg>
)

export const Activity = (p) => (
  <Svg {...p}>
    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
  </Svg>
)

export const Eye = (p) => (
  <Svg {...p}>
    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
    <circle cx="12" cy="12" r="3" />
  </Svg>
)

export const Sparkles = (p) => (
  <Svg {...p}>
    <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
  </Svg>
)

export const Zap = (p) => (
  <Svg {...p}>
    <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
  </Svg>
)

export const CheckCircle = (p) => (
  <Svg {...p}>
    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
    <polyline points="22 4 12 14.01 9 11.01" />
  </Svg>
)

export const MEDIA_ICON = { image: Image, audio: Waveform, video: Video }
