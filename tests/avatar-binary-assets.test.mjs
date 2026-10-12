import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {PNG_PARTS} from '../shared/avatar-png-catalog.js';

const root=new URL('../public/',import.meta.url);
const signature=Buffer.from([137,80,78,71,13,10,26,10]);
// Guard game loading speed: keep each transparent avatar part lightweight.
const MAX_PNG_BYTES=150*1024;
const MAX_READY_ASSET_BYTES=1024*1024;
const MAX_PNG_DIMENSION=1024;
test('every marked-uploaded avatar asset exists as a valid PNG in GitHub checkout',()=>{
 const ready=Object.values(PNG_PARTS).flat().filter(p=>p.ready);
 assert.ok(ready.length>=2,'two face images must remain in the repository');
 let total=0;
 for(const part of ready){
  const relative=part.src.replace(/^\//,'');
  const path=fileURLToPath(new URL(relative,root));
  assert.ok(existsSync(path),'missing committed PNG: '+part.src);
  const bytes=readFileSync(path);
  assert.ok(bytes.length>32,'empty PNG: '+part.src);
  assert.ok(bytes.length<=MAX_PNG_BYTES,'PNG exceeds 150 KiB: '+part.src+' ('+bytes.length+' bytes)');
  total+=bytes.length;
  assert.ok(bytes.subarray(0,8).equals(signature),'invalid PNG signature: '+part.src);
  const width=bytes.readUInt32BE(16),height=bytes.readUInt32BE(20);
  assert.ok(width>0&&height>0,'invalid dimensions: '+part.src);
  assert.ok(width<=MAX_PNG_DIMENSION&&height<=MAX_PNG_DIMENSION,'PNG dimensions too large: '+part.src);
 }
 assert.ok(total<=MAX_READY_ASSET_BYTES,'Ready avatar PNGs exceed 1 MiB combined: '+total+' bytes');
});
