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
   if(shirtStyle==='shirt')assert.match(clip,/data-avatar-part="shirt-sleeve-tailoring"/,context+' shirt finish clipped');
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

test('relaxed hand contours and left/right forearms stay mirrored across all 400 variants',()=>{
 for(const id of ids)for(const shirtStyle of outfits)for(const pose of poses){
  const svg=renderAvatar({presetId:id,bodyStyle:id.startsWith('F')?'female':'male',shirtStyle,pose,materialPrefix:'hand-qa-'+id+'-'+shirtStyle+'-'+pose});
  const relaxed=pose==='stand'||pose==='wave'||pose==='think';
  assert.equal((svg.match(/data-avatar-part="relaxed-hand"/g)||[]).length,relaxed?(pose==='stand'?2:1):0,id+'/'+shirtStyle+'/'+pose+' relaxed palm count');
  if(pose==='stand'||pose==='wave'){
   assert.match(svg,/data-avatar-part="mirrored-right-hand" transform="translate\(118 145\) scale\(-1 1\)"/,id+'/'+shirtStyle+'/'+pose+' right mirror');
  }
  assert.equal((svg.match(/data-avatar-part="left-forearm"/g)||[]).length,1,id+'/'+shirtStyle+'/'+pose+' left forearm');
  assert.equal((svg.match(/data-avatar-part="right-forearm"/g)||[]).length,1,id+'/'+shirtStyle+'/'+pose+' right forearm');
 }
});

test('three expressive hand gestures keep their wrist details attached across the full wardrobe matrix',()=>{
 for(const id of ids)for(const shirtStyle of outfits)for(const pose of poses){
  const context=id+'/'+shirtStyle+'/'+pose;
  const svg=renderAvatar({presetId:id,bodyStyle:id.startsWith('F')?'female':'male',shirtStyle,pose,materialPrefix:'gesture-'+id+'-'+shirtStyle+'-'+pose});
  const expected={stand:[],wave:[],celebrate:['celebration-wrist-contour'],think:['thinking-wrist-contour'],confident:['fist-wrist-contour']}[pose];
  for(const part of ['thinking-wrist-contour','celebration-wrist-contour','fist-wrist-contour']){
   const count=(svg.match(new RegExp('data-avatar-part="'+part+'"','g'))||[]).length;
   assert.equal(count,expected.includes(part)?(part==='thinking-wrist-contour'?1:2):0,context+' '+part);
  }
  if(pose==='think')assert.ok(svg.indexOf('data-avatar-part="thinking-wrist-contour"')>svg.indexOf('data-avatar-part="thinking-hand"'),context+' wrist remains in thinking-hand assembly');
  if(pose==='celebrate')assert.equal((svg.match(/data-avatar-part="mirrored-right-hand"/g)||[]).length,1,context+' mirrored raised hand');
  assert.ok(!svg.includes('undefined'),context+' no missing hand interpolation');
 }
});

test('reshaped thinking elbow and confident arms stay bilateral in 400 avatar renders',()=>{
 const poses=['stand','wave','celebrate','think','confident'];
 for(const id of ids)for(const shirtStyle of outfits)for(const pose of poses){
  const svg=renderAvatar({presetId:id,bodyStyle:id[0]==='F'?'female':'male',shirtStyle,pose,materialPrefix:'elbow-'+id+'-'+shirtStyle+'-'+pose});
  const context=id+'/'+shirtStyle+'/'+pose;
  const left=svg.match(/data-avatar-part="left-forearm" d="([^"]+)"/);
  const right=svg.match(/data-avatar-part="right-forearm" d="([^"]+)"/);
  assert.ok(left&&right,context+' both arms must render');
  assert.equal((left[1].match(/Z/g)||[]).length,1,context+' closed left forearm');
  assert.equal((right[1].match(/Z/g)||[]).length,1,context+' closed right forearm');
  if(pose==='confident'){
   assert.match(left[1],/Q44 141 50 142/,context+' reshaped left elbow');
   assert.match(right[1],/Q116 141 110 142/,context+' reshaped right elbow');
  }
  if(pose==='think')assert.match(right[1],/Q120 137 114 138/,context+' smooth bent forearm');
  assert.equal((svg.match(/data-avatar-part="sleeve-cuff"/g)||[]).length,2,context+' sleeves retained');
 }
});
