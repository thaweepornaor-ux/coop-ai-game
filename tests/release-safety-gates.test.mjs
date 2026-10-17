import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const read=p=>readFileSync(new URL(p,import.meta.url),'utf8');
test('release process retains explicit staged approval and physical QA',()=>{
 const guide=read('../docs/FINAL_ACCEPTANCE_TH.md');
 const readme=read('../README.md');
 for(const requirement of ['Issue #125','8 วินาที','15 ข้อ','25 คน','Chromium','WebKit','Microsoft Excel','Reduced Motion','Rollback']){
  if(requirement==='Rollback'){assert.match(guide,/ย้อนกลับเวอร์ชัน/);continue}
  assert.ok(guide.includes(requirement),'missing real acceptance step: '+requirement);
 }
 assert.match(guide,/ห้ามล้างห้องเรียนเดิม/);
 assert.match(guide,/อนุญาตอย่างชัดเจน/);
 assert.match(readme,/Do not trigger Cloudflare Staging deployment/);
});
test('browser proof cannot point at a hosted deployment',()=>{
 const browser=read('../scripts/test-browser-smoke.mjs');
 assert.match(browser,/Browser smoke requires a loopback preview/);
 assert.match(browser,/Confirm the CI preview uses disposable local D1/);
 const config=read('../wrangler.ci.jsonc');
 assert.match(config,/"remote": false/);
 assert.match(config,/00000000-0000-4000-8000-000000000000/);
});
