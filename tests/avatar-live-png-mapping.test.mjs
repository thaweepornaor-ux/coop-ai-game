import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {AVATAR_OPTIONS} from '../shared/avatar.js';
import {PNG_PARTS} from '../shared/avatar-png-catalog.js';
import {avatarSelectionReadiness} from '../shared/avatar-selection-readiness.js';
const source=readFileSync(new URL('../app/components/avatar.tsx',import.meta.url),'utf8');

const choices={bodyStyle:'male',hairStyle:'shoulder',shirtStyle:'jacket',bottomStyle:'pants',shoeColor:'white',glassesStyle:'none'};
test('uploaded PNG shirt and shoe aliases resolve to actual wardrobe selections',()=>{
 assert.ok(AVATAR_OPTIONS.shirtStyle.some(p=>p.value==='jacket'));
 assert.ok(AVATAR_OPTIONS.shoeColor.some(p=>p.value==='white'));
 const result=avatarSelectionReadiness(choices);
 assert.ok(result.selected.some(p=>p.src==='/avatar-parts/clothing_male_beige_overshirt.png'));
 assert.ok(result.reasons.includes('missing:shoes'));
 assert.equal(result.selected.some(p=>p.src==='/avatar-parts/shoes_female_white_sneakers.png'),false);
});
test('playable Avatar layers come from one validated selection without separate lookups',()=>{
 assert.match(source,/const readiness=avatarSelectionReadiness\(v,PNG_PARTS\)/);
 assert.match(source,/const layers=readiness\.selected/);
 assert.match(source,/const complete=readiness\.ready&&parts\.length===layers\.length/);
 assert.match(source,/PNG_PARTS\.face\.includes\(p\)/);
 assert.match(source,/PNG_PARTS\.glasses\.includes\(p\)/);
});
test('existing cropped PNG previews are not authorized as a full playable avatar',()=>{
 assert.equal(avatarSelectionReadiness(choices).ready,false);
 assert.equal(PNG_PARTS.body.length,0);
 assert.equal(PNG_PARTS.bottom.find(p=>p.src==='/avatar-parts/clothing_male_beige_chinos.png')?.playable,false);
 for(const group of Object.values(PNG_PARTS))for(const part of group)assert.equal(part.aligned,false);
});

test('PNG load completion is keyed by the chosen outfit to avoid stale display when switching',()=>{
 assert.match(source,/loaded\[signature\+'\|'\+p\.src\]==='ok'/);
 assert.match(source,/onLoad=\{\(\)=>setLoaded\(prev=>\(\{\.\.\.prev,\[signature\+'\|'\+part\.src\]:'ok'\}\)\)\}/);
 assert.match(source,/onError=\{\(\)=>setLoaded\(prev=>\(\{\.\.\.prev,\[signature\+'\|'\+part\.src\]:'error'\}\)\)\}/);
});

test('playable PNG layers require approved geometry and use part coordinates, not full-frame overlay',()=>{
 assert.match(source,/parts\.every\(hasLayout\)/);
 assert.match(source,/left:part\.position!\.x\+'%'/);
 assert.match(source,/top:part\.position!\.y\+'%'/);
 assert.match(source,/width:part\.position!\.scale\+'%'/);
 assert.match(source,/maxHeight:'65%'/);
 assert.match(source,/Number\.isFinite\(pos\[k as keyof typeof pos\]\)/);
});
