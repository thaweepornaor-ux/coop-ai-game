import { normalizeWardrobe } from "../../../shared/avatar-registry";
import { env } from "cloudflare:workers";
import {
  assertExpectedState, assertQuestions, GameError, makeSnapshot, normalizeRoomCode, planTransition,
  QUESTION_SECONDS, sanitizeAvatar, sanitizeName,
  type Answer, type Caller, type ControlAction, type Player, type Room,
} from "../../../server/game";
import { QUESTIONS } from "../../../server/questions";

 type Value = string | number | null;
interface QueryResult<T = Record<string, unknown>> {
  results: T[];
  success: boolean;
  meta: { changes?: number };
}
interface Statement {
  bind(...values: Value[]): Statement;
  run(): Promise<QueryResult>;
}
interface Database {
  prepare(sql: string): Statement;
  batch(statements: Statement[]): Promise<QueryResult[]>;
}
interface RoomRow {
  code: string;
  host_token_hash: string;
  phase: Room["phase"];
  question_index: number;
  round_id: number;
  deadline: number | null;
  server_now: number;
}
interface PlayerRow {
  id: string;
  token_hash: string;
  name: string;
  avatar_json: string;
  created_at: number;
}
interface AnswerRow {
  player_id: string;
  round_id: number;
  question_index: number;
  choice: number;
  answered_at: number;
}
interface StoredState {
  row: RoomRow;
  room: Room;
  playerRows: PlayerRow[];
  players: Player[];
  answers: Answer[];
}

// SQLite's execution-time clock, not a timestamp supplied by the phone or an
// earlier Worker read. This expression is supported by SQLite without extensions.
const SQL_NOW = "CAST((julianday('now') - 2440587.5) * 86400000 AS INTEGER)";
const CONTROLS = ["start", "reveal", "next", "finish", "reset"] as const;
const JSON_HEADERS = {
  "Content-Type": "application/json; charset=utf-8",
  "Cache-Control": "no-store, max-age=0",
  "X-Content-Type-Options": "nosniff",
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: JSON_HEADERS });
}

function database(): Database {
  const db = (env as unknown as { DB?: Database }).DB;
  if (!db || typeof db.prepare !== "function") {
    throw new GameError("DATABASE_UNAVAILABLE", "ระบบห้องเกมยังไม่เชื่อมฐานข้อมูล", 503);
  }
  assertQuestions(QUESTIONS);
  return db;
}

function randomToken(): string {
  return Array.from(crypto.getRandomValues(new Uint8Array(32)), x => x.toString(16).padStart(2, "0")).join("");
}

function randomRoomCode(): string {
  const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  return Array.from(crypto.getRandomValues(new Uint8Array(6)), n => alphabet[n % alphabet.length]).join("");
}

async function hashToken(token: string): Promise<string> {
  const bytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(token));
  return Array.from(new Uint8Array(bytes), x => x.toString(16).padStart(2, "0")).join("");
}

async function requestTokenHash(request: Request): Promise<string> {
  const match = /^Bearer ([a-f0-9]{64})$/i.exec(request.headers.get("Authorization") ?? "");
  if (!match) throw new GameError("UNAUTHORIZED", "กรุณาเข้าห้องเกมจากหน้าผู้สอนหรือผู้เล่น", 401);
  return hashToken(match[1].toLowerCase());
}

async function readBody(request: Request): Promise<Record<string, unknown>> {
  const length = Number(request.headers.get("Content-Length") ?? 0);
  if (length > 16384) throw new GameError("BODY_TOO_LARGE", "ข้อมูลคำขอมากเกินไป", 413);
  const text = await request.text();
  if (text.length > 16384) throw new GameError("BODY_TOO_LARGE", "ข้อมูลคำขอมากเกินไป", 413);
  let body: unknown;
  try { body = JSON.parse(text); } catch { throw new GameError("INVALID_JSON", "ข้อมูลคำขอไม่ถูกต้อง"); }
  if (!body || typeof body !== "object" || Array.isArray(body)) throw new GameError("INVALID_JSON", "ข้อมูลคำขอไม่ถูกต้อง");
  return body as Record<string, unknown>;
}

/** All three SELECTs execute in one D1 batch, so reset cannot mix two rounds. */
async function readState(db: Database, code: string): Promise<StoredState> {
  const queries = await db.batch([
    db.prepare(`SELECT code, host_token_hash, phase, question_index, round_id, deadline, ${SQL_NOW} AS server_now
      FROM rooms WHERE code = ? AND created_at > ${SQL_NOW} - 86400000`).bind(code),
    db.prepare("SELECT id, token_hash, name, avatar_json, created_at FROM players WHERE room_code = ? ORDER BY created_at, id").bind(code),
    db.prepare(`SELECT a.player_id, a.round_id, a.question_index, a.choice, a.answered_at
      FROM answers a JOIN rooms r ON r.code = a.room_code AND r.round_id = a.round_id
      WHERE r.code = ? ORDER BY a.question_index, a.player_id`).bind(code),
  ]);
  const row = queries[0].results[0] as unknown as RoomRow | undefined;
  if (!row) throw new GameError("ROOM_NOT_FOUND", "QR Code นี้หมดอายุแล้ว กรุณาขอให้ผู้สอนแสดง QR Code ใหม่ครับ", 404);
  const playerRows = queries[1].results as unknown as PlayerRow[];
  const answerRows = queries[2].results as unknown as AnswerRow[];
  return {
    row,
    room: { code: row.code, phase: row.phase, questionIndex: row.question_index, roundId: row.round_id, deadline: row.deadline },
    playerRows,
    players: playerRows.map(p => {
      let avatar = {};
      try { avatar = normalizeWardrobe(sanitizeAvatar(JSON.parse(p.avatar_json))); } catch { /* Keep malformed data out of rendering. */ }
      return { id: p.id, name: sanitizeName(p.name), avatar, createdAt: p.created_at };
    }),
    answers: answerRows.map(a => ({ playerId: a.player_id, roundId: a.round_id, questionIndex: a.question_index,
      choice: a.choice, submittedAt: a.answered_at })),
  };
}

function identifyCaller(state: StoredState, tokenHash: string): Caller {
  if (state.row.host_token_hash === tokenHash) return { role: "host" };
  const player = state.playerRows.find(p => p.token_hash === tokenHash);
  if (!player) throw new GameError("UNAUTHORIZED", "สิทธิ์เข้าห้องนี้ไม่ถูกต้อง กรุณาเข้าห้องใหม่", 401);
  return { role: "player", playerId: player.id };
}

function snapshot(state: StoredState, caller: Caller) {
  return makeSnapshot(state.room, state.players, state.answers, caller, state.row.server_now, QUESTIONS);
}

async function authenticatedState(db: Database, code: string, tokenHash: string) {
  let state = await readState(db, code);
  let caller = identifyCaller(state, tokenHash);
  // Expiration only locks the current question. It never reveals or advances it.
  if (state.room.phase === "question" && state.room.deadline !== null && state.room.deadline <= state.row.server_now) {
    await db.prepare(`UPDATE rooms SET phase = 'closed', updated_at = ${SQL_NOW}
      WHERE code = ? AND round_id = ? AND question_index = ? AND phase = 'question' AND deadline <= ${SQL_NOW}`)
      .bind(code, state.room.roundId, state.room.questionIndex).run();
    state = await readState(db, code);
    caller = identifyCaller(state, tokenHash);
  }
  return { state, caller };
}

async function createRoom(db: Database): Promise<Response> {
  const token = randomToken();
  const tokenHash = await hashToken(token);
  for (let attempt = 0; attempt < 8; attempt++) {
    const code = randomRoomCode();
    const result = await db.prepare(`INSERT OR IGNORE INTO rooms
      (code, host_token_hash, phase, question_index, round_id, deadline, created_at, updated_at)
      VALUES (?, ?, 'lobby', -1, 1, NULL, ${SQL_NOW}, ${SQL_NOW})`).bind(code, tokenHash).run();
    if ((result.meta.changes ?? 0) > 0) {
      const state = await readState(db, code);
      return json({ roomCode: code, token, role: "host", snapshot: snapshot(state, { role: "host" }) }, 201);
    }
  }
  throw new GameError("CREATE_ROOM_FAILED", "สร้างห้องไม่สำเร็จ กรุณาลองอีกครั้ง", 503);
}

async function limit(db: Database, request: Request, action: string) {
 const ip = request.headers.get("CF-Connecting-IP") ?? "unknown";
 const identity = action === "read" ? (request.headers.get("Authorization") ?? ip) : ip;
 const key = await hashToken(identity + ":" + action + ":" + Math.floor(Date.now()/60000));
 const budget = action === "create" ? 8 : action === "read" ? 120 : 300;
 const results = await db.batch([
  db.prepare(`INSERT INTO rate_limits (key, count, expires_at) VALUES (?,1,${SQL_NOW}+120000)
   ON CONFLICT(key) DO UPDATE SET count=count+1 RETURNING count`).bind(key),
  db.prepare(`DELETE FROM rate_limits WHERE expires_at < ${SQL_NOW}`),
  db.prepare(`DELETE FROM rooms WHERE created_at < ${SQL_NOW}-86400000`),
 ]);
 if (Number(results[0].results[0]?.count) > budget) throw new GameError("RATE_LIMIT", "ทำรายการบ่อยเกินไป กรุณารอสักครู่", 429);
}

async function joinRoom(db: Database, body: Record<string, unknown>): Promise<Response> {
  const code = normalizeRoomCode(body.room ?? body.roomCode);
  const name = sanitizeName(body.name);
  let avatar;
  try { avatar = normalizeWardrobe(sanitizeAvatar(body.avatar), true); } catch(error) { throw new GameError("INVALID_AVATAR", error instanceof Error ? error.message : "ข้อมูลตัวละครไม่ถูกต้อง"); }
  const id = crypto.randomUUID();
  const token = randomToken();
  const tokenHash = await hashToken(token);
  const inserted = await db.prepare(`INSERT INTO players (id, room_code, token_hash, name, avatar_json, created_at)
    SELECT ?, code, ?, ?, ?, ${SQL_NOW} FROM rooms WHERE code = ? AND created_at > ${SQL_NOW}-86400000 AND (SELECT COUNT(*) FROM players WHERE room_code = ?) < 300`)
    .bind(id, tokenHash, name, JSON.stringify(avatar), code, code).run();
  if ((inserted.meta.changes ?? 0) !== 1) throw new GameError("ROOM_NOT_FOUND", "QR Code นี้หมดอายุแล้ว กรุณาขอให้ผู้สอนแสดง QR Code ใหม่ครับ", 404);
  const { state, caller } = await authenticatedState(db, code, tokenHash);
  return json({ roomCode: code, token, role: "player", playerId: id, snapshot: snapshot(state, caller) }, 201);
}

async function submitAnswer(db: Database, code: string, tokenHash: string, state: StoredState, caller: Caller,
  body: Record<string, unknown>): Promise<Response> {
  if (caller.role !== "player") throw new GameError("PLAYER_ONLY", "เฉพาะผู้เล่นเท่านั้นที่ส่งคำตอบได้", 403);
  assertExpectedState(state.room, body.roundId, body.questionIndex);
  if (typeof body.choice !== "number" || !Number.isInteger(body.choice) || body.choice < 0 || body.choice > 2) {
    throw new GameError("INVALID_CHOICE", "กรุณาเลือกคำตอบหนึ่งข้อ");
  }
  // The INSERT ... SELECT is one atomic statement. Every acceptance condition,
  // including the execution-time deadline and token ownership, is inside SQL.
  const result = await db.prepare(`INSERT INTO answers
    (room_code, round_id, question_index, player_id, choice, answered_at)
    SELECT r.code, r.round_id, r.question_index, p.id, ?, ${SQL_NOW}
    FROM rooms r JOIN players p ON p.room_code = r.code
    WHERE r.code = ? AND p.id = ? AND p.token_hash = ?
      AND r.round_id = ? AND r.question_index = ? AND r.phase = 'question'
      AND r.deadline > ${SQL_NOW}
    ON CONFLICT(room_code, round_id, question_index, player_id) DO NOTHING`)
    .bind(body.choice as number, code, caller.playerId, tokenHash, body.roundId as number, body.questionIndex as number).run();
  const fresh = await authenticatedState(db, code, tokenHash);
  if ((result.meta.changes ?? 0) !== 1) {
    const old = fresh.state.answers.find(a => a.playerId === caller.playerId
      && a.roundId === body.roundId && a.questionIndex === body.questionIndex);
    const code = old ? "ALREADY_ANSWERED" : "ANSWER_WINDOW_CLOSED";
    return json({ error: old ? "ส่งคำตอบข้อนี้แล้ว เปลี่ยนคำตอบไม่ได้ครับ" : "หมดเวลาหรือห้องเปลี่ยนข้อแล้วครับ",
      code, snapshot: snapshot(fresh.state, fresh.caller) }, 409);
  }
  return json(snapshot(fresh.state, fresh.caller));
}

async function controlRoom(db: Database, code: string, tokenHash: string, state: StoredState, caller: Caller,
  action: ControlAction, body: Record<string, unknown>): Promise<Response> {
  if (caller.role !== "host") throw new GameError("HOST_ONLY", "ผู้สอนเท่านั้นที่ควบคุมเกมได้", 403);
  assertExpectedState(state.room, body.roundId, body.questionIndex);
  const plan = planTransition(state.room, action, state.row.server_now);
  const update = db.prepare(`UPDATE rooms SET phase = ?, question_index = ?, round_id = round_id + ?,
    deadline = ${plan.startTimer ? `${SQL_NOW} + ${QUESTION_SECONDS * 1000}` : "NULL"}, updated_at = ${SQL_NOW}
    WHERE code = ? AND host_token_hash = ? AND round_id = ? AND question_index = ? AND phase = ?`)
    .bind(plan.phase, plan.questionIndex, plan.incrementRound ? 1 : 0, code, tokenHash,
      state.room.roundId, state.room.questionIndex, state.room.phase);
  let changes = 0;
  if (action === "reset") {
    const results = await db.batch([
      update,
      // Never delete active-round rows if another reset won the race. A failed
      // conditional UPDATE may only remove obsolete rows from an earlier round.
      db.prepare(`DELETE FROM answers WHERE room_code = ?
        AND round_id < (SELECT round_id FROM rooms WHERE code = ?)`)
        .bind(code, code),
    ]);
    changes = results[0].meta.changes ?? 0;
  } else {
    changes = (await update.run()).meta.changes ?? 0;
  }
  const fresh = await authenticatedState(db, code, tokenHash);
  if (changes !== 1) {
    return json({ error: "สถานะห้องเปลี่ยนแล้ว กรุณาลองจากหน้าปัจจุบัน", code: "STALE_STATE",
      snapshot: snapshot(fresh.state, fresh.caller) }, 409);
  }
  return json(snapshot(fresh.state, fresh.caller));
}

function failure(error: unknown): Response {
  if (error instanceof GameError) return json({ error: error.message, code: error.code }, error.status);
  // Do not include SQL, bindings, tokens, or database diagnostics in the response.
  console.error("Game API operation failed");
  return json({ error: "ระบบห้องเกมยังไม่พร้อม กรุณาลองอีกครั้ง", code: "SERVER_UNAVAILABLE" }, 503);
}

export async function GET(request: Request): Promise<Response> {
  try {
    const url = new URL(request.url);
    const code = normalizeRoomCode(url.searchParams.get("room") ?? url.searchParams.get("roomCode"));
    const tokenHash = await requestTokenHash(request);
    const db = database();
    await limit(db, request, "read");
    const { state, caller } = await authenticatedState(db, code, tokenHash);
    return json(snapshot(state, caller));
  } catch (error) { return failure(error); }
}

export async function POST(request: Request): Promise<Response> {
  try {
    const body = await readBody(request);
    const db = database();
    if (body.action === "create" || body.action === "join") await limit(db, request, String(body.action));
    if (body.action === "create") return await createRoom(db);
    if (body.action === "join") return await joinRoom(db, body);
    if (body.action !== "answer" && !CONTROLS.includes(body.action as ControlAction)) {
      throw new GameError("INVALID_ACTION", "ไม่พบรายการที่ขอ");
    }
    const code = normalizeRoomCode(body.room ?? body.roomCode);
    const tokenHash = await requestTokenHash(request);
    const { state, caller } = await authenticatedState(db, code, tokenHash);
    if (body.action === "answer") return await submitAnswer(db, code, tokenHash, state, caller, body);
    return await controlRoom(db, code, tokenHash, state, caller, body.action as ControlAction, body);
  } catch (error) { return failure(error); }
}
