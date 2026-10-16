import test from 'node:test';
import assert from 'node:assert/strict';
import {renderAvatar} from '../shared/avatar.js';
test('cuff ink exactly follows the same curve already present in the cloth silhouette, all 40 pose/body/outfit variants',()=>{
 for(const pose of ['stand','wave','celebrate','think','confident'])
 for(const bodyStyle of ['male','female'])
 for(const shirtStyle of ['tshirt','polo','shirt','jacket']){
  const svg=renderAvatar({pose,bodyStyle,shirtStyle});
  const sleeve=[...svg.matchAll(/data-sleeve-side="(?:left|right)" d="([^"]+)"/g)].map(m=>m[1]);
  const cuff=[...svg.matchAll(/data-avatar-part="sleeve-cuff" d="([^"]+)"/g)].map(m=>m[1]);
  assert.equal(sleeve.length,2);
  assert.equal(cuff.length,2);
  for(let side=0;side<2;side++){
   assert.ok(sleeve[side].includes(cuff[side].slice(1)),pose+' '+bodyStyle+' '+shirtStyle+' '+side+' cuff curve must be a sleeve edge');
  }
 }
});
