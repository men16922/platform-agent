/**
 * Records scenario A ("초록을 빨갛게 만들어 본다") as raw footage.
 *
 * Records the BROWSER VIEWPORT ONLY, in a throwaway profile — the operator's own
 * screen, tabs and session are never captured. (A full-screen `screencapture`
 * test proved that point the hard way.)
 *
 * The script does not stage anything: it deletes a real NetworkPolicy, waits for
 * the real dashboard to notice through the real push path, and restores it. Every
 * beat timestamp written to beats.json is when the DOM actually changed, so the
 * edit that follows can be cut to observed reality rather than to intentions.
 */
const { chromium } = require('playwright');
const { execSync } = require('child_process');
const fs = require('fs');

const REPO = '/Users/men1692/Desktop/AWS/platform-agent';
const NS = 'acme-dev-logging';
const sh = (cmd) => execSync(cmd, { cwd: REPO, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });

async function networkAxis(page) {
  // 5th cell of the acme/dev row: Tenant/env, Tier, Namespaces, Quota, Network...
  const cells = page.locator('tr:has(td:text-is("acme/dev")) td');
  const n = await cells.count();
  if (n < 5) return null;
  return (await cells.nth(4).innerText()).trim();
}

async function waitForAxis(page, want, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if ((await networkAxis(page)) === want) return Date.now();
    await page.waitForTimeout(250);
  }
  throw new Error(`network axis never became ${want} within ${timeoutMs}ms`);
}

(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const t_context = Date.now();
  const context = await browser.newContext({
    viewport: { width: 1080, height: 1080 },
    recordVideo: { dir: 'raw/', size: { width: 1080, height: 1080 } },
    deviceScaleFactor: 1,
  });
  const page = await context.newPage();
  const beats = {};
  const mark = (name) => { beats[name] = Date.now() - t_context; console.log(name, beats[name]); };

  await page.goto('http://localhost:3000/provisioning', { waitUntil: 'networkidle' });
  const box = await page.locator('section:has-text("Tenants & environments")').boundingBox();
  await page.evaluate((y) => window.scrollTo(0, y - 24), box.y);

  // Refuse to film a baseline that is not actually green — a demo that opens on a
  // stale or half-applied cluster is exactly the "screen says fine" failure this
  // video is about.
  await waitForAxis(page, '✓', 60000);
  await page.waitForTimeout(1500);
  mark('baseline_stable');

  await page.waitForTimeout(6000);
  mark('delete_issued');
  console.log(sh(`kubectl delete networkpolicy deny-cross-tenant -n ${NS}`).trim());

  const flipped = await waitForAxis(page, '✕', 90000);
  beats.flip_observed = flipped - t_context;
  console.log('flip_observed', beats.flip_observed);

  await page.waitForTimeout(6000);
  mark('restore_issued');
  sh(`python scripts/render_tenancy.py acme -e dev 2>/dev/null | kubectl apply -f - >/dev/null`);

  const restored = await waitForAxis(page, '✓', 90000);
  beats.restore_observed = restored - t_context;
  console.log('restore_observed', beats.restore_observed);

  await page.waitForTimeout(4000);
  mark('end');

  const video = page.video();
  await context.close();
  await browser.close();
  beats.video = await video.path();
  fs.writeFileSync('beats.json', JSON.stringify(beats, null, 2));
  console.log(JSON.stringify(beats, null, 2));
})().catch((e) => { console.error('FAILED:', e.message); process.exit(1); });
