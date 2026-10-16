import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

test('retired classrooms stop polling rather than retrying forbidden room tokens',()=>{
 const source=readFileSync(new URL('../app/game.tsx',import.meta.url),'utf8');
 assert.match(source,/let disposed=false,retired=false,tick/);
 assert.match(source,/if\(response\.status===401\|\|response\.status===404\)/);
 assert.match(source,/snapshotRef\.current=null;setSnapshot\(null\);setQr\(''\);setJoinUrl\(''\)/);
 assert.match(source,/const retireRoom=\(\)=>\{/);
 assert.match(source,/retired=true;[\s\S]{0,350}setShowRecovery\(true\)/);
 assert.match(source,/window\.addEventListener\('storage',onHostRoomChange\)/);
 assert.match(source,/window\.removeEventListener\('storage',onHostRoomChange\)/);
 assert.match(source,/if\(next\.role==='host'&&next\.room!==session\.room\)/);
 assert.match(source,/if\(!disposed&&!retired\)tick=window\.setTimeout\(poll,850\)/);
 assert.match(source,/if\(tick\)\{window\.clearTimeout\(tick\);tick=undefined;\}/);
 assert.match(source,/async function poll\(\)\{\s*if\(disposed\|\|retired\)return;/);
 assert.match(source,/if\(disposed\|\|retired\|\|thisGeneration!==generation\.current\)return/);
});
