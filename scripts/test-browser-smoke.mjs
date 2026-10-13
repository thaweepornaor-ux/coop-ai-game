import assert from 'node:assert/strict';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

// This check may create synthetic rooms only in the disposable CI preview.
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
  plannedCases: 14,
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
const nameLabel = '2. ชื่อผู้เล่น';
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
    return within(pending, 25_000, 'Context initialization');
  };
  const createPage = async context => {
    const page = await within(context.newPage(), 25_000, 'Page initialization');
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
  if (!source) {
    // Current playable fallback is an inline front-facing SVG, not a raster canvas.
    // Verify meaningful painted geometry and a visible box in the actual browser.
    const svg = container.querySelector('svg');
    if (!svg || svg.getBoundingClientRect().width < 16 || svg.getBoundingClientRect().height < 16) return null;
    if (getComputedStyle(svg).visibility === 'hidden' || Number(getComputedStyle(svg).opacity) === 0) return null;
    const shapes = svg.querySelectorAll('path,ellipse,rect,circle,polygon').length;
    if (shapes < 15) return null;
    return { source: 'inline-svg', shapeCount: shapes, width: svg.getBoundingClientRect().width };
  }
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

async function wardrobe(page) {
 const gallery=page.locator('.quick-characters');
 assert.equal(await gallery.getByRole('button').count(),10);
 await page.getByRole('button',{name:'ผู้หญิง · 10 แบบ',exact:true}).click();
 assert.equal(await gallery.getByRole('button').count(),10);
 const chosen=gallery.getByRole('button',{name:/^F03 /});
 await chosen.click();
 assert.equal(await chosen.getAttribute('aria-pressed'),'true','Choosing the face changes real selected state');
 await page.getByRole('button',{name:/อยากเปลี่ยนผม สีผิว/}).click();
 const options=page.locator('.quick-options fieldset');
 assert.equal(await options.count(),7,'Only seven optional wardrobe groups are displayed');
 const styles=options.nth(2).locator('button');
 await styles.nth(1).click();
 assert.equal(await styles.nth(1).getAttribute('aria-pressed'),'true');
 const shirtColors=options.nth(3).locator('button');
 await shirtColors.nth(2).click();
 assert.equal(await shirtColors.nth(2).getAttribute('aria-pressed'),'true');
 assert.equal(await page.locator('select').count(),0);
 assert.equal(await page.locator('input[placeholder*="รหัส"]').count(),0,'No learner room-code field');
}

async function surfaces(browser, browserName, size, reducedMotion = 'no-preference') {
  const label = browserName + '-' + size.label + (reducedMotion === 'reduce' ? '-reduced' : '');
  return boundedCase(browser, label, 75_000, async ({ createContext, createPage, stage }, row) => {
    const context = await createContext({ viewport: { width: size.width, height: size.height }, isMobile: size.mobile, hasTouch: size.mobile, deviceScaleFactor: 1, reducedMotion, locale: 'th-TH' });
    const page = await createPage(context);
    let previewImage = null;
    // Only the projector opens an instructor room. Mobile learners use QR deep links.
    // This prevents synthetic test contexts from consuming the real anti-abuse quota.
    if(size.label==='desktop-1280'&&reducedMotion==='no-preference'){
      await stage('landing-document');
      await page.goto(preview.origin+'/',{waitUntil:'domcontentloaded'});
      await page.locator('.host-lobby .qr img').waitFor({timeout:25000});
      row.checks.push({instructor:await noOverflow(page,label+' instructor')});
      await shot(page,label+'-projector');
      const releaseResponse=await page.request.get(preview.origin+'/coop-release.json');
      assert.equal(releaseResponse.status(),200);
      const release=await releaseResponse.json();
      assert.equal(release.application,'coop-ai-game');
      await stage('host-entry');
      await page.goto(preview.origin+'/host',{waitUntil:'domcontentloaded'});
      await page.locator('.host-lobby .qr img').waitFor({timeout:20000});
      row.checks.push({hostEntry:await noOverflow(page,label+' host')});
      // Recover a genuinely unusable saved instructor session with one tap.
      // This runs in the disposable D1 preview, not the public staging site.
      if(browserName==='chromium'){
        await stage('expired-instructor-session-recovery');
        await page.evaluate(()=>{
          localStorage.setItem('coop-ai-game-session-host',JSON.stringify({
            role:'host',room:'ZZZZZZ',token:'a'.repeat(64)
          }));
        });
        await page.reload({waitUntil:'domcontentloaded'});
        await page.getByRole('button',{name:'เริ่มเกมใหม่',exact:true}).waitFor({timeout:15000});
        await page.getByRole('button',{name:'เริ่มเกมใหม่',exact:true}).click();
        await page.locator('.host-lobby .qr img').waitFor({timeout:20000});
        assert.notEqual((await page.locator('.room-code').textContent()).trim(),'ZZZZZZ');
        row.checks.push({expiredInstructorRecovered:true});
      }
    }
    await stage('player-entry-hydration');
    await page.goto(preview.origin+'/play?room=ABC234',{waitUntil:'domcontentloaded'});
    await page.locator('.quick-characters').waitFor({timeout:15000});
    assert.equal(await page.getByRole('button',{name:'เข้าเล่นเกม →'}).isDisabled(),true);
    assert.equal(await page.locator('input[placeholder*="รหัส"]').count(),0);
    await page.getByLabel(nameLabel,{exact:true}).fill(syntheticName);
    await stage('wardrobe-controls');
    await wardrobe(page);
    // Regression: the gallery tab must follow an asynchronously restored female preset.
    if(browserName==='chromium' && size.label==='mobile-390' && reducedMotion==='no-preference'){
      await stage('saved-female-preset-restore');
      await page.evaluate(()=>{
        localStorage.setItem('coop-ai-game-avatar',JSON.stringify({presetId:'F03',bodyStyle:'female'}));
        localStorage.setItem('coop-ai-game-name','ผู้เล่นทดสอบ');
      });
      await page.reload({waitUntil:'domcontentloaded'});
      await page.waitForFunction(()=>{
        const female=[...document.querySelectorAll('.quick-gender button')].find(x=>x.textContent?.includes('ผู้หญิง'));
        return female?.getAttribute('aria-pressed')==='true' && document.querySelector('.quick-character.selected')?.textContent?.includes('F03');
      },null,{timeout:15000});
      assert.equal(await page.getByLabel(nameLabel,{exact:true}).inputValue(),syntheticName);
      row.checks.push({femaleSelectionRestored:true});
    }
    await stage('wardrobe-avatar');
    const overlap = await page.evaluate(() => {
      const parent=document.querySelector('.quick-player .customizer-preview');
      const title=parent?.querySelector('h1');
      const portrait=parent?.querySelector('.character-stage');
      const caption=parent?.querySelector('.character-name');
      if(!parent||!title||!portrait||!caption)return {error:'Expected preview elements missing'};
      const intersect=(a,b)=>{const x=a.getBoundingClientRect(),y=b.getBoundingClientRect();return Math.max(0,Math.min(x.right,y.right)-Math.max(x.left,y.left))*Math.max(0,Math.min(x.bottom,y.bottom)-Math.max(x.top,y.top))};
      return {titlePortrait:intersect(title,portrait),captionPortrait:intersect(caption,portrait),titleCaption:intersect(title,caption)};
    });
    assert.deepEqual(overlap,{titlePortrait:0,captionPortrait:0,titleCaption:0},label+' preview must never cover title or player name');
    row.checks.push({previewNoOverlap:true});
    if (size.width <= 900) {
      assert.equal(await page.locator('.quick-player .customizer-preview').isVisible(),false,'Mobile must show face choices without duplicate hero panel');
      const firstFace=await page.locator('.quick-character').first().boundingBox();
      assert.ok(firstFace&&firstFace.y < size.height,'A face choice must begin within the initial phone viewport');
      row.checks.push({mobileFaceChoicesAboveFold:true});
    }
    row.avatarRaster = await avatarPainted(page, size.width <= 900 ? '.quick-character.selected' : '.avatar-preview');
    row.checks.push({ wardrobe: await noOverflow(page, label + ' wardrobe') }); await shot(page, label + '-wardrobe');
    if (browserName === 'chromium' && reducedMotion === 'no-preference' && ['desktop-1280', 'mobile-390'].includes(size.label)) previewImage = await screenshotPreview(page, label + '-wardrobe');
    await stage('motion-controls');
    // Learners should not face technical animation toggles on their quick-join screen.
    const toggle = page.getByRole('button', { name: 'เปิดหรือปิดการเคลื่อนไหว', exact: true });
    assert.equal(await toggle.isVisible(),false,'Advanced motion settings must not clutter learner setup');
    row.motion=await page.evaluate(()=>({reduced:matchMedia('(prefers-reduced-motion: reduce)').matches,runningCssAnimations:document.getAnimations().filter(x=>x.playState==='running').length}));
    if(reducedMotion==='reduce')assert.equal(row.motion.runningCssAnimations,0,'Reduced motion should stop CSS effects');
    return { previewImage };
  });
}

async function realRoom(browser, browserName) {
  return boundedCase(browser, browserName + '-real-room', 150_000, async ({ createContext, createPage, stage }, row) => {
    const hostContext = await createContext({ viewport: { width: 1280, height: 900 }, locale: 'th-TH' });
    const playerContext = await createContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, locale: 'th-TH' });
    const host = await createPage(hostContext); const player = await createPage(playerContext);
    await stage('host-create-real-room');
    await host.goto(preview.origin + '/host', { waitUntil: 'domcontentloaded' });
    await host.locator('.host-lobby .qr img').waitFor({timeout:20000}); await online(host);
    assert.equal(await host.locator('header .brand').evaluate(el=>el.tagName),'DIV','Header must not navigate away from a live game');
    assert.equal(await host.getByRole('button',{name:/เต็มจอโปรเจคเตอร์/}).count(),1,'Instructor has a projector full-screen control');
    const room = (await host.locator('.room-code').textContent()).trim(); assert.match(room, /^[A-Z0-9]{6}$/);
    await host.getByRole('img', { name: 'QR สำหรับผู้เล่นเข้าห้อง', exact: true }).waitFor();
    const urlInput = host.getByLabel('ลิงก์ผู้เล่น', { exact: true });
    await host.waitForFunction(() => document.querySelector('.join-url')?.value.includes('/play?room='));
    const joinUrl = new URL(await urlInput.inputValue());
    assert.equal(joinUrl.origin, preview.origin); assert.equal(joinUrl.pathname, '/play');
    assert.deepEqual([...joinUrl.searchParams.keys()], ['room']); assert.equal(joinUrl.searchParams.get('room'), room);
    await stage('player-join-real-room');
    await player.goto(joinUrl.href, { waitUntil: 'domcontentloaded' });
    await player.locator('.quick-characters').waitFor({timeout:20000});
    await player.locator('.quick-characters').waitFor({timeout:15000});
    await player.getByLabel(nameLabel, { exact: true }).fill(syntheticName); await wardrobe(player);
    const [sent] = await Promise.all([
      player.waitForRequest(req => req.method() === 'POST' && new URL(req.url()).pathname === '/api/game' && req.postDataJSON()?.action === 'join'),
      player.getByRole('button', { name: 'เข้าเล่นเกม →' }).click(),
    ]);
    const submittedAvatar = sent.postDataJSON().avatar;
    assert.equal(Object.keys(submittedAvatar).length, 13); assert.equal(submittedAvatar.presetId, 'F03'); assert.equal(submittedAvatar.bodyStyle,'female');
    await online(player); await player.getByRole('heading', { name: syntheticName, exact: true }).waitFor();
    assert.equal(await player.locator('header .brand').evaluate(el=>el.tagName),'DIV','Player must not accidentally return to host by tapping the header');
    assert.equal(await player.getByRole('button',{name:/เต็มจอโปรเจคเตอร์/}).count(),0);
    await host.locator('.roster .mini-player').filter({ hasText: syntheticName }).waitFor();
    row.checks.push('Independent host/player contexts joined through the real local API; QR contains only the room');
    await stage('edit-profile-without-duplicate-join');
    await player.getByRole('button',{name:'เปลี่ยนชื่อ / ตัวละคร',exact:true}).click();
    await player.locator('.inline-profile-form').waitFor();
    await player.getByRole('button',{name:'ผู้ชาย · 10 แบบ'}).click();
    await player.locator('.inline-profile-form .quick-character').filter({hasText:'M02'}).click();
    const interimName=syntheticName+'ใหม่';
    await player.locator('#edit-player-name').fill(interimName);
    const [edited] = await Promise.all([
      player.waitForRequest(req=>req.method()==='POST'&&new URL(req.url()).pathname==='/api/game'&&req.postDataJSON()?.action==='profile'),
      player.getByRole('button',{name:'บันทึกตัวละครและชื่อ'}).click()
    ]);
    assert.equal(edited.postDataJSON().avatar.presetId,'M02');
    await player.getByRole('heading',{name:interimName,exact:true}).waitFor();
    await host.locator('.roster .mini-player').filter({hasText:interimName}).waitFor();
    assert.equal(await host.locator('.roster .mini-player').count(),1,'Editing an existing player cannot create a duplicate roster entry');
    await player.getByRole('button',{name:'เปลี่ยนชื่อ / ตัวละคร',exact:true}).click();
    await player.getByRole('button',{name:'ผู้หญิง · 10 แบบ'}).click();
    await player.locator('.inline-profile-form .quick-character').filter({hasText:'F03'}).click();
    await player.locator('#edit-player-name').fill(syntheticName);
    await player.getByRole('button',{name:'บันทึกตัวละครและชื่อ'}).click();
    await player.getByRole('heading',{name:syntheticName,exact:true}).waitFor();
    await host.locator('.roster .mini-player').filter({hasText:syntheticName}).waitFor();
    assert.equal(await host.locator('.roster .mini-player').count(),1);
    row.checks.push('Name and selected character update the SAME player twice, with no duplicate or second join');
    await stage('session-reload');
    await player.reload({ waitUntil: 'domcontentloaded' }); await online(player);
    await player.getByRole('heading', { name: syntheticName, exact: true }).waitFor();
    const persisted = await player.evaluate(() => JSON.parse(localStorage.getItem('coop-ai-game-avatar') || 'null'));
    assert.equal(persisted.presetId,'F03'); assert.equal(persisted.bodyStyle,'female'); row.checks.push('Edited name and wardrobe survive reload under the same player token');
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
        await player.waitForFunction(() => document.querySelector('.countdown .timer-value')?.textContent?.trim() === '0', undefined, { timeout: 20_000 });
        assert.equal(await player.locator('.answer-grid button:disabled').count(), 3);
        assert.equal(await player.locator('.explanation').count(), 0);
        assert.equal(await host.locator('.explanation').count(), 0);
        await question(host, 2); row.checks.push('Real fifteen-second deadline locks answers without revealing or advancing');
      }
      if (number === 1) {
        await noOverflow(player,'mobile active question');
        const timerSize=await host.locator('.countdown').boundingBox();
        assert.ok(timerSize && timerSize.width>=130 && timerSize.height>=130,'Projector countdown must be large and visible');
        const titleSize=await host.locator('.question-card h1').evaluate(el=>parseFloat(getComputedStyle(el).fontSize));
        assert.ok(titleSize>=35,'Projector question must have a prominently readable font');
        await shot(player,browserName+'-question-player');await shot(host,browserName+'-question-host');
      }
      await stage('reveal-' + number);
      await host.locator('.host-controls button').click();
      await host.locator('.explanation').waitFor(); await player.locator('.explanation').waitFor();
      const correctChoice = await player.locator('.answer-grid button').evaluateAll(buttons => buttons.findIndex(button => button.classList.contains('correct')));
      assert(correctChoice >= 0 && correctChoice <= 2, 'One visible correct choice after reveal');
      assert.equal(await player.locator('.answer.correct').count(), 1);
      if (answered && correctChoice === 0) expectedScore++;
      await player.locator('.own-result').filter({ hasText: 'คะแนนตอนนี้ ' + expectedScore + ' / 15' }).waitFor();
      assert.equal(await player.locator('.answer-grid button:disabled').count(), 3);
      if (number === 1) {
        await noOverflow(host,'desktop reveal');
        // Layout stress-test with twenty-five players without changing the actual room.
        // Synthetic cloned cells are only a visual geometry probe, not fake API players.
        await stage('projector-25-person-reveal-layout');
        const actual=await host.locator('.reveal-tiles .reveal-person').count();
        assert.equal(actual,1,'Actual backend still has exactly one enrolled test player');
        await host.evaluate(()=>{
          const grid=document.querySelector('.reveal-tiles');
          const first=grid?.querySelector('.reveal-person');
          if(!grid||!first)throw Error('Missing actual reveal board');
          for(let i=1;i<25;i++){
            const copy=first.cloneNode(true);
            copy.dataset.synthetic='true';
            copy.classList.toggle('correct',i%3===0);
            copy.classList.toggle('incorrect',i%3===1);
            copy.classList.toggle('unanswered',i%3===2);
            copy.querySelector('.reveal-details strong').textContent='ผู้เรียนทดสอบ '+String(i+1).padStart(2,'0');
            grid.appendChild(copy);
          }
        });
        for(const vp of [{width:1280,height:720},{width:1920,height:1080}]){
          await host.setViewportSize(vp);
          const geometry=await host.evaluate(()=>{
            const cards=[...document.querySelectorAll('.reveal-tiles .reveal-person')];
            const g=document.querySelector('.reveal-tiles').getBoundingClientRect();
            const viewport={width:innerWidth,height:innerHeight};
            const outside=cards.map((c,i)=>({i,rect:c.getBoundingClientRect()})).filter(({rect})=>
              rect.height<35||rect.width<110||rect.top<0||rect.bottom>viewport.height+1||rect.left<0||rect.right>viewport.width+1);
            return {count:cards.length,outside:outside.map(x=>x.i),scrollOverflow:g.height>innerHeight,
              pageOverflow:document.documentElement.scrollHeight>innerHeight+4,gridHeight:g.height,viewport};
          });
          assert.equal(geometry.count,25);
          assert.deepEqual(geometry.outside,[], 'All twenty-five avatar cards must be in frame at '+vp.width+'x'+vp.height);
          assert.equal(geometry.pageOverflow,false,'25 learners must not require projector page scrolling');
          await shot(host,browserName+'-'+vp.width+'x'+vp.height+'-reveal-25-synthetic');
        }
        await host.evaluate(()=>document.querySelectorAll('[data-synthetic="true"]').forEach(el=>el.remove()));
        await host.setViewportSize({width:1280,height:900});
        row.checks.push('Synthetic visual geometry: 25 avatar/score results simultaneously in projector at 1280x720 and 1920x1080');
        await shot(host,browserName+'-reveal-host');await shot(player,browserName+'-reveal-player');
      }
      await host.locator('.host-controls button').click();
    }
    await stage('final-scoreboard');
    await host.getByRole('table', { name: 'คะแนนผู้เล่นทั้งหมด', exact: true }).waitFor();
    await player.getByRole('table', { name: 'คะแนนผู้เล่นทั้งหมด', exact: true }).waitFor();
    assert.equal((await player.locator('.personal-finish .big-score').innerText()).replace(/\s/g, ''), expectedScore + '/15');
    assert.equal(await player.locator('.score-row.me').count(), 1); row.score = expectedScore;
    await stage('teacher-export-scores');
    assert.equal(await player.getByRole('button',{name:/ดาวน์โหลดผลคะแนน CSV/}).count(),0,'Learners cannot use the teacher CSV export');
    const [download]=await Promise.all([
      host.waitForEvent('download',{timeout:15000}),
      host.getByRole('button',{name:/ดาวน์โหลดผลคะแนน CSV/}).click()
    ]);
    assert.match(download.suggestedFilename(),/^AI-Assessment-Results-[0-9]{4}-[0-9]{2}-[0-9]{2}[.]csv$/);
    row.checks.push('Instructor can export final score CSV, but learner cannot');
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
    assert.deepEqual(await player.evaluate(() => JSON.parse(localStorage.getItem('coop-ai-game-avatar') || 'null')),persisted);
    row.checks.push('Reset requires instructor confirmation and returns both clients to lobby with identity and wardrobe retained');
  });
}



/** Twenty-five REAL API enrollments in disposable D1, unlike copied browser tiles.
 * One projector renders the actual backend results for all 25 in a single frame.
 * Never call a public Worker or mutate a persistent database from this test.
 */
async function realTwentyFive(browser,browserName){
 return boundedCase(browser,browserName+'-real-25-attendees',105_000,async({createContext,createPage,stage},row)=>{
   const context=await createContext({viewport:{width:1280,height:720},locale:'th-TH'});
   const host=await createPage(context);
   await stage('create-real-classroom');
   await host.goto(preview.origin+'/host',{waitUntil:'domcontentloaded'});
   await host.locator('.host-lobby .qr img').waitFor({timeout:20000});
   const room=(await host.locator('.room-code').textContent()).trim();
   assert.match(room,/^[A-Z0-9]{6}$/);
   await stage('enroll-25-genuine-players');
   const joined=[];
   for(let i=0;i<25;i++){
     const female=i%2===1;
     const code=(female?'F':'M')+String(Math.floor(i/2)%10+1).padStart(2,'0');
     const response=await host.request.post(preview.origin+'/api/game',{data:{
       action:'join',room,name:'ผู้เรียน '+String(i+1).padStart(2,'0'),
       avatar:{presetId:code,bodyStyle:female?'female':'male'}
     },timeout:12000});
     assert.equal(response.status(),201,'Player '+(i+1)+' should join with an approved character');
     const record=await response.json();
     assert.equal(record.playerId?.length>0,true);
     joined.push(record);
   }
   await host.waitForFunction(()=>document.querySelectorAll('.host-lobby .mini-player').length===25,null,{timeout:18000});
   assert.equal(await host.locator('.host-lobby .mini-player').count(),25);
   row.checks.push('Twenty-five actual authenticated players joined disposable D1 with 20 distinct character IDs');
   await shot(host,browserName+'-25-real-lobby');
   await stage('begin-game-with-25-players');
   await host.getByRole('button',{name:/เริ่มเกมกับผู้เล่น 25 คน/}).click();
   await question(host,1);
   const firstState=await host.request.get(preview.origin+'/api/game?room='+room,{
     headers:{Authorization:'Bearer '+joined[0].token}
   });
   assert.equal(firstState.status(),200);
   const gameState=await firstState.json();
   assert.equal(gameState.room.questionIndex,0);
   const action=(token,choice)=>host.request.post(preview.origin+'/api/game',{
     headers:{Authorization:'Bearer '+token},
     data:{action:'answer',room,roundId:gameState.room.roundId,
       questionIndex:gameState.room.questionIndex,choice}
   });
   const answeredRight=await action(joined[0].token,1);
   const answeredWrong=await action(joined[1].token,0);
   assert.equal(answeredRight.status(),200);
   assert.equal(answeredWrong.status(),200);
   await stage('reveal-genuine-25-player-result-board');
   await host.locator('.host-controls button').click();
   await host.locator('.reveal-tiles .reveal-person').first().waitFor({timeout:15000});
   await host.waitForFunction(()=>document.querySelectorAll('.reveal-tiles .reveal-person').length===25,null,{timeout:15000});
   assert.equal(await host.locator('.reveal-person.correct').count(),1);
   assert.equal(await host.locator('.reveal-person.incorrect').count(),1);
   assert.equal(await host.locator('.reveal-person.unanswered').count(),23);
   const names=await host.locator('.reveal-person .reveal-details strong').allTextContents();
   assert.equal(new Set(names).size,25,'Every real learner must appear once');
   const graphicCount=await host.locator('.reveal-person svg').count();
   assert.equal(graphicCount,25,'Every real learner has a rendered character image');
   for(const viewport of [{width:1280,height:720},{width:1920,height:1080}]){
     await stage('real-25-in-frame-'+viewport.width+'x'+viewport.height);
     await host.setViewportSize(viewport);
     const dimensions=await host.evaluate(()=>{
       const viewport={width:innerWidth,height:innerHeight};
       const cards=[...document.querySelectorAll('.reveal-tiles .reveal-person')];
       const outside=cards.map((x,i)=>({i,r:x.getBoundingClientRect()})).filter(({r})=>
         r.width<110||r.height<35||r.left<0||r.right>innerWidth+1||r.top<0||r.bottom>innerHeight+1);
       const clipped=cards.map((x,i)=>({i,parent:x.closest('.reveal-tiles'),rect:x.getBoundingClientRect()}))
         .filter(({parent,rect})=>{const p=parent.getBoundingClientRect();return rect.top<p.top-1||rect.bottom>p.bottom+1});
       return {count:cards.length,outside:outside.map(x=>x.i),clipped:clipped.map(x=>x.i),
         viewport,pageScroll:document.documentElement.scrollHeight>innerHeight+4};
     });
     assert.equal(dimensions.count,25);
     assert.deepEqual(dimensions.outside,[],'All real player tiles must be on projector '+viewport.width+'x'+viewport.height);
     assert.deepEqual(dimensions.clipped,[],'No real player may be clipped inside board '+viewport.width+'x'+viewport.height);
     assert.equal(dimensions.pageScroll,false,'No vertical scrolling for projector reveal '+viewport.width+'x'+viewport.height);
     await shot(host,browserName+'-real-25-reveal-'+viewport.width+'x'+viewport.height);
   }
   row.checks.push('Twenty-five real avatar cards, all answer-status groups and scores fit at 720p and 1080p without scrolling');
 });
}

const surfaceOrder = [sizes[3], sizes[1], sizes[0], sizes[2]];
for (const [name, type] of [['chromium', chromium], ['webkit', webkit]]) {
  let browser, prerequisite = true;
  try {
    browser = await type.launch({ headless: true, timeout: 20_000 });
    for (const size of surfaceOrder) {
      if (!prerequisite) { await notRun(name + '-' + size.label, 'Earlier browser surface failed; fix that prerequisite before dependent scenarios'); continue; }
      prerequisite = await surfaces(browser, name, size);
    }
    if (prerequisite) prerequisite = await surfaces(browser, name, sizes[1], 'reduce');
    else await notRun(name + '-mobile-390-reduced', 'Earlier browser surface failed');
    if(prerequisite){
      prerequisite=await realRoom(browser,name);
      if(prerequisite)await realTwentyFive(browser,name);
      else await notRun(name+'-real-25-attendees','Ordinary game journey failed; twenty-five-player test not yet valid');
    }else{
      await notRun(name+'-real-room','Browser entry or wardrobe prerequisites failed; room journey remains unverified');
      await notRun(name+'-real-25-attendees','Browser entry or wardrobe prerequisites failed');
    }
  } catch (error) {
    const row = { label: name + '-launch', status: 'failed', stage: 'browser-lifecycle', error: safeCaseText(error.message) };
    report.cases.push(row); emitCase(row); await saveReport();
    for (const label of [...surfaceOrder.map(size => name + '-' + size.label), name + '-mobile-390-reduced', name + '-real-room', name+'-real-25-attendees']) {
      if (!report.cases.some(row => row.label === label)) await notRun(label, 'Browser initialization or lifecycle failed');
    }
  } finally {
    if (browser) {
      try { await within(browser.close(), 15_000, name + ' browser cleanup'); }
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
console.log(JSON.stringify({ check: 'real-browser-smoke', planned: report.plannedCases, cases: report.cases.length, passed: report.cases.filter(row => row.status === 'passed').length, failed, notExecuted, evidence: 'browser-proof screenshots and report.json' }));
// All evidence is saved before exit. A broken browser process must not retain
// the Node runner indefinitely after its bounded cleanup has already failed.
process.exit(failed || notExecuted ? 1 : 0);
