# Staging release — 2026-10-15: welcome cast and user-facing language

Merged PR #40 repairs the full NHK welcome group image sizing without altering art or uniforms.
Merged PR #41 revises player and instructor UI labels to reduce technical/developer-facing terms, hiding preset IDs and variant counts from learners while keeping avatar/audio/score flows.

QA: Both change branches passed Game smoke tests and browser proof before merge. This main push requests a **staging-only** publish through the repository's guarded [publish-staging] workflow. Do not publish to production.
