# Preview staging — cooperative AI game

This branch isolates a staging candidate from `main` and the existing published Site. It is **not** a public deployment and must not be presented as one.

## Evidence at branch point
- Browser proof #26: 12/12 scenarios pass in CI Chromium and WebKit; both run the complete 15-question room flow.
- Runtime proof #43: validator, asset access, game rules, integration, avatar recovery pass.
- Real iPhone/Android hardware and final visual acceptance **not yet verified**.
- The parallel `codex/avatar-preview-quality-20261011` branch contains newer avatar edits that have **not** been imported or accepted into this candidate.

## Before publishing a staging URL
1. Identify a staging deployment destination controlled by the repo owner. **Do not overwrite the current ChatGPT Site or main branch.**
2. Create a **separate staging Cloudflare Worker and D1 database**. The included `wrangler.ci.jsonc` is for local disposable D1 only; its all-zero database ID must never be treated as a real resource.
3. Obtain the actual staging D1 database ID and Cloudflare authorization from the owner through a secure channel. Do not commit credentials, learner data, or production identifiers to the repository.
4. Configure the Worker with the `DB` binding and migrations from `drizzle/` using an explicit staging-only configuration. The CI command shown below works **locally only**.
5. Run staging migrations against the *staging* database, deploy the matching build and test a public HTTPS URL with an instructor and learner on **separate devices**.
6. Verify room creation, join-by-code, avatar choices, all 15 questions and server timeouts, scoring, leaderboard, reset, and navigation on desktop and phone. Record screenshots for visual signoff.
7. Keep the draft PR unmerged until deployment smoke, asset quality review, privacy/data retention and rollback checks pass.

## Existing reproducible local gate
```sh
corepack pnpm install --frozen-lockfile
corepack pnpm exec wrangler d1 migrations apply DB --local --config wrangler.ci.jsonc --persist-to .wrangler/ci-state
corepack pnpm exec vite build --config vite.ci.config.ts
```

Do **not** run `wrangler deploy` against the CI config or production without an approved staging target, real DB binding and correct deployed assets.

## Rollback
Staging should be independently removable without affecting the existing published Site or production database. Retain prior staging release information and verify a rollback mechanism before exposing users.

## Blockers
There is currently no verified staging deployment destination, authorized Cloudflare deployment credential, or distinct remote staging D1 database in this repo; no deploy has been performed.
