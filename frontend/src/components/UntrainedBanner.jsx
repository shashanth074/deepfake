/**
 * Shown whenever a result came from a model with no trained checkpoint.
 * A demo build must never be mistaken for an evidential one.
 */
export default function UntrainedBanner({ weightsStatus }) {
  if (!weightsStatus || weightsStatus === 'trained') return null
  return (
    <div className="rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-900">
      <p className="font-semibold">Demonstration mode — this score is not evidence</p>
      <p className="mt-1 leading-relaxed">
        No trained model checkpoint is installed on this deployment, so the network is running with
        untrained weights. The number below is meaningless as evidence. Train the detectors (see
        <code className="mx-1 rounded bg-red-100 px-1">ml/training</code>) or install checkpoints
        before using any report from this instance.
      </p>
    </div>
  )
}
