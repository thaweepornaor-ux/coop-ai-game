import test from 'node:test';import assert from 'node:assert/strict';import {renderAvatar} from '../shared/avatar.js';
test('all twenty presets retain anatomy and gain stable face depth in all five poses',()=>{
 for(const gender of ['M','F'])for(let n=1;n<=10;n++)for(const pose of ['stand','wave','think','confident','celebrate']){
  const id=gender+String(n).padStart(2,'0');
  const svg=renderAvatar({presetId:id,bodyStyle:gender==='M'?'male':'female',pose});
  for(const marker of ['face-cheeks','face-chin-light','brows','pose-sleeves']){
   assert.equal((svg.match(new RegExp('data-avatar-part="'+marker+'"','g'))||[]).length,1,id+'/'+pose+'/'+marker);
  }
  assert.equal((svg.match(/data-avatar-part="sleeve-cuff"/g)||[]).length,2);
  assert.doesNotMatch(svg,/NaN|undefined/);
 }
});
test('different presets have individually controlled cheek and eyebrow dimensions',()=>{
 const a=renderAvatar({presetId:'M01'}),b=renderAvatar({presetId:'M02'});
 const cheeks=svg=>svg.match(/data-avatar-part="face-cheeks"[^>]*>[\s\S]*?<\/g>/)?.[0];
 assert.notEqual(cheeks(a),cheeks(b));
});
