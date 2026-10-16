import test from 'node:test';import assert from 'node:assert/strict';import {renderAvatar} from '../shared/avatar.js';
test('right resting and raised celebration hands point outward rather than duplicating left-hand direction',()=>{
 for(const bodyStyle of ['male','female'])for(const shirtStyle of ['tshirt','polo','shirt','jacket']){
  for(const pose of ['stand','wave','think','celebrate']){
   const svg=renderAvatar({bodyStyle,shirtStyle,pose});
   assert.equal((svg.match(/data-avatar-part="mirrored-right-hand"/g)||[]).length,pose==='think'?0:1,bodyStyle+'/'+shirtStyle+'/'+pose);
   assert.equal((svg.match(/data-avatar-part="(left|right)-forearm"/g)||[]).length,2);
   assert.equal((svg.match(/data-avatar-part="sleeve-cuff"/g)||[]).length,2);
  }
 }
});
