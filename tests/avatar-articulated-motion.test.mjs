import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {renderAvatar} from '../shared/avatar.js';
const css=readFileSync(new URL('../app/globals.css',import.meta.url),'utf8');
const poses=['stand','wave','celebrate','think','confident'];
const outfits=['tshirt','polo','shirt','jacket'];
const ids=Array.from({length:20},(_,i)=>(i<10?'M':'F')+String(i%10+1).padStart(2,'0'));

test('raised forearms and their own sleeves form paired pose-specific animation joints',()=>{
 let total=0;
 for(const id of ids)for(const shirtStyle of outfits)for(const pose of poses){
  const ctx=id+'/'+shirtStyle+'/'+pose;
  const svg=renderAvatar({presetId:id,bodyStyle:id[0]==='F'?'female':'male',shirtStyle,pose,materialPrefix:'joint-'+id+'-'+shirtStyle+'-'+pose});
  const raised=pose==='wave'?['left']:pose==='celebrate'?['left','right']:[];
  for(const side of ['left','right']){
   const arm=(svg.match(new RegExp('data-avatar-part="'+side+'-articulated-arm"','g'))||[]).length;
   const sleeve=(svg.match(new RegExp('data-avatar-part="'+side+'-articulated-sleeve"','g'))||[]).length;
   assert.equal(arm,raised.includes(side)?1:0,ctx+' '+side+' raised arm');
   assert.equal(sleeve,1,ctx+' '+side+' clipped sleeve group retained');
  }
  assert.equal((svg.match(/data-sleeve-side="(?:left|right)"/g)||[]).length,2,ctx+' paired sleeves still render');
  assert.equal((svg.match(/data-avatar-part="sleeve-cuff"/g)||[]).length,2,ctx+' paired cuffs still render');
  total++;
 }
 assert.equal(total,400);
});

test('arm/sleeve animations match and stop for reduced-motion or explicit off',()=>{
 assert.match(css,/@keyframes game-avatar-wave-joint/);
 assert.match(css,/@keyframes game-avatar-cheer-left-joint/);
 assert.match(css,/@keyframes game-avatar-cheer-right-joint/);
 for(const pose of ['wave','celebrate']){
  for(const side of pose==='wave'?['left']:['left','right']){
   assert.ok(css.includes('.game-avatar-motion-'+pose+' svg [data-avatar-part="'+side+'-articulated-arm"]'));
   assert.ok(css.includes('.game-avatar-motion-'+pose+' svg [data-avatar-part="'+side+'-articulated-sleeve"]'));
  }
 }
 assert.match(css,/@media\(prefers-reduced-motion:reduce\)\{\.game-avatar-motion svg/);
 assert.match(css,/\.motion-off \.game-avatar-motion svg/);
});
