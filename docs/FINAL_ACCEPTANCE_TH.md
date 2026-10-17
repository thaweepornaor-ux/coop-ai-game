# Cooperative AI Game — on-site release acceptance

**Candidate:** review the current `main` SHA in GitHub before testing. This checklist never authorizes deployment.

## Step A — pre-deployment safety
1. Record the existing staging URL, currently served release SHA/version if visible, and its operational owner.
2. Obtain **explicit approval** to replace the staging version. A GitHub merge is not deployment approval.
3. Confirm an actual rollback path in Cloudflare for this project and the existing D1 database backup/restore procedure with the deployment owner; do not infer it from `wrangler.ci.jsonc`.
4. Keep any existing classroom rooms, scores, and production database untouched. No reset, migration, or fake test data against hosted staging.
5. Reconfirm the teaching rule: server currently uses **8 seconds per question after narration**, across 15 questions. If 15 seconds is required, do not deploy until the rule is resolved and retested.

## Step B — automated proof (disposable preview)
- [ ] Same candidate SHA: Game Smoke all green, 0 failed.
- [ ] Same candidate SHA: Chromium/WebKit Browser Proof 14/14, 0 skipped.
- [ ] Inspect current artifact `browser-proof/report.json` and selected 1920×1080/390px screenshots; check QR, 25 simulated tiles and 400 SVG character variants.
- [ ] All CSS arm, cloth, fist joints share pivot and transformations, and motion-off/reduced-motion stop moving elements.
- [ ] All 15 questions / 25 simulated learners / CSV export and room reset are exercised in isolated CI; **these are simulated users**.

## Step C — staging / physical review (only after explicit authorization)
- [ ] Deploy the pinned, reviewed SHA via the project's **verified** Cloudflare deployment procedure; capture deployment URL, timestamp, and release identifier.
- [ ] Confirm app health and audio assets Q01–Q15 and R01–R15; no synthetic CI fixtures are installed.
- [ ] Projector: QR large and readable from rear seats; names/timer legible with 25 participants.
- [ ] At least two physical phones: scan QR, select avatars, set Thai names, answer full 15 questions, see rankings. No manual room code.
- [ ] Test with live classroom audio, no clipping, delayed playback or missing reveal sounds.
- [ ] Export score CSV; open in Microsoft Excel and verify Thai text, columns, scores.
- [ ] Check each of the 20 face presets and 4 garments in 5 poses at desktop and phone size; hand/finger/cuff/branding not detached during motion.
- [ ] Test motion-off and OS reduced motion.
- [ ] Rehearse with 25 real devices if physical concurrency assurance is required.

## Step D — closure
- [ ] User accepts visual quality and on-site functional behavior explicitly.
- [ ] Record approved release SHA and acceptance notes in Issue #125.
- [ ] Leave staging untouched until all pre-deploy permissions; production is separately authorized.
- [ ] If any item fails, keep the old release and attach screenshots/repro steps to Issue #125; fix **concrete blockers only**.

**Known limitation:** The repo's `wrangler.ci.jsonc` is an isolated, dummy-ID database for CI. It is *not* the deployment or rollback configuration.
