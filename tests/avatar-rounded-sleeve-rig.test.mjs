import test from 'node:test';
import assert from 'node:assert/strict';
import {renderAvatar} from '../shared/avatar.js';
const cases=['stand','wave','celebrate','think','confident'];
const shoulderStarts={stand:['M53 99','M107 99'],wave:['M54 99','M107 99'],celebrate:['M54 99','M106 99'],think:['M53 99','M107 99'],confident:['M53 99','M107 99']};
test('all shoulder panels are gently curved, closed and finish at the matching sleeve cuff',()=>{
 for(const pose of cases)for(const bodyStyle of ['male','female'])for(const shirtStyle of ['tshirt','polo','shirt','jacket']){
  const svg=renderAvatar({pose,bodyStyle,shirtStyle});
  const sleeves=[...svg.matchAll(/data-sleeve-side="(left|right)" d="([^"]+)"/g)];
  assert.deepEqual(sleeves.map(x=>x[1]),['left','right']);
  for(let side=0;side<2;side++){
   const d=sleeves[side][2];
   assert.ok(d.startsWith(shoulderStarts[pose][side]),pose+' shoulder origin');
   assert.ok(d.endsWith('Z'),pose+' closed cloth');
   assert.ok((d.match(/Q/g)||[]).length>=4,pose+' smooth shoulders');
  }
  assert.equal((svg.match(/data-avatar-part="shirt-torso"/g)||[]).length,1);
  assert.equal((svg.match(/data-avatar-part="sleeve-cuff"/g)||[]).length,2);
  assert.equal((svg.match(/data-avatar-part="(left|right)-forearm"/g)||[]).length,2);
 }
});
