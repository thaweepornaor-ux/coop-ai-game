import test from 'node:test';
import assert from 'node:assert/strict';
import {renderAvatar} from '../shared/avatar.js';
const poses=['stand','wave','celebrate','think','confident'];
test('twenty characters in five poses have actual shoulder cap, sleeve and attached forearm assemblies',()=>{
 for(const sex of ['M','F'])for(let i=1;i<=10;i++)for(const pose of poses){
  const svg=renderAvatar({presetId:sex+String(i).padStart(2,'0'),bodyStyle:sex==='M'?'male':'female',pose,shirtColor:'mint'});
  for(const side of ['left','right']){
   for(const part of [side+'-shoulder-cap',side+'-forearm']){
    assert.equal((svg.match(new RegExp('data-avatar-part="'+part+'"','g'))||[]).length,1);
   }
   assert.equal((svg.match(new RegExp('data-sleeve-side="'+side+'"','g'))||[]).length,1);
  }
  assert.equal((svg.match(/data-avatar-part="shirt-torso"/g)||[]).length,1);
  assert.equal((svg.match(/data-avatar-part="sleeve-cuff"/g)||[]).length,2);
  assert.match(svg,/<g fill="url\(#avatar-shirt-lit\)"><g data-avatar-part="shoulder-caps">/);
  assert.doesNotMatch(svg,/NaN|undefined/);
 }
});

test('shoulder joins are overlapped by moving sleeves without visible cutout patches',()=>{
 const svg=renderAvatar({pose:'wave',shirtColor:'white'});
 const sleevesAt=svg.indexOf('data-avatar-part="pose-sleeves"');
 const capsAt=svg.indexOf('data-avatar-part="shoulder-caps"');
 const leftJoinAt=svg.indexOf('data-avatar-part="shoulder-join-left"');
 assert.ok(sleevesAt>=0&&capsAt>=0&&leftJoinAt>capsAt&&sleevesAt>leftJoinAt,'moving sleeves must cover shoulder caps and seams');
});
