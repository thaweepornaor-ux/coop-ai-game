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

test('preset cards do not inherit clothing from the last selected avatar',()=>{
 const source=readFileSync('app/components/simple-wardrobe.tsx','utf8');
 const card=source.match(/<span className="quick-character-portrait">([\\s\\S]*?)<\\/span>/);
 assert.ok(card,'character portrait card must exist');
 assert.doesNotMatch(card[1],/\.\.\.avatar/,'gallery can never leak the active player clothes');
 assert.match(card[1],/\.\.\.normalizeWardrobe\\(\\{presetId:c\.id,bodyStyle:c\.gender\\}\\)/);
 for(const part of ['shirtColor:c.shirtColor','bottomStyle:c.bottomStyle','bottomColor:c.bottomColor','hairColor:c.hairColor',"hatStyle:'none'","shirtStyle:'polo'","shoeColor:'black'"]){
  assert.ok(card[1].includes(part),'expected preset property '+part);
 }
});
