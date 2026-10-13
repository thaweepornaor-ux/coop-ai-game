// Install the user's REAL Q01…Q15 ElevenLabs recordings in the Worker bundle.
// Source: public/voice/AI_Game_Official_15_Recordings.zip uploaded once to GitHub.
// Unlike per-device IndexedDB import, this works on every instructor computer.
// This script runs before staging build; never ship an incomplete voice pack.
import {readFile,writeFile,mkdir,stat} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {resolve} from 'node:path';
import {unpackQuizVoiceZip} from '../shared/quiz-voice-zip.js';

const root=resolve('public/voice');
const archive=resolve(root,'AI_Game_Official_15_Recordings.zip');
const required=process.argv.includes('--required');

async function install(){
  let raw;
  try{raw=await readFile(archive);}
  catch(err){
    if(err.code==='ENOENT'&&!required){
      console.log('Recorded voice archive not uploaded yet; build continues without bundled MP3s.');
      return;
    }
    throw new Error('ยังไม่มี ZIP เสียงต้นฉบับ 15 ข้อใน public/voice/AI_Game_Official_15_Recordings.zip');
  }
  const zipFile=new File([raw],'AI_Game_Official_15_Recordings.zip',{type:'application/zip'});
  const tracks=await unpackQuizVoiceZip(zipFile);
  if(tracks.length!==15)throw new Error('Missing real recorded tracks');
  await mkdir(root,{recursive:true});
  const hashes=[];
  for(let i=0;i<15;i++){
    const name='Q'+String(i+1).padStart(2,'0')+'.mp3';
    const file=tracks[i];
    const bytes=Buffer.from(await file.arrayBuffer());
    if(bytes.length<50_000||bytes.length>3_000_000)throw new Error('Invalid recording size: '+name);
    if(bytes.slice(0,3).toString()!=='ID3'&&(bytes[0]!==0xff))throw new Error('Invalid MP3 file: '+name);
    const hash=createHash('sha256').update(bytes).digest('hex');
    await writeFile(resolve(root,name),bytes);
    hashes.push(name+':'+hash.slice(0,12));
  }
  const size=(await stat(archive)).size;
  console.log('Installed 15 ORIGINAL voice tracks from '+size+' byte archive; '+hashes.join(' '));
}
await install();
