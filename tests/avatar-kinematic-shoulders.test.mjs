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

test('moving sleeves cover shoulder seams; thinking hand and arm cross in front of clothing',()=>{
 for(const bodyStyle of ['male','female']) for(const shirtStyle of ['tshirt','polo','shirt','jacket']){
  for(const pose of poses){
   const svg=renderAvatar({bodyStyle,shirtStyle,pose});
   const torso=svg.indexOf('data-avatar-part="shirt-torso"');
   const shoulder=svg.indexOf('data-avatar-part="left-shoulder-cap"');
   const seam=svg.indexOf('data-avatar-part="shoulder-join-left"');
   const sleeve=svg.indexOf('data-sleeve-side="left"');
   const cuff=svg.indexOf('data-avatar-part="sleeve-cuff"');
   assert.ok(torso>=0&&torso<shoulder&&shoulder<seam&&seam<sleeve&&sleeve<cuff,pose+' layers must hide exposed shoulder patch');
   const forearm=svg.indexOf('data-avatar-part="right-forearm"');
   const restingLeft=svg.indexOf('data-avatar-part="left-forearm"');
   if(pose==='think') {
    assert.ok(forearm>torso&&forearm<shoulder,'thinking arm goes in front of shirt, below its sleeve');
    assert.ok(restingLeft<torso,'relaxed left arm must remain behind the shirt');
    assert.equal((svg.match(/data-avatar-part="left-forearm"/g)||[]).length,1);
   }
   else assert.ok(forearm<torso,'resting and raised arms stay behind shirt');
   assert.match(svg,/data-avatar-part="right-forearm"/);
   assert.equal((svg.match(/data-avatar-part="sleeve-cuff"/g)||[]).length,2);
  }
 }
});

test('raised open hands have articulated finger details for both sides without losing anatomy',()=>{
 for(const bodyStyle of ['male','female'])for(const shirtStyle of ['tshirt','polo','shirt','jacket']){
  const wave=renderAvatar({bodyStyle,shirtStyle,pose:'wave'});
  const cheer=renderAvatar({bodyStyle,shirtStyle,pose:'celebrate'});
  assert.equal((wave.match(/data-avatar-part="finger-creases"/g)||[]).length,1,'one raised waving palm');
  assert.equal((wave.match(/data-avatar-part="wrist-crease"/g)||[]).length,1,'waving wrist follows its palm');
  assert.equal((cheer.match(/data-avatar-part="wrist-crease"/g)||[]).length,2,'both cheering wrists follow their palms');
  assert.equal((cheer.match(/data-avatar-part="finger-creases"/g)||[]).length,2,'two raised cheering palms');
  assert.equal((wave.match(/data-avatar-part="open-hand"/g)||[]).length,1);
  assert.equal((cheer.match(/data-avatar-part="open-hand"/g)||[]).length,2);
  assert.doesNotMatch(wave,/NaN|undefined/);
  assert.doesNotMatch(cheer,/NaN|undefined/);
 }
});

test('confident fists paint in front of torso while their forearms stay behind',()=>{
 for(const bodyStyle of ['male','female'])for(const shirtStyle of ['tshirt','polo','shirt','jacket']){
  const svg=renderAvatar({bodyStyle,shirtStyle,pose:'confident'});
  const torso=svg.indexOf('data-avatar-part="shirt-torso"');
  const firstForearm=svg.indexOf('data-avatar-part="left-forearm"');
  const secondForearm=svg.indexOf('data-avatar-part="right-forearm"');
  const leftFist=svg.indexOf('data-avatar-part="left-confident-hand"');
  const rightFist=svg.indexOf('data-avatar-part="right-confident-hand"');
  const shoulder=svg.indexOf('data-avatar-part="left-shoulder-cap"');
  assert.ok(firstForearm<torso&&secondForearm<torso,'both forearms remain behind shirt');
  assert.ok(leftFist>torso&&rightFist>torso,'both clenched hands sit on top of shirt waist');
  assert.ok(leftFist<shoulder&&rightFist<shoulder,'hands remain below sleeve overlays');
  assert.equal((svg.match(/data-avatar-part="closed-hand"/g)||[]).length,2);
 }
});

test('both neutral hands have identical mirrored silhouettes across poses and outfits',()=>{
 const getRelaxed=svg=>[...svg.matchAll(/data-avatar-part="relaxed-hand" d="([^"]+)"/g)].map(x=>x[1]);
 for(const bodyStyle of ['male','female'])for(const shirtStyle of ['tshirt','polo','shirt','jacket']){
  for(const pose of ['stand','wave','think']){
   const svg=renderAvatar({bodyStyle,shirtStyle,pose});
   const hands=getRelaxed(svg);
   assert.equal(hands.length,pose==='stand'?2:pose==='wave'?1:1,pose+' relaxed hand count');
   if(pose==='stand')assert.equal(hands[0],hands[1],'left and right relaxed hands must mirror the same geometry');
   assert.doesNotMatch(svg,/NaN|undefined/);
  }
 }
});

test('neutral palm volume is shared by both hands without changing selected skin and wardrobe',()=>{
 for(const bodyStyle of ['male','female'])for(const shirtStyle of ['tshirt','polo','shirt','jacket'])for(const skinTone of ['fair','warm','tan','deep']){
  const stand=renderAvatar({bodyStyle,shirtStyle,skinTone,pose:'stand'});
  assert.equal((stand.match(/data-avatar-part="palm-volume"/g)||[]).length,2);
  for(const side of ['left','right']){
   assert.match(stand,new RegExp('id="avatar-palm-'+side+'"'));
   assert.ok(stand.includes('clip-path="url(#avatar-palm-'+side+')"'),'Palm highlight must reference its own clipping mask');
  }
  assert.equal((stand.match(/data-avatar-part="thumb-fold"/g)||[]).length,2);
  assert.equal((stand.match(/data-avatar-part="relaxed-hand"/g)||[]).length,2);
  assert.match(stand,/data-avatar-part="mirrored-right-hand"/);
  for(const pose of ['wave','think']){
   const svg=renderAvatar({bodyStyle,shirtStyle,skinTone,pose});
   assert.equal((svg.match(/data-avatar-part="palm-volume"/g)||[]).length,1,pose+' retains one neutral hand');
  }
 }
});

test('thinking gesture retains distinct finger joints and palm volume without duplicating forearms',()=>{
 for(const bodyStyle of ['male','female'])for(const shirtStyle of ['tshirt','polo','shirt','jacket']){
  const svg=renderAvatar({bodyStyle,shirtStyle,pose:'think'});
  assert.equal((svg.match(/data-avatar-part="thinking-finger-joints"/g)||[]).length,1);
  assert.equal((svg.match(/data-avatar-part="thinking-palm-volume"/g)||[]).length,1);
  assert.equal((svg.match(/data-avatar-part="thinking-hand"/g)||[]).length,1);
  for(const side of ['left','right']) assert.equal((svg.match(new RegExp('data-avatar-part="'+side+'-forearm"','g'))||[]).length,1);
  assert.doesNotMatch(svg,/NaN|undefined/);
 }
});

test('bulk integrated celebration palms and confident fists remain symmetric',()=>{
 for(const bodyStyle of ['male','female']) for(const shirtStyle of ['tshirt','polo','shirt','jacket']){
  const cheer=renderAvatar({bodyStyle,shirtStyle,pose:'celebrate'});
  const waveHands=[...cheer.matchAll(/data-avatar-part="open-hand" d="([^"]+)"/g)].map(x=>x[1]);
  assert.equal(waveHands.length,2);
  assert.equal(waveHands[0],waveHands[1]);
  const confident=renderAvatar({bodyStyle,shirtStyle,pose:'confident'});
  const fists=[...confident.matchAll(/data-avatar-part="closed-hand" d="([^"]+)"/g)].map(x=>x[1]);
  assert.equal(fists.length,2);
  assert.equal(fists[0],fists[1]);
  assert.equal((confident.match(/data-avatar-part="fist-volume"/g)||[]).length,2);
  assert.equal((confident.match(/data-avatar-part="fist-knuckles"/g)||[]).length,2);
 }
});

test('full pose-and-wardrobe matrix keeps closed sleeves, paired cuffs and valid anatomy',()=>{
 const poses=['stand','wave','think','confident','celebrate'];
 for(const bodyStyle of ['male','female']) for(const shirtStyle of ['tshirt','polo','shirt','jacket']) for(const pose of poses){
  const svg=renderAvatar({bodyStyle,shirtStyle,pose});
  const description=bodyStyle+'/'+shirtStyle+'/'+pose;
  assert.equal((svg.match(/data-sleeve-side="left"/g)||[]).length,1,description+' left sleeve');
  assert.equal((svg.match(/data-sleeve-side="right"/g)||[]).length,1,description+' right sleeve');
  assert.equal((svg.match(/data-avatar-part="sleeve-cuff"/g)||[]).length,2,description+' paired cuffs');
  assert.equal((svg.match(/data-avatar-part="left-forearm"/g)||[]).length,1,description+' left forearm');
  assert.equal((svg.match(/data-avatar-part="right-forearm"/g)||[]).length,1,description+' right forearm');
  assert.doesNotMatch(svg,/NaN|undefined|Infinity/,description+' valid geometry');
  assert.equal((svg.match(/<svg /g)||[]).length,1,description+' unique root');
 }
});

test('all twenty face presets preserve hand anatomy and sleeves across every pose and shirt',()=>{
 const poses=['stand','wave','think','confident','celebrate'];
 for(const prefix of ['M','F'])for(let i=1;i<=10;i++)for(const shirtStyle of ['tshirt','polo','shirt','jacket'])for(const pose of poses){
  const presetId=prefix+String(i).padStart(2,'0');
  const svg=renderAvatar({presetId,bodyStyle:prefix==='M'?'male':'female',shirtStyle,pose});
  const which=presetId+'/'+shirtStyle+'/'+pose;
  assert.equal((svg.match(/data-avatar-part="pose-sleeves"/g)||[]).length,1,which+' sleeve group');
  assert.equal((svg.match(/data-avatar-part="sleeve-cuff"/g)||[]).length,2,which+' hem endpoints');
  assert.equal((svg.match(/data-avatar-part="left-forearm"/g)||[]).length,1,which+' left arm');
  assert.equal((svg.match(/data-avatar-part="right-forearm"/g)||[]).length,1,which+' right arm');
  assert.doesNotMatch(svg,/NaN|undefined|Infinity/,which+' finite geometry');
  if(pose==='celebrate')assert.equal((svg.match(/data-avatar-part="open-hand"/g)||[]).length,2,which+' open palms');
  if(pose==='confident')assert.equal((svg.match(/data-avatar-part="closed-hand"/g)||[]).length,2,which+' fists');
  if(pose==='think')assert.equal((svg.match(/data-avatar-part="thinking-hand"/g)||[]).length,1,which+' pondering hand');
 }
});

test('raised hands have matched palm depth and thumb folds at every wardrobe choice',()=>{
 for(const bodyStyle of ['male','female'])for(const shirtStyle of ['tshirt','polo','shirt','jacket']){
  for(const [pose,count] of [['wave',1],['celebrate',2]]){
   const svg=renderAvatar({bodyStyle,shirtStyle,pose});
   assert.equal((svg.match(/data-avatar-part="raised-palm-depth"/g)||[]).length,count,pose+' palm highlights');
   assert.equal((svg.match(/data-avatar-part="raised-thumb-fold"/g)||[]).length,count,pose+' thumb creases');
   assert.equal((svg.match(/data-avatar-part="finger-creases"/g)||[]).length,count,pose+' finger joints');
  }
  assert.equal((renderAvatar({bodyStyle,shirtStyle,pose:'stand'}).match(/data-avatar-part="raised-palm-depth"/g)||[]).length,0);
 }
});

test('thinking pose preserves single articulated thumb and finger highlight with all outfit styles',()=>{
 for(const bodyStyle of ['male','female'])for(const shirtStyle of ['tshirt','polo','shirt','jacket']){
  const svg=renderAvatar({bodyStyle,shirtStyle,pose:'think'});
  assert.equal((svg.match(/data-avatar-part="thinking-thumb-joint"/g)||[]).length,1);
  assert.equal((svg.match(/data-avatar-part="thinking-finger-highlight"/g)||[]).length,1);
  assert.equal((svg.match(/data-avatar-part="thinking-finger-joints"/g)||[]).length,1);
  assert.equal((svg.match(/data-avatar-part="sleeve-cuff"/g)||[]).length,2);
 }
});

test('underarm sleeve seams follow both sleeves and remain clipped in every pose',()=>{
 for(const bodyStyle of ['male','female'])for(const shirtStyle of ['tshirt','polo','shirt','jacket'])for(const pose of ['stand','wave','think','confident','celebrate']){
  const svg=renderAvatar({bodyStyle,shirtStyle,pose});
  assert.equal((svg.match(/data-avatar-part="sleeve-underarm-seam"/g)||[]).length,2,bodyStyle+'/'+shirtStyle+'/'+pose);
  assert.equal((svg.match(/data-avatar-part="sleeve-material-(?:left|right)"/g)||[]).length,2);
  assert.equal((svg.match(/data-avatar-part="sleeve-cuff"/g)||[]).length,2);
 }
});

test('confident fists have paired thumb joints and knuckle lighting after WebKit room fix',()=>{
 for(const bodyStyle of ['male','female'])for(const shirtStyle of ['tshirt','polo','shirt','jacket']){
  const svg=renderAvatar({bodyStyle,shirtStyle,pose:'confident'});
  for(const part of ['closed-hand','fist-knuckles','fist-volume','fist-thumb-fold','fist-knuckle-light']){
   assert.equal((svg.match(new RegExp('data-avatar-part="'+part+'"','g'))||[]).length,2,bodyStyle+'/'+shirtStyle+'/'+part);
  }
 }
});

test('celebration hands share the same five-digit palm and remain mirrored across outfits',()=>{
 for(const bodyStyle of ['male','female'])for(const shirtStyle of ['tshirt','polo','shirt','jacket']){
  const svg=renderAvatar({bodyStyle,shirtStyle,pose:'celebrate'});
  assert.equal((svg.match(/data-avatar-part="celebration-palm"/g)||[]).length,2);
  assert.equal((svg.match(/data-avatar-part="open-hand"/g)||[]).length,2);
  assert.equal((svg.match(/data-avatar-part="finger-creases"/g)||[]).length,2);
  assert.equal((svg.match(/data-avatar-part="raised-palm-depth"/g)||[]).length,2);
  assert.equal((svg.match(/data-avatar-part="sleeve-cuff"/g)||[]).length,2);
  assert.match(svg,/data-avatar-part="mirrored-right-hand" transform="translate\(129 58\) scale\(-1 1\)"/);
 }
});

test('relaxed palms use shared extended-finger silhouette and symmetric matching clipping',()=>{
 for(const bodyStyle of ['male','female'])for(const shirtStyle of ['tshirt','polo','shirt','jacket'])for(const pose of ['stand','wave','think']){
  const svg=renderAvatar({bodyStyle,shirtStyle,pose});
  const palm=svg.match(/data-avatar-part="relaxed-hand" d="([^"]+)"/);
  assert.ok(palm,bodyStyle+'/'+shirtStyle+'/'+pose);
  assert.match(palm[1],/L-9 15Q-9 19/);
  assert.match(palm[1],/L-1 22Q-1 24 1 24/);
  assert.equal((svg.match(/data-avatar-part="palm-volume"/g)||[]).length,pose==='stand'?2:1);
 }
});

test('confident fists have the same enlarged mirrored scale in all outfits',()=>{
 for(const bodyStyle of ['male','female'])for(const shirtStyle of ['tshirt','polo','shirt','jacket']){
  const svg=renderAvatar({bodyStyle,shirtStyle,pose:'confident'});
  assert.match(svg,/data-avatar-part="left-confident-hand" transform="translate\(60 135\) scale\(1\.16\) translate\(-60 -135\)"/);
  assert.match(svg,/data-avatar-part="right-confident-hand" transform="translate\(160 0\) scale\(-1 1\)"/);
  assert.equal((svg.match(/scale\(1\.16\) translate\(-60 -135\)/g)||[]).length,2);
  assert.equal((svg.match(/data-avatar-part="closed-hand"/g)||[]).length,2);
  assert.equal((svg.match(/data-avatar-part="sleeve-cuff"/g)||[]).length,2);
 }
});

test('confident knuckle creases do not protrude above the closed fist contour',()=>{
 for(const bodyStyle of ['male','female'])for(const shirtStyle of ['tshirt','polo','shirt','jacket']){
  const svg=renderAvatar({bodyStyle,shirtStyle,pose:'confident'});
  assert.equal((svg.match(/data-avatar-part="fist-knuckles" d="M57 134Q58 133 59 134M60 133Q61 132 62 133M63 133Q64 133 65 134"/g)||[]).length,2);
  assert.equal((svg.match(/data-avatar-part="closed-hand"/g)||[]).length,2);
 }
});

test('jacket sleeve stitching is clipped and only appears on jacket across five poses',()=>{
 for(const bodyStyle of ['male','female'])for(const pose of ['stand','wave','think','confident','celebrate']){
  for(const shirtStyle of ['tshirt','polo','shirt','jacket']){
   const svg=renderAvatar({bodyStyle,shirtStyle,pose});
   assert.equal((svg.match(/data-avatar-part="jacket-sleeve-stitch"/g)||[]).length,shirtStyle==='jacket'?2:0);
   assert.equal((svg.match(/data-avatar-part="sleeve-underarm-seam"/g)||[]).length,2);
   assert.equal((svg.match(/data-avatar-part="sleeve-cuff"/g)||[]).length,2);
  }
 }
});

test('jacket shoulder yokes stay exclusive to jacket across all poses',()=>{
 for(const bodyStyle of ['male','female'])for(const pose of ['stand','wave','celebrate','think','confident'])for(const shirtStyle of ['tshirt','polo','shirt','jacket']){
  const svg=renderAvatar({bodyStyle,shirtStyle,pose});
  assert.equal((svg.match(/data-avatar-part="jacket-shoulder-yoke"/g)||[]).length,shirtStyle==='jacket'?2:0);
  assert.equal((svg.match(/data-avatar-part="sleeve-cuff"/g)||[]).length,2);
  assert.equal((svg.match(/data-avatar-part="sleeve-material-(left|right)"/g)||[]).length,2);
 }
});

test('confident forearm contours taper smoothly into both mirrored fists',()=>{
 for(const bodyStyle of ['male','female'])for(const shirtStyle of ['tshirt','polo','shirt','jacket']){
  const svg=renderAvatar({bodyStyle,shirtStyle,pose:'confident'});
  assert.match(svg,/L60 136Q57 133 55 133L49 130/);
  assert.match(svg,/L100 136Q103 133 105 133L111 130/);
  assert.equal((svg.match(/data-avatar-part="fist-knuckle-light" d="M58 133Q61 132 64 133"/g)||[]).length,2);
  assert.equal((svg.match(/data-avatar-part="closed-hand"/g)||[]).length,2);
 }
});

test('confident hands use a rounded integrated fist silhouette in all garments',()=>{
 for(const bodyStyle of ['male','female'])for(const shirtStyle of ['tshirt','polo','shirt','jacket']){
  const svg=renderAvatar({bodyStyle,shirtStyle,pose:'confident'});
  assert.equal((svg.match(/data-avatar-part="closed-hand" d="M54 135Q53 130 57 129Q61 127 65 130Q69 132 69 136Q69 140 64 141L58 141Q54 140 54 135Z"/g)||[]).length,2);
  assert.equal((svg.match(/data-avatar-part="fist-knuckles"/g)||[]).length,2);
 }
});

test('thinking hand keeps one enlarged integrated palm and its shading across all outfits',()=>{
 for(const bodyStyle of ['male','female'])for(const shirtStyle of ['tshirt','polo','shirt','jacket']){
  const svg=renderAvatar({bodyStyle,shirtStyle,pose:'think'});
  assert.match(svg,/data-avatar-part="thinking-hand" d="M-6 2Q-8 -1 -6 -6/);
  assert.match(svg,/data-avatar-part="thinking-palm-volume" d="M-4 0Q-4 -3 -1 -5/);
  assert.equal((svg.match(/data-avatar-part="thinking-hand"/g)||[]).length,1);
  assert.equal((svg.match(/data-avatar-part="sleeve-cuff"/g)||[]).length,2);
 }
});

test('wave hand scales all finger, palm and wrist details together about the same anchor',()=>{
 for(const bodyStyle of ['male','female'])for(const shirtStyle of ['tshirt','polo','shirt','jacket']){
  const svg=renderAvatar({bodyStyle,shirtStyle,pose:'wave'});
  assert.match(svg,/data-avatar-part="wave-palm-assembly" transform="scale\(1\.12\)"/);
  assert.equal((svg.match(/data-avatar-part="wave-palm-assembly"/g)||[]).length,1);
  assert.equal((svg.match(/data-avatar-part="open-hand"/g)||[]).length,1);
  assert.equal((svg.match(/data-avatar-part="sleeve-cuff"/g)||[]).length,2);
 }
});

test('wave finger contour separates digit tips without modifying celebration palms',()=>{
 for(const bodyStyle of ['male','female'])for(const shirtStyle of ['tshirt','polo','shirt','jacket']){
  const svg=renderAvatar({bodyStyle,shirtStyle,pose:'wave'});
  assert.match(svg,/data-avatar-part="open-hand" d="M-5 2Q-9 -1 -12 -7Q-14 -10 -11 -12/);
  assert.match(svg,/L-4 -25Q-5 -29 -1 -29/);
  assert.match(svg,/L5 -24Q5 -28 9 -27/);
  assert.equal((svg.match(/data-avatar-part="wave-palm-assembly"/g)||[]).length,1);
  const celebrate=renderAvatar({bodyStyle,shirtStyle,pose:'celebrate'});
  assert.equal((celebrate.match(/data-avatar-part="celebration-palm"/g)||[]).length,2);
  assert.equal((celebrate.match(/data-avatar-part="open-hand"/g)||[]).length,2);
 }
});

test('relaxed hands have independent tapered fingertips with perfectly matched highlight clipping',()=>{
 for(const bodyStyle of ['male','female'])for(const shirtStyle of ['tshirt','polo','shirt','jacket']){
  for(const pose of ['stand','wave','think']){
   const svg=renderAvatar({bodyStyle,shirtStyle,pose});
   assert.match(svg,/data-avatar-part="relaxed-hand" d="M-5 -1Q-9 1 -9 7/);
   assert.match(svg,/L-1 22Q-1 24 1 24/);
   assert.match(svg,/L7 13Q9 15 11 13/);
   assert.equal((svg.match(/data-avatar-part="relaxed-hand"/g)||[]).length,pose==='stand'?2:1);
   assert.equal((svg.match(/data-avatar-part="palm-volume"/g)||[]).length,pose==='stand'?2:1);
   assert.equal((svg.match(/data-avatar-part="sleeve-cuff"/g)||[]).length,2);
  }
 }
});

test('celebration palms use larger matching wrists and fingers across all clothes',()=>{
 for(const bodyStyle of ['male','female'])for(const shirtStyle of ['tshirt','polo','shirt','jacket']){
  const svg=renderAvatar({bodyStyle,shirtStyle,pose:'celebrate'});
  assert.equal((svg.match(/data-avatar-part="celebration-palm" transform="scale\(\.94\)"/g)||[]).length,2);
  assert.equal((svg.match(/data-avatar-part="open-hand"/g)||[]).length,2);
  assert.equal((svg.match(/data-avatar-part="sleeve-cuff"/g)||[]).length,2);
  assert.match(svg,/data-avatar-part="mirrored-right-hand" transform="translate\(129 58\) scale\(-1 1\)"/);
 }
});
