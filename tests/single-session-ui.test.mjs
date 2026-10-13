import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const game=readFileSync(new URL('../app/game.tsx',import.meta.url),'utf8');
const picker=readFileSync(new URL('../app/components/simple-wardrobe.tsx',import.meta.url),'utf8');
const home=readFileSync(new URL('../app/page.tsx',import.meta.url),'utf8');
const layout=readFileSync(new URL('../app/layout.tsx',import.meta.url),'utf8');
test('instructor projector opens directly and creates private QR automatically',()=>{
 assert.match(home,/initialRole="host"/);
 assert.match(game,/initialRole==='host'&&!sessionRef\.current&&!busyRef\.current\)void send\('create'\)/);
 assert.match(game,/QRCode\.toDataURL\(url/);
 assert.match(game,/simple-join-ticket/);
 assert.doesNotMatch(game,/สร้างห้องเกม →/);
});
test('learner QR join does not ask for room or open a separate character studio',()=>{
 assert.match(game,/new URLSearchParams\(window\.location\.search\)/);
 assert.match(game,/roomInput/);
 assert.match(game,/<SimpleWardrobe avatar=\{avatar\} onChange=\{setAvatar\}\/>/);
 assert.doesNotMatch(game,/placeholder="รหัส 6 ตัว"/);
 assert.doesNotMatch(game,/เปิดห้องแต่งตัวเต็มรูปแบบ/);
 assert.match(game,/เข้าเล่นเกม →/);
});
test('face picker offers ten male and ten female images and writes the selected preset',()=>{
 assert.match(picker,/CHARACTERS\.filter\(c=>c\.gender===gender\)/);
 assert.match(picker,/chooseGender\('male'\)/);
 assert.match(picker,/chooseGender\('female'\)/);
 assert.match(picker,/onClick=\{\(\)=>selectPreset\(c\)\}/);
 assert.match(picker,/aria-pressed=\{selectedId===c\.id\}/);
 assert.match(picker,/onChange\(next\)/);
 assert.match(picker,/normalizeWardrobe/);
});
test('name, QR and legacy scoring are preserved under the simpler flow',()=>{
 assert.match(game,/name:playerName,avatar/);
 assert.match(game,/send\('reveal'\)/);
 assert.match(game,/timer\/15/);
 assert.match(game,/snapshot\.leaderboard/);
 assert.match(layout,/ประเมินความเข้าใจ AI/);
});

test('persisted female avatar opens the female face gallery after player state hydration',()=>{
 assert.match(picker,/useEffect\(\(\)=>\{setGender\(avatar\.bodyStyle==='female'\?'female':'male'\)\},\[avatar\.bodyStyle\]\)/);
 assert.match(game,/setAvatar\(normalizeWardrobe\(previousAvatar\)\)/);
});

test('editing learner identity preserves existing player and never creates a second join',()=>{
 const api=readFileSync(new URL('../app/api/game/route.ts',import.meta.url),'utf8');
 assert.match(api,/async function updatePlayerProfile\(/);
 assert.match(api,/if \(caller\.role !== "player"\)/);
 assert.match(api,/assertExpectedState\(state\.room, body\.roundId, body\.questionIndex\)/);
 assert.match(api,/state\.room\.phase !== "lobby"/);
 assert.match(api,/UPDATE players SET name = \?, avatar_json = \?/);
 assert.match(api,/AND token_hash = \?/);
 assert.match(api,/AND EXISTS \(SELECT 1 FROM rooms WHERE code = \? AND phase = 'lobby'/);
 assert.match(api,/if \(body\.action === "profile"\) return await updatePlayerProfile/);
 assert.match(game,/send\('profile',\{name:updated,avatar\}\)/);
 assert.match(game,/className="inline-profile-form"/);
 assert.match(game,/เปลี่ยนชื่อ \/ ตัวละคร/);
 assert.doesNotMatch(game,/\?\s*'เปลี่ยนตัวละคร \/ ชื่อ'\}\<\/button\>/);
});
test('lost instructor session can reopen a new QR without asking for codes',()=>{
 assert.match(game,/function restartHost\(\)/);
 assert.match(game,/onClick=\{isHost\?restartHost:leave\}/);
 assert.match(game,/session!\.role==='host'/);
});

test('trainer tools are available only in the presenter view',()=>{
 assert.match(game,/role==='host'&&<button className="icon-button fullscreen-toggle"/);
 assert.match(game,/document\.documentElement\.requestFullscreen\(\)/);
 assert.match(game,/document\.exitFullscreen\(\)/);
 assert.match(game,/isHost&&<button type="button" className="button secondary export-results"/);
 assert.match(game,/scoreCsv\(snapshot\.leaderboard\)/);
 assert.doesNotMatch(game,/<a className="brand" href="\/"/);
 assert.match(game,/<div className="brand">/);
 assert.match(game,/session&&isHost&&<footer/);
});

test('restart is a new server-side classroom, not a same-room reset preserving characters',()=>{
 const api=readFileSync(new URL('../app/api/game/route.ts',import.meta.url),'utf8');
 assert.match(api,/async function startFreshRoom\(/);
 assert.match(api,/if\(caller\.role!=="host"\)/);
 assert.match(api,/INSERT OR IGNORE INTO rooms/);
 assert.match(api,/DELETE FROM rooms WHERE code=\? AND host_token_hash=\?/);
 assert.match(api,/if \(body\.action === "newroom"\) return await startFreshRoom/);
 assert.match(game,/void send\('newroom'\)/);
 assert.match(game,/เริ่มเกมใหม่ \(ห้องว่าง\)/);
 assert.match(game,/className="icon-button restart-host-top"/);
 assert.match(game,/session&&isHost&&<button className="icon-button restart-host-top"/);
 assert.match(game,/ผู้เรียนต้องสแกน QR Code ใหม่/);
 assert.match(game,/ยืนยัน สร้างห้องว่างใหม่/);
 assert.doesNotMatch(game,/void send\('reset'\)/);
});
