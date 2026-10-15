# Mobile responsive staging release — 2026-10-15

This staging-only rollout includes merged PRs #37, #38 and #39.

- PR #37: QR lobby positioning and mascot spacing.
- PR #38: player mobile layouts across join, avatar selection, waiting, question, result reveal, leaderboard and dialogs.
- PR #39: actual-browser viewport geometry assertions for mobile question and answer reveal.

Scope: existing game behavior remains unchanged (15 questions, 10-second answer window, audio pack, 25-player capacity and score export). The current host/projector design remains preserved.

Validation before publish: Game smoke tests, Browser proof and Runtime proof for merged changes succeeded. This commit intentionally triggers the repository's staging-only publish workflow using [publish-staging] after the prior merges.
