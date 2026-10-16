import test from 'node:test';
import assert from 'node:assert/strict';
import {renderAvatar} from '../shared/avatar.js';
const poses=['stand','wave','think','confident','celebrate'];
test('all five poses preserve selected clothing and skin while changing only rendering expression',()=>{
 for(const bodyStyle of ['male','female'])for(const pose of poses){
  const svg=renderAvatar({bodyStyle,pose,skinTone:'tan',shirtColor:'indigo',shirtStyle:'polo',hairColor:'brown'});
  assert.match(svg,/data-avatar-part="pose-sleeves"/);
  assert.equal((svg.match(/data-avatar-part="sleeve-cuff"/g)||[]).length,2);
  assert.equal((svg.match(/data-avatar-part="joyful-eyes"/g)||[]).length,pose==='celebrate'?1:0);
  assert.doesNotMatch(svg,/NaN|undefined/);
 }
});
test('celebration grin and closed happy eyes differ from ordinary standing expression',()=>{
 const standing=renderAvatar({pose:'stand'});
 const cheering=renderAvatar({pose:'celebrate'});
 assert.match(cheering,/data-avatar-part="joyful-eyes"/);
 assert.doesNotMatch(standing,/data-avatar-part="joyful-eyes"/);
 const expression=svg=>svg.match(/M73 78Q80 [^ ]+ 87 78/)?.[0];
 assert.notEqual(expression(standing),expression(cheering));
});
