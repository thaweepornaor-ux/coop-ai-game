import test from 'node:test';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {readFileSync,rmSync} from 'node:fs';
const location='artifacts/avatar-qa/pose-contact-sheet.html';

test('pose contact sheet renders ten complete avatars with unique material IDs',()=>{
 try{
  execFileSync(process.execPath,['scripts/generate-avatar-pose-review.mjs'],{stdio:'pipe'});
  const html=readFileSync(location,'utf8');
  assert.equal((html.match(/<article>/g)||[]).length,10);
  assert.equal((html.match(/<svg /g)||[]).length,10);
  for(const pose of ['stand','wave','celebrate','think','confident']){
   assert.match(html,new RegExp('M01 — '+pose));
   assert.match(html,new RegExp('F01 — '+pose));
  }
  assert.equal((html.match(/<g data-avatar-part="pose-sleeves">/g)||[]).length,10);
  execFileSync(process.execPath,['scripts/generate-avatar-pose-review.mjs','--all'],{stdio:'pipe'});
  const full=readFileSync('artifacts/avatar-qa/all-presets-contact-sheet.html','utf8');
  assert.equal((full.match(/<article>/g)||[]).length,100);
  assert.equal((full.match(/<svg /g)||[]).length,100);
  for(const prefix of ['M','F'])for(let n=1;n<=10;n++)for(const pose of ['stand','wave','celebrate','think','confident']){
   assert.ok(full.includes(prefix+String(n).padStart(2,'0')+' — '+pose));
  }
  const ids=[...full.matchAll(/<linearGradient id="(proof-[MF]\d{2}-(?:stand|wave|celebrate|think|confident)-skin-lit)"/g)].map(m=>m[1]);
  assert.equal(ids.length,100,'every rendered avatar must have its own skin gradient');
  assert.equal(new Set(ids).size,100,'material identifiers must be unique across 100 SVGs');
  const catalog=readFileSync('shared/characters.ts','utf8');
  const match=catalog.match(/export const CHARACTERS:CharacterPreset\[\]\s*=\s*(\[[\s\S]*?\]);/);
  assert.ok(match,'catalog must be readable');
  const presets=JSON.parse(match[1]);
  assert.equal(presets.length,20);
  for(const preset of presets){
   const first=full.indexOf('<strong>'+preset.id+' — stand</strong>');
   assert.ok(first>0,'missing visible preset label '+preset.id);
   const portrait=full.slice(Math.max(0,first-11500),first);
   assert.ok(portrait.includes('proof-'+preset.id+'-stand'),'preset should use its own SVG gradient');
  }
 }finally{rmSync('artifacts/avatar-qa',{recursive:true,force:true});}
});
