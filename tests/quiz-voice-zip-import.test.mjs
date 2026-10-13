import test from 'node:test';
import assert from 'node:assert/strict';
import {deflateRawSync} from 'node:zlib';
import {readFileSync} from 'node:fs';
import {unpackQuizVoiceZip} from '../shared/quiz-voice-zip.js';

function voiceZip({count=15,method=8}={}){
 const parts=[],central=[];let offset=0;
 for(let i=1;i<=count;i++){
  const name=Buffer.from('Q'+String(i).padStart(2,'0')+'.mp3');
  const raw=Buffer.alloc(1200+i,0x55),compressed=method===8?deflateRawSync(raw):raw;
  const local=Buffer.alloc(30);
  local.writeUInt32LE(0x04034b50,0);local.writeUInt16LE(method,8);
  local.writeUInt32LE(compressed.length,18);local.writeUInt32LE(raw.length,22);
  local.writeUInt16LE(name.length,26);
  const dir=Buffer.alloc(46);
  dir.writeUInt32LE(0x02014b50,0);dir.writeUInt16LE(method,10);
  dir.writeUInt32LE(compressed.length,20);dir.writeUInt32LE(raw.length,24);
  dir.writeUInt16LE(name.length,28);dir.writeUInt32LE(offset,42);
  parts.push(local,name,compressed);central.push(dir,name);
  offset+=local.length+name.length+compressed.length;
 }
 const directory=Buffer.concat(central),end=Buffer.alloc(22);
 end.writeUInt32LE(0x06054b50,0);end.writeUInt16LE(count,8);
 end.writeUInt16LE(count,10);end.writeUInt32LE(directory.length,12);
 end.writeUInt32LE(offset,16);
 return new File([Buffer.concat([...parts,directory,end])],'narration.zip',{type:'application/zip'});
}

test('A single ordinary compressed ZIP installs all 15 question voice tracks',async()=>{
 const voices=await unpackQuizVoiceZip(voiceZip());
 assert.equal(voices.length,15);
 assert.deepEqual(voices.map(x=>x.name),Array.from({length:15},(_,i)=>'Q'+String(i+1).padStart(2,'0')+'.MP3'));
 assert.equal(voices[0].size,1201);
 assert.equal(voices[14].size,1215);
});
test('Uncompressed ZIP is also supported',async()=>{
 const voices=await unpackQuizVoiceZip(voiceZip({method:0}));
 assert.equal(voices.length,15);
});
test('Do not accept ZIP missing any question audio',async()=>{
 await assert.rejects(()=>unpackQuizVoiceZip(voiceZip({count:14})),/ครบ 15 ข้อ/);
});
test('Instructor sees unmistakable spoken-audio ZIP and preview controls, separate from sound effects',()=>{
 const app=readFileSync(new URL('../app/game.tsx',import.meta.url),'utf8');
 assert.match(app,/importVoiceSelection/);
 assert.match(app,/unpackQuizVoiceZip\(chosen\[0\]\)/);
 assert.match(app,/🎙 เลือก ZIP เสียงโจทย์/);
 assert.match(app,/▶ ทดลองเสียงอ่าน/);
 assert.match(app,/voice-setup-panel/);
 assert.match(app,/เอฟเฟกต์เปิด/);
 assert.match(app,/voiceReady&&narrationEnabled/);
});
