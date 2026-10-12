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
