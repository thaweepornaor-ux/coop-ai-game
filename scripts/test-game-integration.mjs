import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';
const require = createRequire(import.meta.url);
const wranglerRequire = createRequire(require.resolve('wrangler'));
const { Miniflare } = wranglerRequire('miniflare');
const { build } = wranglerRequire('esbuild');
const mf = new Miniflare({modules:true, script:'export default {fetch(){return new Response("test")}}', compatibilityDate:'2026-05-15', d1Databases:['DB']});
try {
const db = await mf.getD1Database('DB');
const journal=JSON.parse(readFileSync('drizzle/meta/_journal.json','utf8'));
for (const e of journal.entries) {
 for (const sql of readFileSync(`drizzle/${e.tag}.sql`,'utf8').split('--> statement-breakpoint').filter(x=>x.trim())) await db.prepare(sql).run();
}
globalThis.testEnv={DB:db};
await build({entryPoints:['app/api/game/route.ts'],outfile:'.sites-runtime/game-test.mjs',bundle:true,platform:'node',format:'esm',plugins:[{name:'test-env',setup(b){b.onResolve({filter:/^cloudflare:workers$/},()=>({path:'env',namespace:'test'}));b.onLoad({filter:/.*/,namespace:'test'},()=>({contents:'export const env=globalThis.testEnv;',loader:'js'}));}}]});
const api=await import('../.sites-runtime/game-test.mjs');
await build({entryPoints:['server/questions.ts'],outfile:'.sites-runtime/questions-test.mjs',bundle:true,platform:'node',format:'esm'});
const {QUESTIONS}=await import('../.sites-runtime/questions-test.mjs');
async function post(body,token){const r=await api.POST(new Request('https://test/api/game',{method:'POST',headers:{'Content-Type':'application/json',...(token?{Authorization:'Bearer '+token}:{})},body:JSON.stringify(body)}));return {status:r.status,data:await r.json()};}
async function state(token,room){const r=await api.GET(new Request('https://test/api/game?room='+room,{headers:{Authorization:'Bearer '+token}}));assert.equal(r.status,200);return r.json();}
const h=await post({action:'create'});assert.equal(h.status,201);const room=h.data.roomCode,host=h.data.token;
const a=await post({action:'join',room,name:'ปิง',avatar:{hairStyle:'short'}}),b=await post({action:'join',room,name:'ผู้เล่นสอง',avatar:{hatStyle:'none'}});
assert.equal(a.status,201);assert.equal(b.status,201);
let snap=await state(host,room);
const command=async(action,token=host,extra={})=>{const r=await post({action,room,roundId:snap.room.roundId,questionIndex:snap.room.questionIndex,...extra},token);if(r.status===200)snap=r.data;return r;};
assert.equal((await command('start',a.data.token)).status,403);
assert.equal((await command('start')).status,200);assert.equal(snap.room.questionIndex,0);
assert.equal(snap.room.deadline-snap.serverNow<=15000,true);
assert.equal((await command('answer',a.data.token,{choice:QUESTIONS[0].answer})).status,200);
assert.equal((await command('answer',a.data.token,{choice:1})).status,409);
let player=await state(b.data.token,room);assert.equal(player.results,undefined);assert.equal(player.correctAnswer,undefined);assert.equal(player.ownAnswer,null);
// Database-clock timeout, without relying on a mocked phone clock.
await db.prepare("UPDATE rooms SET deadline=CAST((julianday('now')-2440587.5)*86400000 AS INTEGER)-1 WHERE code=?").bind(room).run();
assert.equal((await command('answer',b.data.token,{choice:0})).status,409);
snap=await state(host,room);assert.equal(snap.room.phase,'closed');assert.equal(snap.room.questionIndex,0);
assert.equal((await command('next')).status,409);
assert.equal((await command('reveal')).status,200);assert.deepEqual(snap.results.map(x=>x.status),['correct','unanswered']);
for(let i=1;i<15;i++){
 assert.equal((await command('next')).status,200);
 assert.equal(snap.room.questionIndex,i);
 assert.equal((await command('answer',a.data.token,{choice:QUESTIONS[i].answer})).status,200);
 assert.equal((await command('answer',b.data.token,{choice:(QUESTIONS[i].answer+1)%3})).status,200);
 assert.equal((await command('reveal')).status,200);
}
assert.equal((await command('next')).status,200);assert.equal(snap.room.phase,'finished');
assert.equal(snap.leaderboard[0].score,15);assert.equal(snap.leaderboard[1].incorrectCount,14);assert.equal(snap.leaderboard[1].unansweredCount,1);
const stale={roundId:snap.room.roundId,questionIndex:snap.room.questionIndex};
assert.equal((await command('reset',a.data.token)).status,403);
assert.equal((await command('reset')).status,200);assert.equal(snap.room.phase,'lobby');assert.equal(snap.players.length,2);assert.equal(snap.players[0].score,0);
assert.equal((await post({action:'answer',room,...stale,choice:0},a.data.token)).status,409);
player=await state(a.data.token,room);assert.equal(player.ownAnswer,null);assert.equal(player.players[0].name,'ปิง');
assert.equal((await command('start')).status,200);
const racingState={roundId:snap.room.roundId,questionIndex:snap.room.questionIndex};
const race=await Promise.all([
 post({action:'answer',room,...racingState,choice:0},a.data.token),
 post({action:'reset',room,...racingState},host),
]);
assert.equal(race[1].status,200);
snap=await state(host,room);assert.equal(snap.room.phase,'lobby');assert.equal(snap.players[0].score,0);
assert.equal((await state(a.data.token,room)).ownAnswer,null);
const duplicate=await Promise.all([command('start'),command('start')]);
assert.deepEqual(duplicate.map(x=>x.status).sort(),[200,409]);
await db.prepare('UPDATE rooms SET created_at=0 WHERE code=?').bind(room).run();
assert.equal((await api.GET(new Request('https://test/api/game?room='+room,{headers:{Authorization:'Bearer '+host}}))).status,404);
// Exact twenty flat presets persist through GET (refresh/reconnect) and reset.
await build({entryPoints:['shared/characters.ts'],outfile:'.sites-runtime/characters-test.mjs',bundle:true,platform:'node',format:'esm'});
const {CHARACTERS}=await import('../.sites-runtime/characters-test.mjs');
assert.equal(CHARACTERS.length,20);assert.equal(new Set(CHARACTERS.map(c=>c.id)).size,20);
const catalogueHost=await post({action:'create'});assert.equal(catalogueHost.status,201);const catalogueRoom=catalogueHost.data.roomCode;
const entries=[];
for(const c of CHARACTERS){
 const avatar={presetId:c.id,bodyStyle:c.gender,skinTone:c.skinTone,hairStyle:c.hairStyle,hairColor:c.hairColor,shirtStyle:'tshirt',shirtColor:c.shirtColor,bottomStyle:c.bottomStyle,bottomColor:c.bottomColor,shoeColor:'black',glassesStyle:'none',hatStyle:'none',hatColor:'navy'};
 const joined=await post({action:'join',room:catalogueRoom,name:'ชื่อเอง '+c.id,avatar});assert.equal(joined.status,201,JSON.stringify(joined));entries.push({c,avatar,joined});
 const refreshed=await state(joined.data.token,catalogueRoom);const self=refreshed.players.find(p=>p.id===refreshed.caller.playerId);assert.deepEqual(self.avatar,avatar);assert.equal(self.name,'ชื่อเอง '+c.id);assert.equal(refreshed.correctAnswer,undefined);assert.equal(JSON.stringify(self.avatar).includes('token'),false);
}
for(const bad of [{presetId:'M99',bodyStyle:'male'},{presetId:'F01',bodyStyle:'male'},{presetId:'M01',bodyStyle:'male',appearance:{}},{presetId:'M01',bodyStyle:'male',token:'secret'},{presetId:'M01',bodyStyle:'male',answer:1},{presetId:'M01',bodyStyle:'male',shirtColor:'not-a-color'}])assert.equal((await post({action:'join',room:catalogueRoom,name:'invalid',avatar:bad})).status,400);
let catalogue=await state(catalogueHost.data.token,catalogueRoom);const ids=catalogue.players.map(p=>p.id);
assert.equal((await post({action:'reset',room:catalogueRoom,roundId:catalogue.room.roundId,questionIndex:catalogue.room.questionIndex},catalogueHost.data.token)).status,200);
for(const {c,avatar,joined} of entries){const r=await state(joined.data.token,catalogueRoom);const self=r.players.find(p=>p.id===r.caller.playerId);assert.deepEqual(self.avatar,avatar);assert.equal(self.name,'ชื่อเอง '+c.id);assert.equal(self.score,0);assert.deepEqual(r.players.map(p=>p.id),ids);}
console.log('Catalogue integration passed:20 preset IDs,12 flat fields, gender,enum,key validation, independent names/tokens,refresh/reset persistence.');
// Isolate the fixed-minute quota from earlier room creation and minute rollover.
// Only the rate-limit key's Worker clock is pinned; D1 execution-time clocks stay real.
await db.prepare('DELETE FROM rate_limits').run();
const originalNow = Date.now, quotaNow = originalNow();
Date.now = () => quotaNow;
try {
 for(let i=0;i<8;i++)assert.equal((await post({action:'create'})).status,201);
 const limited = await post({action:'create'});
 assert.equal(limited.status,429);
 assert.equal(limited.data.code,'RATE_LIMIT');
} finally { Date.now = originalNow; }
console.log('D1 integration passed: migration, independent tokens, permissions, hidden keys, timeout, all 15 questions, final counts, reset, reconnect, stale action, expiry, rate limit.');
} finally {await mf.dispose();delete globalThis.testEnv;}
