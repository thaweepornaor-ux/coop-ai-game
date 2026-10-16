import test from 'node:test';
import assert from 'node:assert/strict';
import {renderAvatar} from '../shared/avatar.js';
const poses=['stand','wave','celebrate','think','confident'];
const getPart=(svg,part)=>svg.match(new RegExp('data-avatar-part="'+part+'" d="([^"]+)"'))?.[1];
test('shoulder joints and caps follow all five actual arm poses rather than fixed circular patches',()=>{
 for(const bodyStyle of ['male','female'])for(const shirtStyle of ['tshirt','polo','shirt','jacket']){
  const variants=poses.map(pose=>renderAvatar({pose,bodyStyle,shirtStyle,shirtColor:'mint'}));
  for(const [i,svg] of variants.entries()){
   assert.match(svg,new RegExp('data-avatar-pose="'+poses[i]+'"'));
   for(const side of ['left','right']){
    assert.ok(getPart(svg,side+'-shoulder-cap'),side+' shoulder exists');
    assert.ok(getPart(svg,'shoulder-join-'+side),side+' seam exists');
    assert.ok(getPart(svg,side+'-forearm'),side+' skin exists');
    assert.equal((svg.match(new RegExp('data-sleeve-side="'+side+'"','g'))||[]).length,1);
   }
   assert.equal((svg.match(/data-avatar-part="sleeve-cuff"/g)||[]).length,2);
   assert.doesNotMatch(svg,/NaN|undefined/);
  }
  assert.notEqual(getPart(variants[0],'left-shoulder-cap'),getPart(variants[1],'left-shoulder-cap'),'raised waving shoulder must actually move');
  assert.equal(getPart(variants[0],'right-shoulder-cap'),getPart(variants[1],'right-shoulder-cap'),'stationary wave arm must stay still');
  assert.notEqual(getPart(variants[0],'right-shoulder-cap'),getPart(variants[2],'right-shoulder-cap'),'both raised shoulders move for cheering');
  assert.notEqual(getPart(variants[0],'right-shoulder-cap'),getPart(variants[3],'right-shoulder-cap'),'thinking shoulder follows bent arm');
 }
});
