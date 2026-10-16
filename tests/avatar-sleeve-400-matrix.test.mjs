import test from 'node:test';
import assert from 'node:assert/strict';
import {renderAvatar} from '../shared/avatar.js';

/** Inspect every playable combination before approving visual-art changes.
 * Structural coverage does not substitute for browser screenshot approval. */
const poses=['stand','wave','celebrate','think','confident'];
const outfits=['tshirt','polo','shirt','jacket'];
const ids=Array.from({length:20},(_,i)=>(i<10?'M':'F')+String(i%10+1).padStart(2,'0'));

test('400 avatar combinations preserve paired, pose-specific sleeve and shoulder geometry',()=>{
 let count=0;
 for(const id of ids) for(const shirtStyle of outfits) for(const pose of poses){
  const svg=renderAvatar({presetId:id,bodyStyle:id[0]==='F'?'female':'male',shirtStyle,pose,materialPrefix:'qa-'+id+'-'+shirtStyle+'-'+pose});
  const context=id+'/'+shirtStyle+'/'+pose;
  assert.match(svg,/<svg\b[^>]*data-avatar-pose=/,context);
  assert.equal((svg.match(/data-sleeve-side="(?:left|right)"/g)||[]).length,2,context+' has exactly two sleeve shapes');
  for(const side of ['left','right']){
   const sidePath=svg.match(new RegExp('<path data-sleeve-side="'+side+'" d="([^"]+)"'));
   assert.ok(sidePath,context+' '+side+' sleeve exists');
   assert.match(sidePath[1],/Z$/,context+' '+side+' fabric silhouette closes');
   assert.match(svg,new RegExp('data-avatar-part="'+side+'-shoulder-cap"'),context+' '+side+' cap exists');
   assert.match(svg,new RegExp('data-avatar-part="sleeve-material-'+side+'"'),context+' '+side+' sleeve shading group exists');
   assert.match(svg,new RegExp('id="qa-'+id+'-'+shirtStyle+'-'+pose+'-sleeve-'+side+'"'),context+' '+side+' clip ID is unique');
   assert.match(svg,new RegExp('clip-path="url\\(#qa-'+id+'-'+shirtStyle+'-'+pose+'-sleeve-'+side+'\\)"'),context+' '+side+' shading clipped to fabric');
  }
  const poloCount=(svg.match(/data-avatar-part="polo-sleeve-tailoring"/g)||[]).length;
  const shirtCount=(svg.match(/data-avatar-part="shirt-sleeve-tailoring"/g)||[]).length;
  assert.equal(poloCount,shirtStyle==='polo'?2:0,context+' polo has exactly its two tailored sleeve seams');
  assert.equal(shirtCount,shirtStyle==='shirt'?2:0,context+' shirt has exactly its two sleeve seams');
  for(const side of ['left','right']){
   const prefix='<g data-avatar-part="sleeve-material-'+side+'"';
   const start=svg.indexOf(prefix);
   const finish=svg.indexOf('</g>',start);
   const clip=start>=0&&finish>start?svg.slice(start,finish):'';
   assert.ok(clip,context+' '+side+' clipped sleeve material');
   if(shirtStyle==='polo')assert.match(clip,/data-avatar-part="polo-sleeve-tailoring"/,context+' polo finish clipped');
   if(shirtStyle==='shirt')assert.match(clip[2],/data-avatar-part="shirt-sleeve-tailoring"/,context+' shirt finish clipped');
  }
  assert.equal((svg.match(/data-avatar-part="sleeve-cuff"/g)||[]).length,2,context+' two cuffs');
  assert.equal((svg.match(/data-avatar-part="shoulder-join-(?:left|right)"/g)||[]).length,2,context+' two joins');
  assert.equal((svg.match(/data-avatar-part="jacket-shoulder-yoke"/g)||[]).length,shirtStyle==='jacket'?2:0,context+' jacket yoke only on jacket');
  assert.equal((svg.match(/data-avatar-part="jacket-sleeve-stitch"/g)||[]).length,shirtStyle==='jacket'?2:0,context+' jacket stitching only on jacket');
  assert.ok(!svg.includes('NaN')&&!svg.includes('undefined'),context+' contains no broken coordinates');
  count++;
 }
 assert.equal(count,400);
});

test('arms and hands remain pose-specific rather than all reusing a default',()=>{
 const sample=pose=>renderAvatar({pose,materialPrefix:'qa-pose-'+pose});
 for(const pose of poses){
  const svg=sample(pose);
  assert.match(svg,/data-avatar-part="left-forearm"/,pose);
  assert.match(svg,/data-avatar-part="right-forearm"/,pose);
 }
 assert.match(sample('wave'),/data-avatar-part="wave-palm-assembly"/);
 assert.match(sample('celebrate'),/data-avatar-part="celebration-palm"/);
 assert.match(sample('think'),/data-avatar-part="thinking-hand"/);
 assert.match(sample('confident'),/data-avatar-part="left-confident-hand"/);
 assert.match(sample('stand'),/data-avatar-part="relaxed-hand"/);
});
