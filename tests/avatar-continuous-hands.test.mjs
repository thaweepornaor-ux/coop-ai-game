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

test('neutral arms and thinking pose have continuous fingers for both bodies and outfits',()=>{
 for(const gender of ['male','female'])for(const style of ['polo','tshirt','shirt','jacket']){
  for(const [pose,rest,think] of [['stand',2,0],['wave',1,0],['think',1,1],['confident',0,0],['celebrate',0,0]]){
   const svg=renderAvatar({bodyStyle:gender,shirtStyle:style,pose});
   assert.equal((svg.match(/data-avatar-part="relaxed-hand"/g)||[]).length,rest,gender+'/'+style+'/'+pose+' relaxed');
   assert.equal((svg.match(/data-avatar-part="thinking-hand"/g)||[]).length,think,gender+'/'+style+'/'+pose+' think');
   assert.equal((svg.match(/data-avatar-part="sleeve-cuff"/g)||[]).length,2);
   assert.doesNotMatch(svg, /NaN|undefined/, 'render must contain valid numbers');
  }
 }
});
