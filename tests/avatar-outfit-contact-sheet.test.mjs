import test from 'node:test';import assert from 'node:assert/strict';import {execFileSync} from 'node:child_process';import {readFileSync,rmSync} from 'node:fs';
test('visual QA produces a complete 400-render matrix for all twenty presets, five poses and four shirts',()=>{
 const file='artifacts/avatar-qa/all-outfits-contact-sheet.html';
 try{
  execFileSync(process.execPath,['scripts/generate-avatar-pose-review.mjs','--all','--outfits','--validate'],{stdio:'pipe'});
  const html=readFileSync(file,'utf8');
  assert.equal((html.match(/<article\b[^>]*>/g)||[]).length,400);
  assert.equal((html.match(/<svg /g)||[]).length,400);
  assert.match(html,/id="preset-filter"/);
  assert.match(html,/id="shirt-filter"/);
  assert.equal((html.match(/data-shirt="/g)||[]).length,400);
  assert.equal((html.match(/class="review-status"/g)||[]).length,400);
  assert.equal((html.match(/data-review="unreviewed"/g)||[]).length,400);
  assert.match(html,/id="export-review"/);
  assert.ok(html.includes('avatar-art-review.csv'));
  for(const prefix of ['M','F'])for(let n=1;n<=10;n++)for(const pose of ['stand','wave','celebrate','think','confident'])for(const shirt of ['tshirt','polo','shirt','jacket']){
   assert.ok(html.includes(prefix+String(n).padStart(2,'0')+' — '+pose+' — '+shirt));
  }
  const ids=[...html.matchAll(/<linearGradient id="(proof-[MF]\d{2}-(?:stand|wave|celebrate|think|confident)-(?:tshirt|polo|shirt|jacket)-skin-lit)"/g)];
  assert.equal(ids.length,400);
  assert.equal(new Set(ids.map(x=>x[1])).size,400);
 }finally{rmSync(file,{force:true});}
});
