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
const nameLabel = 'ชื่อที่ใช้ในเกม';
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
  const contexts = new Set(), pages = [], errors = [], failedRequests = [];
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
    page.on('pageerror', error => errors.push(safeCaseText(`${page.url()} :: ${error.message}`)));
    page.on('requestfailed', request => {
      if (failedRequests.length >= 12) return;
      let pathname = 'unknown';
      try { pathname = new URL(request.url()).pathname; } catch {}
      failedRequests.push({page: safeCaseText(new URL(page.url()).pathname), method: request.method(), pathname, reason: safeCaseText(request.failure()?.errorText || 'unknown')});
    });
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
    row.failedRequests = failedRequests.slice(0, 12);
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
/** Keep both the TOP controls and BOTTOM Start/Exit buttons visible.
 * Verify actual screen geometry, not just stylesheet presence.
 * Participant cards may scroll inside the scoreboard when there are many.
 */
async function assertHostLobbyFits(page, label) {
  const geometry=await page.evaluate(()=>{
    const rect=selector=>{
      const el=document.querySelector(selector);
      if(!el)return null;
      const r=el.getBoundingClientRect();
      return {top:Math.round(r.top),bottom:Math.round(r.bottom),left:Math.round(r.left),
        right:Math.round(r.right),width:Math.round(r.width),height:Math.round(r.height)};
    };
    return {
      viewport:{width:innerWidth,height:innerHeight},
      docHeight:document.documentElement.scrollHeight,
      scrollY:window.scrollY,
      header:rect('.game-shell > .topbar'),
      connection:rect('.game-shell > .connection'),
      lobby:rect('.host-lobby'),
      left:rect('.host-lobby .lobby-main'),
      right:rect('.host-lobby .roster-panel'),
      qr:rect('.host-lobby .qr'),
      start:rect('.host-lobby .lobby-main > button.primary'),
      footer:rect('.game-shell > .session-footer'),
      playerCount:document.querySelectorAll('.host-lobby .roster-panel .mini-player').length,
    };
  });
  const {viewport,header,connection,lobby,left,right,qr,start,footer,docHeight}=geometry;
  for(const [key,box] of Object.entries({header,connection,lobby,left,right,qr,start,footer})){
    assert.ok(box,'Missing host control: '+key+' '+JSON.stringify(geometry));
    assert.ok(box.top>=-1 && box.bottom<=viewport.height+2 &&
      box.left>=-1 && box.right<=viewport.width+2,
      label+' '+key+' must be FULLY on screen '+JSON.stringify(geometry));
  }
  assert.ok(docHeight<=viewport.height+3,label+' must not require page vertical scrolling '+JSON.stringify(geometry));
  assert.ok(right.width/viewport.width>=.35,
    label+' live participant stage must not be squeezed '+JSON.stringify(geometry));
  assert.ok(qr.width>=146&&qr.height>=146,
    label+' QR must remain scannable '+JSON.stringify(geometry));
  assert.ok(start.height>=35,label+' start button must be usable '+JSON.stringify(geometry));
  return geometry;
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
async function checkProjectorQuestionFit(page,label) {
  const sample=await page.evaluate(()=>{
    const card=document.querySelector('.host-question:not(.reveal-mode) .question-card');
    const title=card?.querySelector('h1');
    const buttons=[...(card?.querySelectorAll('.answer-grid button')||[])];
    const controls=card?.querySelector('.host-controls');
    const timer=document.querySelector('.host-question .question-roster .projector-timer-wrap .countdown');
    if(!card||!title||buttons.length!==3||!controls||!timer) return {missing:true};
    const frame=card.getBoundingClientRect(),t=title.getBoundingClientRect();
    const answers=buttons.map(b=>({r:b.getBoundingClientRect(),textClip:b.scrollHeight>b.clientHeight+3}));
    const action=controls.getBoundingClientRect(),clock=timer.getBoundingClientRect();
    return {
      missing:false,
      textClip:answers.some(a=>a.textClip),
      titleToAnswer:t.bottom<=answers[0].r.top+1,
      answersSeparated:answers[0].r.bottom<=answers[1].r.top+1&&answers[1].r.bottom<=answers[2].r.top+1,
      controlsVisible:action.bottom<=frame.bottom+1&&action.bottom<=innerHeight+2,
      titleInCard:t.top>=frame.top-1&&t.bottom<=frame.bottom+1,
      pageOverflow:document.documentElement.scrollHeight>innerHeight+4,
      timerInFrame:clock.width>=130&&clock.left>=0&&clock.right<=innerWidth+1&&clock.bottom<=innerHeight+1,
      optionReadable:innerHeight>790||parseFloat(getComputedStyle(buttons[0]).fontSize)>=(card.parentElement.classList.contains('dense-question')?18:21)
    };
  });
  assert.equal(sample.missing,false,label+' needs all question, answer and timer elements');
  for(const [key,value] of Object.entries(sample)){
    if(key==='missing')continue;
    assert.equal(value,!['textClip','pageOverflow'].includes(key),label+': '+key+' '+JSON.stringify(sample));
  }
}
function pageErrors(page) { const errors = []; page.on('pageerror', error => errors.push(error.message.slice(0, 300))); return errors; }

async function wardrobe(page) {
 const gallery=page.locator('.quick-characters');
 assert.equal(await gallery.getByRole('button').count(),10);
 await page.getByRole('button',{name:'ตัวละครหญิง',exact:true}).click();
 assert.equal(await gallery.getByRole('button').count(),10);
 // Geometry gate: every gallery portrait must stay in its own grid row;
 // this catches feet or arms covering the Thai character name.
 for(const genderName of ['ตัวละครชาย','ตัวละครหญิง']){
  await page.getByRole('button',{name:genderName,exact:true}).click();
  const layout=await gallery.locator('.quick-character').evaluateAll(cards=>cards.map(card=>{
   const portrait=card.querySelector('.quick-character-portrait');
   const caption=card.querySelector('strong');
   if(!portrait||!caption)return {missing:true};
   const a=portrait.getBoundingClientRect(),b=caption.getBoundingClientRect();
   return {portraitBottom:a.bottom,captionTop:b.top,
     svgCount:portrait.querySelectorAll('svg').length,
     pngCount:portrait.querySelectorAll('img').length};
  }));
  assert.equal(layout.length,10,genderName+' gallery should contain ten avatars');
  for(const card of layout){
   assert.equal(card.missing,undefined,'Each avatar card needs portrait and caption');
   assert.ok(card.portraitBottom<=card.captionTop+1,'Avatar portrait must not overlap name');
   assert.equal(card.svgCount,1,'Gallery thumbnail uses a single SVG');
   assert.equal(card.pngCount,0,'Gallery thumbnail must not mix PNG and SVG');
  }
  // Inspect real rendered character SVGs, not just the thumbnail bounding boxes.
  const rigAudit=await gallery.locator('.quick-character').evaluateAll(cards=>cards.map(card=>{
    const svg=card.querySelector('svg');
    return {torso:svg?.querySelectorAll('[data-avatar-part="shirt-torso"]').length??0,
      sleeves:svg?.querySelectorAll('[data-sleeve-side]').length??0,
      hands:svg?.querySelectorAll('[data-avatar-part="left-forearm"],[data-avatar-part="right-forearm"]').length??0,
      joins:svg?.querySelectorAll('[data-avatar-part="shoulder-join-left"],[data-avatar-part="shoulder-join-right"]').length??0,
      caps:svg?.querySelectorAll('[data-avatar-part="left-shoulder-cap"],[data-avatar-part="right-shoulder-cap"]').length??0};
  }));
  for(const rig of rigAudit){
    assert.deepEqual(rig,{torso:1,sleeves:2,hands:2,joins:2,caps:2},genderName+' avatar has a single torso, joined shoulders and two complete arms');
    // The source galleries share the same joint geometry, with distinct poses.


  }
 }
 const chosen=gallery.locator('.quick-character').nth(2);
 await chosen.click();
 assert.equal(await chosen.getAttribute('aria-pressed'),'true','Choosing the face changes real selected state');
 const hero=page.locator('.character-stage .avatar-preview svg');
 const selectedCard=chosen.locator('svg');
 assert.equal(await hero.count(),1,'Selected hero uses the same vector rig as chosen gallery card');
 const portraitGeometry=await selectedCard.evaluate(svg=>[...svg.querySelectorAll('[data-sleeve-side]')].map(el=>el.getAttribute('d')));
 const heroGeometry=await hero.evaluate(svg=>[...svg.querySelectorAll('[data-sleeve-side]')].map(el=>el.getAttribute('d')));
 assert.deepEqual(heroGeometry,portraitGeometry,'Selected large hero and gallery must display the identical arm pose');
 const activePreview=page.locator('.wardrobe-live-avatar svg');
 const chosenPoseGeometry=await activePreview.evaluate(svg=>[...svg.querySelectorAll('[data-sleeve-side]')].map(el=>el.getAttribute('d')));
 assert.deepEqual(chosenPoseGeometry,portraitGeometry,'Live editing preview starts on the same pose as the newly chosen character');
 const selectedHemBefore=await chosen.locator('[data-avatar-part="sleeve-cuff"]').first().getAttribute('stroke-width');
 await page.locator('.quick-options fieldset').nth(3).getByRole('button',{name:'เสื้อแจ็กเก็ต'}).click();
 const selectedHemAfter=await chosen.locator('[data-avatar-part="sleeve-cuff"]').first().getAttribute('stroke-width');
 const heroHemAfter=await hero.locator('[data-avatar-part="sleeve-cuff"]').first().getAttribute('stroke-width');
 assert.notEqual(selectedHemAfter,selectedHemBefore,'Customizing shirt visibly changes selected gallery card');
 assert.equal(selectedHemAfter,heroHemAfter,'Selected card and large hero use matching garment seam styling');
 const previewHemAfter=await activePreview.locator('[data-avatar-part="sleeve-cuff"]').first().getAttribute('stroke-width');
 assert.equal(previewHemAfter,selectedHemAfter,'Live preview also reflects the edited jacket material');


 assert.equal(await page.locator('.quick-options').isVisible(),true,'Wardrobe options are expanded by default');
 const livePreview=page.locator('.quick-options .wardrobe-live-preview');
 await livePreview.waitFor();
 assert.ok(await livePreview.locator('[role="img"]').count()>=1,'Expanded wardrobe displays the actual selected live character');
 const options=page.locator('.quick-options fieldset');
 assert.equal(await options.count(),8,'All eight wardrobe groups including hair color are displayed');
 const hairColors=options.nth(2).locator('button');
 await hairColors.nth(1).click();
 assert.equal(await hairColors.nth(1).getAttribute('aria-pressed'),'true','Hair color can be customized');
 const styles=options.nth(3).locator('button');
 await styles.nth(1).click();
 assert.equal(await styles.nth(1).getAttribute('aria-pressed'),'true');
 const shirtColors=options.nth(4).locator('button');
 await shirtColors.nth(2).click();
 assert.equal(await shirtColors.nth(2).getAttribute('aria-pressed'),'true');
 assert.equal(await livePreview.isVisible(),true,'Live selected avatar stays visible after a wardrobe change');
 const poseButtons=livePreview.locator('.wardrobe-pose-choices button');
 assert.equal(await poseButtons.count(),5,'Five live poses are immediately selectable');
 await poseButtons.nth(1).click();
 assert.equal(await poseButtons.nth(1).getAttribute('aria-pressed'),'true','Pose preview changes immediately');
 assert.equal(await livePreview.locator('[data-avatar-part="raised-palm-depth"]').count(),1,'Wave displays one raised-palm highlight');
 assert.equal(await livePreview.locator('[data-avatar-part="raised-thumb-fold"]').count(),1,'Wave displays one thumb articulation');
 const previewArtwork=livePreview.locator('.wardrobe-live-avatar');
 assert.equal(await previewArtwork.locator('svg').count(),1,'Full body preview uses one coherent SVG across poses');
 assert.equal(await previewArtwork.locator('img').count(),0,'Do not overlay differently proportioned PNG artwork in neutral pose');
 await poseButtons.nth(4).click();
 assert.equal(await poseButtons.nth(4).getAttribute('aria-pressed'),'true','Celebrate pose responds');
 assert.equal(await previewArtwork.locator('svg').count(),1,'Switching poses preserves the same art renderer');
 const handCounts=await previewArtwork.locator('svg').evaluate(svg=>({
  open:svg.querySelectorAll('[data-avatar-part="open-hand"]').length,
  relaxed:svg.querySelectorAll('[data-avatar-part="relaxed-hand"]').length,
  think:svg.querySelectorAll('[data-avatar-part="thinking-hand"]').length,
  cuff:svg.querySelectorAll('[data-avatar-part="sleeve-cuff"]').length
 }));
 assert.deepEqual(handCounts,{open:2,relaxed:0,think:0,cuff:2},'Celebrate pose uses two contiguous hands and two garment cuffs');
 assert.equal(await previewArtwork.locator('[data-avatar-part="raised-palm-depth"]').count(),2,'Celebrate shows two palm highlights');
 assert.equal(await previewArtwork.locator('[data-avatar-part="raised-thumb-fold"]').count(),2,'Celebrate shows two thumb folds');
 const celebratedPalms=await previewArtwork.locator('svg').evaluate(svg=>[...svg.querySelectorAll('[data-avatar-part="open-hand"]')].map(el=>el.getAttribute('d')));
 assert.equal(celebratedPalms.length,2,'Browser has both cheering palms');
 assert.equal(celebratedPalms[0],celebratedPalms[1],'Live cheering palms mirror identical finger anatomy');

 await poseButtons.nth(0).click();
 assert.equal(await previewArtwork.locator('[data-avatar-part="relaxed-hand"]').count(),2,'Stand pose displays two finished resting hands');
 assert.equal(await previewArtwork.locator('[data-avatar-part="palm-volume"]').count(),2,'Both resting palms have volume highlights in the browser');
 assert.equal(await previewArtwork.locator('[data-avatar-part="thumb-fold"]').count(),2,'Both thumbs retain their folds in the browser');
 await poseButtons.nth(2).click();
 assert.equal(await previewArtwork.locator('[data-avatar-part="thinking-hand"]').count(),1,'Thinking pose displays one joined palm and fingers');
 assert.equal(await previewArtwork.locator('[data-avatar-part="thinking-finger-joints"]').count(),1,'Thinking pose has articulated finger joints in real browser');
 assert.equal(await previewArtwork.locator('[data-avatar-part="thinking-palm-volume"]').count(),1,'Thinking palm retains subtle depth in real browser');
 await poseButtons.nth(3).click();
 assert.equal(await previewArtwork.locator('[data-avatar-part="closed-hand"]').count(),2,'Confident pose displays both enclosed fist contours');
 const confidentFingerContours=await previewArtwork.locator('svg').evaluate(svg=>[...svg.querySelectorAll('[data-avatar-part="closed-hand"]')].map(el=>el.getAttribute('d')));
 assert.deepEqual(confidentFingerContours,[confidentFingerContours[0],confidentFingerContours[0]],'Live confident fists share one mirrored anatomical contour');
 assert.equal(await previewArtwork.locator('[data-avatar-part="fist-knuckles"]').count(),2,'Both confident hands render articulated knuckles');
 assert.equal(await previewArtwork.locator('[data-avatar-part="fist-volume"]').count(),2,'Both confident hands render palm volume');

 const confidentPaintOrder=await previewArtwork.locator('svg').evaluate(svg=>{
  const nodes=[...svg.querySelectorAll('*')];
  const index=selector=>nodes.indexOf(svg.querySelector(selector));
  return {
    torso:index('[data-avatar-part="shirt-torso"]'),
    leftArm:index('[data-avatar-part="left-forearm"]'),
    rightArm:index('[data-avatar-part="right-forearm"]'),
    leftFist:index('[data-avatar-part="left-confident-hand"]'),
    rightFist:index('[data-avatar-part="right-confident-hand"]'),
    shoulder:index('[data-avatar-part="left-shoulder-cap"]')
  };
 });
 assert.ok(confidentPaintOrder.leftArm>=0&&confidentPaintOrder.leftArm<confidentPaintOrder.torso,'Confident left forearm stays behind shirt in browser');
 assert.ok(confidentPaintOrder.rightArm>=0&&confidentPaintOrder.rightArm<confidentPaintOrder.torso,'Confident right forearm stays behind shirt in browser');
 assert.ok(confidentPaintOrder.leftFist>confidentPaintOrder.torso&&confidentPaintOrder.rightFist>confidentPaintOrder.torso,'Live confident fists visibly paint in front of torso');
 assert.ok(confidentPaintOrder.leftFist<confidentPaintOrder.shoulder&&confidentPaintOrder.rightFist<confidentPaintOrder.shoulder,'Fists belong below sleeve assembly');

 await poseButtons.nth(4).click();
 assert.equal(await previewArtwork.locator('[data-avatar-part="joyful-eyes"]').count(),1,'Celebration face visibly closes both eyes');
 await poseButtons.nth(0).click();
 assert.equal(await previewArtwork.locator('[data-avatar-part="joyful-eyes"]').count(),0,'Neutral pose restores open eyes');
 const shoulderPoseProfiles=[];
 for(let poseIndex=0;poseIndex<5;poseIndex++){
  await poseButtons.nth(poseIndex).click();
  for(const side of ['left','right']){
   assert.equal(await previewArtwork.locator('[data-avatar-part="'+side+'-forearm"]').count(),1,'Every pose should connect '+side+' forearm to the sleeve');
  }
  assert.equal(await previewArtwork.locator('[data-avatar-part="sleeve-cuff"]').count(),2,'Each pose has two fabric cuffs');
  assert.equal(await previewArtwork.locator('[data-avatar-part="sleeve-volume"]').count(),2,'Both fabric volumes render in the live pose');
  for(const side of ['left','right']){
   const joint=previewArtwork.locator('[data-avatar-part="sleeve-material-'+side+'"]');
   const clip=await joint.getAttribute('clip-path');
   assert.match(clip||'',/^url\(#avatar-[\w-]+-sleeve-(?:left|right)\)$/,'Live sleeve material is bounded by the true shoulder-to-cuff path');
  }
  shoulderPoseProfiles.push(await previewArtwork.locator('svg').evaluate(svg=>({
   pose:svg.getAttribute('data-avatar-pose'),
   left:svg.querySelector('[data-avatar-part="left-shoulder-cap"]')?.getAttribute('d'),
   right:svg.querySelector('[data-avatar-part="right-shoulder-cap"]')?.getAttribute('d')
  })));
  if(poseIndex===0||poseIndex===1||poseIndex===4){
   assert.equal(await previewArtwork.locator('[data-avatar-part="mirrored-right-hand"]').count(),1,'Right palm points outward in live pose');
  }
 }



 assert.deepEqual(shoulderPoseProfiles.map(x=>x.pose),['stand','wave','think','confident','celebrate']);
 assert.notEqual(shoulderPoseProfiles[0].left,shoulderPoseProfiles[1].left,'Left shoulder geometry must rotate when waving');
 assert.equal(shoulderPoseProfiles[0].right,shoulderPoseProfiles[1].right,'Right shoulder stays neutral while waving');
 assert.notEqual(shoulderPoseProfiles[0].right,shoulderPoseProfiles[4].right,'Both shoulders must rotate when celebrating');
 await poseButtons.first().click();
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
      assert.equal(await page.locator('.host-lobby .arena-empty-stage').count(),1,
        'Empty host lobby must show the welcoming broadcast artwork');
      assert.equal(await page.locator('.host-lobby .empty-stage-art').count(),1,
        'Show the actual original-uniform group only while lobby is empty');
      await page.locator('.host-lobby .empty-stage-art').evaluate(async img=>{
        if(!img.complete)await new Promise((resolve,reject)=>{img.addEventListener('load',resolve,{once:true});img.addEventListener('error',reject,{once:true})});
        if(img.naturalWidth<100)throw new Error('Missing original-uniform illustration asset');
      });
      assert.equal(await page.locator('.host-lobby .arena-join-steps span').count(),3,
        'Scannable onboarding keeps all three join steps visible');
      assert.match(await page.locator('.host-lobby .roster-panel h2').innerText(),/ผู้เข้าร่วม\s*0 คน/);
      assert.equal(await page.locator('.host-lobby .arena-attendance').count(),0,'No fixed quota meter in lobby');
      row.checks.push({premiumLobbyEmptyStage:true,originalCharacterArtwork:true,joinSteps:3,displayedPlayers:0});
      if(browserName==='chromium'||browserName==='webkit'){
        await stage('host-lobby-fits-viewport');
        for(const vp of [{width:1280,height:720},{width:1366,height:768},{width:1600,height:780},{width:1920,height:1080}]){
          await page.setViewportSize(vp);
          const fit=await assertHostLobbyFits(page,'Empty host lobby '+vp.width+'x'+vp.height);
          const qrCentered=await page.evaluate(()=>{
            const box=document.querySelector('.host-lobby .qr-visual-stage')?.getBoundingClientRect();
            const qr=document.querySelector('.host-lobby .qr')?.getBoundingClientRect();
            return box&&qr?{distance:Math.abs(qr.left+qr.width/2-(box.left+box.width/2)),
              labelVisible:document.querySelector('.host-lobby .qr-stage-label')?.getBoundingClientRect().height>10}:null;
          });
          assert.ok(qrCentered&&qrCentered.distance<=10&&qrCentered.labelVisible,
            'QR must be visibly centered within its dedicated scan stage '+JSON.stringify(qrCentered));
          row.checks.push({lobbyFit:vp.width+'x'+vp.height,participantWidth:fit.right.width,qrWidth:fit.qr.width,qrCenterOffset:qrCentered.distance});
          if(browserName==='chromium'&&(vp.width===1280||vp.width===1600))
            await shot(page,browserName+'-empty-host-lobby-'+vp.width+'x'+vp.height);
        }
        await page.setViewportSize({width:size.width,height:size.height});
      }
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
        await page.locator('.host-lobby .qr img').waitFor({timeout:20000});
        assert.notEqual((await page.locator('.room-code').textContent()).trim(),'ZZZZZZ');
        assert.equal(await page.locator('.host-lobby .roster-panel .mini-player').count(),0,
          'Expired saved instructor credential must recover to a brand-new empty class automatically');
        row.checks.push({expiredInstructorRecoveredAutomatically:true});
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
        const female=[...document.querySelectorAll('.quick-gender button')].find(x=>x.textContent?.includes('ตัวละครหญิง'));
        return female?.getAttribute('aria-pressed')==='true' && document.querySelector('.quick-character:nth-child(3).selected') !== null;
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
    // Keep actual per-pose raster evidence in the browser-proof artifact.
    // This is artwork review material, not a claim that the anatomy is correct.
    if (browserName === 'chromium' && reducedMotion === 'no-preference' && ['desktop-1280','mobile-390'].includes(size.label)) {
      const preview=page.locator('.quick-options .wardrobe-live-preview');
      const poses=['stand','wave','think','confident','celebrate'];
      for(let index=0;index<poses.length;index++){
        const button=preview.locator('.wardrobe-pose-choices button').nth(index);
        await button.click();
        assert.equal(await button.getAttribute('aria-pressed'),'true',label+' '+poses[index]+' should be selected');
        await preview.screenshot({path:path.join(out,label+'-avatar-'+poses[index]+'.png'),timeout:15_000});
      }
      await preview.locator('.wardrobe-pose-choices button').first().click();
      row.checks.push({avatarPoseScreenshots:poses.length});
    }

    if (browserName === 'chromium' && reducedMotion === 'no-preference' && ['desktop-1280', 'mobile-390'].includes(size.label)) previewImage = await screenshotPreview(page, label + '-wardrobe');
    await stage('motion-controls');
    // Learners should not face technical animation toggles on their quick-join screen.
    const toggle = page.getByRole('button', { name: 'เปิดหรือปิดการเคลื่อนไหว', exact: true });
    assert.equal(await toggle.isVisible(),false,'Advanced motion settings must not clutter learner setup');
    row.motion=await page.evaluate(()=>({reduced:matchMedia('(prefers-reduced-motion: reduce)').matches,runningCssAnimations:document.getAnimations().filter(x=>x.playState==='running').length}));
    if(reducedMotion==='reduce')assert.equal(row.motion.runningCssAnimations,0,'Reduced motion should stop CSS effects');
    // Verify actual computed animations in both browser engines, not merely
    // the presence of CSS strings in source. Shoulder-linked cloth must share
    // its arm's animation name; motion-off and OS reduced motion stop both.
    if(size.label==='desktop-1280'||(size.label==='mobile-390'&&reducedMotion==='reduce')){
      const studio=page.locator('.quick-options .wardrobe-live-preview');
      const poseButtons=studio.locator('.wardrobe-pose-choices button');
      for(const [index,pose,sides] of [[1,'wave',['left']],[2,'think',['right']],[3,'confident',['left','right']],[4,'celebrate',['left','right']]]){
        await poseButtons.nth(index).click();
        await page.waitForFunction(target=>{
          const svg=document.querySelector('.quick-options .wardrobe-live-preview svg[data-avatar-pose]');
          return svg?.getAttribute('data-avatar-pose')===target;
        },pose,{timeout:12000});
        const measured=await studio.evaluate((root,params)=>{
          root.classList.add('game-avatar-motion','game-avatar-motion-'+params.pose);
          const sample=()=>params.sides.map(side=>{
            const svg=root.querySelector('svg[data-avatar-pose="'+params.pose+'"]');
            const arm=svg?.querySelector('[data-avatar-part="'+side+'-articulated-arm"]');
            const cloth=svg?.querySelector('[data-avatar-part="'+side+'-articulated-sleeve"]');
            const fist=params.pose==='confident'?svg?.querySelector('[data-avatar-part="'+side+'-articulated-fist"]'):null;
            return {side,exists:!!arm&&!!cloth,
              armAnimation:arm?getComputedStyle(arm).animationName:'missing',
              clothAnimation:cloth?getComputedStyle(cloth).animationName:'missing',
              fistExists:params.pose!=='confident'||!!fist,
              fistAnimation:fist?getComputedStyle(fist).animationName:'not-applicable'};
          });
          const running=sample();
          // Freeze every part at the same deterministic animation times. This
          // compares real CSS transform matrices, beyond animation names.
          const frames=params.reduced?[]:params.sides.map(side=>{
            const svg=root.querySelector('svg[data-avatar-pose="'+params.pose+'"]');
            const parts=['arm','sleeve',...(params.pose==='confident'?['fist']:[])];
            const nodes=parts.map(part=>svg?.querySelector('[data-avatar-part="'+side+'-articulated-'+part+'"]'));
            const animations=nodes.map(el=>el?.getAnimations().find(a=>a.animationName?.includes('game-avatar-')));
            if(nodes.some(el=>!el)||animations.some(a=>!a))return {side,complete:false,aligned:false,moved:false};
            const snap=time=>{
              animations.forEach(a=>{a.pause();a.currentTime=time;});
              return nodes.map(el=>getComputedStyle(el).transform);
            };
            const atZero=snap(0),atMid=snap(650);
            return {side,complete:true,
              aligned:new Set(atZero).size===1&&new Set(atMid).size===1,
              moved:atZero[0]!==atMid[0]};
          });
          document.body.classList.add('motion-off');
          const stopped=sample();
          document.body.classList.remove('motion-off');
          root.classList.remove('game-avatar-motion','game-avatar-motion-'+params.pose);
          return {running,stopped,frames};
        },{pose,sides});
        for(const joint of measured.running){
          assert.ok(joint.exists,label+' '+pose+' '+joint.side+' paired joint elements');
          assert.ok(joint.fistExists,label+' '+pose+' '+joint.side+' foreground fist available');
          if(pose==='confident')assert.equal(joint.armAnimation,joint.fistAnimation,label+' '+pose+' '+joint.side+' fist moves with arm');
          assert.equal(joint.armAnimation,joint.clothAnimation,label+' '+pose+' '+joint.side+' paired animation');
          assert.equal(joint.armAnimation,reducedMotion==='reduce'?'none':pose==='wave'?'game-avatar-wave-joint':pose==='think'?'game-avatar-think-joint':pose==='confident'?'game-avatar-confident-'+joint.side+'-joint':'game-avatar-cheer-'+joint.side+'-joint',
            label+' '+pose+' '+joint.side+' OS motion mode');
        }
        if(reducedMotion!=='reduce')for(const frame of measured.frames){
          assert.ok(frame.complete,label+' '+pose+' '+frame.side+' actual CSS animation instances exist');
          assert.ok(frame.aligned,label+' '+pose+' '+frame.side+' identical sampled matrices at 0ms and 650ms');
          assert.ok(frame.moved,label+' '+pose+' '+frame.side+' sampled 650ms frame genuinely moves');
        }
        for(const joint of measured.stopped){
          assert.equal(joint.armAnimation,'none',label+' '+pose+' '+joint.side+' motion-off arm');
          assert.equal(joint.clothAnimation,'none',label+' '+pose+' '+joint.side+' motion-off cloth');
          if(pose==='confident')assert.equal(joint.fistAnimation,'none',label+' '+pose+' '+joint.side+' motion-off fist');
        }
      }
      await poseButtons.first().click();
      row.checks.push('Real computed joint motions track both forearm and cloth, and stop together under motion-off/reduced-motion');
    }

    return { previewImage };
  });
}

/** A disposable R ZIP with playable MP3 bytes from the existing Q sample.
 * Browser test only: NEVER use generated fixture voices on published staging. */
function zipTestRevealAudio(mp3){
  const locals=[],central=[];let offset=0;
  for(let i=1;i<=15;i++){
    const name=Buffer.from('R'+String(i).padStart(2,'0')+'.mp3');
    const local=Buffer.alloc(30);local.writeUInt32LE(0x04034b50,0);local.writeUInt16LE(20,4);
    local.writeUInt32LE(mp3.length,18);local.writeUInt32LE(mp3.length,22);
    local.writeUInt16LE(name.length,26);
    locals.push(local,name,mp3);
    const cd=Buffer.alloc(46);cd.writeUInt32LE(0x02014b50,0);cd.writeUInt16LE(20,4);cd.writeUInt16LE(20,6);
    cd.writeUInt32LE(mp3.length,20);cd.writeUInt32LE(mp3.length,24);
    cd.writeUInt16LE(name.length,28);cd.writeUInt32LE(offset,42);
    central.push(cd,name);offset+=local.length+name.length+mp3.length;
  }
  const directory=Buffer.concat(central),end=Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50,0);end.writeUInt16LE(15,8);end.writeUInt16LE(15,10);
  end.writeUInt32LE(directory.length,12);end.writeUInt32LE(offset,16);
  return Buffer.concat([...locals,directory,end]);
}

async function realRoom(browser, browserName) {
  return boundedCase(browser, browserName + '-real-room', browserName === 'webkit' ? 210_000 : 150_000, async ({ createContext, createPage, stage }, row) => {
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
    // Prove the REAL 15-track ZIP import works on an instructor browser and
    // gets persisted. No release binary is fabricated: use the Q sample solely
    // as playable synthetic audio inside the disposable CI preview.
    if(browserName==='chromium'){
      await stage('install-and-test-new-answer-voice-pack');
      const q=await host.request.get(preview.origin+'/voice/Q01.mp3');
      assert.equal(q.status(),200,'Preview must have real playable MP3 bytes');
      const mp3=await q.body();
      assert.ok(mp3.byteLength>50_000);
      const selector=host.locator('.reveal-voice-settings');
      assert.match(await selector.locator('summary').innerText(),/เพิ่มเสียงเฉลย|ยังไม่มีเสียงเฉลย/);
      await selector.locator('summary').click();
      await selector.locator('input[type=file]').setInputFiles({
        name:'ci-only-R01-R15.zip',mimeType:'application/zip',buffer:zipTestRevealAudio(mp3)
      });
      await host.getByText('เสียงเฉลยพร้อม ✓').waitFor({timeout:20000});
      const count=await host.evaluate(async()=>{
        const db=await new Promise((resolve,reject)=>{
          const r=indexedDB.open('coop-ai-answer-recorded-voice',1);
          r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);
        });
        try{
          const blobs=await Promise.all(Array.from({length:15},(_,i)=>new Promise(resolve=>{
            const r=db.transaction('tracks','readonly').objectStore('tracks')
              .get('R'+String(i+1).padStart(2,'0')+'.mp3');
            r.onsuccess=()=>resolve(r.result);r.onerror=()=>resolve(null);
          })));
          return blobs.filter(x=>x instanceof Blob&&x.size>50_000).length;
        }finally{db.close()}
      });
      assert.equal(count,15,'All 15 answer MP3 recordings must persist in IndexedDB');
      await selector.getByRole('button',{name:'▶ ทดสอบเสียงเฉลย'}).click();
      await selector.getByRole('button',{name:/กำลังเล่น/}).waitFor({timeout:15000});
      await selector.locator('summary').click();
      row.checks.push('Teacher imported 15 playable reveal MP3 files and auditioned R01 in real browser');
    }
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
    await player.getByRole('button',{name:'แก้ไขตัวละคร',exact:true}).click();
    await player.locator('.inline-profile-form').waitFor();
    await player.getByRole('button',{name:'ตัวละครชาย'}).click();
    await player.locator('.inline-profile-form .quick-character').nth(1).click();
    const interimName=syntheticName+'ใหม่';
    await player.locator('#edit-player-name').fill(interimName);
    const [edited] = await Promise.all([
      player.waitForRequest(req=>req.method()==='POST'&&new URL(req.url()).pathname==='/api/game'&&req.postDataJSON()?.action==='profile'),
      player.getByRole('button',{name:'บันทึกการเปลี่ยนแปลง'}).click()
    ]);
    assert.equal(edited.postDataJSON().avatar.presetId,'M02');
    await player.getByRole('heading',{name:interimName,exact:true}).waitFor();
    await host.locator('.roster .mini-player').filter({hasText:interimName}).waitFor();
    assert.equal(await host.locator('.roster .mini-player').count(),1,'Editing an existing player cannot create a duplicate roster entry');
    await player.getByRole('button',{name:'แก้ไขตัวละคร',exact:true}).click();
    await player.getByRole('button',{name:'ตัวละครหญิง'}).click();
    await player.locator('.inline-profile-form .quick-character').nth(2).click();
    await player.locator('#edit-player-name').fill(syntheticName);
    await player.getByRole('button',{name:'บันทึกการเปลี่ยนแปลง'}).click();
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
    await host.getByRole('button', { name: '▶ เริ่มเกม', exact: true }).click();
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
        await stage('last-five-seconds-projector-visual');
        await host.locator('.countdown.urgent').waitFor({timeout:65000});
        const flash=await host.locator('.countdown.urgent').evaluate(el=>{
          const style=getComputedStyle(el);
          return {width:el.getBoundingClientRect().width,
            name:style.animationName,color:style.color,
            label:el.querySelector('.timer-kicker')?.textContent};
        });
        assert.ok(flash.width>=130,'Last-five-seconds countdown remains large');
        assert.ok(flash.name.includes('arena-last-five'),'Last five seconds should visibly pulse in motion-enabled mode');
        assert.match(flash.label,/เร็วเข้า/);
        await shot(host,browserName+'-urgent-five-seconds');
        row.checks.push('Legible instructor countdown with a subtle warm pulse during the final five seconds');
        await player.waitForFunction(() => document.querySelector('.countdown .timer-value')?.textContent?.trim() === '0', undefined, { timeout: 20_000 });
        assert.equal(await player.locator('.answer-grid button:disabled').count(), 3);
        assert.equal(await player.locator('.explanation').count(), 0);
        assert.equal(await host.locator('.explanation').count(), 0);
        await question(host, 2); row.checks.push('8-second answer deadline after narration locks answers without revealing or advancing');
      }
      // Every real assessment question must fit the real 720p projector, not just samples.
      await host.setViewportSize({width:1280,height:720});
      await checkProjectorQuestionFit(host,'Projector 1280x720 question '+number);
      if ([1,8,15].includes(number)) {
        const visuals=await host.evaluate(()=>{
          const stage=document.querySelector('.host-question');
          const colors=[...document.querySelectorAll('.host-question .answer-grid .answer')].map(x=>getComputedStyle(x).backgroundImage);
          const live=document.querySelector('.live-score-stage');
          const spotlight=document.querySelector('.score-spotlight .spotlight-person');
          return {stage:Boolean(stage),live:Boolean(live),spotlight:Boolean(spotlight),colorCount:new Set(colors).size,
            answers:[...document.querySelectorAll('.answer-grid .answer')].length};
        });
        assert.ok(visuals.stage&&visuals.live&&visuals.spotlight,'Host has question plus broadcast HUD at 720p');
        assert.equal(visuals.colorCount,3,'Each answer must have its own saturated broadcast color');
        assert.equal(visuals.answers,3);
        await shot(host,browserName+'-1280x720-question-'+number);
        await host.setViewportSize({width:1366,height:768});
        await checkProjectorQuestionFit(host,'Projector 1366x768 question '+number);
        await host.setViewportSize({width:1920,height:1080});
        await checkProjectorQuestionFit(host,'Projector 1920x1080 question '+number);
      }
      await host.setViewportSize({width:1280,height:900});
      row.checks.push('Question '+number+' fits 720p with no Thai text clipping, all answer choices and presenter actions');
      if (number === 1) {
        await noOverflow(player,'mobile active question');
        if ((await player.evaluate(()=>innerWidth))<=430) {
          const frame=await player.evaluate(()=>{
            const card=document.querySelector('.player-question .question-card');
            const answers=[...document.querySelectorAll('.player-question .answer-grid .answer')];
            const rect=card?.getBoundingClientRect();
            return {viewport:innerWidth,left:rect?.left,right:rect?.right,
              count:answers.length,overflow:answers.filter(el=>{const b=el.getBoundingClientRect();return b.left < -1 || b.right > innerWidth+1}).length};
          });
          assert.equal(frame.count,3);
          assert.equal(frame.overflow,0,'Mobile answer buttons extend beyond viewport '+JSON.stringify(frame));
          assert.ok(frame.left>=-1 && frame.right<=frame.viewport+1,'Mobile question card extends beyond viewport '+JSON.stringify(frame));
        }
        const timerSize=await host.locator('.countdown').boundingBox();
        assert.ok(timerSize && timerSize.width>=130 && timerSize.height>=130,'Projector countdown must be large and visible');
        const titleSize=await host.locator('.question-card h1').evaluate(el=>parseFloat(getComputedStyle(el).fontSize));
        assert.ok(titleSize>=35,'Projector question must have a prominently readable font');
        const liveCast=await host.evaluate(()=>{
          const panel=document.querySelector('.host-question:not(.reveal-mode) .question-roster');
          const person=document.querySelector('.score-spotlight .spotlight-person');
          const portrait=document.querySelector('.score-spotlight .spotlight-avatar');
          const board=document.querySelector('.host-question:not(.reveal-mode) .question-layout');
          const root=document.querySelector('.host-question:not(.reveal-mode)');
          const rect=el=>el?.getBoundingClientRect();
          return {panelWidth:rect(panel)?.width,portraitHeight:rect(portrait)?.height,
            personHeight:rect(person)?.height,stageWidth:rect(root)?.width,
            viewport:innerWidth,bodyScroll:document.documentElement.scrollHeight>innerHeight+4};
        });
        assert.ok(liveCast.panelWidth/liveCast.viewport>.29,
          'Live player stage should reserve >=29% of display even with just 1 contestant '+JSON.stringify(liveCast));
        assert.ok(liveCast.personHeight<=180&&liveCast.personHeight>=72,
          'One player should be a compact named card, not a giant full-height avatar '+JSON.stringify(liveCast));
        assert.ok(liveCast.portraitHeight<=145,'One avatar should not dominate the entire stage '+JSON.stringify(liveCast));
        assert.equal(liveCast.bodyScroll,false,'Compact 1-player stage should not require projector scroll');
        row.checks.push({singlePlayerStageWidth:liveCast.panelWidth,portraitHeight:liveCast.portraitHeight});
        await shot(player,browserName+'-question-player');await shot(host,browserName+'-question-host');
      }
      await stage('reveal-' + number);
      await host.locator('.host-controls button').click();
      await host.locator('.explanation').waitFor(); await player.locator('.explanation').waitFor();
      if(number===1){
        const answerPanel=host.locator('.reveal-audio-panel');
        await answerPanel.waitFor();
        if(browserName==='chromium'){
          assert.equal(await answerPanel.getByRole('button',{name:'▶ เล่นเสียงเฉลยข้อนี้'}).count(),1,
            'An installed R pack must expose manual replay during reveal');
        }else{
          assert.match(await answerPanel.innerText(),/เพิ่มเสียงเฉลย|ยังไม่มีเสียงเฉลย/);
          assert.equal(await answerPanel.locator('input[type=file]').count(),1,
            'Without R pack, instructor must be able to import it DURING reveal');
        }
      }
      const correctChoice = await player.locator('.answer-grid button').evaluateAll(buttons => buttons.findIndex(button => button.classList.contains('correct')));
      assert(correctChoice >= 0 && correctChoice <= 2, 'One visible correct choice after reveal');
      assert.equal(await player.locator('.answer.correct').count(), 1);
      if (answered && correctChoice === 0) expectedScore++;
      await player.locator('.own-result').filter({ hasText: 'คะแนนตอนนี้ ' + expectedScore + ' / 15' }).waitFor();
      assert.equal(await player.locator('.answer-grid button:disabled').count(), 3);
      if (number === 1) {
        if((await player.evaluate(()=>innerWidth))<=430){
          await noOverflow(player,'mobile reveal frame');
          const result=await player.evaluate(()=>{
            const card=document.querySelector('.player-question .question-card');
            const hero=card?.querySelector('.own-result');
            const explanation=card?.querySelector('.explanation');
            const b=card?.getBoundingClientRect(),h=hero?.getBoundingClientRect(),e=explanation?.getBoundingClientRect();
            return {viewport:innerWidth,right:b?.right,
              heroVisible:!!h&&h.width>0&&h.height>0,
              explanationVisible:!!e&&e.width>0&&e.height>0,
              resultFirst:!!h&&!!e&&h.top<e.top};
          });
          assert.ok(result.heroVisible && result.explanationVisible && result.resultFirst,
            'Mobile reveal must show feedback above correct answer '+JSON.stringify(result));
          assert.ok(result.right<=result.viewport+1,'Mobile reveal card extends beyond viewport');
        }
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
    // The level must be shown to EVERY learner, not only in an off-screen
    // legend or desktop-only fourth column.
    const expectedTier=expectedScore<=5?'นักสำรวจ AI':expectedScore<=10?'นักต่อยอด AI':'นักรู้ทัน AI';
    for(const [page,role] of [[host,'host'],[player,'learner']]){
      assert.equal(await page.locator('.result-level-summary').count(),3,'All three levels appear at finish');
      assert.equal(await page.locator('.result-level-summary').allTextContents().then(xs=>xs.reduce((n,x)=>n+Number(x.match(/([0-9]+) คน/)?.[1]||0),0)),1,
        'Level distribution must count the real finished learner');
      assert.ok((await page.locator('.score-row:not(.table-heading) .score-level').first().innerText()).includes(expectedTier));
      assert.ok((await page.locator('.result-podium-detail .result-level-chip').first().innerText()).includes(expectedTier));
      if(role==='learner')assert.ok((await page.locator('.personal-finish .result-level-chip').innerText()).includes(expectedTier));
      for(const vp of [{width:1280,height:720},{width:390,height:844},{width:320,height:720}]){
        await page.setViewportSize(vp);
        const visible=await page.evaluate(()=>{
          const displayed=el=>!!el&&getComputedStyle(el).display!=='none'&&el.getBoundingClientRect().width>0&&el.getBoundingClientRect().height>0;
          const row=document.querySelector('.score-row:not(.table-heading)');
          const chip=vp=>vp<701?row?.querySelector('.result-level-inline'):row?.querySelector('.score-level');
          return {labels:[...document.querySelectorAll('.result-level-summary strong')].map(x=>x.textContent),
            rowLevelVisible:displayed(chip(innerWidth)),
            podiumLevelVisible:displayed(document.querySelector('.result-podium-detail .result-level-chip')),
            hasHorizontalOverflow:document.documentElement.scrollWidth>innerWidth+2};
        });
        assert.deepEqual(visible.labels,['นักสำรวจ AI','นักต่อยอด AI','นักรู้ทัน AI']);
        assert.ok(visible.rowLevelVisible,'Every score row must show the awarded AI level '+role+' '+vp.width);
        assert.ok(visible.podiumLevelVisible,'Winning contestant must show awarded AI level '+role+' '+vp.width);
        assert.equal(visible.hasHorizontalOverflow,false,'Level badges must not force side scrolling');
        if(vp.width===390)await shot(page,browserName+'-'+role+'-visible-ai-level-390');
      }
    }
    await host.setViewportSize({width:1280,height:900});
    await player.setViewportSize({width:390,height:844});
    row.checks.push('Every finished learner has a visible named AI level, with all three level bands and accurate class counts');

    // Regression: avatars must not grow to viewport height or cover the scoreboard.
    for(const [page,role] of [[host,'host'],[player,'learner']]){
      for(const viewport of [{width:1280,height:720},{width:1920,height:1080},{width:390,height:844},{width:320,height:720}]){
        await page.setViewportSize(viewport);
        const layout=await page.evaluate(()=>{
          const shapes=(selector)=>[...document.querySelectorAll(selector)].map(el=>{
            const rect=el.getBoundingClientRect();
            const svg=el.querySelector('svg')?.getBoundingClientRect();
            const card=el.closest('.podium-person,.score-row,.personal-finish')?.getBoundingClientRect();
            return {width:rect.width,height:rect.height,
              svgWidth:svg?.width||0,svgHeight:svg?.height||0,
              cardHeight:card?.height||0,
              contained:!svg||(svg.width<=rect.width+2&&svg.height<=rect.height+2)};
          });
          return {winners:shapes('.result-podium-avatar'),
            rows:shapes('.result-score-avatar'),self:shapes('.result-personal-avatar'),
            restartButtons:document.querySelectorAll('.result-host-actions .result-reset-button').length};
        });
        assert.ok(layout.winners.length>0,'At least one compact podium entry');
        assert.ok(layout.rows.length>0,'At least one ranked table entry');
        for(const item of layout.winners){
          assert.ok(item.width<=63&&item.height<=91&&item.cardHeight<=125&&item.contained,
            'Podium portrait is bounded '+role+' '+viewport.width+' '+JSON.stringify(item));
        }
        for(const item of layout.rows){
          assert.ok(item.width<=43&&item.height<=57&&item.contained,
            'Scoreboard portrait is bounded '+role+' '+viewport.width+' '+JSON.stringify(item));
        }
        for(const item of layout.self){
          assert.ok(item.width<=74&&item.height<=100&&item.contained,
            'Self portrait is bounded '+role+' '+viewport.width+' '+JSON.stringify(item));
        }
        assert.equal(layout.restartButtons,role==='host'?1:0,'Only trainer gets visible reset button');
        if(viewport.width===1280)await shot(page,browserName+'-'+role+'-compact-final-1280x720');
      }
    }
    await host.setViewportSize({width:1280,height:900});
    await player.setViewportSize({width:390,height:844});
    row.checks.push('No giant podium, personal, or table avatars in 720p/1080p/mobile final screens');

    await stage('teacher-export-scores');
    assert.equal(await player.getByRole('button',{name:/ดาวน์โหลดคะแนน/}).count(),0,'Learners cannot use the teacher CSV export');
    const [download]=await Promise.all([
      host.waitForEvent('download',{timeout:15000}),
      host.locator('.scoreboard .export-results').click()
    ]);
    assert.match(download.suggestedFilename(),/^AI-Assessment-Results-[0-9]{4}-[0-9]{2}-[0-9]{2}[.]csv$/);
    row.checks.push('Instructor can export final score CSV, but learner cannot');
    for (const size of sizes) {
      await player.setViewportSize({ width: size.width, height: size.height });
      await noOverflow(player, size.label + ' final scoreboard'); await shot(player, browserName + '-' + size.label + '-final');
    }
    row.checks.push('All fifteen questions, instructor reveals and final score rendered through real API');
    await stage('instructor-new-empty-room');
    assert.equal(await player.locator('.new-game-top').count(),0,'Only instructor gets New Game control');
    assert.equal(await host.locator('.new-game-top:visible').count(),1,'Visible instructor New Game button at all times');
    const oldHost=await host.evaluate(()=>JSON.parse(localStorage.getItem('coop-ai-game-session-host')||'null'));
    const oldPlayer=await player.evaluate(()=>JSON.parse(localStorage.getItem('coop-ai-game-session-player')||'null'));
    assert.ok(oldHost?.room&&oldHost?.token&&oldPlayer?.token);
    await host.locator('.new-game-top').click();
    await host.getByRole('dialog').waitFor();
    assert.match(await host.getByRole('dialog').innerText(),/ล้างผู้เล่นทั้งหมด/);
    assert.match(await host.getByRole('dialog').innerText(),/QR Code ใหม่/);
    await host.getByRole('button',{name:'ยังไม่เริ่มใหม่',exact:true}).click();
    await host.getByRole('table',{name:'คะแนนผู้เล่นทั้งหมด',exact:true}).waitFor();
    await host.locator('.new-game-top').click();
    const [newRoomReply]=await Promise.all([
      host.waitForResponse(res=>new URL(res.url()).pathname==='/api/game'
        &&res.request().method()==='POST'&&res.request().postDataJSON()?.action==='newroom',{timeout:15000}),
      host.getByRole('button',{name:'ยืนยัน สร้างห้องใหม่',exact:true}).click(),
    ]);
    const newRoomBody=await newRoomReply.json();
    assert.equal(newRoomReply.status(),201,'Server rejected New Game: '+JSON.stringify({
      status:newRoomReply.status(),error:newRoomBody.error,code:newRoomBody.code
    }));
    assert.equal(newRoomBody.snapshot?.players?.length,0,'Backend must return an empty new classroom');
    await host.locator('.host-lobby').waitFor({timeout:16000});
    await host.waitForFunction(old=>{
      const saved=JSON.parse(localStorage.getItem('coop-ai-game-session-host')||'null');
      return saved?.room&&saved.room!==old;
    },oldHost.room,{timeout:15000});
    const freshHost=await host.evaluate(()=>JSON.parse(localStorage.getItem('coop-ai-game-session-host')||'null'));
    assert.notEqual(freshHost.room,oldHost.room,'New game must rotate room/QR invitation');
    assert.notEqual(freshHost.token,oldHost.token,'New game must rotate instructor credential');
    assert.equal(await host.locator('.host-lobby .roster-panel .mini-player').count(),0,'New room has zero avatars');
    assert.match(await host.locator('.roster-panel').innerText(),/0 คน/);
    const freshReply=await host.request.get(preview.origin+'/api/game?room='+freshHost.room,{
      headers:{Authorization:'Bearer '+freshHost.token}
    });
    assert.equal(freshReply.status(),200);
    const freshState=await freshReply.json();
    assert.equal(freshState.room.phase,'lobby');
    assert.equal(freshState.players.length,0);
    const retiredReply=await player.request.get(preview.origin+'/api/game?room='+oldHost.room,{
      headers:{Authorization:'Bearer '+oldPlayer.token}
    });
    assert.equal(retiredReply.status(),404,'Old QR and old player token must no longer be valid');
    await player.reload({waitUntil:'domcontentloaded'});
    await player.getByRole('button',{name:'กลับไปสแกน QR ใหม่'}).waitFor({timeout:18000});
    assert.deepEqual(await player.evaluate(()=>JSON.parse(localStorage.getItem('coop-ai-game-avatar')||'null')),persisted);
    row.checks.push('New Game control visible on host; confirmed reset rotates QR/token, shows ZERO players and revokes old room');
    await stage('host-reopen-must-clear-previous-classroom');
    // A normal refresh during a live class is safe: the same tab can recover.
    // A fresh visit/new tab is NOT the same class and must retire all attendees.
    const enrolled=await host.request.post(preview.origin+'/api/game',{
      data:{action:'join',room:freshHost.room,name:'นักเรียนค้างทดสอบ',
        avatar:{presetId:'M01',bodyStyle:'male'}}
    });
    assert.equal(enrolled.status(),201,'Set up a real player for reopen regression');
    const enrolledBody=await enrolled.json();
    assert.ok(enrolledBody.token);
    await host.waitForFunction(()=>document.querySelector('.roster-panel')?.textContent.includes('นักเรียนค้างทดสอบ'),null,{timeout:10000});
    await host.reload({waitUntil:'domcontentloaded'});
    await host.locator('.host-lobby').waitFor({timeout:15000});
    assert.equal((await host.locator('.room-code').textContent()).trim(),freshHost.room,
      'Refreshing a classroom must NOT silently wipe its active players');
    assert.equal(await host.locator('.host-lobby .roster-panel .mini-player').count(),1,
      'Same-tab reload must resume the CURRENT classroom');
    const secondHost=await createPage(hostContext);
    await secondHost.goto(preview.origin+'/host',{waitUntil:'domcontentloaded'});
    await secondHost.locator('.host-lobby .qr img').waitFor({timeout:20000});
    const opened=await secondHost.evaluate(()=>JSON.parse(localStorage.getItem('coop-ai-game-session-host')||'null'));
    assert.ok(opened?.token&&opened?.room);
    assert.notEqual(opened.room,freshHost.room,'New instructor visit must get a new QR');
    assert.equal(await secondHost.locator('.host-lobby .roster-panel .mini-player').count(),0,
      'New instructor visit must not show previous student avatars');
    assert.match(await secondHost.locator('.roster-panel').innerText(),/0 คน/);
    const retiredFresh=await host.request.get(preview.origin+'/api/game?room='+freshHost.room,{
      headers:{Authorization:'Bearer '+enrolledBody.token}
    });
    assert.equal(retiredFresh.status(),404,'Previously joined students cannot stay inside a newly opened game');
    const latest=await secondHost.request.get(preview.origin+'/api/game?room='+opened.room,{
      headers:{Authorization:'Bearer '+opened.token}
    });
    assert.equal(latest.status(),200);
    const latestRoom=await latest.json();
    assert.equal(latestRoom.players.length,0,'The new class database roster must be empty');
    await host.waitForFunction(()=>document.querySelector('.host-lobby .roster-panel .mini-player')===null,
      null,{timeout:12000});
    assert.equal(await host.locator('.host-lobby .mini-player').count(),0,
      'Previous instructor tab must remove stale player portraits when the new classroom retires its token');
    row.checks.push('Reopening instructor in a new tab revokes QR/students and wipes stale old-tab roster; same-tab refresh safely resumes current class');
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
     const choice=Math.floor(i/2)%10;
     const code=(female?'F':'M')+String(choice+1).padStart(2,'0');
     // Use the actual visible customization contract, NOT just presetId.
     // A preset ID alone intentionally uses generic default clothes/hair and
     // misleadingly makes 25 independent players look like identical twins.
     const maleHair=['sidepart','wavy','short','buzz','sidepart','swept','curly','short','sidepart','short'];
     const femaleHair=['bob','ponytail','shoulder','bob','pixie','bun','wavy','shoulder','ponytail','bob'];
     const hairColor=['brown','black','chestnut','black','saltpepper','blonde','brown','silver','black','silver'];
     const shirtColors=['lightgreen','blueviolet','white','red','charcoal','teal','purple','coral','sky','gold'];
     const avatar={
       presetId:code,bodyStyle:female?'female':'male',
       skinTone:['warm','fair','tan','warm','deep','warm','tan','fair','warm','fair'][choice],
       hairStyle:(female?femaleHair:maleHair)[choice],
       hairColor:hairColor[choice],shirtStyle:choice%3===0?'polo':choice%3===1?'shirt':'tshirt',
       shirtColor:shirtColors[(choice+i%4)%10],
       bottomStyle:female&&choice%3===0?'skirt':'pants',
       bottomColor:['navy','charcoal','denim','sand','olive'][i%5],
       shoeColor:i%3===0?'white':'black',glassesStyle:choice%5===2?'rectangle':'none',
     };
     const response=await host.request.post(preview.origin+'/api/game',{data:{
       action:'join',room,name:'ผู้เรียน '+String(i+1).padStart(2,'0'),avatar
     },timeout:12000});
     assert.equal(response.status(),201,'Player '+(i+1)+' should join with an approved character');
     const record=await response.json();
     assert.equal(record.playerId?.length>0,true);
     joined.push(record);
   }
   await host.waitForFunction(()=>document.querySelectorAll('.host-lobby .mini-player').length===25,null,{timeout:18000});
   assert.equal(await host.locator('.host-lobby .mini-player').count(),25);
   assert.equal(await host.locator('.host-lobby .arena-empty-stage').count(),0,
     'Decorative cast image must disappear once real players appear');
   assert.equal(await host.locator('.host-lobby .empty-stage-art').count(),0,
     'Real 25-player roster must not be obstructed by decorative art');
   assert.match(await host.locator('.host-lobby .roster-panel h2').innerText(),/ผู้เข้าร่วม\s*25 คน/);
   assert.equal(await host.locator('.host-lobby .arena-attendance').count(),0,'No fixed quota meter for 25 participants');
   const uniqueWardrobes=await host.locator('.host-lobby .mini-player svg').evaluateAll(nodes=>
     new Set(nodes.map(node=>node.outerHTML)).size);
   assert.ok(uniqueWardrobes>=18,'At least 18 visibly distinct full-wardrobe SVGs must render on the host');
   row.checks.push('25 real players with 20 character presets and >=18 visibly distinct wardrobe renders');
   await stage('full-lobby-25-participants-fits-projector');
   for(const vp of [{width:1280,height:720},{width:1366,height:768},{width:1600,height:780},{width:1920,height:1080}]){
     await host.setViewportSize(vp);
     const fit=await assertHostLobbyFits(host,'Twenty-five-person lobby '+vp.width+'x'+vp.height);
     assert.equal(fit.playerCount,25,'Full classroom must still show all 25 participant DOM cards');
     const cast=await host.evaluate(()=>{
       const board=document.querySelector('.host-lobby .roster-panel .roster');
       const items=[...board.querySelectorAll('.mini-player')];
       const bounds=board.getBoundingClientRect();
       const slots=items.map(el=>{
         const r=el.getBoundingClientRect(),styles=getComputedStyle(el);
         return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,opacity:Number(styles.opacity)};
       });
       const columns=getComputedStyle(board).gridTemplateColumns.split(' ').filter(Boolean).length;
       const qr=document.querySelector('.simple-join-ticket .qr');
       return {columns,bounds:{left:bounds.left,right:bounds.right,top:bounds.top,bottom:bounds.bottom},
         outside:slots.filter(x=>x.left<bounds.left-2||x.right>bounds.right+2||x.top<bounds.top-2||x.bottom>bounds.bottom+2),
         invisible:slots.filter(x=>x.opacity<.95),
         qrFilter:getComputedStyle(qr).filter,qrOpacity:Number(getComputedStyle(qr).opacity)};
     });
     assert.equal(cast.columns,5,'All 25 people must be laid out in five visible columns '+vp.width);
     assert.deepEqual(cast.outside,[],'All 25 lobby cards must be inside scoreboard viewport '+vp.width);
     assert.deepEqual(cast.invisible,[],'All 25 cast members must be immediately visible '+vp.width);
     assert.equal(cast.qrFilter,'none','QR must never be blurred for scanning '+vp.width);
     assert.equal(cast.qrOpacity,1,'QR must be fully visible for scanning '+vp.width);
     if(vp.width===1280||vp.width===1600)await shot(host,browserName+'-full-lobby-25-'+vp.width+'x'+vp.height);
   }
   await host.setViewportSize({width:1280,height:720});
   await shot(host,browserName+'-25-real-lobby');
   await stage('begin-game-with-25-players');
   await host.getByRole('button',{name:'▶ เริ่มเกม',exact:true}).click();
   await question(host,1);
   await stage('verify-all-25-live-score-cells-are-visible');
   await host.waitForFunction(()=>document.querySelectorAll('.host-scored-roster.packed-players .mini-player').length===25,null,{timeout:15000});
   for(const viewport of [{width:1280,height:720},{width:1366,height:768},{width:1920,height:1080}]){
     await host.setViewportSize(viewport);
     const live=await host.evaluate(()=>{
       const board=document.querySelector('.host-scored-roster.packed-players');
       const cards=[...document.querySelectorAll('.host-scored-roster.packed-players .mini-player')];
       const timer=document.querySelector('.projector-timer-wrap .countdown');
       if(!board||!timer)return {missing:true};
       const bb=board.getBoundingClientRect();
       const outside=cards.map((item,i)=>({i,box:item.getBoundingClientRect()})).filter(({box})=>
         box.top<bb.top-1||box.bottom>bb.bottom+1||box.left<bb.left-1||box.right>bb.right+1||
         box.top<0||box.bottom>innerHeight+1||box.left<0||box.right>innerWidth+1||
         box.width<65||box.height<25);
       return {missing:false,count:cards.length,outside:outside.map(x=>x.i),
         boardScroll:board.scrollHeight>board.clientHeight+3,
         pageScroll:document.documentElement.scrollHeight>innerHeight+4,
         timerVisible:timer.getBoundingClientRect().bottom<=innerHeight,
         names:cards.map(el=>el.querySelector('strong')?.textContent),
         voiceButtons:document.querySelectorAll('.host-question .narrate-button').length};
     });
     assert.equal(live.missing,false,'Live contestant board exists');
     assert.equal(live.count,25,'All enrolled learners must be in scoreboard DOM');
     assert.deepEqual(live.outside,[],'Every one of 25 live avatar-score cards must fit '+viewport.width+'x'+viewport.height);
     assert.equal(live.boardScroll,false,'Live board must show all 25 without scrolling '+viewport.width);
     assert.equal(live.pageScroll,false,'Projector page must not scroll with 25 players');
     assert.equal(live.timerVisible,true,'Countdown remains visible even with 25 players');
     assert.equal(new Set(live.names).size,25,'Each player is uniquely represented in the live board');
     const visiblePortraits=await host.locator('.host-scored-roster.packed-players .mini-player svg').count();
     assert.equal(visiblePortraits,25,'Each of 25 live scorecards paints an actual avatar, not just a CSS placeholder');
     assert.ok(live.voiceButtons>=1,'Trainer has Thai question narration control');
     if(viewport.width!==1366)await shot(host,browserName+'-real-25-live-score-'+viewport.width+'x'+viewport.height);
   }
   await host.setViewportSize({width:1280,height:720});
   row.checks.push('All 25 REAL player portraits, names, points and answer markers fit live at 720p/768p/1080p without scrolling');
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
   // Test the live 25-player board BEFORE reveal, not only the answer tiles.
   await stage('25-real-players-question-stage');
   await host.locator('.host-question.packed-roster .host-scored-roster .mini-player').first().waitFor({timeout:15000});
   for(const vp of [{width:1280,height:720},{width:1920,height:1080}]){
     await host.setViewportSize(vp);
     const cast=await host.evaluate(()=>{
       const root=document.querySelector('.host-question:not(.reveal-mode)');
       const panel=root?.querySelector('.question-roster');
       const grid=root?.querySelector('.host-scored-roster.packed-players');
       const items=[...(grid?.querySelectorAll('.mini-player')||[])];
       const board=grid?.getBoundingClientRect();
       const bounds=items.map(item=>item.getBoundingClientRect());
       return {columns:grid?getComputedStyle(grid).gridTemplateColumns.split(' ').length:0,
         rows:grid?getComputedStyle(grid).gridTemplateRows.split(' ').length:0,
         players:items.length,
         rightRatio:panel.getBoundingClientRect().width/innerWidth,
         minCardWidth:Math.min(...bounds.map(r=>r.width)),
         minCardHeight:Math.min(...bounds.map(r=>r.height)),
         clipped:bounds.map((r,i)=>({r,i})).filter(({r})=>r.left<board.left-2||r.right>board.right+2||r.top<board.top-2||r.bottom>board.bottom+2).map(x=>x.i),
         pageScroll:document.documentElement.scrollHeight>innerHeight+4};
     });
     assert.equal(cast.players,25,'All 25 real player avatars must appear on question screen');
     assert.equal(cast.columns,5,'25 learners must have five stage columns');
     assert.equal(cast.rows,5,'25 learners must have five stage rows');
     assert.ok(cast.rightRatio>=.30,'The right board must have enough real estate '+JSON.stringify(cast));
     assert.ok(cast.minCardWidth>=65&&cast.minCardHeight>=40,'Every contestant must get visible card space '+JSON.stringify(cast));
     assert.deepEqual(cast.clipped,[],'Every cast tile must remain inside the visible board '+JSON.stringify(cast));
     assert.equal(cast.pageScroll,false,'25 player live question stage must not create document scrolling');
     await shot(host,browserName+'-25-live-stage-'+vp.width+'x'+vp.height);
     row.checks.push({fullCast:vp.width+'x'+vp.height,columns:cast.columns,rows:cast.rows,minWidth:cast.minCardWidth});
   }
   await host.setViewportSize({width:1280,height:720});
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
