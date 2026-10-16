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

test('confident pose mirrors one hand anatomy across all shirts and bodies',()=>{
 for(const bodyStyle of ['male','female'])for(const shirtStyle of ['tshirt','polo','shirt','jacket']){
  const svg=renderAvatar({bodyStyle,shirtStyle,pose:'confident'});
  const fists=[...svg.matchAll(/data-avatar-part="closed-hand" d="([^"]+)"/g)].map(m=>m[1]);
  assert.equal(fists.length,2);
  assert.equal(fists[0],fists[1],'closed palms share a contour');
  assert.match(svg,/data-avatar-part="right-confident-hand" transform="translate\(160 0\) scale\(-1 1\)"/);
  assert.equal((svg.match(/data-avatar-part="fist-volume"/g)||[]).length,2);
  assert.equal((svg.match(/data-avatar-part="fist-knuckles"/g)||[]).length,2);
 }
});
