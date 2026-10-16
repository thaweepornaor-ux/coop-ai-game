import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

test('retired classrooms stop polling rather than retrying forbidden room tokens',()=>{
 const source=readFileSync(new URL('../app/game.tsx',import.meta.url),'utf8');
 assert.match(source,/let disposed=false,retired=false,tick/);
 assert.match(source,/if\(response\.status===401\|\|response\.status===404\)/);
 assert.match(source,/snapshotRef\.current=null;setSnapshot\(null\);setQr\(''\);setJoinUrl\(''\)/);
 assert.match(source,/setShowRecovery\(true\);[\s\S]{0,250}retired=true;/);
 assert.match(source,/if\(!disposed&&!retired\)tick=window\.setTimeout\(poll,850\)/);
});
