# ภารกิจ AI ในสหกรณ์ — Cooperative AI Game

Existing game source (do not rebuild from scratch). The active host/learner game is operated through the existing Cloudflare Staging deployment. Changes are reviewed in GitHub PRs before publication.

## Current game contract (14 October 2026)
- 15 multiple-choice scenario questions; **10-second answer window** per question.
- Up to 25 learners in a room, QR join without entering a manual room code; learners choose a character and enter a name.
- Teacher screen: join QR, live roster, 15 question recordings Q01–Q15, 15 answer recordings R01–R15, reveal/next, ranking, score CSV and new-room reset.
- Visual theme: original rich blue/violet game-show palette with moderated glow. Never change submitted character uniforms, colors or logos through CSS recoloring or regenerated art.
- Original image wrappers: `public/art/nhk-welcome-original.svg`, `nhk-presenter-original.svg`, `nhk-celebrate-original.svg`.
- `main` includes merged PR #36; PR #37 is additional mobile/instructor polish on a **separate review branch**.

## Verification boundaries
GitHub Game Smoke Tests and Browser Proof check code/integration and simulated browser behavior. A passing check does **not** certify physical mobile devices, visual design quality, audio audibility in a classroom, a real group of 25 people or Excel's rendering of an exported CSV. Review screenshots and manually test the full learner journey before merging/deploying.

## Safe delivery workflow
1. Make changes on a branch and open a PR.
2. Run Game Smoke Tests and Browser Proof (local, disposable data).
3. Inspect actual 720p/1080p/phone screenshots and make sure 25 real learner tiles are not obstructed.
4. Only then merge and trigger the existing explicit staging deploy; confirm release identifier and scanability.

Avoid replacing the existing Cloudflare deployment, altering question scores/timing/audio, or presenting tests as approval of artwork without actual visual inspection.
