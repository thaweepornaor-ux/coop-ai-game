# ภารกิจ AI ในสหกรณ์ — Cooperative AI Game

Existing game source (do not rebuild from scratch). The active host/learner game is operated through the existing Cloudflare Staging deployment. Changes are reviewed in GitHub PRs before publication.

## Current implemented game contract (17 October 2026)
- 15 multiple-choice scenario questions; **8-second answer window** per question.
- Up to 25 learners in a room, QR join without entering a manual room code; learners choose a character and enter a name.
- Teacher screen: join QR, live roster, 15 question recordings Q01–Q15, 15 answer recordings R01–R15, reveal/next, ranking, score CSV and new-room reset.
- Visual theme: original rich blue/violet game-show palette with moderated glow. Never change submitted character uniforms, colors or logos through CSS recoloring or regenerated art.
- Original image wrappers: `public/art/nhk-welcome-original.svg`, `nhk-presenter-original.svg`, `nhk-celebrate-original.svg`.
- The current baseline includes merged avatar and browser QA PRs #110–#123; consult GitHub merge history for the precise release SHA.

**Timing note:** All 15 questions currently use `timeLimitSeconds: 8` in `server/questions.ts`, consistent with the host countdown display and browser smoke test. This documentation update does **not** change the timer. An earlier requested timing variant must be approved as a separate game-rule change before any release.

## Verification boundaries
GitHub Game Smoke Tests and Browser Proof check code/integration and simulated browser behavior. A passing check does **not** certify physical mobile devices, visual design quality, audio audibility in a classroom, a real group of 25 people or Excel's rendering of an exported CSV. Review screenshots and manually test the full learner journey before merging/deploying.

## Safe delivery workflow
1. Make changes on a branch and open a PR.
2. Run Game Smoke Tests and Browser Proof (local, disposable data).
3. Inspect actual 720p/1080p/phone screenshots and make sure 25 real learner tiles are not obstructed.
4. Only then merge and trigger the existing explicit staging deploy; confirm release identifier and scanability.

Avoid replacing the existing Cloudflare deployment, altering question scores/timing/audio, or presenting tests as approval of artwork without actual visual inspection.

## Final acceptance checklist (17 October 2026)

The reviewed baseline includes PRs #110–#123 on main. PR #123 added a
browser-level transform-origin guard and did not change artwork or gameplay.
This section is a release checklist, **not** a claim that staging is already updated.

### Automated release blockers (must all pass on the release commit)
- [ ] Run `npm test` / GitHub **Game smoke tests** on exact release SHA.
- [ ] GitHub **Browser proof**: all 14 planned Chromium/WebKit host and learner cases pass,
      zero skipped, including simulated 25-user roster, all 15 questions, score CSV,
      old-room invalidation and new-room reset.
- [ ] Confirm animation group movement, matching arm/fabric/fist transforms at 0 ms and
      650 ms, matching shoulder pivot origins, reduced motion and explicit motion-off.
- [ ] Inspect 400 SVG variants (20 presets × 4 shirts × 5 poses) from the **actual**
      browser proof artifact. Confirm hair, shirts, logos, arms and hands are not occluded.
- [ ] Confirm only reviewed commits and approved assets are included in release.

### Manual acceptance (requires actual user/teacher approval)
- [ ] On a real teacher projector, QR remains visible and readable at a distance.
- [ ] Two different physical phones can scan, choose distinct avatars and join
      without typing a room code; repeat through the full 15-question journey.
- [ ] Check audible Thai questions Q01–Q15 and reveal audios R01–R15 from the
      classroom loudspeaker, music mix and timings; no test fixture audio.
- [ ] Run a real 25-person rehearsal if 25-person classroom reliability must be certified.
- [ ] Open the exported score CSV in actual Excel and verify Thai names and columns.
- [ ] Visually approve 20 preset characters, their arm/sleeve/finger anatomy and
      animation on actual PC/phone, including stopping movement when motion is off.

### Publish policy
Do not trigger Cloudflare Staging deployment, production release, or announce
the game as complete until automated checks are green **and** the user explicitly
accepts the manual visual/operational gates. Preserve the current staging URL and
existing server data; do not reset real classrooms while testing.
