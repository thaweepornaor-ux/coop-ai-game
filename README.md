# ภารกิจ AI ในสหกรณ์

Recovery source for the existing cooperative AI training game.

## Verified execution

The recovery branch has run successfully on GitHub Actions with Node 22.23.3 and the frozen pnpm lockfile. The GLB validator self-test passed 46 cases. Eight game-rule unit tests, local D1 integration, the recovered renderer geometry checks, and character reload/reset persistence checks passed.

These results cover the recovered source. They do **not** approve the new character art, prove physical iPhone/Android compatibility, or constitute a new deployed game.

## Work in progress

- Build a real independent preview from the recovered source while preserving the original Sites configuration.
- Inspect the official Snow and Rain Blender source models with automatic script execution disabled. Verify the Blender binary against its official SHA-256 manifest.
- Replace the rejected puppet-like renderer with detailed adult characters, actual rig animation and compatible clothing. Inspect actual renders and exported GLBs before acceptance.
- Preserve 10 male and 10 female characters, 11 independent dress fields, server-controlled 15-second questions, host permissions, score and reset behavior.
- Verify responsive browser layouts, reduced-motion behavior, and subtle studio lighting, sparkles and celebrations.

The main branch and existing published game are unchanged. The recovery work is on `codex/game-recovery`. No credentials, learner data, signed download links, or original private model checkpoints are stored here.
