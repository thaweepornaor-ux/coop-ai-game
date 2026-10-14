import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {unpackAnswerVoiceZip} from '../shared/answer-voice-zip.js';
import {unpackQuizVoiceZip} from '../shared/quiz-voice-zip.js';

const game=readFileSync(new URL('../app/game.tsx',import.meta.url),'utf8');
const css=readFileSync(new URL('../app/answer-voice-controls.css',import.meta.url),'utf8');
const layout=readFileSync(new URL('../app/layout.tsx',import.meta.url),'utf8');

// Build a tiny stored ZIP with genuine central-directory headers for the exact
// ZIP parser used by the browser. This checks folder entries, order and format.
function makeZip(prefix,missing=[]){
  const locals=[],centrals=[];
  let offset=0,count=0;
  for(let i=1;i<=15;i++){
    if(missing.includes(i))continue;
    const name=Buffer.from(prefix+String(i).padStart(2,'0')+'.mp3');
    const payload=Buffer.concat([Buffer.from('ID3'),Buffer.alloc(1300,i)]);
    const local=Buffer.alloc(30);
    local.writeUInt32LE(0x04034b50,0);local.writeUInt16LE(20,4);
    local.writeUInt16LE(0,8);local.writeUInt32LE(payload.length,18);
    local.writeUInt32LE(payload.length,22);local.writeUInt16LE(name.length,26);
    locals.push(local,name,payload);
    const central=Buffer.alloc(46);
    central.writeUInt32LE(0x02014b50,0);central.writeUInt16LE(20,4);
    central.writeUInt16LE(20,6);central.writeUInt32LE(payload.length,20);
    central.writeUInt32LE(payload.length,24);
    central.writeUInt16LE(name.length,28);
    central.writeUInt32LE(offset,42);
    centrals.push(central,name);offset+=local.length+name.length+payload.length;count++;
  }
  const cd=Buffer.concat(centrals),eocd=Buffer.alloc(22);
  eocd.writeUInt32LE(0x06054b50,0);eocd.writeUInt16LE(count,8);eocd.writeUInt16LE(count,10);
  eocd.writeUInt32LE(cd.length,12);eocd.writeUInt32LE(offset,16);
  const data=Buffer.concat([...locals,cd,eocd]);
  return new File([data],prefix+'.zip',{type:'application/zip'});
}

test('Fifteen R audio files are extracted in correct numerical order',async()=>{
  const tracks=await unpackAnswerVoiceZip(makeZip('R'));
  assert.equal(tracks.length,15);
  for(let i=0;i<15;i++){
    assert.equal(tracks[i].name,'R'+String(i+1).padStart(2,'0')+'.MP3');
    assert.equal(tracks[i].size,1303);
  }
});
test('Answer parser refuses Q ZIP and incomplete R ZIP',async()=>{
  await assert.rejects(()=>unpackAnswerVoiceZip(makeZip('Q')),/R01/);
  await assert.rejects(()=>unpackAnswerVoiceZip(makeZip('R',[14])),/15 ข้อ/);
});
test('Original question voice parser still accepts the unmodified Q01–Q15 format',async()=>{
  assert.equal((await unpackQuizVoiceZip(makeZip('Q'))).length,15);
});
test('Voice files are persisted separately and used for reveal in place of TTS',()=>{
  for(const token of ['coop-ai-answer-recorded-voice','saveAnswerVoicePack',
    'loadAnswerVoicePack','answerVoiceUrls.current[playingNumber-1]',
    "mode==='reveal'&&answerSource",'action===\\'reveal\\'',
    'narrateSnapshot(snapshot,currentMode)','unpackAnswerVoiceZip(chosen[0])']){
    assert.ok(game.includes(token.replaceAll("\\'","'")),'Missing reveal voice contract: '+token);
  }
  assert.ok(game.includes("if(answerSource){"));
  assert.ok(game.includes("if(!('speechSynthesis' in window)"),'Graceful fallback for instructors not yet imported');
  assert.ok(game.includes("Q'+String(nextNumber).padStart(2,'0')+'.mp3"),'Question playback must stay unchanged');
});
test('New voice selector is compact and honors existing show layout',()=>{
  assert.ok(layout.includes("import './answer-voice-controls.css';"));
  assert.ok(game.includes('className="reveal-voice-settings"'));
  assert.ok(game.includes("เสียงเฉลยใหม่พร้อม ✓"));
  assert.ok(css.includes('prefers-reduced-motion:reduce'));
  assert.ok(css.includes('max-width:1260px'));
  let n=0;for(const ch of css){if(ch==='{')n++;if(ch==='}')n--;}assert.equal(n,0);
});
