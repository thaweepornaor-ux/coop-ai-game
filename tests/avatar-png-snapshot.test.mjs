import test from 'node:test';
import assert from 'node:assert/strict';
import {validateAssemblySnapshot,PNG_ASSEMBLY_VERSION} from '../shared/avatar-png-snapshot.js';
import {PNG_PARTS} from '../shared/avatar-png-catalog.js';

const categories=['bottom','shoes','top','face','hair'];
const positions=Object.fromEntries(categories.map(k=>[k,{x:50,y:50,scale:40}]));
const selected=Object.fromEntries(categories.map(k=>[k,PNG_PARTS[k].find(p=>p.ready).src]));
// A synthetic complete set proves round trips; today's original mixed-gender pack is intentionally blocked.
const testCatalog=Object.fromEntries(Object.entries(PNG_PARTS).map(([category,parts])=>[category,parts.map(({gender,...rest})=>rest)]));
const validateForTest=input=>validateAssemblySnapshot(input,testCatalog);

test('portable snapshot selects matching female face even if the saved one is male',()=>{
 const result=validateForTest({version:PNG_ASSEMBLY_VERSION,gender:'female',positions,selected});
 assert.equal(result.selected.face,'/avatar-parts/female.png');
 assert.deepEqual(result.positions,positions);
});
test('unverified images and absent parts are rejected',()=>{
 assert.throws(()=>validateForTest({version:1,gender:'male',positions,selected:{...selected,top:'/avatar-parts/unknown.png'}}),TypeError);
 assert.throws(()=>validateForTest({version:1,gender:'male',positions,selected:{...selected,top:PNG_PARTS.top.find(p=>!p.ready).src}}),TypeError);
});
test('unsupported schema, gender and invalid percentages are rejected',()=>{
 assert.throws(()=>validateForTest({version:2,gender:'male',positions,selected}),TypeError);
 assert.throws(()=>validateForTest({version:1,gender:'other',positions,selected}),TypeError);
 assert.throws(()=>validateForTest({version:1,gender:'male',positions:{...positions,hair:{x:Infinity,y:50,scale:50}},selected}),RangeError);
});

test('malformed JSON snapshots report missing coordinates and selections cleanly',()=>{
 assert.throws(()=>validateForTest({version:1,gender:'male',selected}),/Missing positions/);
 assert.throws(()=>validateForTest({version:1,gender:'male',positions}),/Missing selected parts/);
 assert.throws(()=>validateForTest({version:1,gender:'male',positions:{...positions,face:null},selected}),/Missing PNG position/);
 assert.throws(()=>validateForTest({version:1,gender:'male',positions:{...positions,face:[1,2]},selected}),/Missing PNG position/);
});

test('portable PNG alignment survives JSON export and re-import without changing selected parts',()=>{
 const original=validateForTest({version:1,gender:'male',positions,selected});
 const restored=validateForTest(JSON.parse(JSON.stringify(original)));
 assert.deepEqual(restored,original);
 assert.equal(restored.selected.face,'/avatar-parts/male.png');
});
test('tampered JSON cannot select arbitrary URLs or unapproved files',()=>{
 const selectedBad={...selected,hair:'https://example.com/evil.png'};
 assert.throws(()=>validateForTest({version:1,gender:'male',positions,selected:selectedBad}),TypeError);
 const positionedBad={...positions,top:{x:101,y:10,scale:20}};
 assert.throws(()=>validateForTest({version:1,gender:'male',positions:positionedBad,selected}),RangeError);
});

test('mixed male shirt and female sneakers are rejected in production PNG alignment snapshots',()=>{
 assert.throws(()=>validateAssemblySnapshot({version:1,gender:'male',positions,selected}),/Unverified PNG layer: shoes/);
 assert.throws(()=>validateAssemblySnapshot({version:1,gender:'female',positions,selected}),/Unverified PNG layer: top/);
});
