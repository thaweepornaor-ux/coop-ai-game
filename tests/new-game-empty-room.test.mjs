import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const app=readFileSync(new URL('../app/game.tsx',import.meta.url),'utf8');
const api=readFileSync(new URL('../app/api/game/route.ts',import.meta.url),'utf8');
const css=readFileSync(new URL('../app/showtime.css',import.meta.url),'utf8');
const schema=readFileSync(new URL('../drizzle/0000_superb_scorpion.sql',import.meta.url),'utf8');

test('New Game is visible in the instructor header in every stage, never on learner screens',()=>{
 assert.match(app,/\{isHost&&<button type="button" className="icon-button new-game-top"/);
 assert.match(app,/onClick=\{\(\)=>setResetDialog\(true\)\}>↻ เริ่มเกมใหม่/);
 assert.match(css,/\.game-shell \.topbar \.new-game-top\{/);
 assert.match(css,/flex-wrap:wrap/);
 assert.match(app,/isHost&&<div className="result-host-actions"/);
});
test('Instructor confirms deleting old players, not merely resetting scores',()=>{
 assert.match(app,/เริ่มเกมใหม่และล้างผู้เล่นทั้งหมด/);
 assert.match(app,/ผู้เรียนทุกคนต้องสแกน QR Code ใหม่/);
 assert.match(app,/void send\('newroom'\)/);
 assert.doesNotMatch(app,/void send\('reset'\)/);
 assert.match(app,/setQr\(''\);setJoinUrl\(''\)/);
});
test('Fresh room is restricted to host and rotates QR and credentials',()=>{
 assert.match(api,/async function newEmptyRoom\(/);
 assert.match(api,/if \(caller\.role !== "host"\)/);
 assert.match(api,/newHash=await hashToken\(token\)/);
 assert.match(api,/INSERT OR IGNORE INTO rooms/);
 assert.match(api,/DELETE FROM rooms WHERE code=\? AND host_token_hash=\?/);
 assert.match(api,/AND EXISTS \(SELECT 1 FROM rooms WHERE code=\? AND host_token_hash=\?\)/);
 assert.match(api,/if \(body\.action === "newroom"\) return await newEmptyRoom/);
 assert.match(api,/snapshot\(fresh,\{role:"host"\}\)/);
 assert.match(schema,/ON DELETE cascade/);
});

test('Opening /host again is NOT an implicit return to the previous players',()=>{
 assert.match(app,/const hostTabRoomKey='coop-ai-game-host-active-tab-room'/);
 assert.match(app,/kind==='reload'&&sessionStorage\.getItem\(hostTabRoomKey\)===savedRoom/);
 assert.match(app,/if\(initialRole==='host'&&!isSameHostReload\(saved\.room\)\)/);
 assert.match(app,/void startFreshTeachingSession\(saved\)/);
 assert.match(app,/body:JSON\.stringify\(\{action:'newroom',room:previous\.room\}\)/);
 assert.match(app,/data\.snapshot\.players\.length!==0/);
 assert.match(app,/data\.roomCode===previous\.room/);
 assert.match(app,/rememberHostTab\(fresh\.room\)/);
 assert.match(app,/if\(value\.role==='host'\)rememberHostTab\(value\.room\)/);
 assert.match(app,/if\(role==='host'\)clearHostTab\(\)/);
});
