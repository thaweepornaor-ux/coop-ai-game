#!/usr/bin/env node
// Reproducible non-deploying release evidence; never connects to Cloudflare or D1.
import {readFileSync,writeFileSync,mkdirSync,existsSync} from 'node:fs';
import {resolve,dirname} from 'node:path';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
const root=resolve(import.meta.dirname,'..');
const read=p=>readFileSync(resolve(root,p));
const hash=bytes=>createHash('sha256').update(bytes).digest('hex');
const commit=process.env.GITHUB_SHA||execFileSync('git',['rev-parse','HEAD'],{cwd:root,encoding:'utf8'}).trim();
if(!/^[0-9a-f]{40}$/.test(commit))throw new Error('Invalid source SHA');
const questionSource=read('server/questions.ts').toString('utf8');
const timers=[...questionSource.matchAll(/"timeLimitSeconds":\s*(\d+)/g)].map(m=>Number(m[1]));
if(timers.length!==15||timers.some(v=>v!==8))throw new Error('Unexpected question count/timer');
const artifactPath='browser-proof/avatar-art-review/all-outfits-contact-sheet.html';
const artifact=resolve(root,artifactPath);
if(!existsSync(artifact))throw new Error('400 avatar review artifact missing');
const html=readFileSync(artifact,'utf8');
const svgCount=(html.match(/<svg\b/g)||[]).length;
if(svgCount!==400)throw new Error('Expected exactly 400 reviewed SVGs, found '+svgCount);
const reportPath=resolve(root,'browser-proof/report.json');
if(!existsSync(reportPath))throw new Error('Browser report missing');
const report=JSON.parse(readFileSync(reportPath,'utf8'));
const manifest={
 schema:'coop-ai-game-release-evidence-v1',
 sourceCommit:commit,
 generatedAt:new Date().toISOString(),
 staged:false,
 deploymentAuthorized:false,
 classroomApproved:false,
 questionCount:timers.length,
 answerWindowSeconds:8,
 avatarVariants:svgCount,
 evidence:{
  browserReport:{path:'browser-proof/report.json',sha256:hash(readFileSync(reportPath))},
  avatarReview:{path:artifactPath,sha256:hash(readFileSync(artifact))}
 },
 warning:'CI simulation only; not physical 25 phones, classroom audio, Excel, or deployment approval.'
};
if(!report||typeof report!=='object')throw new Error('Invalid browser proof report');
const out=resolve(root,'browser-proof/release-evidence.json');
mkdirSync(dirname(out),{recursive:true});
writeFileSync(out,JSON.stringify(manifest,null,2)+'\n');
console.log('Release evidence generated',commit,svgCount,'variants');
