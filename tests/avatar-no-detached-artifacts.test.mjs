import test from 'node:test';
import assert from 'node:assert/strict';
import {renderAvatar} from '../shared/avatar.js';

test('all five poses render full SVG without legacy detached wrist tick marks',()=>{
 for(const pose of ['stand','wave','celebrate','think','confident']){
  const svg=renderAvatar({pose,bodyStyle:'female',skinTone:'warm',shirtStyle:'tshirt'});
  assert.match(svg,/<svg\b/);
  assert.match(svg,/<\/svg>/);
  assert.doesNotMatch(svg,/M43 138L41 148M117 138L119 148/,'Old arm tick marks float outside the hands');
  assert.match(svg,/arm|ellipse|path/);
 }
});
