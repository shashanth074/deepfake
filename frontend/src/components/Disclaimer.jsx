export default function Disclaimer({ compact = false }) {
  if (compact) {
    return (
      <p className="text-xs text-slate-500">
        Automated assessment — not a certified forensic opinion. Verification by a certified expert
        is recommended for legal proceedings.
      </p>
    )
  }
  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
      <p className="font-semibold">Read this before relying on the result</p>
      <p className="mt-1 leading-relaxed">
        This tool provides an automated technical assessment. Deepfake detectors are not certain:
        authentic media is sometimes flagged, and skilled manipulations are sometimes missed. For
        legal proceedings, verification by a certified forensic expert is recommended.
      </p>
    </div>
  )
}
