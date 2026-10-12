# Release status — cooperative AI game

## Verified on 2026-10-12

- GitHub `main` contains the restored game, 20 avatar presets, and Avatar Studio.
- The browser proof on commit `e70bcfc3` passed 12/12 real Chromium/WebKit scenarios. The merge was `7c1c13e`.
- The staging **build-only** workflow passed on `4d04b1e` and did **not** publish.
- The staging host currently referenced by this repository is `https://coop-ai-game-staging.thaweeporn-aor.workers.dev/`. It is NOT proof of a current deployment.
- The original live-site address/provider was not verified. Do not confuse publishing staging with replacing that site.
- Uploaded PNG references are not a full approved layered character pack; current playable fallback is SVG.

## Publish to the known staging Worker (manual, never automatic)

1. Open GitHub Actions → **Deploy staging game (manual)** → **Run workflow** on `main`.
2. Choose `publish=true` only when deliberately publishing to **coop-ai-game-staging**. With `publish=false`, this workflow only builds and verifies the staging-only bundle.
3. Ensure the GitHub repository secret `CLOUDFLARE_API_TOKEN` is configured with access to the staging Worker and staging D1. Do not paste the token into code, chat, or the repository.
4. The workflow first installs frozen dependencies, generates a staging-only config, builds, asserts exact Worker and D1 IDs and absence of production routes, checks all 4 required tables in remote D1, then deploys.
5. The final step tests the **exact** staging host and routes `/`, `/play`, `/host`, `/avatar-studio`. Failures are reported as failures, not success.
6. Confirm the live game manually using desktop and a phone, particularly learner joins, instructor questions, 15-second countdown, reset, and names/wardrobe persistence.

**This does not migrate remote D1, deploy the original website, or set a custom domain.** Production publishing requires a verified original website URL and ownership/mapping of its deployment target. Never point staging DB credentials at a production database. Do not assume a workflow green check with `publish=false` means deployed.

## Deployment record to fill after actual publication

- Exact target URL:
- GitHub commit SHA:
- GitHub Actions run:
- Cloudflare Worker:
- D1 binding:
- Smoke check:
- Verified at (timezone):

## One-time verified staging refresh — 13 October 2026

The QR-first simplified AI understanding assessment passed 12/12 browser scenarios on commit `cfb4df0f`. Additional source changes only extend bounded Cloudflare release verification with observed-commit diagnostics. A staging-only one-shot publish is requested to verify the latest `main` revision. The workflow will be restored to manual-only publishing immediately after verification.
