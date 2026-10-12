import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {AVATAR_OPTIONS} from '../shared/avatar.js';
import {cleanStudioName,cleanStudioAvatar,validateStudioTransfer,STUDIO_TRANSFER_KEY} from '../shared/avatar-studio-transfer.js';

const build=(gender='female')=>({presetId:gender==='female'?'F08':'M02',bodyStyle:gender,...Object.fromEntries(Object.entries(AVATAR_OPTIONS).filter(([k])=>k!=='bodyStyle').map(([key,options])=>[key,options[0].value]))});
test('accepts named male and female avatars with valid wearable selections',()=>{
 for(const gender of ['male','female']){
  const transfer=validateStudioTransfer({version:1,name:'ปิง',avatar:build(gender)});
  assert.equal(transfer.name,'ปิง');
  assert.equal(transfer.avatar.bodyStyle,gender);
 }
});
test('rejects forged gender, missing items, invalid preset or blank name',()=>{
 assert.equal(validateStudioTransfer({version:1,name:' ',avatar:build()}),null);
 assert.equal(cleanStudioAvatar({...build(),presetId:'M02'}),null);
 assert.equal(cleanStudioAvatar({...build(),presetId:'F11'}),null);
 assert.equal(cleanStudioAvatar({...build(),shoeColor:'javascript:alert(1)'}),null);
 const missing=build();delete missing.hairStyle;
 assert.equal(cleanStudioAvatar(missing),null);
});
test('caps user-entered name at 24 code points and normalizes male skirt',()=>{
 assert.equal([...cleanStudioName(' สวัสดี'+'ก'.repeat(40))].length,24);
 assert.equal(cleanStudioAvatar({...build('male'),bottomStyle:'skirt'}).bottomStyle,'pants');
});
test('Studio and game use same transfer token with explicit player-only handoff',()=>{
 const studio=readFileSync(new URL('../app/avatar-studio/page.tsx',import.meta.url),'utf8');
 const game=readFileSync(new URL('../app/game.tsx',import.meta.url),'utf8');
 assert.match(studio,/localStorage\.setItem\(STUDIO_TRANSFER_KEY,JSON\.stringify\(handoff\)\)/);
 assert.match(studio,/window\.location\.assign\('\/play\?studio=1'\)/);
 assert.match(game,/initialRole==='player'&&query\.get\('studio'\)==='1'&&!sessionRef\.current/);
 assert.match(game,/setName\(transfer\.name\)/);
 assert.match(game,/setAvatar\(normalizeWardrobe\(transfer\.avatar,true\)\)/);
 assert.match(game,/localStorage\.removeItem\(STUDIO_TRANSFER_KEY\)/);
 assert.equal(STUDIO_TRANSFER_KEY,'coop-ai-avatar-studio-transfer-v1');
});
