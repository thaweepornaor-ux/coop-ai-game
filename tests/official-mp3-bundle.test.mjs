import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const install=readFileSync(new URL('../scripts/install-recorded-voice.mjs',import.meta.url),'utf8');
const host=readFileSync(new URL('../app/game.tsx',import.meta.url),'utf8');
const verify=readFileSync(new URL('../scripts/verify-staging-http.mjs',import.meta.url),'utf8');
const deployment=readFileSync(new URL('../.github/workflows/deploy-staging-manual.yml',import.meta.url),'utf8');

test('the exact user-provided 15 MP3s are pinned by SHA256 at publish time',()=>{
 const hashes=install.match(/[a-f0-9]{64}/g)||[];
 assert.equal(hashes.length,15,'15 exact original MP3 hashes must be pinned');
 assert.match(install,/unpackQuizVoiceZip\(zipFile\)/);
 assert.match(install,/hash!==OFFICIAL_SHA256\[i\]/);
 assert.match(install,/await writeFile\(resolve\(root,name\),bytes\)/);
 assert.match(install,/questionCount:15/);
});
test('the instructor automatically uses the real Cloudflare audio without importing ZIP',()=>{
 assert.match(host,/fetch\('\/voice\/manifest.json'/);
 assert.match(host,/source==='official-user-recordings-2026-10-13'/);
 assert.match(host,/voiceUrls.current=index.names.map/);
 assert.match(host,/setVoiceReady\(true\);setNarrationEnabled\(true\)/);
 assert.match(host,/new Audio\(voiceUrls.current\[qnum-1\]/);
});
test('staging must include and serve all 15 authentic MP3 files or publishing fails',()=>{
 assert.match(deployment,/node scripts\/install-recorded-voice.mjs --required/);
 assert.match(verify,/\/voice\/manifest.json/);
 assert.match(verify,/for\(const name of voiceManifest.names\)/);
 assert.match(verify,/STAGING AUDIO PASS/);
 assert.match(verify,/STAGING VOICE FAIL/);
});
