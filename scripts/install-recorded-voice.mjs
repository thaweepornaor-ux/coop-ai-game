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
const OFFICIAL_SHA256=[
  "ba779d03bcefedd0a8aa7cf336afe15da286d94be9d2796256cd5868419b941a",
  "d22378d0b6d9c60ebc9a9aec6a7b76c377da95eea930e36324828e8a8b43439c",
  "7eaba986d845f50640983dc9ab9f113c9fd4ec94071e15abe7078b6ebcd3b5ca",
  "8f778022a44a79c40c9bd9b550ab0c849ff71b65720b5b6a8dd4ef36a74772f1",
  "f217c1a958c519d9ebcf42d7efd4e44903ed5688e2967e008da6b83d0c961883",
  "c66decdb7124626964509dbd26d8bf5662e4a226861df9567939939f299a5a63",
  "00269b0ae336f7c77a1a35072de96ed812e8747991ddb1cad9e180f3be8c696d",
  "104e165747229ebcfec821baf79e00661ae6564941de7181be0b0163259c1afa",
  "eeed77064b88c7cb2229e56779068c424026b8a4d8bd7099555ab37caa0ed56a",
  "fcced19ed2974bbd0c590aa205e9753d82e5cf726f03d6f7d5203286dd9ffc79",
  "0c8278763bb131c7712847319e920d6b8e8da0352a10a621cd1d74196255d174",
  "9b31affdb5ea353e7407ca5b4e50c12fad72a700d645b60a63f4d6cf2e26666f",
  "8ffaaa0dfc77f92d82aaa996b2a2da445fc5e789cfd8c435987d75aba545a94c",
  "96820894e2b7d205d9ee07153035557d296fed2a93cd5ce63713e80b5d0d5d7b",
  "860ad9861784979f1a19492bcc60e2967fc1fbeef7c7a1e1b9a1ead38f0e9348"
];

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
    if(hash!==OFFICIAL_SHA256[i])throw new Error('เสียง '+name+' ไม่ตรงกับไฟล์ต้นฉบับที่ผู้ใช้ส่งมา โปรดใช้ ZIP ทางการที่ตรวจสอบแล้ว');
    await writeFile(resolve(root,name),bytes);
    hashes.push(name+':'+hash.slice(0,12));
  }
  const size=(await stat(archive)).size;
  await writeFile(resolve(root,'manifest.json'),JSON.stringify({
    source:'official-user-recordings-2026-10-13',
    questionCount:15,
    names:Array.from({length:15},(_,i)=>'Q'+String(i+1).padStart(2,'0')+'.mp3'),
    hashes,
  },null,2));
  console.log('Installed 15 ORIGINAL voice tracks from '+size+' byte archive; '+hashes.join(' '));
}
await install();
