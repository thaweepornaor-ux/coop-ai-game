import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

test('gallery displays the actual selected preset clothing and colors',()=>{
 const source=readFileSync('app/components/simple-wardrobe.tsx','utf8');
 for(const attribute of ['shirtColor','bottomStyle','bottomColor','skinTone','hairStyle','hairColor']){
  assert.match(source,new RegExp(attribute+':c\\.'+attribute));
 }
 assert.match(source,/\{key:'hairColor',label:'สีผม'\}/);
 assert.match(source,/onChange\(normalizeWardrobe\(next\)\)/);
});
