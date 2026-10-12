import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {PNG_PARTS} from '../shared/avatar-png-catalog.js';

const root=new URL('../public',import.meta.url);
const signature=Buffer.from([137,80,78,71,13,10,26,10]);
test('every marked-uploaded avatar asset exists as a valid PNG in GitHub checkout',()=>{
 const ready=Object.values(PNG_PARTS).flat().filter(p=>p.ready);
 assert.ok(ready.length>=2,'two face images must remain in the repository');
 for(const part of ready){
  const relative=part.src.replace(/^\//,'');
  const path=fileURLToPath(new URL(relative,root));
  assert.ok(existsSync(path),'missing committed PNG: '+part.src);
  const bytes=readFileSync(path);
  assert.ok(bytes.length>32,'empty PNG: '+part.src);
  assert.ok(bytes.subarray(0,8).equals(signature),'invalid PNG signature: '+part.src);
  const width=bytes.readUInt32BE(16),height=bytes.readUInt32BE(20);
  assert.ok(width>0&&height>0,'invalid dimensions: '+part.src);
 }
});
