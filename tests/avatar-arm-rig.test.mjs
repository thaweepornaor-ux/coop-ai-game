import test from 'node:test';
import assert from 'node:assert/strict';
import { AVATAR_ARM_RIG, armForPose } from '../shared/avatar-arm-rig.js';
import { renderAvatar } from '../shared/avatar.js';

const poses=['stand','wave','celebrate','think','confident'];
const outfits=['tshirt','polo','shirt','jacket'];
const ids=Array.from({length:20},(_,i)=>(i<10?'M':'F')+String(i%10+1).padStart(2,'0'));

test('five-pose arm rig has complete paired forearms and hems',()=>{
 assert.deepEqual(Object.keys(AVATAR_ARM_RIG).sort(),[...poses].sort());
 for(const pose of poses)for(const side of ['left','right']){
  const arm=armForPose(pose,side);
  assert.match(arm.forearm,/^M[\d.\sQCLZ-]+Z$/);
  assert.match(arm.cuff,/^M[\d.\sQCLZ-]+$/);
  assert.ok(Object.isFrozen(arm));
  assert.ok(!arm.forearm.includes('NaN'));
 }
 assert.throws(()=>armForPose('unknown','left'),RangeError);
 assert.throws(()=>armForPose('wave','center'),RangeError);
});

test('400 playable SVG figures use canonical forearms and matching sleeve cuffs',()=>{
 let rendered=0;
 for(const id of ids)for(const shirtStyle of outfits)for(const pose of poses){
  const ctx=id+'/'+shirtStyle+'/'+pose;
  const svg=renderAvatar({presetId:id,bodyStyle:id[0]==='F'?'female':'male',shirtStyle,pose,materialPrefix:'rig-'+id+'-'+shirtStyle+'-'+pose});
  for(const side of ['left','right']){
   const arm=armForPose(pose,side);
   assert.ok(svg.includes('data-avatar-part="'+side+'-forearm" d="'+arm.forearm+'"'),ctx+' '+side+' canonical forearm');
   const cuff=arm.cuff.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
   assert.match(svg,new RegExp('data-avatar-part="sleeve-cuff" d="'+cuff+'"'),ctx+' '+side+' corresponding cuff');
  }
  assert.equal((svg.match(/data-avatar-part="sleeve-cuff"/g)||[]).length,2,ctx+' exactly 2 hems');
  rendered++;
 }
 assert.equal(rendered,400);
});

test('shared neutral arm is identical when resting in different poses',()=>{
 assert.equal(armForPose('stand','right').forearm,armForPose('wave','right').forearm);
 assert.equal(armForPose('stand','left').forearm,armForPose('think','left').forearm);
 assert.equal(armForPose('stand','right').cuff,armForPose('wave','right').cuff);
});
