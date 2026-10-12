import test from 'node:test';
import assert from 'node:assert/strict';
import {avatarSelectionReadiness} from '../shared/avatar-selection-readiness.js';
import {PNG_PARTS} from '../shared/avatar-png-catalog.js';
const choices={bodyStyle:'male',hairStyle:'shoulder',shirtStyle:'jacket',bottomStyle:'pants',shoeColor:'white',glassesStyle:'none'};
test('existing authentic thumbnail PNGs cannot go live without alignment and body',()=>{
 const result=avatarSelectionReadiness(choices);
 assert.equal(result.ready,false);
 assert.ok(result.reasons.includes('body-base'));
 assert.ok(result.reasons.includes('unaligned:face'));
 assert.ok(!result.reasons.includes('missing:shoes'));
 assert.ok(!result.reasons.includes('missing:top'));
});
test('glasses missing is required only when player has selected glasses',()=>{
 const no=avatarSelectionReadiness(choices);
 const yes=avatarSelectionReadiness({...choices,glassesStyle:'round'});
 assert.equal(no.reasons.includes('missing:glasses'),false);
 assert.equal(yes.reasons.includes('missing:glasses'),true);
});
test('correct gender and specific garment are required instead of any unrelated upload',()=>{
 const female=avatarSelectionReadiness({...choices,bodyStyle:'female',shirtStyle:'polo'});
 assert.ok(female.reasons.includes('missing:top'));
 const noHair=avatarSelectionReadiness({...choices,hairStyle:'bald'});
 assert.equal(noHair.reasons.includes('missing:hair'),false);
});
test('a fully prepared selected outfit can pass even if other catalog entries are unapproved',()=>{
 const catalog=Object.fromEntries(Object.entries(PNG_PARTS).map(([k,v])=>[k,v.map(p=>({...p,aligned:p.ready}))]));
 catalog.body=[{value:'male',src:'/avatar-parts/approved-male-body.png',ready:true,aligned:true}];
 const result=avatarSelectionReadiness(choices,catalog);
 assert.equal(result.ready,true);
 assert.deepEqual(result.reasons,[]);
});

test('a committed and approved body PNG unlocks the readiness gate for its own gender only',()=>{
 const aligned=Object.fromEntries(Object.entries(PNG_PARTS).map(([key,parts])=>[key,parts.map(part=>({...part,aligned:part.ready}))]));
 aligned.body=[{value:'male',src:'/avatar-parts/approved-male-body.png',ready:true,aligned:true}];
 assert.equal(avatarSelectionReadiness(choices,aligned).ready,true);
 assert.ok(avatarSelectionReadiness({...choices,bodyStyle:'female'},aligned).reasons.includes('body-base'));
});
test('an absent, unapproved, or unaligned base never unlocks the real avatar',()=>{
 const catalog={...PNG_PARTS,body:[{value:'male',src:'/avatar-parts/bad-body.png',ready:true,aligned:false}]};
 assert.ok(avatarSelectionReadiness(choices,catalog).reasons.includes('body-base'));
});

test('caller cannot fake an approved body by setting an obsolete override flag',()=>{
 const catalog=Object.fromEntries(Object.entries(PNG_PARTS).map(([key,parts])=>[key,parts.map(part=>({...part,aligned:part.ready}))]));
 assert.ok(avatarSelectionReadiness(choices,catalog,{hasBodyBase:true}).reasons.includes('body-base'));
});
