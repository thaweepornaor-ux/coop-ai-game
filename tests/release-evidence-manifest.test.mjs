import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const read=p=>readFileSync(new URL(p,import.meta.url),'utf8');
test('evidence builder requires exact release SHA and 400 rendered avatars',()=>{
 const code=read('../scripts/build-release-evidence.mjs');
 assert.match(code,/\^\[0-9a-f\]\{40\}\$/);
 assert.match(code,/svgCount!==400/);
 assert.match(code,/timers.length!==15/);
 assert.match(code,/staged:false/);
 assert.match(code,/deploymentAuthorized:false/);
 assert.match(code,/classroomApproved:false/);
 assert.match(code,/sha256/);
});
test('browser workflow binds evidence to real artifacts and cannot deploy',()=>{
 const yaml=read('../.github/workflows/browser-proof.yml');
 assert.match(yaml,/Generate SHA-bound release evidence/);
 assert.match(yaml,/node scripts\/build-release-evidence\.mjs/);
 assert.match(yaml,/name: browser-proof/);
 assert.doesNotMatch(yaml,/wrangler deploy|wrangler publish/);
});
