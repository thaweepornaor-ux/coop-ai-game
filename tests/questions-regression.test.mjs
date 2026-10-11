// Regression checks for the cooperative AI classroom quiz.
// Run with: node --test tests/questions-regression.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';

const source = readFileSync(new URL('../server/questions.ts', import.meta.url), 'utf8');
const expression = source.replace(/^export const QUESTIONS\s*=\s*/, '').replace(/\s+as const;?\s*$/, '');
const questions = runInNewContext('(' + expression + ')', Object.create(null), { timeout: 1000 });

test('quiz contains exactly 15 numbered questions in order', () => {
  assert.equal(questions.length, 15);
  assert.deepEqual(Array.from(questions, q => q.number), Array.from({length: 15}, (_, i) => i + 1));
});

test('every question has three usable answer options and one valid answer', () => {
  for (const q of questions) {
    assert.ok(typeof q.question === 'string' && q.question.trim(), 'Missing question #' + q.number);
    assert.ok(typeof q.topic === 'string' && q.topic.trim(), 'Missing topic #' + q.number);
    assert.equal(q.options.length, 3, 'Expected 3 options in #' + q.number);
    assert.equal(new Set(Array.from(q.options, x => x.trim())).size, 3, 'Repeated option in #' + q.number);
    assert.ok(q.options.every(x => typeof x === 'string' && x.trim()), 'Empty option in #' + q.number);
    assert.ok(Number.isInteger(q.answer) && q.answer >= 0 && q.answer < 3, 'Invalid answer in #' + q.number);
    assert.ok(typeof q.explanation === 'string' && q.explanation.trim(), 'Missing explanation in #' + q.number);
  }
});

test('all rounds have a positive finite time limit', () => {
  for (const q of questions) assert.ok(Number.isFinite(q.timeLimitSeconds) && q.timeLimitSeconds > 0, 'Invalid timer in #' + q.number);
});
