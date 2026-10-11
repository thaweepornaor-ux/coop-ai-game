/** Pure game rules. This module does not depend on Cloudflare or browser APIs. */
export const QUESTION_SECONDS = 15;
export const QUESTION_COUNT = 15;
export const GAME_LEVELS = ["นักสำรวจ AI", "นักต่อยอด AI", "นักรู้ทัน AI"] as const;

export type Phase = "lobby" | "question" | "closed" | "reveal" | "finished";
export type ControlAction = "start" | "reveal" | "next" | "finish" | "reset";
export type Avatar = Record<string, string | number | boolean>;
export interface Question {
  number: number;
  topic: string;
  question: string;
  options: readonly string[];
  answer: number;
  explanation: string;
}
export interface Room {
  code: string;
  phase: Phase;
  questionIndex: number;
  roundId: number;
  deadline: number | null;
}
export interface Player {
  id: string;
  name: string;
  avatar: Avatar;
  createdAt: number;
}
export interface Answer {
  playerId: string;
  roundId: number;
  questionIndex: number;
  choice: number;
  submittedAt: number;
}
export type Caller = { role: "host"; playerId?: never } | { role: "player"; playerId: string };
export class GameError extends Error {
  constructor(public readonly code: string, message: string, public readonly status = 400) {
    super(message);
    this.name = "GameError";
  }
}

/** Restrict names to displayed text, including Thai. Count Unicode code points. */
export function sanitizeName(value: unknown): string {
  if (typeof value !== "string") throw new GameError("INVALID_NAME", "กรุณาตั้งชื่อผู้เล่น");
  const name = Array.from(value.normalize("NFKC")
    .replace(/[<>\u0000-\u001f\u007f-\u009f\u200b-\u200f\u202a-\u202e\u2066-\u2069]/g, "")
    .replace(/\s+/g, " ").trim()).slice(0, 24).join("");
  if (!name) throw new GameError("INVALID_NAME", "กรุณาตั้งชื่อผู้เล่น");
  return name;
}

/** Avatars are local component selections, never remote URLs or HTML. */
export function sanitizeAvatar(value: unknown): Avatar {
  if (value === undefined || value === null) return {};
  if (typeof value !== "object" || Array.isArray(value)) {
    throw new GameError("INVALID_AVATAR", "ข้อมูลตัวละครไม่ถูกต้อง");
  }
  const entries = Object.entries(value);
  if (entries.length > 24) throw new GameError("INVALID_AVATAR", "ข้อมูลตัวละครมากเกินไป");
  const avatar: Avatar = {};
  for (const [key, selection] of entries) {
    if (!/^[a-zA-Z][a-zA-Z0-9_]{0,31}$/.test(key) || ["constructor", "prototype", "__proto__"].includes(key)) {
      throw new GameError("INVALID_AVATAR", "ข้อมูลตัวละครไม่ถูกต้อง");
    }
    if (typeof selection === "string") {
      if (selection.length > 64 || /[<>\u0000-\u001f\u007f]|(?:https?:|data:|javascript:)/i.test(selection)) {
        throw new GameError("INVALID_AVATAR", "เลือกตัวละครจากรายการในเกม");
      }
      avatar[key] = selection;
    } else if (typeof selection === "number" && Number.isFinite(selection) && Math.abs(selection) <= 10000) {
      avatar[key] = selection;
    } else if (typeof selection === "boolean") {
      avatar[key] = selection;
    } else {
      throw new GameError("INVALID_AVATAR", "ข้อมูลตัวละครไม่ถูกต้อง");
    }
  }
  if (JSON.stringify(avatar).length > 2048) throw new GameError("INVALID_AVATAR", "ข้อมูลตัวละครมากเกินไป");
  return avatar;
}

export function normalizeRoomCode(value: unknown): string {
  if (typeof value !== "string") throw new GameError("INVALID_ROOM", "กรุณาระบุรหัสห้อง");
  const code = value.trim().toUpperCase();
  if (!/^[A-Z0-9]{6}$/.test(code)) throw new GameError("INVALID_ROOM", "รหัสห้องต้องมี 6 ตัว");
  return code;
}

export function assertExpectedState(room: Room, roundId: unknown, questionIndex: unknown): void {
  if (typeof roundId !== "number" || typeof questionIndex !== "number"
    || !Number.isSafeInteger(roundId) || !Number.isSafeInteger(questionIndex)) {
    throw new GameError("MISSING_STATE", "กรุณาโหลดสถานะห้องล่าสุดก่อนทำรายการ");
  }
  if (roundId !== room.roundId || questionIndex !== room.questionIndex) {
    throw new GameError("STALE_STATE", "ห้องเปลี่ยนข้อหรือเริ่มรอบใหม่แล้ว กรุณาลองจากหน้าปัจจุบัน", 409);
  }
}

export function effectivePhase(room: Room, now: number): Phase {
  return room.phase === "question" && (room.deadline === null || now >= room.deadline) ? "closed" : room.phase;
}

export function getLevel(score: number): typeof GAME_LEVELS[number] {
  return score <= 5 ? GAME_LEVELS[0] : score <= 10 ? GAME_LEVELS[1] : GAME_LEVELS[2];
}

export interface Transition {
  phase: Phase;
  questionIndex: number;
  incrementRound: boolean;
  startTimer: boolean;
}

/** The caller's expected state and host authorization must also be checked by storage. */
export function planTransition(room: Room, action: ControlAction, now: number): Transition {
  const phase = effectivePhase(room, now);
  if (action === "reset") return { phase: "lobby", questionIndex: -1, incrementRound: true, startTimer: false };
  if (action === "start" && phase === "lobby") {
    return { phase: "question", questionIndex: 0, incrementRound: false, startTimer: true };
  }
  if (action === "reveal" && (phase === "question" || phase === "closed")) {
    return { phase: "reveal", questionIndex: room.questionIndex, incrementRound: false, startTimer: false };
  }
  if (action === "next" && phase === "reveal") {
    const last = room.questionIndex >= QUESTION_COUNT - 1;
    return { phase: last ? "finished" : "question", questionIndex: last ? room.questionIndex : room.questionIndex + 1,
      incrementRound: false, startTimer: !last };
  }
  if (action === "finish" && phase === "reveal" && room.questionIndex === QUESTION_COUNT - 1) {
    return { phase: "finished", questionIndex: room.questionIndex, incrementRound: false, startTimer: false };
  }
  throw new GameError("INVALID_PHASE", "ยังทำรายการนี้ไม่ได้ในช่วงปัจจุบัน", 409);
}

export function assertQuestions(questions: readonly Question[]): void {
  if (questions.length !== QUESTION_COUNT || questions.some((q, i) => q.number !== i + 1 || q.options.length !== 3
    || !Number.isInteger(q.answer) || q.answer < 0 || q.answer > 2)) {
    throw new GameError("QUESTION_CONFIGURATION", "ชุดคำถามยังไม่พร้อมใช้งาน", 503);
  }
}

/** Build the only public representation. Private answers are excluded before reveal. */
export function makeSnapshot(room: Room, players: readonly Player[], answers: readonly Answer[], caller: Caller,
  now: number, questions: readonly Question[]) {
  const phase = effectivePhase(room, now);
  const revealed = phase === "reveal" || phase === "finished";
  const visibleCount = phase === "finished" ? QUESTION_COUNT : phase === "reveal" ? room.questionIndex + 1 : Math.max(0, room.questionIndex);
  const currentAnswers = answers.filter(a => a.roundId === room.roundId);
  const scores = new Map<string, number>();
  const submittedCounts = new Map<string, number>();
  const thisQuestion = new Map<string, Answer>();
  for (const answer of currentAnswers) {
    if (answer.questionIndex === room.questionIndex) thisQuestion.set(answer.playerId, answer);
    if (answer.questionIndex < visibleCount) {
      submittedCounts.set(answer.playerId, (submittedCounts.get(answer.playerId) ?? 0) + 1);
      if (questions[answer.questionIndex]?.answer === answer.choice) {
        scores.set(answer.playerId, (scores.get(answer.playerId) ?? 0) + 1);
      }
    }
  }
  const scoreFor = (playerId: string) => scores.get(playerId) ?? 0;
  const answerFor = (playerId: string) => thisQuestion.get(playerId);
  const roster = players.map(p => ({ id: p.id, name: p.name, avatar: p.avatar, score: scoreFor(p.id),
    level: getLevel(scoreFor(p.id)), answered: Boolean(answerFor(p.id)) }));
  const question = questions[room.questionIndex];
  const ownAnswer = caller.role === "player" ? answerFor(caller.playerId) : undefined;
  const resultRows = revealed && question ? roster.map(p => {
    const answer = answerFor(p.id);
    const correct = answer ? answer.choice === question.answer : null;
    return { playerId: p.id, name: p.name, avatar: p.avatar, choice: answer?.choice ?? null, correct,
      status: !answer ? "unanswered" as const : correct ? "correct" as const : "incorrect" as const, score: p.score };
  }) : undefined;
  const creationTimes = new Map(players.map(p => [p.id, p.createdAt]));
  const ordered = [...roster].sort((a, b) => b.score - a.score
    || (creationTimes.get(a.id) ?? 0) - (creationTimes.get(b.id) ?? 0)
    || a.id.localeCompare(b.id));
  let lastScore = -1;
  let rank = 0;
  const leaderboard = ordered.map((p, index) => {
    if (p.score !== lastScore) rank = index + 1;
    lastScore = p.score;
    const submitted = submittedCounts.get(p.id) ?? 0;
    return { ...p, rank, correctCount: p.score, incorrectCount: submitted - p.score,
      unansweredCount: visibleCount - submitted };
  });
  return {
    serverNow: now,
    room: { code: room.code, phase, questionIndex: room.questionIndex, roundId: room.roundId, deadline: room.deadline },
    caller,
    question: question && phase !== "lobby" && phase !== "finished" ? {
      number: question.number, topic: question.topic, question: question.question, options: question.options,
    } : undefined,
    players: roster,
    ownAnswer: ownAnswer ? { choice: ownAnswer.choice, submittedAt: ownAnswer.submittedAt } : null,
    results: resultRows,
    correctAnswer: revealed && question ? question.answer : undefined,
    explanation: revealed && question ? question.explanation : undefined,
    leaderboard: revealed ? leaderboard : undefined,
    totalQuestions: QUESTION_COUNT,
    timeLimitSeconds: QUESTION_SECONDS,
  };
}
