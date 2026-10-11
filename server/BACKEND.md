# Game backend contract

This source targets the selected Vinext / Cloudflare Worker starter with a D1 binding named `DB`. Apply `drizzle/0000_game.sql` to that database before using the game. `server/questions.ts` is server-only and must not be imported by a browser component or returned as a complete question bank.

## Requests

The endpoint is `/api/game`. Protected requests carry `Authorization: Bearer <token>`; tokens are never passed in a URL. A token is returned only once by create/join and should be saved locally by the client for refresh recovery.

| Request | Body or parameters | Result |
| --- | --- | --- |
| POST create | `{ "action": "create" }` | `{ roomCode, token, role: "host", snapshot }` |
| POST join | `{ action: "join", room, name, avatar }` | `{ roomCode, token, role: "player", playerId, snapshot }` |
| GET state | `?room=ABC234`, plus bearer token | Public snapshot for that caller |
| POST answer | `{ action: "answer", room, roundId, questionIndex, choice }` | Snapshot; choice is the zero-based option index |
| POST control | `{ action: "start"|"reveal"|"next"|"finish"|"reset", room, roundId, questionIndex }` | Snapshot; host token required |

`roomCode` is also accepted as a body/query alias for `room`. Every control or answer must carry the latest numeric round/index from the snapshot. An outdated client receives HTTP 409. Error responses are `{ error: readableThaiMessage, code, snapshot? }`. Do not blindly retry an old answer against a new round.

Profiles use a text name of at most 24 Unicode code points. `avatar` is a flat object of local component selections: short string keys with string/number/boolean values. Remote image URLs, HTML, and nested objects are rejected.

## Snapshot

- `serverNow` and `room.deadline` use database-clock epoch milliseconds. The UI estimates its clock offset from `serverNow`, displays the countdown, and stops enabling answers at the deadline; the database is authoritative even when a phone clock is wrong.
- `room` contains `code`, `phase`, `questionIndex` (zero-based; -1 in the lobby), `roundId`, and `deadline`.
- `caller` identifies host/player and the current player's ID.
- `question` contains only number/topic/question/options. It is absent in lobby and final summary.
- `players` contains ID/name/avatar/score/level and the boolean `answered`. Current-question choices, correctness, and points do not appear before reveal.
- `ownAnswer` is the player's own immutable choice/submission time or null.
- `results`, `correctAnswer`, `explanation`, and `leaderboard` appear only after reveal or finish.
- Reveal result rows distinguish `correct`, `incorrect`, and `unanswered`; final leaderboard rows include `rank`, `correctCount`, `incorrectCount`, `unansweredCount`, and `level`.

Correct answers earn exactly one point. Equal scores share a rank; answer speed does not affect points or tie ranking. Levels describe this baseline quiz only: 0–5 นักสำรวจ AI, 6–10 นักต่อยอด AI, 11–15 นักรู้ทัน AI. They do not certify practical AI skill.

## State and race guarantees in the source

`lobby → question → closed → reveal → question … → finished`. A host may reveal early to end a question; timeout itself only locks answers. Starting and advancing each question establishes a new database-clock deadline exactly 15,000 ms later. There is no automatic next question.

An answer INSERT includes room/token/round/index/phase/deadline predicates in the same SQL statement. A primary key makes the answer immutable. Host state changes use conditional UPDATE predicates. Reset increments the round in a transaction, removes obsolete answers, and returns the same roster to the lobby; answers carrying an earlier round can never land in the new round. Room/player tokens are 256-bit random secrets; only SHA-256 hashes are stored.

Poll state approximately once a second while active; use a slower interval in the lobby/final page if appropriate. Resume an existing session using the saved token. Clearing browser storage loses that session. Cross-device host PIN recovery is not implemented; no weak PIN fallback is accepted.

## Validation status and deployment needs

Pure rule tests were written in `server/game.test.ts` for hidden answers, exact timeout boundary, manual progression, reset isolation, score visibility, final counts/ties, and profile validation. **They have not been run:** local executable and Node execution are blocked by the machine policy reported to the parent task. No deployment or working online link has been verified by this backend subtask.

Before public use: apply the migration, run the tests/build in an approved runtime, and exercise D1 through two independent browsers including simultaneous answer/reveal/reset requests and refresh recovery. This source has no room expiry/garbage collection, public creation/join rate limiting, load test, or cross-device host recovery. Public room joining is intentional; host controls still require the private token. The UI is responsible for confirmation before reset and for responsive desktop/mobile presentation.
