import test from 'node:test';
import assert from 'node:assert/strict';
import {PNG_PARTS} from '../shared/avatar-png-catalog.js';
import {AVATAR_OPTIONS} from '../shared/avatar.js';

const groups={face:'bodyStyle',hair:'hairStyle',top:'shirtStyle',bottom:'bottomStyle',shoes:'shoeColor',glasses:'glassesStyle'};
test('PNG asset keys must match selectable wardrobe values or explicitly special-case variant',()=>{
 for(const [group,key] of Object.entries(groups)){
  const valid=new Set(AVATAR_OPTIONS[key].map(item=>item.value));
  for(const part of PNG_PARTS[group]){
   assert.ok(valid.has(part.value)||part.value==='pants-jeans',group+' invalid value '+part.value);
   assert.equal(part.ready,false,'binary not uploaded: '+part.src);
  }
 }
});
