import test from 'node:test';
import assert from 'node:assert/strict';
import {PNG_PARTS} from '../shared/avatar-png-catalog.js';
import {AVATAR_OPTIONS} from '../shared/avatar.js';

const groups={face:'bodyStyle',hair:'hairStyle',top:'shirtStyle',bottom:'bottomStyle',glasses:'glassesStyle'};
test('PNG catalog options map to wardrobe selections',()=>{
 for(const [group,key] of Object.entries(groups)){
  const valid=new Set(AVATAR_OPTIONS[key].map(item=>item.value));
  for(const part of PNG_PARTS[group]){
   assert.ok(valid.has(part.value)||part.value==='pants-jeans',group+' invalid value '+part.value);
   assert.equal(part.ready,false,'binary not uploaded: '+part.src);
  }
 }
});
test('shoes are identified by real product type, not an inaccurate color name',()=>{
 const styles=new Set(['beige','boots','sneakers']);
 for(const shoe of PNG_PARTS.shoes){
  assert.ok(styles.has(shoe.value),shoe.value);
  assert.equal(shoe.ready,false);
 }
});
