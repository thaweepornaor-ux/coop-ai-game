import test from 'node:test';
import assert from 'node:assert/strict';
import {avatarArtReadiness} from '../shared/avatar-art-readiness.js';
import {PNG_PARTS} from '../shared/avatar-png-catalog.js';
test('real uploaded crops cannot be declared a complete playable PNG avatar',()=>{
 const state=avatarArtReadiness(PNG_PARTS);
 assert.equal(state.ready,false);
 assert.ok(state.missing.includes('body-base'));
 assert.ok(state.missing.includes('glasses'));
 assert.ok(state.unaligned.includes('face'));
 assert.ok(state.unaligned.includes('top'));
});
test('aligned images with a body base can pass readiness',()=>{
 const complete=Object.fromEntries(['face','hair','top','bottom','shoes','glasses'].map(category=>[category,[{ready:true,aligned:true,src:'/avatar-parts/example.png'}]]));
 assert.deepEqual(avatarArtReadiness(complete,{hasBodyBase:true}),{ready:true,missing:[],unaligned:[]});
});
test('upload status alone does not imply pixel alignment',()=>{
 const incomplete={...PNG_PARTS,glasses:[{ready:true,aligned:false}]};
 assert.equal(avatarArtReadiness(incomplete,{hasBodyBase:true}).ready,false);
});

test('gender-aware readiness rejects opposite-gender garments even with aligned assets',()=>{
 const parts=Object.fromEntries(['face','hair','top','bottom','shoes','glasses'].map(category=>[category,[{ready:true,aligned:true,src:'/test.png',gender:'male'}]]));
 assert.equal(avatarArtReadiness(parts,{hasBodyBase:true,gender:'male'}).ready,true);
 const female=avatarArtReadiness(parts,{hasBodyBase:true,gender:'female'});
 assert.equal(female.ready,false);
 assert.ok(female.missing.includes('top'));
 assert.ok(female.missing.includes('shoes'));
});
test('non-playable reference shorts cannot certify a complete avatar',()=>{
 const parts=Object.fromEntries(['face','hair','top','bottom','shoes','glasses'].map(category=>[category,[{ready:true,aligned:true,src:'/test.png'}]]));
 parts.bottom[0].playable=false;
 const result=avatarArtReadiness(parts,{hasBodyBase:true,gender:'male'});
 assert.equal(result.ready,false);
 assert.ok(result.missing.includes('bottom'));
});
test('invalid gender does not silently fall back to combined art catalog',()=>{
 assert.throws(()=>avatarArtReadiness(PNG_PARTS,{gender:'other'}),/Invalid avatar gender/);
});
