/**
 * Records the On-Prem multi-tenancy full-stack demo as raw footage.
 *
 * The arc is one tenant's life: declared in git and nowhere else -> isolated ->
 * full stack standing inside its own boundary -> proven, by breaking it.
 *
 * The tenant is built by TYPING A SENTENCE into the dashboard's Agents chat, not
 * by this script shelling out to kubectl. That is the demo's claim, so the
 * recording has to make the claim rather than illustrate it: an earlier cut ran
 * `render_tenancy | kubectl apply` off-screen while the dashboard watched, which
 * is a different (and weaker) statement than the one the article makes.
 *
 * Nothing here is staged. Every state on screen is produced by a real local model
 * choosing real tools against a real cluster, and by the real push path noticing.
 * Beat timestamps are written from when the DOM actually changed, so the edit is
 * cut to what happened rather than to what was supposed to happen.
 *
 * Records the BROWSER VIEWPORT ONLY, in a throwaway profile: a full-screen
 * capture puts the operator's other tabs in a file that is about to be published.
 *
 * Pre-requisite: bash scripts/demo/prep_fullstack.sh   (arranges the empty frame)
 */
const { chromium } = require('playwright');
const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const REPO = path.resolve(__dirname, '..', '..');
const ORIGIN = process.env.DASHBOARD_URL || 'http://localhost:3000';
const DASHBOARD = `${ORIGIN}/provisioning`;
const AGENTS = `${ORIGIN}/agents`;
// The sentence is the demo. Kept here verbatim so the script and
// docs/post/video-30s-script.md cannot drift into showing different words.
const INSTRUCTION =
  'Stand up tenant acme in the dev environment on this cluster: ' +
  'create its isolation boundary and then install the add-ons it declares.';
const ARGOCD = process.env.ARGOCD_URL || 'https://localhost:8090';
const HUB = process.env.HUB_URL || 'http://127.0.0.1:8077';
const NETPOL_NS = 'acme-dev-logging';

const sh = (cmd) => execSync(cmd, { cwd: REPO, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
const squash = (s) => s.replace(/\s+/g, ' ').trim();

/** Sign in to the dashboard out of frame, so the chat can actually run something.
 *
 * The recording profile is a throwaway with no cookies, and without a session the
 * Agents chat is read-only: `canDeploy` is false, the input is disabled, and the
 * Run button does nothing. A take was lost to exactly that — the sentence was
 * typed into a dead field and the script waited five minutes for a tool block that
 * could never appear.
 *
 * Uses the dashboard's own local-dev provider (admin, no secret, refused unless
 * DASHBOARD_DEV_AUTH=1), so nothing here handles a real credential.
 */
async function dashboardSignIn(context) {
  const csrf = await (await context.request.get(`${ORIGIN}/api/auth/csrf`)).json();
  const res = await context.request.post(`${ORIGIN}/api/auth/callback/dev-credentials`, {
    form: { csrfToken: csrf.csrfToken, callbackUrl: ORIGIN, json: 'true' },
  });
  if (!res.ok()) throw new Error(`dev sign-in refused (${res.status()}) — is DASHBOARD_DEV_AUTH=1 set?`);
  const session = await (await context.request.get(`${ORIGIN}/api/auth/session`)).json();
  if (session?.user?.role !== 'admin') {
    throw new Error('signed in but role is not admin — the chat would stay read-only');
  }
}

/** Log in to ArgoCD out of frame, so the demo lands on Applications, not a login form.
 *
 * The password is read from the cluster at record time rather than from a file.
 * The file version cost a take: it did not exist, so the run died before the first
 * frame — and had anyone created it, nothing ignored it, so a credential would have
 * been committed to a repository that a public article links to.
 *
 * Verified the hard way: opening the add-on's "Open" link in a browser with no Argo
 * session lands on the login form. Without this cookie the demo films a login page
 * at the exact beat that is supposed to prove the dashboard is not a mockup.
 */
async function argocdCookie(request) {
  const password = Buffer.from(
    sh(`kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}'`).trim(),
    'base64',
  ).toString('utf8').trim();
  if (!password) throw new Error('could not read the ArgoCD admin password from the cluster');
  const res = await request.post(`${ARGOCD}/api/v1/session`, {
    data: { username: 'admin', password },
    ignoreHTTPSErrors: true,
  });
  const { token } = await res.json();
  if (!token) throw new Error('ArgoCD session refused');
  return { name: 'argocd.token', value: token, url: ARGOCD };
}

/** The acme/dev fleet row, normalised. `null` while the tenant has never reported. */
async function fleetRow(page) {
  const cells = page.locator('tr:has(td:text-is("acme/dev")) td');
  const n = await cells.count();
  if (n < 9) return null; // the "never reported" row is one wide cell
  const text = [];
  for (let i = 0; i < n; i++) text.push(squash(await cells.nth(i).innerText()));
  return { namespaces: text[2], quota: text[3], network: text[4], rbac: text[5],
           pss: text[6], cpu: text[7], addons: text[8] };
}

async function until(label, predicate, timeoutMs = 180000, page = null) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await predicate()) return Date.now();
    if (page) await page.waitForTimeout(300);
  }
  throw new Error(`timed out waiting for: ${label}`);
}

(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const t0 = Date.now();
  const beats = {};
  const mark = (name) => { beats[name] = Date.now() - t0; console.log(`${name}\t${beats[name]}ms`); };

  const context = await browser.newContext({
    viewport: { width: 1080, height: 1350 },
    recordVideo: { dir: 'raw-fullstack/', size: { width: 1080, height: 1350 } },
    ignoreHTTPSErrors: true,
  });
  await dashboardSignIn(context);
  await context.addCookies([await argocdCookie(context.request)]);

  const page = await context.newPage();
  await page.goto(DASHBOARD, { waitUntil: 'networkidle' });
  const section = await page.locator('section:has-text("Tenants & environments")').boundingBox();
  await page.evaluate((y) => window.scrollTo(0, y - 20), section.y);
  await page.waitForTimeout(2500);

  // --- 1. the empty frame -------------------------------------------------
  if (await fleetRow(page)) throw new Error('acme/dev is already reporting — run prep_fullstack.sh first');
  mark('empty_shown');
  await page.waitForTimeout(4000);

  // --- 2. one sentence, typed on camera -----------------------------------
  await page.goto(AGENTS, { waitUntil: 'networkidle' });
  const box = page.locator('input[placeholder^="Ask the agent"]');
  await box.scrollIntoViewIfNeeded();
  await page.waitForTimeout(1200);
  mark('typing_started');
  // Typed rather than pasted: a field that fills instantly reads as a scripted
  // fixture, which is the one thing this shot is trying not to look like.
  await box.type(INSTRUCTION, { delay: 28 });
  await page.waitForTimeout(600);
  mark('sentence_sent');
  await box.press('Enter');

  // The spoke agent starts reporting only now: the tenant did not exist before it.
  // Started here rather than after the tools finish, so the dashboard's first
  // sight of the tenant is the push path working, not a fixture we pre-loaded.
  sh(`nohup env PLATFORM_PUSH_KEY=local-dev python scripts/push_addon_status.py ` +
     `--tenant acme --env dev --hub ${HUB} --interval 2 > /tmp/platform-agent/push-acme.log 2>&1 &`);

  // The chat shows a tool's state as an ICON only — ◐ running, ✓ ok, ✗ failed —
  // so that is what has to be read. An earlier version of this waited for the
  // absence of the word "running", which never appears in the DOM at all: every
  // wait returned true the instant the block rendered, and the recording would
  // have filmed a chain that had not happened yet.
  const toolMark = async (name) => {
    const btn = page.locator(`button:has(code:text-is("${name}"))`).first();
    if (!(await btn.count())) return null;
    return squash(await btn.locator('span').first().innerText().catch(() => ''));
  };
  const toolDone = async (name) => {
    const mark = await toolMark(name);
    if (mark === '✗') throw new Error(`${name} failed in the chat — nothing worth filming`);
    return mark === '✓';
  };

  beats.tenancy_tool_done = await until('setup_tenancy finished in the chat',
    () => toolDone('setup_tenancy'), 300000, page) - t0;
  console.log('tenancy_tool_done\t' + beats.tenancy_tool_done + 'ms');
  await page.waitForTimeout(2000);

  // --- 3. the chain continues on its own ----------------------------------
  // Two tools from one sentence, in an order the prompt states a reason for.
  // If a model change ever reorders them, this wait fails loudly instead of
  // filming a chain that did not happen.
  beats.addons_tool_done = await until('install_tenant_addons finished in the chat',
    () => toolDone('install_tenant_addons'), 300000, page) - t0;
  console.log('addons_tool_done\t' + beats.addons_tool_done + 'ms');
  await page.waitForTimeout(3500);

  // --- 4. back to the fleet: the boundary and the stack, as reported ------
  await page.goto(DASHBOARD, { waitUntil: 'networkidle' });
  const built = await page.locator('section:has-text("Tenants & environments")').boundingBox();
  await page.evaluate((y) => window.scrollTo(0, y - 20), built.y);

  beats.tenancy_visible = await until('acme/dev row with all four axes', async () => {
    const row = await fleetRow(page);
    return row && row.namespaces === '4 / 4' &&
      [row.quota, row.network, row.rbac, row.pss].every((c) => c === '✓');
  }, 180000, page) - t0;
  console.log('tenancy_visible\t' + beats.tenancy_visible + 'ms');
  await page.waitForTimeout(3000);

  beats.addons_healthy = await until('logging + tracing synced/healthy and quota consumed', async () => {
    const row = await fleetRow(page);
    const logging = squash(await page.locator('tr:has(td:text-is("logging"))').innerText().catch(() => ''));
    // Any non-zero CPU: what the tenant consumes depends on what its pods are
    // doing at that second, and pinning it to one number made the wait flaky.
    return row && /^[1-9]/.test(row.cpu) && /synced/.test(logging) && /healthy/.test(logging);
  }, 300000, page) - t0;
  console.log('addons_healthy\t' + beats.addons_healthy + 'ms');
  await page.waitForTimeout(4000);

  // --- 5. the neighbour: same cluster, its own budget ---------------------
  mark('globex_clicked');
  await page.locator('button:has-text("globex")').first().click();
  await page.waitForTimeout(3500);
  await page.locator('button:has-text("acme")').first().click();
  await page.waitForTimeout(2500);

  // --- 6. out to the real ArgoCD, in the same tab -------------------------
  mark('scroll_to_addons');
  await page.evaluate(() => {
    const heading = [...document.querySelectorAll('*')]
      .find((el) => el.textContent?.trim() === 'PLATFORM ADD-ONS');
    if (heading) heading.scrollIntoView({ behavior: 'smooth', block: 'start' });
    // Same link, same destination — only the tab it opens in, so the recording
    // stays one continuous video instead of splitting into a second file.
    document.querySelectorAll('a[href*="8090"]').forEach((a) => (a.target = '_self'));
  });
  await page.waitForTimeout(2500);

  mark('argocd_clicked');
  await page.locator('a[href*="8090"]').first().click();
  await page.waitForURL(/localhost:8090/, { timeout: 60000 });
  await page.waitForTimeout(1500);
  await page.goto(`${ARGOCD}/applications?search=acme-dev`, { waitUntil: 'domcontentloaded' });
  await until('the tenant applications listed in ArgoCD',
    async () => (await page.locator('text=acme-dev-logging').count()) > 0, 60000, page);
  mark('argocd_shown');
  await page.waitForTimeout(4500);

  // --- 7. prove the boundary by breaking it -------------------------------
  await page.goto(DASHBOARD, { waitUntil: 'networkidle' });
  const again = await page.locator('section:has-text("Tenants & environments")').boundingBox();
  await page.evaluate((y) => window.scrollTo(0, y - 20), again.y);
  await until('dashboard back with the tenant green',
    async () => (await fleetRow(page))?.network === '✓', 90000, page);
  mark('back_on_dashboard');
  await page.waitForTimeout(2500);

  mark('netpol_deleted');
  sh(`kubectl delete networkpolicy deny-cross-tenant -n ${NETPOL_NS}`);
  beats.network_false = await until('acme network axis flips',
    async () => (await fleetRow(page))?.network === '✕', 90000, page) - t0;
  console.log('network_false\t' + beats.network_false + 'ms');
  await page.waitForTimeout(4500);

  mark('netpol_restored');
  sh('python scripts/render_tenancy.py acme -e dev 2>/dev/null | kubectl apply -f - >/dev/null');
  beats.network_true = await until('acme network axis restored',
    async () => (await fleetRow(page))?.network === '✓', 90000, page) - t0;
  console.log('network_true\t' + beats.network_true + 'ms');
  await page.waitForTimeout(3500);
  mark('end');

  const video = page.video();
  await context.close();
  await browser.close();
  beats.video = await video.path();
  fs.writeFileSync('beats-fullstack.json', JSON.stringify(beats, null, 2));
  console.log('\n' + JSON.stringify(beats, null, 2));
})().catch((e) => { console.error('FAILED:', e.message); process.exit(1); });
