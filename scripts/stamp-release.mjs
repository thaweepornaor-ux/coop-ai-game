#!/usr/bin/env node
import {mkdir,writeFile} from 'node:fs/promises';
const sha=process.argv[2]||process.env.GITHUB_SHA||'';
if(!/^[0-9a-f]{40}$/.test(sha)){console.error('Invalid release commit SHA');process.exit(2);}
await mkdir('public',{recursive:true});
await writeFile('public/coop-release.json',JSON.stringify({schema:1,commit:sha,application:'coop-ai-game'})+'\n');
console.log('Stamped exact release '+sha);
