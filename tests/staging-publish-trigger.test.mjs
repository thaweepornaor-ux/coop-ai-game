import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const deploy=readFileSync(new URL('../.github/workflows/deploy-staging-manual.yml',import.meta.url),'utf8');
const guard="inputs.publish || (github.event_name == 'push' && contains(github.event.head_commit.message, '[publish-staging]'))";

test('only explicit manual approval or specially tagged main merge may publish staging',()=>{
 assert.match(deploy,/branches: \[main\]/);
 assert.match(deploy,/workflow_dispatch:/);
 assert.equal(deploy.split(guard).length-1,4,'All four publishing prerequisites must use the same explicit guard');
 assert.match(deploy,/Verify existing D1 schema before publishing/);
 assert.match(deploy,/Publish to existing staging Worker only/);
 assert.match(deploy,/Verify published staging serves the actual game/);
 assert.match(deploy,/STAGING_WORKER_NAME: coop-ai-game-staging/);
 assert.doesNotMatch(deploy,/wrangler d1 migrations apply.*--remote/);
});
