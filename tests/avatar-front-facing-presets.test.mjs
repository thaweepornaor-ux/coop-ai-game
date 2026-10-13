import test from 'node:test';
import assert from 'node:assert/strict';
import {renderAvatar,AVATAR_OPTIONS} from '../shared/avatar.js';

test('all twenty front-facing presets generate distinct SVG faces',()=>{
 for(const gender of ['male','female']){
  const prefix=gender==='male'?'M':'F';
  const portraits=Array.from({length:10},(_,i)=>renderAvatar({bodyStyle:gender,presetId:prefix+String(i+1).padStart(2,'0'),hairStyle:'bald',glassesStyle:'none'}));
  assert.equal(new Set(portraits).size,10,'face geometry must differ for '+gender);
  portraits.forEach(svg=>{assert.match(svg,/^<svg /);assert.ok(!svg.includes('NaN'));assert.ok(!svg.includes('undefined'));});
 }
});
test('every visible style choice still affects the front-facing avatar',()=>{
 const baseline={bodyStyle:'female',presetId:'F01',hatStyle:'cap'};
 for(const key of ['skinTone','hairStyle','hairColor','shirtStyle','shirtColor','bottomStyle','bottomColor','shoeColor','glassesStyle','hatStyle','hatColor']){
  const variants=AVATAR_OPTIONS[key];
  const first=renderAvatar({...baseline,[key]:variants[0].value});
  const last=renderAvatar({...baseline,[key]:variants[variants.length-1].value});
  assert.notEqual(first,last,key+' must update the portrait');
 }
});
test('mismatched or invalid face presets do not generate invalid SVG',()=>{
 const standard=renderAvatar({bodyStyle:'female',presetId:'F01'});
 assert.equal(renderAvatar({bodyStyle:'female',presetId:'M09'}),standard);
 assert.equal(renderAvatar({bodyStyle:'female',presetId:'garbage'}),standard);
 assert.ok(!renderAvatar({bodyStyle:'male',presetId:'M10'}).includes('NaN'));
});

test('visibly different hair presets no longer collapse into aliased silhouettes',()=>{
 const outfit={bodyStyle:'female',presetId:'F05',hairColor:'brown',hatStyle:'none'};
 for(const [styled,previousAlias] of [
  ['wavy','long'],['swept','sidepart'],['shoulder','bob'],
  ['pixie','short'],['bun','ponytail']
 ]){
  assert.notEqual(renderAvatar({...outfit,hairStyle:styled}),renderAvatar({...outfit,hairStyle:previousAlias}),
   styled+' must look different from '+previousAlias);
 }
});

test('SVG character fallback has curved anti-clipped, per-wardrobe material depth',()=>{
  const one=renderAvatar({bodyStyle:'female',presetId:'F03',shirtColor:'blue',skinTone:'warm',hairColor:'brown'});
  const two=renderAvatar({bodyStyle:'female',presetId:'F03',shirtColor:'red',skinTone:'warm',hairColor:'brown'});
  assert.match(one,/shape-rendering:geometricPrecision/);
  assert.match(one,/<linearGradient id="a[0-9a-z]+-skin"/);
  assert.match(one,/<linearGradient id="a[0-9a-z]+-shirt"/);
  assert.match(one,/<linearGradient id="a[0-9a-z]+-hair"/);
  assert.match(one,/fill="url\(#a[0-9a-z]+-shirt\)"/);
  assert.match(one,/fill="url\(#a[0-9a-z]+-skin\)"/);
  assert.match(one,/fill="url\(#a[0-9a-z]+-hair\)"/);
  assert.notEqual(one,two,'Outfit colors must keep independent gradient IDs and materials');
  for(const gender of ['male','female']){
    for(let i=1;i<=10;i++){
      const portrait=renderAvatar({bodyStyle:gender,presetId:(gender==='male'?'M':'F')+String(i).padStart(2,'0')});
      assert.ok(portrait.startsWith('<svg'),'Each preset remains valid SVG');
      assert.ok(portrait.includes('<defs>')&&portrait.includes('</svg>'),'Every character includes complete vector material definitions');
      assert.ok(!portrait.includes('NaN'),'No malformed face or body geometry');
    }
  }
});
