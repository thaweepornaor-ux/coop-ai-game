import test from "node:test";
import assert from "node:assert/strict";
import { assertExpectedState, effectivePhase, getLevel, makeSnapshot, planTransition, sanitizeAvatar, sanitizeName,
  type Answer, type Player, type Question, type Room } from "./game.ts";

const questions: Question[] = Array.from({ length: 15 }, (_, i) => ({
  number: i + 1, topic: "พื้นฐาน", question: `ข้อ ${i + 1}`, options: ["ก", "ข", "ค"], answer: i % 3, explanation: "เหตุผล",
}));
const players: Player[] = [
  { id: "a", name: "เอ", avatar: { hair: "short" }, createdAt: 1 },
  { id: "b", name: "บี", avatar: { hair: "long" }, createdAt: 2 },
];
const first: Room = { code: "ABC234", phase: "question", questionIndex: 0, roundId: 1, deadline: 16000 };
const firstAnswer: Answer = { playerId: "a", roundId: 1, questionIndex: 0, choice: 0, submittedAt: 2000 };

 test("before reveal neither the correct option nor another player's choice is public", () => {
  const result = makeSnapshot(first, players, [firstAnswer], { role: "player", playerId: "b" }, 3000, questions);
  assert.equal(result.correctAnswer, undefined);
  assert.equal(result.explanation, undefined);
  assert.equal(result.results, undefined);
  assert.equal(result.leaderboard, undefined);
  assert.equal(result.ownAnswer, null);
  assert.equal(result.players[0].score, 0);
  assert.equal("answer" in result.question!, false);
  assert.equal(result.players[0].answered, true);
});

 test("deadline locks answers but does not reveal or advance the question", () => {
  assert.equal(effectivePhase(first, 15999), "question");
  assert.equal(effectivePhase(first, 16000), "closed");
  const result = makeSnapshot(first, players, [firstAnswer], { role: "host" }, 16000, questions);
  assert.equal(result.room.phase, "closed");
  assert.equal(result.room.questionIndex, 0);
  assert.equal(result.correctAnswer, undefined);
  assert.throws(() => planTransition(first, "next", 16000));
});

 test("reveal separates correct, incorrect, and unanswered players", () => {
  const extra: Player = { id: "c", name: "ซี", avatar: {}, createdAt: 3 };
  const wrong: Answer = { ...firstAnswer, playerId: "b", choice: 1 };
  const result = makeSnapshot({ ...first, phase: "reveal" }, [...players, extra], [firstAnswer, wrong], { role: "host" }, 17000, questions);
  assert.deepEqual(result.results?.map(r => r.status), ["correct", "incorrect", "unanswered"]);
  assert.equal(result.correctAnswer, 0);
  assert.deepEqual(result.players.map(p => p.score), [1, 0, 0]);
});

 test("a new question shows scores from revealed questions only", () => {
  const currentCorrect: Answer = { ...firstAnswer, questionIndex: 1, choice: 1 };
  const result = makeSnapshot({ ...first, questionIndex: 1, deadline: 31000 }, players,
    [firstAnswer, currentCorrect], { role: "player", playerId: "a" }, 20000, questions);
  assert.equal(result.players[0].score, 1);
  assert.equal(result.ownAnswer?.choice, 1);
  assert.equal(result.correctAnswer, undefined);
});

 test("reset ignores all previous-round answers while retaining the roster", () => {
  const result = makeSnapshot({ ...first, phase: "lobby", questionIndex: -1, roundId: 2, deadline: null },
    players, [firstAnswer], { role: "player", playerId: "a" }, 18000, questions);
  assert.equal(result.players.length, 2);
  assert.deepEqual(result.players[0].avatar, players[0].avatar);
  assert.equal(result.players[0].score, 0);
  assert.equal(result.ownAnswer, null);
  assert.throws(() => assertExpectedState(result.room, 1, 0));
});

 test("final summary totals exactly 15 and uses equal ranks for tied scores", () => {
  const answers: Answer[] = questions.map((q, i) => ({ playerId: "a", roundId: 1, questionIndex: i,
    choice: i < 11 ? q.answer : (q.answer + 1) % 3, submittedAt: 2000 + i }));
  const result = makeSnapshot({ ...first, phase: "finished", questionIndex: 14, deadline: null }, players,
    answers, { role: "host" }, 250000, questions);
  assert.equal(result.leaderboard![0].score, 11);
  assert.equal(result.leaderboard![0].incorrectCount, 4);
  assert.equal(result.leaderboard![0].unansweredCount, 0);
  assert.equal(result.leaderboard![1].unansweredCount, 15);
  assert.equal(result.leaderboard![0].level, "นักรู้ทัน AI");
  const tied = makeSnapshot({ ...first, phase: "finished", questionIndex: 14 }, players, [], { role: "host" }, 250000, questions);
  assert.deepEqual(tied.leaderboard!.map(p => p.rank), [1, 1]);
});

 test("start, manual next, and final finish obey the host progression", () => {
  const lobby: Room = { ...first, phase: "lobby", questionIndex: -1, deadline: null };
  assert.deepEqual(planTransition(lobby, "start", 1000), {
    phase: "question", questionIndex: 0, incrementRound: false, startTimer: true,
  });
  const last: Room = { ...first, phase: "reveal", questionIndex: 14 };
  assert.equal(planTransition(last, "next", 250000).phase, "finished");
  assert.throws(() => planTransition({ ...last, questionIndex: 13 }, "finish", 200000));
  assert.equal(planTransition(first, "reset", 2000).incrementRound, true);
});

 test("level boundaries and text-only profile validation", () => {
  assert.deepEqual([0, 5, 6, 10, 11, 15].map(getLevel), [
    "นักสำรวจ AI", "นักสำรวจ AI", "นักต่อยอด AI", "นักต่อยอด AI", "นักรู้ทัน AI", "นักรู้ทัน AI",
  ]);
  assert.equal(sanitizeName("  <นก>\u0000  "), "นก");
  assert.equal(Array.from(sanitizeName("ก".repeat(30))).length, 24);
  assert.throws(() => sanitizeAvatar({ hair: "https://example.invalid/hair.svg" }));
  assert.throws(() => sanitizeAvatar({ hat: { src: "html" } }));
});
