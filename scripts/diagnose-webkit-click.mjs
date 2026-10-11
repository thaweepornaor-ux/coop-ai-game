import assert from 'node:assert/strict';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

// Diagnostic copy of the full browser smoke; the acceptance script is unchanged.
// This check may create synthetic rooms only in the disposable CI preview.
const diagnosticCase = process.env.COOP_BROWSER_DIAGNOSTIC_CASE || '';
assert(['', 'webkit-desktop-1280'].includes(diagnosticCase), 'Unsupported browser diagnostic case');
const preview = new URL(process.env.COOP_PREVIEW_URL || 'http://127.0.0.1:4173');
assert(['127.0.0.1', 'localhost', '[::1]'].includes(preview.hostname), 'Browser smoke requires a loopback preview');
assert.equal(preview.protocol, 'http:', 'Use the local HTTP preview, never the published game');
assert.equal(process.env.COOP_EPHEMERAL_D1, '1', 'Confirm the CI preview uses disposable local D1 before creating rooms');
assert(!preview.username && !preview.password && !preview.search && !preview.hash, 'Preview URL must not contain credentials or query data');
const packageDir = path.resolve(process.env.COOP_PLAYWRIGHT_DIR || '.ci-browser-runtime');
const installed = JSON.parse(await readFile(path.join(packageDir, 'node_modules/playwright/package.json'), 'utf8'));
assert.equal(installed.version, '1.64.0', 'Use the reviewed fixed Playwright version');
const { chromium, webkit } = await import(pathToFileURL(path.join(packageDir, 'node_modules/playwright/index.mjs')).href);
const out = path.resolve(process.env.COOP_BROWSER_REPORT_DIR || 'browser-proof');
await mkdir(out, { recursive: true });
const report = {
  scope: 'Disposable local preview; synthetic users; no production database',
  playwright: installed.version,
  limits: ['Linux Chromium/WebKit emulation is not a physical iPhone or Android test', 'Nonblank raster and screenshots do not certify professional avatar art'],
  mode: diagnosticCase ? 'diagnostic-only' : 'full-suite',
  acceptanceEligible: !diagnosticCase,
  diagnosticCase: diagnosticCase || null,
  fullSuiteRequiredCases: 12,
  plannedCases: diagnosticCase ? 1 : 12,
  excludedCases: diagnosticCase ? 'Other surfaces and real-room journeys were deliberately not selected; this diagnostic is not full-suite acceptance' : null,
  cases: [],
};
const deadline = setTimeout(() => { console.error('Browser smoke exceeded its ten minute bound'); process.exit(1); }, 600_000);
deadline.unref();
const sizes = [
  { label: 'mobile-320', width: 320, height: 720, mobile: true },
  { label: 'mobile-390', width: 390, height: 844, mobile: true },
  { label: 'landscape-844', width: 844, height: 390, mobile: true },
  { label: 'desktop-1280', width: 1280, height: 900, mobile: false },
];
const syntheticName = 'ผู้เล่นทดสอบ';
const roomLabel = 'รหัสห้อง';
const nameLabel = 'ชื่อผู้เล่น';
async function saveReport() { await writeFile(path.join(out, 'report.json'), JSON.stringify(report, null, 2)); }
async function shot(page, label) { await page.screenshot({ path: path.join(out, label + '.png'), fullPage: true, timeout: 15_000 }); }

function safeCaseText(message) {
  return String(message)
    .replace(/Bearer\s+[^\s"'<>]+/gi, 'Bearer [redacted]')
    .replace(/((?:authorization|token|hostToken|playerToken)\s*["']?\s*[:=]\s*)("[^"]*"|'[^']*'|[^\s,}\n]+)/gi, '$1[redacted]')
    .replace(/[a-f0-9]{48,}/gi, '[redacted identifier]')
    .replace(/https?:\/\/[^\s"'<>]+/gi, '[preview address]')
    .replace(/[\u0000-\u001f]/g, ' ')
    .slice(0, 500);
}
function emitCase(row) {
  console.log('COOP_BROWSER_CASE ' + JSON.stringify({
    label: row.label, status: row.status, stage: row.stage, elapsedMs: row.elapsedMs, score: row.score,
    error: row.error ? safeCaseText(row.error) : undefined,
    raster: row.avatarRaster, motion: row.motion, runtimeErrors: row.runtimeErrors,
  }));
}
async function screenshotPreview(page, label) {
  // These are actual Playwright page screenshots. Compression alone bounds the
  // native log payload; the full PNG artifact remains unchanged.
  for (const options of [
    { fullPage: true, quality: 55 }, { fullPage: true, quality: 35 },
    { fullPage: false, quality: 45 }, { fullPage: false, quality: 20 },
  ]) {
    const bytes = await page.screenshot({ type: 'jpeg', ...options, timeout: 15_000 });
    const proof = {
      label, mimeType: 'image/jpeg', base64: bytes.toString('base64'),
      viewport: page.viewportSize(), fullPage: options.fullPage, quality: options.quality,
    };
    if (Buffer.byteLength(JSON.stringify(proof), 'utf8') <= 300_000) return proof;
  }
  throw new Error('Actual screenshot exceeds the bounded visual evidence payload');
}

function within(promise, milliseconds, description) {
  let timer;
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error(description + ' exceeded ' + milliseconds + ' ms')), milliseconds);
  });
  return Promise.race([promise, timeout]).finally(() => clearTimeout(timer));
}
const contextClosures = new WeakMap();
function closeContext(context) {
  if (!contextClosures.has(context)) {
    contextClosures.set(context, within(context.close(), 5_000, 'Context cleanup'));
  }
  return contextClosures.get(context);
}
async function boundedCase(browser, label, budgetMs, body) {
  const started = Date.now();
  const row = { label, status: 'running', stage: 'context-setup', budgetMs, checks: [] };
  report.cases.push(row); emitCase(row); await saveReport();
  const contexts = new Set(), pages = [], errors = [];
  let active = true, timedOut = false, timer, previewImage;
  const stage = async name => {
    if (!active || timedOut) throw new Error('Case was aborted');
    row.stage = name; row.elapsedMs = Date.now() - started;
    emitCase(row); await saveReport();
  };
  const createContext = async options => {
    const pending = browser.newContext(options);
    // A context created after its owning case ends must also be closed.
    pending.then(context => {
      if (active && !timedOut) contexts.add(context);
      else void closeContext(context).catch(() => {});
    }, () => {});
    return within(pending, 10_000, 'Context initialization');
  };
  const createPage = async context => {
    const page = await within(context.newPage(), 10_000, 'Page initialization');
    if (!active || timedOut) throw new Error('Case was aborted');
    page.setDefaultTimeout(15_000); page.setDefaultNavigationTimeout(10_000);
    pages.push(page);
    page.on('pageerror', error => errors.push(safeCaseText(error.message)));
    return page;
  };
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(() => {
      timedOut = true;
      reject(new Error('Case deadline exceeded at ' + row.stage + ' after ' + budgetMs + ' ms'));
      // Closing only this case's contexts rejects blocked browser operations,
      // including evaluate calls which have no Playwright operation timeout.
      for (const context of contexts) void closeContext(context).catch(() => {});
    }, budgetMs);
  });
  try {
    const result = await Promise.race([body({ createContext, createPage, stage }, row), timeout]);
    assert.deepEqual(errors, [], 'Browser runtime exceptions');
    previewImage = result?.previewImage;
    row.status = 'passed';
  } catch (error) {
    row.status = 'failed'; row.error = safeCaseText(error.message);
    row.runtimeErrors = errors.slice(0, 4);
    // A timed out context is already being closed. Other failures retain a
    // bounded actual screenshot before cleanup; no synthetic evidence is used.
    if (!timedOut) await Promise.allSettled(pages.slice(0, 2).map((page, index) =>
      page.screenshot({ path: path.join(out, label + '-failure-' + index + '.png'), fullPage: true, timeout: 5_000 })));
  } finally {
    active = false; clearTimeout(timer);
    const cleanup = await Promise.allSettled([...contexts].map(closeContext));
    const cleanupError = cleanup.find(result => result.status === 'rejected');
    if (cleanupError) {
      row.status = 'failed';
      row.error = safeCaseText((row.error ? row.error + '; ' : '') + cleanupError.reason.message);
    }
    row.elapsedMs = Date.now() - started; emitCase(row); await saveReport();
  }
  if (row.status === 'passed' && previewImage) console.log('COOP_BROWSER_IMAGE ' + JSON.stringify(previewImage));
  return row.status === 'passed';
}
async function notRun(label, reason) {
  const row = { label, status: 'not-run', stage: 'prerequisite', error: reason };
  report.cases.push(row); emitCase(row); await saveReport();
}

async function noOverflow(page, label) {
  const result = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    document: document.documentElement.scrollWidth,
    body: document.body.scrollWidth,
  }));
  assert(result.document <= result.viewport + 1 && result.body <= result.viewport + 1, label + ': horizontal page overflow ' + JSON.stringify(result));
  return result;
}
// Read the pixels actually presented to the user; a hidden/transparent canvas is
// not accepted as successful rendering. A documented thumbnail fallback is.
function rasterProbe(selector) {
  const container = document.querySelector(selector);
  if (!container) return null;
  const canvas = container.querySelector('canvas');
  const image = container.querySelector('img');
  const visibleCanvas = canvas && Number(getComputedStyle(canvas).opacity) > 0 && canvas.width > 0 && canvas.height > 0;
  const source = visibleCanvas ? canvas : image?.complete && image.naturalWidth > 0 ? image : null;
  if (!source) return null;
  try {
    const sample = document.createElement('canvas'); sample.width = sample.height = 32;
    const ctx = sample.getContext('2d', { willReadFrequently: true });
    ctx.drawImage(source, 0, 0, 32, 32);
    const pixels = ctx.getImageData(0, 0, 32, 32).data;
    let opaque = 0; const colors = new Set();
    for (let i = 0; i < pixels.length; i += 4) if (pixels[i + 3] > 24) { opaque++; colors.add([pixels[i] >> 4, pixels[i + 1] >> 4, pixels[i + 2] >> 4].join(',')); }
    if (opaque < 12 || colors.size < 4) return null;
    return { source: visibleCanvas ? 'canvas' : 'thumbnail-fallback', opaqueSamples: opaque, colorBuckets: colors.size };
  } catch { return null; }
}
async function avatarPainted(page, selector) {
  await page.locator(selector).scrollIntoViewIfNeeded();
  const handle = await page.waitForFunction(rasterProbe, selector, { timeout: 25_000 });
  return handle.jsonValue();
}
async function online(page) { await page.locator('.connection.online').waitFor({ timeout: 15_000 }); }
async function question(page, number) {
  await page.locator('.question-card .badge').filter({ hasText: 'ข้อ ' + number + ' / 15' }).waitFor({ timeout: 15_000 });
  assert.equal(await page.locator('.answer-grid button').count(), 3);
}
function pageErrors(page) { const errors = []; page.on('pageerror', error => errors.push(error.message.slice(0, 300))); return errors; }

const webKitInputAudits = new WeakMap();
const inputAuditPrefix = 'COOP_WEBKIT_INPUT_AUDIT ';
async function installWebKitInputAudit(context) {
  // Passive capture starts before app scripts; never log input contents or keys.
  await within(context.addInitScript(prefix => {
    for (const phase of ['mousedown', 'mouseup', 'click', 'keydown', 'keyup']) {
      document.addEventListener(phase, event => {
        const element = event.target instanceof Element ? event.target : null;
        const button = element?.closest('.character-gender-tabs button');
        let target;
        if (button?.textContent?.trim() === 'หญิง · 10 แบบ') {
          if ((phase === 'keydown' || phase === 'keyup') && event.key !== 'Enter') return;
          target = 'female-catalogue';
        } else if (['mousedown', 'mouseup', 'click'].includes(phase) &&
          element?.matches('.join-fields input[autocomplete="nickname"]')) target = 'name-input';
        else return;
        console.debug(prefix + JSON.stringify({ target, phase: event.type, trusted: event.isTrusted }));
      }, { capture: true, passive: true });
    }
  }, inputAuditPrefix), 2_000, 'WebKit early input audit setup');
}
function observeWebKitInput(page) {
  const events = [];
  let resolveControl;
  const controlEvents = new Promise(resolve => { resolveControl = resolve; });
  const listen = message => {
    const text = message.text();
    if (!text.startsWith(inputAuditPrefix)) return;
    let value;
    try { value = JSON.parse(text.slice(inputAuditPrefix.length)); } catch { return; }
    if (!value || Object.keys(value).sort().join(',') !== 'phase,target,trusted' ||
      !['name-input', 'female-catalogue'].includes(value.target) ||
      !['mousedown', 'mouseup', 'click', 'keydown', 'keyup'].includes(value.phase) ||
      typeof value.trusted !== 'boolean' || events.length >= 18) return;
    const event = { target: value.target, phase: value.phase, trusted: value.trusted };
    events.push(event);
    console.log('COOP_WARDROBE_INPUT ' + JSON.stringify({ browser: 'webkit', observed: events.length, ...event }));
    if (['mousedown', 'mouseup', 'click'].every(phase =>
      events.some(entry => entry.target === 'name-input' && entry.phase === phase && entry.trusted))) resolveControl();
  };
  page.on('console', listen);
  webKitInputAudits.set(page, { events, controlEvents, stop: () => page.off('console', listen) });
}
async function readCatalogueState(page) {
  return within(page.evaluate(() => {
    const button = [...document.querySelectorAll('.character-gender-tabs button')]
      .find(node => node.textContent?.trim() === 'หญิง · 10 แบบ');
    const pressed = button?.getAttribute('aria-pressed');
    return {
      femalePressed: pressed === 'true' || pressed === 'false' ? pressed : null,
      femaleCards: document.querySelectorAll('.character-card[aria-label^="F"]').length,
      maleCards: document.querySelectorAll('.character-card[aria-label^="M"]').length,
    };
  }), 2_000, 'WebKit catalogue state read');
}
function wardrobeOperationMarker(row) {
  return (operation, status, value) => {
    assert([
      'female-click', 'female-card-count', 'f03-click', 'f03-selection-read',
      'shirt-tab-click', 'shirt-tile-count', 'shirt-tile2-click', 'shirt-tile2-selection-read',
      'swatch-count', 'swatch2-click', 'swatch2-selection-read',
      'hat-tab-click', 'hat-tile1-click', 'hat-tile1-selection-read', 'select-count',
    ].includes(operation));
    assert(['begin', 'returned', 'rejected'].includes(status));
    assert(value === undefined || value === null || typeof value === 'boolean' ||
      (Number.isSafeInteger(value) && value >= 0));
    // Keep a timed-out case's pending operation intact during late cleanup.
    if (row.status === 'running') row.stage = 'wardrobe-' + operation + '-' + status;
    console.log('COOP_WARDROBE_OPERATION ' + JSON.stringify({ operation, status, value }));
  };
}

async function clickFemaleCatalogue(page, browserName, mark = () => {}) {
  const female = page.getByRole('button', { name: 'หญิง · 10 แบบ', exact: true });
  if (browserName !== 'webkit') { await female.click(); return; }
  const audit = webKitInputAudits.get(page);
  assert(audit, 'WebKit input observer must be installed before navigation');
  const control = { status: 'failed', observerProven: false };
  try {
    // Independent trusted pointer control. Failure must not suppress the original button click.
    await page.getByLabel(nameLabel, { exact: true }).click({ timeout: 3_000 });
    await within(audit.controlEvents, 500, 'Trusted positive-control phases');
    control.status = 'passed'; control.observerProven = true;
  } catch (controlError) { control.error = safeCaseText(controlError.message); }
  control.events = audit.events.filter(event => event.target === 'name-input');
  console.log('COOP_WARDROBE_POSITIVE_CONTROL ' + JSON.stringify({ browser: 'webkit', ...control }));
  mark('female-click', 'begin');
  try {
    await female.click(); // Original ordinary click, with its existing 15-second timeout.
    mark('female-click', 'returned');
  } catch (error) {
    mark('female-click', 'rejected'); // Synchronous evidence before any state read.
    let state, stateReadError;
    try { state = await readCatalogueState(page); }
    catch (readError) { stateReadError = safeCaseText(readError.message); }
    console.log('COOP_WARDROBE_CLICK_FAILURE ' + JSON.stringify({
      browser: 'webkit', observerProven: control.observerProven, events: audit.events,
      state, stateReadError, error: safeCaseText(error.message),
    }));
    const beforeKeyboard = audit.events.length;
    const keyboard = { status: 'failed' };
    try {
      await within(female.press('Enter', { timeout: 3_000 }), 3_000, 'WebKit keyboard activation diagnostic');
      keyboard.status = 'completed';
    } catch (keyboardError) { keyboard.error = safeCaseText(keyboardError.message); }
    try { keyboard.state = await readCatalogueState(page); }
    catch (readError) { keyboard.stateReadError = safeCaseText(readError.message); }
    keyboard.events = audit.events.slice(beforeKeyboard).filter(event => event.target === 'female-catalogue');
    console.log('COOP_WARDROBE_KEYBOARD_DIAGNOSTIC ' + JSON.stringify({ browser: 'webkit', ...keyboard }));
    throw error; // Keyboard evidence never turns the original failure into a pass.
  } finally { audit.stop(); }
}

async function wardrobe(page, browserName, mark = () => {}) {
  const panel = page.getByRole('tabpanel');
  assert.equal(await page.getByRole('tab').count(), 6);
  assert.equal(await panel.locator('.character-card').count(), 10);
  await clickFemaleCatalogue(page, browserName, mark);
  mark('female-card-count', 'begin');
  const femaleCardCount = await panel.locator('.character-card').count();
  mark('female-card-count', 'returned', femaleCardCount);
  assert.equal(femaleCardCount, 10);
  mark('f03-click', 'begin');
  await panel.getByRole('button', { name: /^F03 / }).click();
  mark('f03-click', 'returned');
  mark('f03-selection-read', 'begin');
  const femaleSelected = await panel.getByRole('button', { name: /^F03 / }).getAttribute('aria-pressed');
  mark('f03-selection-read', 'returned', femaleSelected === 'true' ? true : femaleSelected === 'false' ? false : null);
  assert.equal(femaleSelected, 'true');
  mark('shirt-tab-click', 'begin');
  await page.getByRole('tab', { name: 'เสื้อ', exact: true }).click();
  mark('shirt-tab-click', 'returned');
  mark('shirt-tile-count', 'begin');
  const shirtTileCount = await panel.locator('.wardrobe-tile').count();
  mark('shirt-tile-count', 'returned', shirtTileCount);
  assert.equal(shirtTileCount, 4);
  mark('shirt-tile2-click', 'begin');
  await panel.locator('.wardrobe-tile').nth(2).click();
  mark('shirt-tile2-click', 'returned');
  mark('shirt-tile2-selection-read', 'begin');
  const shirtSelected = await panel.locator('.wardrobe-tile').nth(2).getAttribute('aria-pressed');
  mark('shirt-tile2-selection-read', 'returned', shirtSelected === 'true' ? true : shirtSelected === 'false' ? false : null);
  assert.equal(shirtSelected, 'true');
  mark('swatch-count', 'begin');
  const swatchCount = await panel.locator('.swatch-button').count();
  mark('swatch-count', 'returned', swatchCount);
  assert.equal(swatchCount, 6);
  mark('swatch2-click', 'begin');
  await panel.locator('.swatch-button').nth(2).click();
  mark('swatch2-click', 'returned');
  mark('swatch2-selection-read', 'begin');
  const swatchSelected = await panel.locator('.swatch-button').nth(2).getAttribute('aria-pressed');
  mark('swatch2-selection-read', 'returned', swatchSelected === 'true' ? true : swatchSelected === 'false' ? false : null);
  assert.equal(swatchSelected, 'true');
  mark('hat-tab-click', 'begin');
  await page.getByRole('tab', { name: 'หมวก', exact: true }).click();
  mark('hat-tab-click', 'returned');
  mark('hat-tile1-click', 'begin');
  await panel.locator('.wardrobe-tile').nth(1).click();
  mark('hat-tile1-click', 'returned');
  mark('hat-tile1-selection-read', 'begin');
  const hatSelected = await panel.locator('.wardrobe-tile').nth(1).getAttribute('aria-pressed');
  mark('hat-tile1-selection-read', 'returned', hatSelected === 'true' ? true : hatSelected === 'false' ? false : null);
  assert.equal(hatSelected, 'true');
  mark('select-count', 'begin');
  const selectCount = await page.locator('select').count();
  mark('select-count', 'returned', selectCount);
  assert.equal(selectCount, 0, 'Wardrobe must use visible picture controls');
}

async function surfaces(browser, browserName, size, reducedMotion = 'no-preference') {
  const label = browserName + '-' + size.label + (reducedMotion === 'reduce' ? '-reduced' : '');
  return boundedCase(browser, label, 75_000, async ({ createContext, createPage, stage }, row) => {
    const context = await createContext({ viewport: { width: size.width, height: size.height }, isMobile: size.mobile, hasTouch: size.mobile, deviceScaleFactor: 1, reducedMotion, locale: 'th-TH' });
    if (browserName === 'webkit') await installWebKitInputAudit(context);
    const page = await createPage(context);
    if (browserName === 'webkit') observeWebKitInput(page);
    let previewImage = null;
    await stage('landing-document');
    await page.goto(preview.origin + '/', { waitUntil: 'domcontentloaded' });
    await page.getByRole('link', { name: /เข้าร่วมภารกิจ/ }).waitFor();
    assert.equal(await page.getByRole('link', { name: /เข้าร่วมภารกิจ/ }).getAttribute('href'), '/play');
    assert.equal(await page.getByRole('link', { name: /เปิดเวทีผู้สอน/ }).getAttribute('href'), '/host');
    await stage('landing-avatar');
    row.heroRaster = await avatarPainted(page, '.hero-avatar');
    row.checks.push({ landing: await noOverflow(page, label + ' landing') }); await shot(page, label + '-landing');
    await stage('host-entry');
    await page.goto(preview.origin + '/host', { waitUntil: 'domcontentloaded' });
    await page.getByRole('button', { name: /สร้างห้องเกม/ }).waitFor();
    row.checks.push({ hostEntry: await noOverflow(page, label + ' host entry') }); await shot(page, label + '-host-entry');
    await stage('player-entry-hydration');
    await page.goto(preview.origin + '/play?room=ABC234', { waitUntil: 'domcontentloaded' });
    await page.getByLabel(roomLabel, { exact: true }).waitFor();
    await page.waitForFunction(() => document.querySelector('.join-fields input')?.value === 'ABC234');
    if (size.label === 'mobile-320') {
      await page.getByLabel(roomLabel, { exact: true }).fill('A');
      await page.getByRole('button', { name: /พร้อมแล้ว เข้าสู่เวที/ }).click();
      await page.getByRole('alert').filter({ hasText: 'ใส่รหัสห้อง 6 ตัวให้ครบครับ' }).waitFor();
      await page.getByLabel(roomLabel, { exact: true }).fill('ABC234');
      await page.getByRole('button', { name: /พร้อมแล้ว เข้าสู่เวที/ }).click();
      await page.getByRole('alert').filter({ hasText: 'ตั้งชื่อผู้เล่นก่อนครับ' }).waitFor();
      await page.reload({ waitUntil: 'domcontentloaded' });
    }
    await page.getByLabel(nameLabel, { exact: true }).fill(syntheticName);
    await stage('wardrobe-controls');
    await wardrobe(page, browserName, wardrobeOperationMarker(row));
    await stage('wardrobe-avatar');
    row.avatarRaster = await avatarPainted(page, '.avatar-preview');
    row.checks.push({ wardrobe: await noOverflow(page, label + ' wardrobe') }); await shot(page, label + '-wardrobe');
    if (browserName === 'chromium' && reducedMotion === 'no-preference' && ['desktop-1280', 'mobile-390'].includes(size.label)) previewImage = await screenshotPreview(page, label + '-wardrobe');
    await stage('motion-controls');
    const toggle = page.getByRole('button', { name: 'เปิดหรือปิดการเคลื่อนไหว', exact: true });
    await page.waitForFunction(expected => document.querySelector('[aria-label="เปิดหรือปิดการเคลื่อนไหว"]')?.getAttribute('aria-pressed') === expected, reducedMotion === 'reduce' ? 'false' : 'true');
    row.motion = await page.evaluate(() => ({ reduced: matchMedia('(prefers-reduced-motion: reduce)').matches, runningCssAnimations: document.getAnimations().filter(x => x.playState === 'running').length }));
    if (reducedMotion === 'reduce') assert.equal(row.motion.runningCssAnimations, 0, 'Reduced motion should stop CSS effects');
    else {
      await toggle.click();
      assert.equal(await toggle.getAttribute('aria-pressed'), 'false');
      assert.equal(await page.evaluate(() => document.getAnimations().filter(x => x.playState === 'running').length), 0, 'Effects-off should stop CSS effects');
    }
    return { previewImage };
  });
}

async function realRoom(browser, browserName) {
  return boundedCase(browser, browserName + '-real-room', 150_000, async ({ createContext, createPage, stage }, row) => {
    const hostContext = await createContext({ viewport: { width: 1280, height: 900 }, locale: 'th-TH' });
    const playerContext = await createContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, locale: 'th-TH' });
    if (browserName === 'webkit') await installWebKitInputAudit(playerContext);
    const host = await createPage(hostContext); const player = await createPage(playerContext);
    if (browserName === 'webkit') observeWebKitInput(player);
    await stage('host-create-real-room');
    await host.goto(preview.origin + '/host', { waitUntil: 'domcontentloaded' });
    await host.getByRole('button', { name: /สร้างห้องเกม/ }).click(); await online(host);
    const room = (await host.locator('.room-code').textContent()).trim(); assert.match(room, /^[A-Z0-9]{6}$/);
    await host.getByRole('img', { name: 'QR สำหรับผู้เล่นเข้าห้อง', exact: true }).waitFor();
    const urlInput = host.getByLabel('ลิงก์ผู้เล่น', { exact: true });
    await host.waitForFunction(() => document.querySelector('.join-url')?.value.includes('/play?room='));
    const joinUrl = new URL(await urlInput.inputValue());
    assert.equal(joinUrl.origin, preview.origin); assert.equal(joinUrl.pathname, '/play');
    assert.deepEqual([...joinUrl.searchParams.keys()], ['room']); assert.equal(joinUrl.searchParams.get('room'), room);
    await stage('player-join-real-room');
    await player.goto(joinUrl.href, { waitUntil: 'domcontentloaded' });
    await player.getByLabel(nameLabel, { exact: true }).fill(syntheticName); await wardrobe(player, browserName, wardrobeOperationMarker(row));
    const [sent] = await Promise.all([
      player.waitForRequest(req => req.method() === 'POST' && new URL(req.url()).pathname === '/api/game' && req.postDataJSON()?.action === 'join'),
      player.getByRole('button', { name: /พร้อมแล้ว เข้าสู่เวที/ }).click(),
    ]);
    const submittedAvatar = sent.postDataJSON().avatar;
    assert.equal(Object.keys(submittedAvatar).length, 12); assert.equal(submittedAvatar.presetId, 'F03');
    await online(player); await player.getByRole('heading', { name: syntheticName, exact: true }).waitFor();
    await host.locator('.roster .mini-player').filter({ hasText: syntheticName }).waitFor();
    row.checks.push('Independent host/player contexts joined through the real local API; QR contains only the room');
    await stage('session-reload');
    await player.reload({ waitUntil: 'domcontentloaded' }); await online(player);
    await player.getByRole('heading', { name: syntheticName, exact: true }).waitFor();
    const persisted = await player.evaluate(() => JSON.parse(localStorage.getItem('coop-ai-game-avatar') || 'null'));
    assert.deepEqual(persisted, submittedAvatar); row.checks.push('Name, room session and twelve-field wardrobe survive reload');
    await shot(host, browserName + '-lobby-host'); await shot(player, browserName + '-lobby-player');
    await host.getByRole('button', { name: /เริ่มเกมกับผู้เล่น 1 คน/ }).click();
    let expectedScore = 0;
    for (let number = 1; number <= 15; number++) {
      await stage('question-' + number);
      await question(host, number); await question(player, number);
      assert.equal(await host.locator('.answer-grid button:disabled').count(), 3, 'Instructor cannot submit learner answers');
      assert.equal(await player.locator('.host-controls').count(), 0, 'Learner must not have instructor progression controls');
      const answered = number !== 2;
      if (answered) {
        await player.locator('.answer-grid button').first().click();
        await player.locator('.answer-status').filter({ hasText: 'ส่งคำตอบแล้ว' }).waitFor();
      } else {
        await player.waitForFunction(() => document.querySelector('.countdown')?.firstChild?.textContent === '0', undefined, { timeout: 20_000 });
        assert.equal(await player.locator('.answer-grid button:disabled').count(), 3);
        assert.equal(await player.locator('.explanation').count(), 0);
        assert.equal(await host.locator('.explanation').count(), 0);
        await question(host, 2); row.checks.push('Real fifteen-second deadline locks answers without revealing or advancing');
      }
      if (number === 1) { await noOverflow(player, 'mobile active question'); await shot(player, browserName + '-question-player'); await shot(host, browserName + '-question-host'); }
      await stage('reveal-' + number);
      await host.locator('.host-controls button').click();
      await host.locator('.explanation').waitFor(); await player.locator('.explanation').waitFor();
      const correctChoice = await player.locator('.answer-grid button').evaluateAll(buttons => buttons.findIndex(button => button.classList.contains('correct')));
      assert(correctChoice >= 0 && correctChoice <= 2, 'One visible correct choice after reveal');
      assert.equal(await player.locator('.answer.correct').count(), 1);
      if (answered && correctChoice === 0) expectedScore++;
      await player.locator('.own-result').filter({ hasText: 'คะแนนตอนนี้ ' + expectedScore + ' / 15' }).waitFor();
      assert.equal(await player.locator('.answer-grid button:disabled').count(), 3);
      if (number === 1) { await noOverflow(host, 'desktop reveal'); await shot(host, browserName + '-reveal-host'); await shot(player, browserName + '-reveal-player'); }
      await host.locator('.host-controls button').click();
    }
    await stage('final-scoreboard');
    await host.getByRole('table', { name: 'คะแนนผู้เล่นทั้งหมด', exact: true }).waitFor();
    await player.getByRole('table', { name: 'คะแนนผู้เล่นทั้งหมด', exact: true }).waitFor();
    assert.equal((await player.locator('.personal-finish .big-score').innerText()).replace(/\s/g, ''), expectedScore + '/15');
    assert.equal(await player.locator('.score-row.me').count(), 1); row.score = expectedScore;
    for (const size of sizes) {
      await player.setViewportSize({ width: size.width, height: size.height });
      await noOverflow(player, size.label + ' final scoreboard'); await shot(player, browserName + '-' + size.label + '-final');
    }
    row.checks.push('All fifteen questions, instructor reveals and final score rendered through real API');
    await stage('instructor-reset');
    assert.equal(await player.getByRole('button', { name: /เริ่มรอบใหม่/ }).count(), 0);
    await host.getByRole('button', { name: /เริ่มรอบใหม่/ }).click();
    await host.getByRole('dialog').waitFor(); await host.getByRole('button', { name: 'ยังไม่เริ่มใหม่', exact: true }).click();
    await host.getByRole('table', { name: 'คะแนนผู้เล่นทั้งหมด', exact: true }).waitFor();
    await host.getByRole('button', { name: /เริ่มรอบใหม่/ }).click();
    await host.getByRole('button', { name: 'ยืนยัน เริ่มรอบใหม่', exact: true }).click();
    await host.locator('.host-lobby').waitFor(); await player.locator('.player-lobby').waitFor();
    await player.reload({ waitUntil: 'domcontentloaded' }); await online(player);
    await player.getByRole('heading', { name: syntheticName, exact: true }).waitFor();
    assert.deepEqual(await player.evaluate(() => JSON.parse(localStorage.getItem('coop-ai-game-avatar') || 'null')), submittedAvatar);
    row.checks.push('Reset requires instructor confirmation and returns both clients to lobby with identity and wardrobe retained');
  });
}


const surfaceOrder = diagnosticCase ? [sizes[3]] : [sizes[3], sizes[1], sizes[0], sizes[2]];
const browserPlan = diagnosticCase ? [['webkit', webkit]] : [['chromium', chromium], ['webkit', webkit]];
for (const [name, type] of browserPlan) {
  let browser, prerequisite = true;
  try {
    browser = await type.launch({ headless: true, timeout: 20_000 });
    for (const size of surfaceOrder) {
      if (!prerequisite) { await notRun(name + '-' + size.label, 'Earlier browser surface failed; fix that prerequisite before dependent scenarios'); continue; }
      prerequisite = await surfaces(browser, name, size);
    }
    if (!diagnosticCase) {
      if (prerequisite) prerequisite = await surfaces(browser, name, sizes[1], 'reduce');
      else await notRun(name + '-mobile-390-reduced', 'Earlier browser surface failed');
      if (prerequisite) await realRoom(browser, name);
      else await notRun(name + '-real-room', 'Browser entry or wardrobe prerequisites failed; room journey remains unverified');
    }
  } catch (error) {
    const row = { label: name + '-launch', status: 'failed', stage: 'browser-lifecycle', error: safeCaseText(error.message) };
    report.cases.push(row); emitCase(row); await saveReport();
    const expectedLabels = [...surfaceOrder.map(size => name + '-' + size.label), ...(diagnosticCase ? [] : [name + '-mobile-390-reduced', name + '-real-room'])];
    for (const label of expectedLabels) {
      if (!report.cases.some(row => row.label === label)) await notRun(label, 'Browser initialization or lifecycle failed');
    }
  } finally {
    if (browser) {
      try { await within(browser.close(), 5_000, name + ' browser cleanup'); }
      catch (error) {
        const row = { label: name + '-cleanup', status: 'failed', stage: 'browser-cleanup', error: safeCaseText(error.message) };
        report.cases.push(row); emitCase(row);
      }
    }
    await saveReport();
  }
}
clearTimeout(deadline);
const failed = report.cases.filter(row => row.status === 'failed').length;
const notExecuted = report.cases.filter(row => row.status === 'not-run').length;
const passed = report.cases.filter(row => row.status === 'passed').length;
report.fullSuitePassed = !diagnosticCase && passed === 12 && failed === 0 && notExecuted === 0;
await saveReport();
console.log(JSON.stringify({ check: diagnosticCase ? 'webkit-click-diagnostic' : 'real-browser-smoke', mode: report.mode, acceptanceEligible: report.acceptanceEligible, fullSuiteRequired: 12, fullSuitePassed: report.fullSuitePassed, selectedCase: diagnosticCase || null, planned: report.plannedCases, cases: report.cases.length, passed, failed, notExecuted, evidence: 'browser-proof screenshots and report.json' }));
// All evidence is saved before exit. A broken browser process must not retain
// the Node runner indefinitely after its bounded cleanup has already failed.
process.exit(failed || notExecuted ? 1 : 0);
