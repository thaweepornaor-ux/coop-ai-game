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
for(let attempt=1;attempt<=20;attempt++){
 try{
  // Query variation helps avoid a stale edge response while Cloudflare deploys propagate.
  // The origin host and path are still validated against the exact allowlist above.
  const requestUrl=new URL(manifestUrl);
  requestUrl.searchParams.set('release',expectedSha);
  requestUrl.searchParams.set('check',String(attempt));
  const response=await fetch(requestUrl,{signal:AbortSignal.timeout(12000),redirect:'error',headers:{'Cache-Control':'no-cache','Pragma':'no-cache'}});
  if(!response.ok)throw Error('Release manifest HTTP '+response.status);
  const manifest=await response.json();
  if(manifest?.schema!==1||manifest?.application!=='coop-ai-game'||manifest?.commit!==expectedSha){
   const observed=typeof manifest?.commit==='string'&&/^[0-9a-f]{40}$/.test(manifest.commit)?manifest.commit:'unknown';
   throw Error('Published game version does not match the expected commit; observed='+observed+' expected='+expectedSha);
  }
  console.log('STAGING RELEASE PASS '+expectedSha);
  releaseOk=true;
  break;
 }catch(e){
  releaseError=e instanceof Error?e.message:String(e);
  if(attempt<20){console.log('STAGING RELEASE WAIT '+attempt+'/20: '+releaseError);await sleep(5000)}
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
// Verify the teacher's actual recorded audio has been published as first-party
// media assets, not just a UI claiming the voice pack is ready.
const voiceIndex=await fetch(new URL('/voice/manifest.json',base),{signal:AbortSignal.timeout(12000),redirect:'error'});
if(!voiceIndex.ok)throw new Error('STAGING VOICE FAIL: 15-track manifest missing (HTTP '+voiceIndex.status+')');
const voiceManifest=await voiceIndex.json();
if(voiceManifest.source!=='official-user-recordings-2026-10-13'||voiceManifest.questionCount!==15||voiceManifest.names?.length!==15)throw new Error('STAGING VOICE FAIL: wrong or incomplete recording pack');
for(const name of voiceManifest.names){
 if(!/^Q(0[1-9]|1[0-5])\\.mp3$/.test(name))throw new Error('STAGING VOICE FAIL: illegal filename '+name);
 const response=await fetch(new URL('/voice/'+name,base),{method:'GET',signal:AbortSignal.timeout(12000),redirect:'error'});
 if(!response.ok)throw new Error('STAGING VOICE FAIL '+name+': HTTP '+response.status);
 const bytes=new Uint8Array(await response.arrayBuffer());
 if(bytes.length<50_000||!(bytes[0]===0x49&&bytes[1]===0x44&&bytes[2]===0x33)&&bytes[0]!==0xff)throw new Error('STAGING VOICE FAIL '+name+': invalid MP3 payload');
 console.log('STAGING AUDIO PASS '+name+' '+bytes.length+' bytes');
}
console.log('Staging HTTP smoke and ALL 15 genuine recorded question audios passed.');
