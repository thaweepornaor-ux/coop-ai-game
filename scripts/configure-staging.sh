#!/usr/bin/env bash
# Configure a separate Cloudflare staging target without touching the CI or production config.
set -euo pipefail
cd "$(dirname "$0")/.."
: "${STAGING_D1_DATABASE_ID:?Set the distinct staging D1 UUID}"
if [[ ! "$STAGING_D1_DATABASE_ID" =~ ^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$ ]] || [[ "$STAGING_D1_DATABASE_ID" == "00000000-0000-4000-8000-000000000000" ]]; then
  echo "Invalid staging database UUID" >&2
  exit 2
fi
: "${STAGING_WORKER_NAME:=coop-ai-game-staging}"
if [[ ! "$STAGING_WORKER_NAME" =~ ^[a-z0-9][a-z0-9-]{0,61}[a-z0-9]$ ]] || [[ "$STAGING_WORKER_NAME" != *-staging ]]; then
  echo "Worker name must be a safe staging-only slug ending with -staging" >&2
  exit 2
fi
mkdir -p .staging-local
STAGING_D1_DATABASE_ID="$STAGING_D1_DATABASE_ID" STAGING_WORKER_NAME="$STAGING_WORKER_NAME" node --input-type=module <<'NODE'
import fs from 'node:fs';
const base=JSON.parse(fs.readFileSync('wrangler.ci.jsonc','utf8'));
base.name=process.env.STAGING_WORKER_NAME;
base.d1_databases=[{...base.d1_databases[0], database_name:'coop-ai-game-staging', database_id:process.env.STAGING_D1_DATABASE_ID, remote:true}];
fs.writeFileSync('.staging-local/wrangler.staging.json',JSON.stringify(base,null,2)+'\n',{mode:0o600});
console.log('Generated a staging-only config. No remote action taken.');
NODE
echo "Review .staging-local/wrangler.staging.json before any migration/deploy."
