import test from 'node:test';import assert from 'node:assert/strict';
import {renderAvatar} from '../shared/avatar.js';
const poses=['stand','wave','think','confident','celebrate'];
test('sleeve shading is clipped to the true moving cloth shape for every preset, pose, shirt',()=>{
 for(const sex of ['M','F'])for(let n=1;n<=10;n++)for(const pose of poses)for(const shirtStyle of ['tshirt','polo','shirt','jacket']){
  const id=sex+String(n).padStart(2,'0'), materialPrefix='review-'+id+'-'+pose+'-'+shirtStyle;
  const svg=renderAvatar({presetId:id,bodyStyle:sex==='M'?'male':'female',shirtStyle,pose,materialPrefix});
  for(const side of ['left','right']){
   assert.equal((svg.match(new RegExp('data-avatar-part="sleeve-material-'+side+'"','g'))||[]).length,1);
   assert.ok(svg.includes('<clipPath id="'+materialPrefix+'-sleeve-'+side+'">'));
   assert.ok(svg.includes('clip-path="url(#'+materialPrefix+'-sleeve-'+side+')"'));
  }
  assert.equal((svg.match(/data-avatar-part="sleeve-volume"/g)||[]).length,2);
  assert.equal((svg.match(/data-avatar-part="sleeve-fold"/g)||[]).length,2);
  assert.equal((svg.match(/data-avatar-part="sleeve-cuff"/g)||[]).length,2);
  assert.equal((svg.match(/data-avatar-part="(left|right)-forearm"/g)||[]).length,2);
  assert.doesNotMatch(svg,/NaN|undefined/);
 }
});
