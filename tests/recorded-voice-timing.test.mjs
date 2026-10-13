import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const rules=readFileSync(new URL('../server/game.ts',import.meta.url),'utf8');
const route=readFileSync(new URL('../app/api/game/route.ts',import.meta.url),'utf8');
const game=readFileSync(new URL('../app/game.tsx',import.meta.url),'utf8');
const questions=readFileSync(new URL('../server/questions.ts',import.meta.url),'utf8');
const source=rules.match(/export const NARRATION_DURATION_MS = (\[[^\]]+\])/);
const duration=source?JSON.parse(source[1]):[];

test('Each real recorded narration reserves the full 25-second answer window',()=>{
 assert.match(rules,/export const QUESTION_SECONDS = 25/);
 assert.equal(duration.length,15);
 assert.ok(duration.every(x=>x>=14000&&x<19000));
 assert.match(rules,/NARRATION_BUFFER_MS = 1400/);
 assert.match(rules,/QUESTION_SECONDS\*1000\+/);
 assert.match(route,/answerWindowMs\(plan.questionIndex\)/);
 assert.equal((questions.match(/"timeLimitSeconds": 25/g)||[]).length,15);
});

test('Presenter uses real MP3 for questions while revealing answers separately',()=>{
 assert.ok(game.includes("new Audio(voiceUrls.current["));
 assert.match(game,/\.mp3'\)/);
 assert.match(game,/const letters=\['A','B','C'\]/);
 assert.match(game,/const timer=Math.min\(25,totalRemaining\)/);
 assert.match(game,/const narrationRemaining=/);
 assert.match(game,/narrationRemaining>0\?'🔊 กำลังพากย์'/);
 assert.match(game,/track.onended=/);
 assert.match(game,/track.onerror=/);
 assert.match(game,/SpeechSynthesisUtterance/);
});

test('Instructor can load and retain a complete local MP3 voice pack without a server binary dependency',()=>{
 assert.match(game,/indexedDB\.open\('coop-ai-quiz-recorded-voice',1\)/);
 assert.match(game,/saveVoicePack\(mp3\)/);
 assert.match(game,/loadVoicePack\(\)/);
 assert.match(game,/voiceUrls\.current=mp3\.map\(file=>URL\.createObjectURL\(file\)\)/);
 assert.match(game,/role==='host'&&<label className=/);
 assert.match(game,/Q01\.mp3 ถึง Q15\.mp3/);
 assert.match(game,/narrationEnabled&&voiceReady/);
 assert.match(game,/recordedNarration:narrationEnabled/);
 assert.match(route,/body\.recordedNarration===true\?answerWindowMs\(plan.questionIndex\):QUESTION_SECONDS\*1000/);
});

test('spoken Thai fallback is enabled without installing voice files',()=>{
 assert.match(game,/useState\(true\),\[narrationBusy,setNarrationBusy\]/);
 assert.match(game,/if\(mode==='question'&&!voiceUrls.current\[state.room.questionIndex\]\)/);
 assert.match(game,/const spoken='คำถามข้อที่ '/);
 assert.match(game,/ข้อ เอ\. /);
 assert.match(game,/ข้อ บี\. /);
 assert.match(game,/ข้อ ซี\. /);
 assert.match(game,/window\.speechSynthesis\.speak\(utterance\)/);
 assert.match(game,/utterance\.lang='th-TH'/);
 assert.match(game,/if\(sessionRef\.current\?\.role==='host'&&narrationEnabled&&voiceReady/);
 assert.match(game,/▶ ทดลองเสียงอ่าน/);
 assert.match(game,/disabled=\{voiceImporting\} onClick=\{testRecordedVoice\}/);
});
