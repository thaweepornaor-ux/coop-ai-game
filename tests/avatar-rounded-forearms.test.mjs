import test from 'node:test';import assert from 'node:assert/strict';import {renderAvatar} from '../shared/avatar.js';
test('rounded exposed forearms stay paired with the correct cuffs across twenty presets and five poses',()=>{
 for(const sex of ['M','F'])for(let i=1;i<=10;i++)for(const pose of ['stand','wave','think','confident','celebrate']){
  const svg=renderAvatar({presetId:sex+String(i).padStart(2,'0'),bodyStyle:sex==='M'?'male':'female',pose,shirtColor:'mint'});
  const arms=[...svg.matchAll(/data-avatar-part="(left|right)-forearm" d="([^"]+)"/g)];
  assert.deepEqual(arms.map(m=>m[1]),['left','right']);
  assert.equal((svg.match(/data-avatar-part="sleeve-cuff"/g)||[]).length,2);
  if(pose==='stand'){
   for(const arm of arms)assert.ok((arm[2].match(/Q/g)||[]).length>=5,'resting arm wrists must use smooth curves');
  }
  if(pose==='wave')assert.ok((arms[0][2].match(/Q/g)||[]).length>=4,'waving forearm must bend naturally');
  if(pose==='celebrate')for(const arm of arms)assert.ok((arm[2].match(/Q/g)||[]).length>=4,'cheering arms must be rounded');
  assert.doesNotMatch(svg,/NaN|undefined/);
 }
});
