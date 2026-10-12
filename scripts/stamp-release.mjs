#!/usr/bin/env node
import {mkdir,writeFile} from 'node:fs/promises';
const sha=process.argv[2]||process.env.GITHUB_SHA||'';
if(!/^[0-9a-f]{40}$/.test(sha)){console.error('Invalid release commit SHA');process.exit(2);}
const data={schema:1,commit:sha,application:'coop-ai-game'};
// Embed the commit in the compiled server route; static assets can be intercepted by the worker.
await mkdir('shared',{recursive:true});
await writeFile('shared/release-manifest.js',
 '// Generated during build. Do not edit this artifact in a deployment checkout.\n'
 +'export const RELEASE_MANIFEST=Object.freeze('+JSON.stringify(data)+');\n');
console.log('Bundled release manifest '+sha);
