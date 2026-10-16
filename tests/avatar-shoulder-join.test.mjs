import test from 'node:test';
import assert from 'node:assert/strict';
import {renderAvatar} from '../shared/avatar.js';
const poses=['stand','wave','celebrate','think','confident'];
test('shoulder closing seams use selected shirt material and keep left/right limbs separate on all presets',()=>{
 for(const sex of ['M','F'])for(let n=1;n<=10;n++)for(const pose of poses){
  const svg=renderAvatar({bodyStyle:sex==='M'?'male':'female',presetId:sex+String(n).padStart(2,'0'),pose,shirtColor:'mint'});
  for(const side of ['left','right']){
   assert.equal((svg.match(new RegExp('data-avatar-part="shoulder-join-'+side+'"','g'))||[]).length,1);
   assert.equal((svg.match(new RegExp('data-avatar-part="'+side+'-forearm"','g'))||[]).length,1);
   assert.equal((svg.match(new RegExp('data-sleeve-side="'+side+'"','g'))||[]).length,1);
  }
  assert.equal((svg.match(/data-avatar-part="shirt-torso"/g)||[]).length,1);
  assert.equal((svg.match(/data-avatar-part="sleeve-cuff"/g)||[]).length,2);
  assert.doesNotMatch(svg,/NaN|undefined/);
 }
});
