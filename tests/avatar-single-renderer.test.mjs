import test from 'node:test';
import assert from 'node:assert/strict';
import {renderAvatar} from '../shared/avatar.js';

test('posed SVG maintains the same selected appearance across states',()=>{
  const options={bodyStyle:'female',hairStyle:'long',hairColor:'silver',shirtStyle:'polo',shirtColor:'teal',glassesStyle:'round'};
  for(const pose of ['stand','wave','celebrate','think','confident']){
   const svg=renderAvatar({...options,pose,materialPrefix:'avatar-test'});
   assert.match(svg,/data-avatar-part="pose-sleeves"/);
   assert.match(svg,/#409E91/i);
   assert.match(svg,/#A7ABB6/i);
   assert.match(svg,/stroke="#30343B"/i);
  }
});
