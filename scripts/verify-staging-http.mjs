#!/usr/bin/env node
import { setTimeout as sleep } from 'node:timers/promises';

const target=process.argv[2]||'';
let base;
try{
 base=new URL(target);
 if(base.protocol!=='https:'||base.username||base.password||base.search||base.hash||base.pathname!=='/')throw Error('Invalid base URL');
 if(base.hostname!=='coop-ai-game-staging.thaweeporn-aor.workers.dev')throw Error('Not the approved staging host');
}catch{
 console.error('Expected the exact https://coop-ai-game-staging.thaweeporn-aor.workers.dev/ host; no requests sent.');
 process.exit(2);
}
const expectedSha=process.argv[3]||'';
if(!/^[0-9a-f]{40}$/.test(expectedSha)){
 console.error('Expected exact forty-character release SHA; no requests sent.');
 process.exit(2);
}
const manifestUrl=new URL('/coop-release.json',base);
let releaseOk=false;
let releaseError='';
for(let attempt=1;attempt<=6;attempt++){
 try{
  const response=await fetch(manifestUrl,{signal:AbortSignal.timeout(12000),redirect:'error',headers:{'Cache-Control':'no-cache'}});
  if(!response.ok)throw Error('Release manifest HTTP '+response.status);
  const manifest=await response.json();
  if(manifest?.schema!==1||manifest?.application!=='coop-ai-game'||manifest?.commit!==expectedSha){
   throw Error('Published game version does not match the expected commit');
  }
  console.log('STAGING RELEASE PASS '+expectedSha);
  releaseOk=true;
  break;
 }catch(e){
  releaseError=e instanceof Error?e.message:String(e);
  if(attempt<6)await sleep(3000);
 }
}
if(!releaseOk){
 console.error('STAGING RELEASE FAIL: '+releaseError);
 process.exit(1);
}
const routes=['/','/play','/host','/avatar-studio'];
for(const route of routes){
 let last='';
 let passed=false;
 for(let attempt=1;attempt<=6;attempt++){
  try{
   const response=await fetch(new URL(route,base),{signal:AbortSignal.timeout(12000),redirect:'error'});
   const contentType=response.headers.get('content-type')||'';
   if(!response.ok||!contentType.includes('text/html'))throw Error('HTTP '+response.status+' '+contentType);
   const html=await response.text();
   if(!html.toLowerCase().includes('<html'))throw Error('Response is not an HTML document');
   if(route==='/'&&!html.includes('ประเมินความเข้าใจ AI'))throw Error('Expected game landing markers are missing');
   console.log('STAGING HTTP PASS '+route+' HTTP '+response.status);
   passed=true;break;
  }catch(e){last=e instanceof Error?e.message:String(e);if(attempt<6)await sleep(3000);}
 }
 if(!passed){console.error('STAGING HTTP FAIL '+route+': '+last);process.exit(1);}
}
console.log('Staging HTTP smoke passed for all four game routes.');
