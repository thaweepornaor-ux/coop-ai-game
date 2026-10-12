import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const source=readFileSync(new URL('../server/questions.ts',import.meta.url),'utf8');
const body=source.match(/export const QUESTIONS\s*=\s*(\[[\s\S]*?\])\s*as const\s*;/)?.[1];
if(!body)throw new Error('Cannot locate QUESTIONS in server/questions.ts');
const questions=JSON.parse(body);

test('cooperative AI quiz has exactly 15 numbered questions',()=>{
 assert.equal(questions.length,15);
 assert.deepEqual(questions.map(q=>q.number),Array.from({length:15},(_,i)=>i+1));
});
test('every question is answerable and has a 15-second timer',()=>{
 for(const q of questions){
  assert.ok(typeof q.question==='string'&&q.question.trim().length>3,'question '+q.number);
  assert.equal(q.options.length,3,'question '+q.number);
  assert.ok(q.options.every(x=>typeof x==='string'&&x.trim().length>0));
  assert.ok(Number.isInteger(q.answer)&&q.answer>=0&&q.answer<q.options.length);
  assert.equal(q.timeLimitSeconds,15);
  assert.ok(typeof q.explanation==='string'&&q.explanation.trim().length>0);
 }
});
test('opening question matches approved prompt',()=>{
 assert.equal(questions[0].question,'ข้อไหนคือใช้ AI สร้างเนื้อหาใหม่?');
});

test('no duplicate prompts or answer choices can make a round ambiguous',()=>{
 const seen=new Set();
 for(const q of questions){
  assert.ok(!seen.has(q.question),'duplicate question '+q.number);
  seen.add(q.question);
  assert.equal(new Set(q.options).size,q.options.length,'duplicate options at question '+q.number);
  assert.ok(typeof q.topic==='string'&&q.topic.trim().length>0);
 }
});
