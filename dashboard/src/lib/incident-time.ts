/**
 * How long after the alert fired did this record come into existence?
 *
 * An incident row has always carried `created_at` — the moment *we wrote it* —
 * and nothing else. Every signal adapter captured the source's own fire time
 * (`startsAt`, `firedDateTime`, `started_at`) and dropped it at the record
 * boundary, so a timeline placed each incident at the moment it happened to be
 * processed, and the gap between "it broke" and "we noticed" was not derivable
 * at all. Alertmanager grouping alone separates those by minutes; a replayed
 * backlog, or a P2 waiting on a human, by far more.
 *
 * The rules here are all about refusing to state more than is known:
 *
 *   - no fire time            -> null (render nothing, not "0s")
 *   - unparseable either side -> null
 *   - written *before* it fired -> null, not a negative duration
 *
 * The last one is not hypothetical: clock skew between a spoke cluster and the
 * hub is normal, and "detected -3s" on screen destroys trust in every other
 * number next to it far more than an absent badge does.
 */

export interface DetectionGap {
  /** Whole seconds between firing and recording. */
  seconds: number;
  /** Compact human form, e.g. "8s", "3m", "2h 5m". */
  label: string;
}

function formatGap(totalSeconds: number): string {
  if (totalSeconds < 60) return `${totalSeconds}s`;
  const minutes = Math.floor(totalSeconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;
  // Hours without minutes reads as suspiciously round ("2h" for 2h59m), so the
  // remainder stays unless it is genuinely zero.
  return remainder === 0 ? `${hours}h` : `${hours}h ${remainder}m`;
}

export function describeDetectionGap(
  triggeredAt: string | undefined,
  createdAt: string | undefined,
): DetectionGap | null {
  if (!triggeredAt || !createdAt) return null;
  const fired = Date.parse(triggeredAt);
  const recorded = Date.parse(createdAt);
  if (Number.isNaN(fired) || Number.isNaN(recorded)) return null;
  const seconds = Math.floor((recorded - fired) / 1000);
  if (seconds < 0) return null;
  return { seconds, label: formatGap(seconds) };
}
