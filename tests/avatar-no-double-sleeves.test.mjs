import test from 'node:test';import assert from 'node:assert/strict';import {renderAvatar} from '../shared/avatar.js';
const poses=['stand','wave','think','confident','celebrate'];
test('one sleeveless torso and exactly two pose-aware sleeves per player avatar',()=>{
 for(const bodyStyle of ['male','female'])for(const pose of poses)for(const shirtStyle of ['tshirt','polo','shirt','jacket']){
  const svg=renderAvatar({bodyStyle,pose,shirtStyle,shirtColor:'mint'});
  const torso=svg.match(/<path data-avatar-part="shirt-torso" d="([^"]+)"/)?.[1];
  assert.ok(torso,bodyStyle+'/'+pose+'/'+shirtStyle+' torso');
  assert.doesNotMatch(torso,/L114 113|L117 113|L46 113|L43 113/,'fixed sleeve wings have to be removed from torso');
  assert.equal((svg.match(/data-sleeve-side="left"/g)||[]).length,1);
  assert.equal((svg.match(/data-sleeve-side="right"/g)||[]).length,1);
  assert.equal((svg.match(/data-avatar-part="sleeve-cuff"/g)||[]).length,2);
  assert.equal((svg.match(/data-avatar-part="(left|right)-forearm"/g)||[]).length,2);
 }
});
test('raised-arm poses have distinctly aligned sleeves independent of torso outline',()=>{
 const profiles=poses.map(pose=>renderAvatar({pose,bodyStyle:'male'}));
 const toros=profiles.map(svg=>svg.match(/data-avatar-part="shirt-torso" d="([^"]+)"/)?.[1]);
 assert.equal(new Set(toros).size,1,'torso must not rotate with the arms');
 const sleeves=profiles.map(svg=>[...svg.matchAll(/<path data-sleeve-side="(?:left|right)" d="([^"]+)"/g)].map(x=>x[1]).join('|'));
 assert.equal(new Set(sleeves).size,5,'arm motion comes from each unique sleeve profile');
});
