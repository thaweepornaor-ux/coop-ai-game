// Static regression checks for the 15-round cooperative AI quiz.
// Run locally: node --test tests/questions-regression.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';

const source = readFileSync(new URL('../server/questions.ts', import.meta.url), 'utf8');
assert.match(source, /^export const QUESTIONS\s*=\s*\[/, 'Expected a QUESTIONS array export');
assert.match(source, /\]\s+as const;?\s*$/, 'Expected a readonly QUESTIONS array');
const expression = source.replace(/^export const QUESTIONS\s*=\s*/, '').replace(/\s+as const;?\s*$/, '');
const questions = runInNewContext('(' + expression + ')', Object.create(null), { timeout: 1000 });

test('quiz has exactly fifteen sequential numbered questions', () => {
  assert.equal(questions.length, 15);
  assert.deepEqual(Array.from(questions, q => q.number), Array.from({ length: 15 }, (_, i) => i + 1));
});

test('every question has three distinct nonempty options, one answer and an explanation', () => {
  for (const q of questions) {
    assert.equal(typeof q.question, 'string', 'Missing question #' + q.number);
    assert.ok(q.question.trim(), 'Empty question #' + q.number);
    assert.equal(typeof q.topic, 'string', 'Missing topic #' + q.number);
    assert.ok(q.topic.trim(), 'Empty topic #' + q.number);
    assert.ok(Array.isArray(q.options) && q.options.length === 3, 'Expected 3 options in #' + q.number);
    assert.ok(q.options.every(x => typeof x === 'string' && x.trim()), 'Empty option in #' + q.number);
    assert.equal(new Set(Array.from(q.options, x => x.trim())).size, 3, 'Repeated option in #' + q.number);
    assert.ok(Number.isInteger(q.answer) && q.answer >= 0 && q.answer < 3, 'Invalid answer in #' + q.number);
    assert.ok(typeof q.explanation === 'string' && q.explanation.trim(), 'Missing explanation in #' + q.number);
  }
});

test('each round gives players exactly fifteen seconds', () => {
  for (const q of questions) assert.equal(q.timeLimitSeconds, 15, 'Unexpected timer in #' + q.number);
});

test('every topic is assigned and no prompt is duplicated', () => {
  assert.equal(new Set(Array.from(questions, q => q.question.trim())).size, 15);
  assert.ok(new Set(Array.from(questions, q => q.topic.trim())).size >= 3);
});

test('all three answer positions occur in the question bank', () => {
  assert.deepEqual(Array.from(new Set(Array.from(questions, q => q.answer))).sort(), [0, 1, 2]);
});
