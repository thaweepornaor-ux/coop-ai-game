import test from 'node:test';
import assert from 'node:assert/strict';
import {renderAvatar,AVATAR_OPTIONS} from '../shared/avatar.js';

test('all twenty front-facing presets generate distinct SVG faces',()=>{
 for(const gender of ['male','female']){
  const prefix=gender==='male'?'M':'F';
  const portraits=Array.from({length:10},(_,i)=>renderAvatar({bodyStyle:gender,presetId:prefix+String(i+1).padStart(2,'0'),hairStyle:'bald',glassesStyle:'none'}));
  assert.equal(new Set(portraits).size,10,'face geometry must differ for '+gender);
  portraits.forEach(svg=>{assert.match(svg,/^<svg /);assert.ok(!svg.includes('NaN'));assert.ok(!svg.includes('undefined'));});
 }
});
test('every visible style choice still affects the front-facing avatar',()=>{
 const baseline={bodyStyle:'female',presetId:'F01'};
 for(const key of ['skinTone','hairStyle','hairColor','shirtStyle','shirtColor','bottomStyle','bottomColor','shoeColor','glassesStyle','hatStyle','hatColor']){
  const variants=AVATAR_OPTIONS[key];
  const first=renderAvatar({...baseline,[key]:variants[0].value});
  const last=renderAvatar({...baseline,[key]:variants[variants.length-1].value});
  assert.notEqual(first,last,key+' must update the portrait');
 }
});
test('mismatched or invalid face presets do not generate invalid SVG',()=>{
 const standard=renderAvatar({bodyStyle:'female',presetId:'F01'});
 assert.equal(renderAvatar({bodyStyle:'female',presetId:'M09'}),standard);
 assert.equal(renderAvatar({bodyStyle:'female',presetId:'garbage'}),standard);
 assert.ok(!renderAvatar({bodyStyle:'male',presetId:'M10'}).includes('NaN'));
});
