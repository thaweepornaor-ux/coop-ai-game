import test from 'node:test';
import assert from 'node:assert/strict';
import {renderAvatar} from '../shared/avatar.js';

test('raised-pose hands are enclosed silhouettes with no detached stroke fingers',()=>{
 for(const gender of ['male','female']){
  for(const [pose,count] of [['wave',1],['celebrate',2]]){
   const svg=renderAvatar({bodyStyle:gender,pose,shirtStyle:'polo'});
   assert.equal((svg.match(/data-avatar-part="open-hand"/g)||[]).length,count);
   assert.doesNotMatch(svg,/stroke-width="3\.1" stroke-linecap="round"/,'obsolete detached fingers');
   assert.match(svg,/data-avatar-part="pose-sleeves"/);
   assert.equal((svg.match(/data-avatar-part="sleeve-cuff"/g)||[]).length,2);
  }
 }
});
