import test from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {readFileSync} from 'node:fs';

const verifier=new URL('../scripts/verify-staging-http.mjs',import.meta.url);
for(const [label,url] of [
 ['missing destination',''],['insecure staging','http://coop-ai-game-staging.thaweeporn-aor.workers.dev/'],
 ['production lookalike','https://coop-ai-game.thaweeporn-aor.workers.dev/'],
 ['host suffix attack','https://coop-ai-game-staging.thaweeporn-aor.workers.dev.evil.example/'],
 ['URL with userinfo','https://user:secret@coop-ai-game-staging.thaweeporn-aor.workers.dev/']
]){
 test('staging verifier refuses '+label,()=>{
  const result=spawnSync(process.execPath,[verifier.pathname,url,'a'.repeat(40)],{encoding:'utf8',timeout:4000});
  assert.equal(result.status,2,result.stderr);
  assert.match(result.stderr,/no requests sent/);
 });
}
test('post-deploy smoke checks landing, player, host, and avatar studio routes',()=>{
 const source=readFileSync(verifier,'utf8');
 assert.match(source,/const routes=\['\/','\/play','\/host','\/avatar-studio'\]/);
 assert.match(source,/response\.ok/);
 assert.match(source,/contentType\.includes\('text\/html'\)/);
 assert.match(source,/Expected game landing markers are missing/);
});

test('missing release SHA is rejected before any network request',()=>{
 const result=spawnSync(process.execPath,[verifier.pathname,'https://coop-ai-game-staging.thaweeporn-aor.workers.dev/'],{encoding:'utf8',timeout:4000});
 assert.equal(result.status,2);
 assert.match(result.stderr,/no requests sent/);
});
test('staging version verification requires exact commit and refuses old builds',()=>{
 const source=readFileSync(verifier,'utf8');
 assert.match(source,/\/coop-release\.json/);
 assert.match(source,/manifest\?\.commit!==expectedSha/);
 assert.match(source,/Published game version does not match/);
});
