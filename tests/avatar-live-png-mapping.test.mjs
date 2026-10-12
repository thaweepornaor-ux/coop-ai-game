import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {AVATAR_OPTIONS} from '../shared/avatar.js';
import {PNG_PARTS} from '../shared/avatar-png-catalog.js';
import {avatarSelectionReadiness} from '../shared/avatar-selection-readiness.js';
const source=readFileSync(new URL('../app/components/avatar.tsx',import.meta.url),'utf8');
const wardrobe=readFileSync(new URL('../app/components/wardrobe.tsx',import.meta.url),'utf8');

const choices={bodyStyle:'male',hairStyle:'shoulder',shirtStyle:'jacket',bottomStyle:'pants',shoeColor:'white',glassesStyle:'none'};
test('uploaded PNG shirt and shoe aliases resolve to actual wardrobe selections',()=>{
 assert.ok(AVATAR_OPTIONS.shirtStyle.some(p=>p.value==='jacket'));
 assert.ok(AVATAR_OPTIONS.shoeColor.some(p=>p.value==='white'));
 const result=avatarSelectionReadiness(choices);
 assert.ok(result.selected.some(p=>p.src==='/avatar-parts/clothing_male_beige_overshirt.png'));
 assert.ok(result.reasons.includes('missing:shoes'));
 assert.equal(result.selected.some(p=>p.src==='/avatar-parts/shoes_female_white_sneakers.png'),false);
});
test('playable Avatar uses validated layer stack rather than independent lookups',()=>{
 assert.match(source,/const stack=playableAvatarLayers\(v,PNG_PARTS\)/);
 assert.match(source,/const parts=stack\.layers/);
 assert.match(source,/const complete=stack\.ready/);
});
test('existing cropped PNG previews are not authorized as a full playable avatar',()=>{
 assert.equal(avatarSelectionReadiness(choices).ready,false);
 assert.equal(PNG_PARTS.body.length,0);
 assert.equal(PNG_PARTS.bottom.find(p=>p.src==='/avatar-parts/clothing_male_beige_chinos.png')?.playable,false);
 for(const group of Object.values(PNG_PARTS))for(const part of group)assert.equal(part.aligned,false);
});

test('PNG load completion is keyed by the chosen outfit to avoid stale display when switching',()=>{
 assert.match(source,/loaded\[signature\+'\|'\+p\.src\]==='ok'/);
 assert.match(source,/img\.decode\(\)\.then\(\(\)=>setLoaded/);
 assert.match(source,/decoding="async"/);
 assert.match(source,/onError=\{\(\)=>setLoaded\(prev=>\(\{\.\.\.prev,\[signature\+'\|'\+part\.src\]:'error'\}\)\)\}/);
});

test('playable PNG layers require approved geometry and use part coordinates, not full-frame overlay',()=>{
 assert.match(source,/const stack=playableAvatarLayers\(v,PNG_PARTS\)/);
 assert.match(source,/left:part\.position!\.x\+'%'/);
 assert.match(source,/top:part\.position!\.y\+'%'/);
 assert.match(source,/width:part\.position!\.scale\+'%'/);
 assert.match(source,/maxHeight:'65%'/);
 assert.match(source,/left:part\.position!\.x\+'%'/);
});

test('wardrobe cannot write the nonplayable shorts-preview into player outfit',()=>{
 assert.doesNotMatch(wardrobe,/change\('bottomStyle',part\.value\)/);
 assert.match(wardrobe,/ยังไม่เปิดใช้/);
 assert.match(wardrobe,/PNG_PARTS\.bottom\.filter\(part=>part\.ready\)\.map\(part=><figure/);
});
test('wardrobe shows CGI apparel previews only to compatible gender and lazy-decodes thumbnails',()=>{
 assert.match(wardrobe,/PNG_PARTS\.top\.filter\(part=>part\.ready&&\(!part\.gender\|\|part\.gender===avatar\.bodyStyle\)\)/);
 assert.match(wardrobe,/PNG_PARTS\.shoes\.filter\(part=>part\.ready&&\(!part\.gender\|\|part\.gender===avatar\.bodyStyle\)\)/);
 assert.match(wardrobe,/loading="lazy" decoding="async"/);
});
