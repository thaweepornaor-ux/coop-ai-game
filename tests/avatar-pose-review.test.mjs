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
 }finally{rmSync('artifacts/avatar-qa',{recursive:true,force:true});}
});
