/**
 * Cuts the full-stack raw footage down to exactly 30 seconds.
 *
 * The raw take is 2-3 minutes because the real thing takes 2-3 minutes: a local
 * model choosing tools, Helm charts becoming pods, a push loop noticing. This
 * turns that into 30s of only the moments where something changes.
 *
 * No overlays at all — no captions, no elapsed-time badge. The frame is the
 * dashboard and nothing else. Two consequences worth stating plainly:
 *
 *   No speed-up is used, only cuts — but with the badge gone, nothing IN the video
 *   marks where time was removed. The disclosure therefore has to travel with the
 *   post rather than the file: "컷 편집 · 푸시 주기 60s→2s (촬영용)" belongs in the
 *   body text (docs/post/linkedin-intro-ko.md). A video that silently compresses
 *   90s of waiting into a cut, with no note anywhere, is the thing this project
 *   spends its time refusing to do.
 *
 *   The ffmpeg command is GENERATED from the SEGMENTS list below, never
 *   hand-maintained beside it, and the build refuses to run if the segments do not
 *   sum to 30.0s or if the beats are out of order.
 *
 * Segment starts are read from beats-fullstack.json — when the DOM actually
 * changed — so the cut follows what happened, not what was planned.
 *
 * Usage (from the working directory holding raw-fullstack/ and beats-fullstack.json):
 *   node <repo>/scripts/demo/build_fullstack_cut.js && bash build_fullstack_video.sh
 */
const fs = require('fs');

const W = 1080, H = 1350;
const TARGET = 30.0;

/**
 * Each segment: which beat it starts from, how long it runs, and why it exists.
 *
 * `at` is a key in beats-fullstack.json; `lead` shifts the start earlier so a
 * transition is entered rather than joined halfway. Durations are chosen to sum
 * to TARGET exactly and asserted below — a cut that quietly runs 31s would be
 * re-encoded by the platform and lose the 4:5 framing.
 */
const SEGMENTS = [
  { at: 'empty_shown',       lead: 0.0, dur: 2.8, why: 'declared in git, present nowhere' },
  { at: 'typing_started',    lead: 0.0, dur: 4.2, why: 'the sentence being typed' },
  { at: 'tenancy_tool_done', lead: 2.0, dur: 3.0, why: 'setup_tenancy resolves' },
  { at: 'addons_tool_done',  lead: 1.0, dur: 3.5, why: 'the chain continues, summary lands' },
  { at: 'tenancy_visible',   lead: 1.0, dur: 4.0, why: 'four axes turn green' },
  { at: 'addons_healthy',    lead: 0.5, dur: 2.2, why: 'the quota counts real consumption' },
  { at: 'globex_clicked',    lead: 0.0, dur: 2.0, why: 'the neighbour, its own budget' },
  { at: 'argocd_shown',      lead: 1.0, dur: 3.3, why: 'the same names in the real ArgoCD' },
  // Anchored to the FLIP, not to the kubectl that caused it. The delete and the
  // restore are beats too, but they happen in a terminal this recording does not
  // film, and the screen does not change for another 10-12s. A window opened at
  // the action shows a still frame of the thing not having happened yet — which
  // is the one beat the whole video exists for.
  { at: 'network_false',     lead: 1.6, dur: 3.0, why: 'one policy gone, one axis flips ✕' },
  { at: 'network_true',      lead: 1.4, dur: 2.0, why: 'the registry draws it back ✓' },
];

const clock = (ms) => {
  const s = Math.round(ms / 1000);
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
};

(async () => {
  const beats = JSON.parse(fs.readFileSync('beats-fullstack.json', 'utf8'));

  const missing = SEGMENTS.filter((s) => typeof beats[s.at] !== 'number').map((s) => s.at);
  if (missing.length) throw new Error(`beats-fullstack.json has no ${missing.join(', ')} — re-record`);

  const total = SEGMENTS.reduce((n, s) => n + s.dur, 0);
  if (Math.abs(total - TARGET) > 0.001) {
    throw new Error(`segments sum to ${total.toFixed(2)}s, not ${TARGET}s — fix the durations`);
  }

  // Absolute source positions, and the position each one occupies in the output.
  let out = 0;
  const cuts = SEGMENTS.map((s) => {
    const src = Math.max(0, (beats[s.at] - s.lead * 1000) / 1000);
    const row = { ...s, src, outStart: out, outEnd: out + s.dur, at_clock: clock(beats[s.at]) };
    out += s.dur;
    return row;
  });

  // Monotonic check: a segment that starts before the previous one ended means the
  // beat order changed (a model picking tools in another order, say), and the cut
  // would run backwards while every individual clip looked fine.
  cuts.forEach((c, i) => {
    if (i && c.src < cuts[i - 1].src) {
      throw new Error(`segment ${i + 1} (${c.at}) starts before segment ${i} — beats are out of order`);
    }
  });

  // One trim per segment off a single decode, concatenated. Nothing is laid on top.
  const chain = [
    ...cuts.map((c, i) =>
      `[0:v]trim=start=${c.src.toFixed(3)}:duration=${c.dur.toFixed(3)},setpts=PTS-STARTPTS[s${i}]`
    ),
    `${cuts.map((_, i) => `[s${i}]`).join('')}concat=n=${cuts.length}:v=1:a=0[cat]`,
    `[cat]fps=30,scale=${W}:${H}:flags=lanczos,setsar=1[vout]`,
  ];

  fs.writeFileSync('build_fullstack_video.sh', [
    '#!/bin/bash',
    '# GENERATED by build_fullstack_cut.js — do not edit; change SEGMENTS and re-run.',
    'set -e',
    'RAW=${RAW:-$(ls raw-fullstack/*.webm | head -1)}',
    'ffmpeg -v warning \\',
    '  -i "$RAW" \\',
    `  -f lavfi -t ${TARGET} -i anullsrc=channel_layout=stereo:sample_rate=44100 \\`,
    `  -filter_complex "${chain.join(';')}" \\`,
    '  -map "[vout]" -map 1:a \\',
    '  -c:v libx264 -preset slow -crf 20 -pix_fmt yuv420p -c:a aac -b:a 96k \\',
    '  -movflags +faststart -y multitenancy-fullstack-30s.mp4',
    'echo "wrote multitenancy-fullstack-30s.mp4"',
  ].join('\n') + '\n', { mode: 0o755 });

  console.log(`${cuts.length} segments, ${total.toFixed(1)}s total, no overlays`);
  for (const c of cuts) {
    console.log(`  ${c.at_clock}  src ${c.src.toFixed(1)}s  →  out ${c.outStart.toFixed(1)}-${c.outEnd.toFixed(1)}s  ${c.why}`);
  }
  console.log('wrote build_fullstack_video.sh');
})().catch((e) => { console.error('FAILED:', e.message); process.exit(1); });
