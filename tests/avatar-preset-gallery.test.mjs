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
 const start=source.indexOf('<span className="quick-character-portrait">');
 const end=source.indexOf('</span>',start);
 const cardText=source.slice(start,end);
 assert.ok(start>=0 && end>start,'character portrait card must exist');
 assert.doesNotMatch(cardText,/\.\.\.avatar/,'gallery can never leak the active player clothes');
 assert.ok(cardText.includes('...normalizeWardrobe({presetId:c.id,bodyStyle:c.gender})'));
 for(const part of ['shirtColor:c.shirtColor','bottomStyle:c.bottomStyle','bottomColor:c.bottomColor','hairColor:c.hairColor',"hatStyle:'none'","shirtStyle:'polo'","shoeColor:'black'"]){
  assert.ok(cardText.includes(part),'expected preset property '+part);
 }
});
