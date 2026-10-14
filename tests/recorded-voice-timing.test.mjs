import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const rules=readFileSync(new URL('../server/game.ts',import.meta.url),'utf8');
const route=readFileSync(new URL('../app/api/game/route.ts',import.meta.url),'utf8');
const game=readFileSync(new URL('../app/game.tsx',import.meta.url),'utf8');
const questions=readFileSync(new URL('../server/questions.ts',import.meta.url),'utf8');
const source=rules.match(/export const NARRATION_DURATION_MS = (\[[^\]]+\])/);
const duration=source?JSON.parse(source[1]):[];

test('Each real recorded narration reserves the full 10-second answer window',()=>{
 assert.match(rules,/export const QUESTION_SECONDS = 10/);
 assert.equal(duration.length,15);
 assert.ok(duration.every(x=>x>=14000&&x<19000));
 assert.match(rules,/NARRATION_BUFFER_MS = 1400/);
 assert.match(rules,/QUESTION_SECONDS\*1000\+/);
 assert.match(route,/answerWindowMs\(plan.questionIndex\)/);
 assert.equal((questions.match(/"timeLimitSeconds": 10/g)||[]).length,15);
});

test('Presenter uses real MP3 for questions while revealing answers separately',()=>{
 assert.ok(game.includes("new Audio(voiceUrls.current["));
 assert.match(game,/\.mp3'\)/);
 assert.match(game,/const letters=\['A','B','C'\]/);
 assert.match(game,/const timer=Math.min\(10,totalRemaining\)/);
 assert.match(game,/const narrationRemaining=/);
 assert.match(game,/narrationRemaining>0\?'🔊 กำลังพากย์'/);
 assert.match(game,/track.onended=/);
 assert.match(game,/track.onerror=/);
 assert.doesNotMatch(game,/SpeechSynthesisUtterance/);
 assert.match(game,/answerVoiceUrls\.current\[playingNumber-1\]/);
 assert.match(game,/ยังไม่ได้ติดตั้งเสียงเฉลย R01–R15/);
 assert.doesNotMatch(game,/beep\(740,\.2\)/);
});

test('Instructor can load and retain a complete local MP3 voice pack without a server binary dependency',()=>{
 assert.match(game,/indexedDB\.open\('coop-ai-quiz-recorded-voice',1\)/);
 assert.match(game,/saveVoicePack\(mp3\)/);
 assert.match(game,/loadVoicePack\(\)/);
 assert.match(game,/voiceUrls\.current=mp3\.map\(file=>URL\.createObjectURL\(file\)\)/);
 assert.match(game,/role==='host'&&<label className=/);
 assert.match(game,/Q01\.mp3 ถึง Q15\.mp3/);
 assert.match(game,/voiceReady&&narrationEnabled/);
 assert.match(game,/recordedNarration:voiceReady&&narrationEnabled/);
 assert.match(route,/body\.recordedNarration===true\?answerWindowMs\(plan.questionIndex\):QUESTION_SECONDS\*1000/);
});

test('Narration stays intact and the synchronized answer clock starts at 10 seconds only after each recording',()=>{
 assert.equal(duration.length,15);
 const totalDuration=duration.reduce((sum,ms)=>sum+ms,0);
 assert.ok(totalDuration>230000&&totalDuration<270000,'Keep all original 15 MP3 timing values');
 for(let i=0;i<15;i++){
  const fullRound=duration[i]+1400+10_000;
  const last10=fullRound-duration[i]-1400;
  assert.equal(last10,10_000,'Question '+(i+1)+' must leave precisely 10 seconds after narration');
 }
 assert.match(game,/Math.max\(0,totalRemaining-10\)/);
 assert.match(game,/timer\/10/);
 assert.match(game,/ฟังจบแล้วตอบ 10 วินาที/);
 assert.match(game,/หลังฟังโจทย์มีเวลาตอบ 10 วินาที/);
 assert.match(game,/จากนั้นมีเวลาตอบเต็ม 10 วินาที/);
 assert.match(route,/answerWindowMs\(plan.questionIndex\)/);
 assert.match(route,/QUESTION_SECONDS\*1000/);
});
