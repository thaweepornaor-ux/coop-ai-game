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
