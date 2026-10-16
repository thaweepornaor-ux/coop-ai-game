import test from 'node:test';import assert from 'node:assert/strict';import {renderAvatar} from '../shared/avatar.js';
const finish={tshirt:['1.15','.38'],polo:['1.45','.5'],shirt:['1.6','.54'],jacket:['2.4','.65']};
test('forty pose/gender/shirt combinations have structurally joined and cloth-specific cuff finishes',()=>{
 for(const bodyStyle of ['male','female'])for(const pose of ['stand','wave','think','confident','celebrate'])for(const [shirtStyle,[width,opacity]] of Object.entries(finish)){
  const svg=renderAvatar({bodyStyle,pose,shirtStyle,shirtColor:'mint'});
  const hems=[...svg.matchAll(/data-avatar-part="sleeve-cuff"[^>]*stroke-opacity="([^"]+)" stroke-width="([^"]+)"/g)];
  assert.equal(hems.length,2);
  for(const h of hems){assert.equal(h[1],opacity);assert.equal(h[2],width);}
  assert.equal((svg.match(/data-avatar-part="(left|right)-forearm"/g)||[]).length,2);
  assert.equal((svg.match(/data-avatar-part="(left|right)-shoulder-cap"/g)||[]).length,2);
 }
});
