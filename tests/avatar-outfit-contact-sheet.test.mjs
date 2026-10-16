import test from 'node:test';import assert from 'node:assert/strict';import {execFileSync} from 'node:child_process';import {readFileSync,rmSync,mkdtempSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
test('visual QA produces a complete 400-render matrix for all twenty presets, five poses and four shirts',()=>{
 const dir=mkdtempSync(join(tmpdir(),'coop-avatar-outfits-'));
 const file=join(dir,'all-outfits-contact-sheet.html');
 try{
  execFileSync(process.execPath,['scripts/generate-avatar-pose-review.mjs','--all','--outfits','--validate'],{stdio:'pipe',env:{...process.env,COOP_AVATAR_QA_OUTPUT_DIR:dir}});
  const html=readFileSync(file,'utf8');
  assert.equal((html.match(/<article\b[^>]*>/g)||[]).length,400);
  assert.equal((html.match(/<svg /g)||[]).length,400);
  assert.match(html,/id="preset-filter"/);
  assert.match(html,/id="shirt-filter"/);
  assert.match(html,/id="pose-filter"/);
  assert.match(html,/id="review-filter"/);
  assert.ok(html.includes('reviewFilter.addEventListener("change",apply)'));
  assert.ok(html.includes('card.dataset.review!==reviewFilter.value'));
  assert.ok(html.includes('poseFilter.addEventListener("change",apply)'));
  assert.ok(html.includes('card.dataset.pose!==poseFilter.value'));
  assert.equal((html.match(/data-shirt="/g)||[]).length,400);
  assert.equal((html.match(/class="review-status"/g)||[]).length,400);
  assert.equal((html.match(/data-review="unreviewed"/g)||[]).length,400);
  assert.match(html,/id="export-review"/);
  assert.match(html,/id="import-review"/);
  assert.match(html,/id="import-result"/);
  assert.ok(html.includes('review rows restored'));
  assert.ok(html.includes('Invalid review CSV header'));
  assert.ok(html.includes('avatar-art-review.csv'));
  for(const prefix of ['M','F'])for(let n=1;n<=10;n++)for(const pose of ['stand','wave','celebrate','think','confident'])for(const shirt of ['tshirt','polo','shirt','jacket']){
   assert.ok(html.includes(prefix+String(n).padStart(2,'0')+' — '+pose+' — '+shirt));
  }
  const ids=[...html.matchAll(/<linearGradient id="(proof-[MF]\d{2}-(?:stand|wave|celebrate|think|confident)-(?:tshirt|polo|shirt|jacket)-skin-lit)"/g)];
  assert.equal(ids.length,400);
  assert.equal(new Set(ids.map(x=>x[1])).size,400);
 }finally{rmSync(dir,{recursive:true,force:true});}
});
