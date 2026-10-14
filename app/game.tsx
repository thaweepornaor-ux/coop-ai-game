'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import QRCode from 'qrcode';
import Image from 'next/image';
import { Avatar, AVATAR_OPTIONS } from './components/avatar';
import { normalizeWardrobe } from '../shared/avatar-registry';
import {STUDIO_TRANSFER_KEY,validateStudioTransfer} from '../shared/avatar-studio-transfer.js';
import { SimpleWardrobe } from './components/simple-wardrobe';
import { scoreCsv } from '../shared/score-export.js';
import { unpackQuizVoiceZip } from '../shared/quiz-voice-zip.js';
import { LOGO_SRC, COOPERATIVE_NAME } from '../shared/brand';

type Role='choose'|'host'|'player';
type Session={room:string;token:string;role:'host'|'player'};
type Person={id:string;name:string;avatar:Record<string,string>;score:number;level?:string;answered?:boolean};
type Result={playerId:string;name:string;avatar:Record<string,string>;choice:number|null;correct:boolean|null;status:'correct'|'incorrect'|'unanswered';score:number};
type Leader=Person&{rank:number;correctCount:number;incorrectCount:number;unansweredCount:number};
type Snapshot={serverNow:number;caller:{role:'host'|'player';playerId?:string};room:{code:string;phase:'lobby'|'question'|'closed'|'reveal'|'finished';questionIndex:number;roundId:number;deadline:number|null};question?:{number:number;topic:string;question:string;options:readonly string[]};players:Person[];ownAnswer?:{choice:number;submittedAt:number}|null;results?:Result[];correctAnswer?:number;explanation?:string;leaderboard?:Leader[]};
type ApiResponse={roomCode?:string;token?:string;role?:'host'|'player';snapshot?:Snapshot;error?:string;code?:string}&Partial<Snapshot>;
const letters=['A','B','C'];
const keys=Object.keys(AVATAR_OPTIONS) as (keyof typeof AVATAR_OPTIONS)[];
const initialAvatar=()=>({...Object.fromEntries(keys.map(k=>[k,AVATAR_OPTIONS[k][0].value])),shirtColor:'white',bodyStyle:'male',presetId:'M01',bottomStyle:'pants',bottomColor:'navy',shoeColor:'white',hairStyle:'sidepart',glassesStyle:'none'});
const level=(n:number)=>n<=5?'นักสำรวจ AI':n<=10?'นักต่อยอด AI':'นักรู้ทัน AI';
const levelTier=(n:number)=>n<=5?'explorer':n<=10?'builder':'aware';
const levelFeedback=(n:number)=>n<=5?'เริ่มจากงานร่างข้อความ แล้วฝึกบอก AI ให้เข้าใจงานที่ต้องการ':n<=10?'เข้าใจหลายเรื่องแล้ว ลองฝึกให้บริบทและตรวจคำตอบกับข้อมูลต้นทาง':'พื้นฐานแน่น ลองเลือกงานสหกรณ์หนึ่งงานที่ตรวจผลได้ แล้วนำ AI มาช่วย';
const safeRead=(key:string)=>{try{return localStorage.getItem(key)}catch{return null}};
const safeWrite=(key:string,value:string)=>{try{localStorage.setItem(key,value)}catch{}};
const sessionKey=(role:Role)=>'coop-ai-game-session-'+role;
const hostTabRoomKey='coop-ai-game-host-active-tab-room';
const isSameHostReload=(savedRoom:string)=>{
  try {
    const kind=(performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming|undefined)?.type;
    return kind==='reload'&&sessionStorage.getItem(hostTabRoomKey)===savedRoom;
  } catch { return false }
};
const rememberHostTab=(room:string)=>{try{sessionStorage.setItem(hostTabRoomKey,room)}catch{}};
const clearHostTab=()=>{try{sessionStorage.removeItem(hostTabRoomKey)}catch{}};
const VOICE_TRACKS=15;
function openVoiceStorage():Promise<IDBDatabase>{
 return new Promise((resolve,reject)=>{
   if(typeof indexedDB==='undefined'){reject(new Error('IndexedDB not available'));return;}
   const req=indexedDB.open('coop-ai-quiz-recorded-voice',1);
   req.onupgradeneeded=()=>{if(!req.result.objectStoreNames.contains('tracks'))req.result.createObjectStore('tracks');};
   req.onerror=()=>reject(req.error);
   req.onsuccess=()=>resolve(req.result);
 });
}
async function saveVoicePack(tracks:File[]):Promise<void>{
 const db=await openVoiceStorage();
 try{
  await new Promise<void>((resolve,reject)=>{
   const tx=db.transaction('tracks','readwrite'),store=tx.objectStore('tracks');
   tracks.forEach((file,index)=>store.put(file,'Q'+String(index+1).padStart(2,'0')+'.mp3'));
   tx.oncomplete=()=>resolve();tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error);
  });
 }finally{db.close();}
}
async function loadVoicePack():Promise<(Blob|null)[]>{
 const db=await openVoiceStorage();
 try{
  return await new Promise((resolve,reject)=>{
   const tx=db.transaction('tracks','readonly'),store=tx.objectStore('tracks');
   const tracks:(Blob|null)[]=Array(VOICE_TRACKS).fill(null);
   for(let i=0;i<VOICE_TRACKS;i++){
    const req=store.get('Q'+String(i+1).padStart(2,'0')+'.mp3');
    req.onsuccess=()=>{tracks[i]=req.result instanceof Blob?req.result:null;};
   }
   tx.oncomplete=()=>resolve(tracks);
   tx.onerror=()=>reject(tx.error);
  });
 }finally{db.close();}
}


function ArenaLights({celebrate=false}:{celebrate?:boolean}) {
 return <div className="arena-lighting" aria-hidden="true"><div className="spotlight spotlight-left"/><div className="spotlight spotlight-right"/><div className="arena-grid"/><div className="studio-sparkles">{Array.from({length:14},(_,i)=><i className="studio-sparkle" key={i} style={{left:((i*37+7)%94+3)+'%',top:((i*53+11)%88+6)+'%',width:(4+i%3*2)+'px',height:(4+i%3*2)+'px',animationDelay:-(i*.7)+'s',animationDuration:(4.8+i%5*1.2)+'s'}}/>)}</div>{celebrate&&<div className="confetti-burst">{Array.from({length:16},(_,i)=><i key={i} style={{left:(8+i*6)+'%',animationDelay:(i%4)*.15+'s',background:i%3===0?'#cbe997':i%3===1?'#46dbb5':'#e7c46a'}}/>)}</div>}</div>;
}
function RulesStrip(){return <div className="rules-strip"><div><b>15</b><span>คำถาม AI</span></div><div><b>10<small> วิ</small></b><span>ต่อหนึ่งคำถาม</span></div><div><b>1<small> แต้ม</small></b><span>เมื่อตอบถูก</span></div></div>}
export default function Game({initialRole='choose'}:{initialRole?:Role}){
  const [role,setRole]=useState<Role>(initialRole),[session,setSession]=useState<Session|null>(null);
  const [snapshot,setSnapshot]=useState<Snapshot|null>(null);
  const [roomInput,setRoomInput]=useState(''),[name,setName]=useState(''),[avatar,setAvatar]=useState<Record<string,string>>(initialAvatar);
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[network,setNetwork]=useState<'connecting'|'online'|'offline'>('connecting');
  const [now,setNow]=useState(Date.now()),[qr,setQr]=useState(''),[joinUrl,setJoinUrl]=useState('');
  const [sound,setSound]=useState(true),[motion,setMotion]=useState(true),[pendingChoice,setPendingChoice]=useState<number|null>(null),[resetDialog,setResetDialog]=useState(false),[leaveDialog,setLeaveDialog]=useState(false);
  const [copied,setCopied]=useState(false),[showRecovery,setShowRecovery]=useState(false),[editingProfile,setEditingProfile]=useState(false);
  const [projectorFullscreen,setProjectorFullscreen]=useState(false);
  const [narrationEnabled,setNarrationEnabled]=useState(false),[narrationBusy,setNarrationBusy]=useState(false),[narrationNotice,setNarrationNotice]=useState('');
  const narrationKey=useRef('');
  const voiceTrack=useRef<HTMLAudioElement|null>(null);
  const voiceUrls=useRef<(string|null)[]>(Array(VOICE_TRACKS).fill(null));
  const [voiceReady,setVoiceReady]=useState(false),[voiceImporting,setVoiceImporting]=useState(false);
  const [voiceTesting,setVoiceTesting]=useState(false);
  const voiceImported=useRef(false);
  const offset=useRef(0),lastSync=useRef(0),generation=useRef(0),sessionRef=useRef<Session|null>(null);
  const openingFreshHost=useRef(false);
  const snapshotRef=useRef<Snapshot|null>(null),busyRef=useRef(false);
  const audio=useRef<AudioContext|null>(null),lastBeep=useRef(''),lastEffect=useRef('');
  const totalRemaining=snapshot?.room.deadline ? Math.max(0,Math.ceil((snapshot.room.deadline-(now+offset.current))/1000)):10;
  const narrationRemaining=snapshot?.room.phase==='question'?Math.max(0,totalRemaining-10):0;
  const timer=Math.min(10,totalRemaining);
  const timeOpen=snapshot?.room.phase==='question'&&timer>0;
  const isHost=session?.role==='host';
  const canInteract=network==='online'&&now-lastSync.current<4500&&!busy;
  // Q01–Q15 are the instructor's real ElevenLabs recordings.
  // When the host imported an MP3 pack, the server reserves its duration + a buffer
  // before the full 10-second answer countdown begins.
  const stopNarration=useCallback(()=>{
    if(voiceTrack.current){voiceTrack.current.pause();voiceTrack.current.currentTime=0;voiceTrack.current=null;}
    if(typeof window!=='undefined'&&'speechSynthesis' in window)window.speechSynthesis.cancel();
    setNarrationBusy(false);
  },[]);
  const narrateSnapshot=useCallback((state:Snapshot,mode:'question'|'reveal')=>{
    if(typeof window==='undefined'||!state.question)return false;
    // The instructor START/NEXT click unlocks playback synchronously;
    // receiving the server snapshot must not play this file a second time.
    const playingNumber=state.room.questionIndex+1;
    const wantedSource=voiceUrls.current[playingNumber-1]||'/voice/Q'+String(playingNumber).padStart(2,'0')+'.mp3';
    if(mode==='question'&&voiceTrack.current?.src===new URL(wantedSource,window.location.href).href)return true;
    if(voiceTrack.current){voiceTrack.current.pause();voiceTrack.current=null;}
    if('speechSynthesis' in window)window.speechSynthesis.cancel();
    setNarrationBusy(false);setNarrationNotice('');
    if(mode==='question'){
      const qnum=state.room.questionIndex+1;
      const track=new Audio(voiceUrls.current[qnum-1]||'/voice/Q'+String(qnum).padStart(2,'0')+'.mp3');
      track.preload='auto';track.volume=1;
      track.onplaying=()=>setNarrationBusy(true);
      track.onended=()=>{setNarrationBusy(false);voiceTrack.current=null;};
      track.onerror=()=>{setNarrationBusy(false);setNarrationNotice('ยังไม่พบไฟล์ Q'+String(qnum).padStart(2,'0')+'.mp3 บนเว็บ');};
      voiceTrack.current=track;
      void track.play().catch(()=>setNarrationNotice('กรุณากด “อ่านซ้ำ” เพื่ออนุญาตเปิดเสียงพากย์ในเบราว์เซอร์'));
      return true;
    }
    if(!('speechSynthesis' in window)||!('SpeechSynthesisUtterance' in window))return false;
    const q=state.question;
    const spoken='เฉลยข้อที่ '+q.number+'. คำตอบที่ถูกต้องคือ '+letters[state.correctAnswer??0]+'. '+q.options[state.correctAnswer??0]+'. '+(state.explanation||'');
    const utterance=new SpeechSynthesisUtterance(spoken);
    utterance.lang='th-TH';utterance.rate=1.18;
    const thai=window.speechSynthesis.getVoices().find(v=>v.lang.toLowerCase().startsWith('th'));
    if(thai)utterance.voice=thai;
    utterance.onstart=()=>setNarrationBusy(true);
    utterance.onend=()=>setNarrationBusy(false);
    utterance.onerror=()=>setNarrationBusy(false);
    window.speechSynthesis.speak(utterance);
    return true;
  },[]);


  useEffect(()=>{
    if(role!=='host')return;
    let cancelled=false;
    // Prefer the user's original Q01–Q15 recordings, bundled into the Worker.
    // No ZIP import or upload step for instructors is needed on a published site.
    void (async()=>{
      try{
        const res=await fetch('/voice/manifest.json',{cache:'no-store'});
        if(res.ok){
          const index=await res.json();
          if(index?.source==='official-user-recordings-2026-10-13'&&index?.questionCount===15&&Array.isArray(index.names)&&index.names.length===15){
            if(cancelled||voiceImported.current)return;
            voiceImported.current=true;
            voiceUrls.current=index.names.map((name:string)=>'/voice/'+name);
            setVoiceReady(true);setNarrationEnabled(true);
            // The toolbar already confirms that all 15 recorded tracks are ready.
            // Avoid a persistent toast stealing precious projector space during questions.
            setNarrationNotice('');
            return;
          }
        }
      }catch{}
      try{
        const files=await loadVoicePack();
        if(cancelled||voiceImported.current||files.some(x=>!x))return;
        voiceUrls.current.forEach(url=>{if(url?.startsWith('blob:'))URL.revokeObjectURL(url)});
        voiceUrls.current=files.map(file=>URL.createObjectURL(file!));
        setVoiceReady(true);setNarrationEnabled(true);
      }catch{}
    })();
    return ()=>{cancelled=true;};
  },[role]);
  useEffect(()=>()=>{voiceUrls.current.forEach(url=>{if(url?.startsWith('blob:'))URL.revokeObjectURL(url)})},[]);
  async function importVoicePack(files:File[]){
    const matched=new Map(files.map(file=>[file.name.toUpperCase(),file]));
    const ordered=Array.from({length:VOICE_TRACKS},(_,i)=>matched.get('Q'+String(i+1).padStart(2,'0')+'.MP3'));
    if(ordered.some(file=>!file)){
      setNarrationNotice('กรุณาเลือกไฟล์ MP3 ครบ Q01.mp3 ถึง Q15.mp3 หลังแตก ZIP แล้ว');
      return;
    }
    const mp3=ordered as File[];
    if(mp3.some(file=>file.size<1000||file.size>15_000_000)){
      setNarrationNotice('พบไฟล์เสียงที่ไม่ถูกต้อง กรุณาตรวจสอบไฟล์ MP3');return;
    }
    setVoiceImporting(true);setNarrationNotice('');
    voiceImported.current=true;
    if(voiceTrack.current)voiceTrack.current.pause();
    voiceUrls.current.forEach(url=>{if(url?.startsWith('blob:'))URL.revokeObjectURL(url)});
    voiceUrls.current=mp3.map(file=>URL.createObjectURL(file));
    setVoiceReady(true);setNarrationEnabled(true);
    try{await saveVoicePack(mp3);setNarrationNotice('นำเข้าเสียงพากย์ครบ 15 ข้อแล้ว ใช้ซ้ำได้เมื่อเปิดเกมบนเครื่องนี้');}
    catch{setNarrationNotice('นำเข้าเสียงครบ 15 ข้อแล้ว แต่เบราว์เซอร์บันทึกถาวรไม่ได้ กรุณานำเข้าใหม่เมื่อเปิดเกมครั้งหน้า');}
    finally{setVoiceImporting(false);}
  }

  async function importVoiceSelection(chosen:File[]){
    if(!chosen.length)return;
    if(chosen.length!==1||!chosen[0].name.toLowerCase().endsWith('.zip')){
      await importVoicePack(chosen);
      return;
    }
    setVoiceImporting(true);
    setNarrationNotice('กำลังแตก ZIP และตรวจเสียงพากย์ 15 ข้อ…');
    try{
      const extracted=await unpackQuizVoiceZip(chosen[0]) as File[];
      await importVoicePack(extracted);
    }catch(cause){
      setNarrationNotice(cause instanceof Error?cause.message:'อ่าน ZIP ไม่ได้ กรุณาลองอีกครั้ง');
    }finally{setVoiceImporting(false);}
  }
  function testRecordedVoice(){
    if(!voiceReady||!voiceUrls.current[0]){
      setNarrationNotice('ยังไม่ได้ติดตั้งเสียงโจทย์ กรุณาเลือก ZIP เสียงพากย์ 15 ข้อก่อน');
      return;
    }
    stopNarration();
    setNarrationNotice('กำลังทดสอบเสียงข้อ 1 · หากไม่ได้ยิน ให้ตรวจระดับเสียงลำโพงและแท็บเบราว์เซอร์');
    const player=new Audio(voiceUrls.current[0]);
    player.volume=1;player.preload='auto';
    player.onplaying=()=>{setVoiceTesting(true);setNarrationBusy(true);};
    player.onended=()=>{setVoiceTesting(false);setNarrationBusy(false);voiceTrack.current=null;setNarrationNotice('ทดสอบเสียง Q01 สำเร็จ ✓ เสียงพร้อมเริ่มเกม');};
    player.onerror=()=>{setVoiceTesting(false);setNarrationBusy(false);setNarrationNotice('ไฟล์ Q01 เล่นไม่ได้ กรุณานำเข้า ZIP ใหม่');};
    voiceTrack.current=player;
    void player.play().catch(()=>{setVoiceTesting(false);setNarrationBusy(false);setNarrationNotice('เปิดเสียงไม่สำเร็จ ตรวจว่าปิดเสียงแท็บหรือลำโพงไว้หรือไม่ แล้วกดทดสอบอีกครั้ง');});
  }

  const beep=useCallback((frequency=550,duration=.09)=>{
    if(!sound||!audio.current||audio.current.state!=='running')return;
    try{const ctx=audio.current,o=ctx.createOscillator(),g=ctx.createGain();o.connect(g);g.connect(ctx.destination);o.frequency.value=frequency;
    g.gain.setValueAtTime(.0001,ctx.currentTime);g.gain.exponentialRampToValueAtTime(.075,ctx.currentTime+.012);
    g.gain.exponentialRampToValueAtTime(.0001,ctx.currentTime+duration);o.start();o.stop(ctx.currentTime+duration+.01)}catch{}
  },[sound]);
  function unlockAudio(){
    const AudioConstructor=window.AudioContext||(window as typeof window&{webkitAudioContext?:typeof AudioContext}).webkitAudioContext;
    if(!AudioConstructor)return;
    try{if(!audio.current)audio.current=new AudioConstructor();void audio.current.resume().catch(()=>{})}catch{}
  }
  function acceptState(data:Snapshot,started:number,ended:number){
    const prior=snapshotRef.current;
    const phaseOrder={lobby:0,question:1,closed:2,reveal:3,finished:4};
    if(prior&&prior.room.code===data.room.code){
      if(data.room.roundId<prior.room.roundId)return;
      if(data.room.roundId===prior.room.roundId){
        if(data.room.questionIndex<prior.room.questionIndex)return;
        if(data.room.questionIndex===prior.room.questionIndex){
          if(phaseOrder[data.room.phase]<phaseOrder[prior.room.phase])return;
          if(data.serverNow<prior.serverNow&&phaseOrder[data.room.phase]===phaseOrder[prior.room.phase])return;
          if(prior.ownAnswer&&!data.ownAnswer)data={...data,ownAnswer:prior.ownAnswer};
        }
      }
    }
    offset.current=data.serverNow-(started+ended)/2;lastSync.current=ended;
    snapshotRef.current=data;setSnapshot(data);setNetwork('online');
  }
  useEffect(()=>{
    const id=window.setInterval(()=>setNow(Date.now()),120);
    const query=new URLSearchParams(window.location.search);
    const code=(query.get('room')||'').toUpperCase().replace(/[^A-Z0-9]/g,'').slice(0,6);
    if(code)setRoomInput(code);
    if(initialRole!=='choose'){
      try{
        const saved=JSON.parse(safeRead(sessionKey(initialRole))||'null') as Session|null;
        if(saved&&saved.role===initialRole&&saved.token&&(!code||saved.room===code)){
          if(initialRole==='host'&&!isSameHostReload(saved.room)){
            // Opening /host again is a NEW class, not a hidden restoration of
            // previous students. An actual same-tab refresh stays resumable.
            openingFreshHost.current=true;
            void startFreshTeachingSession(saved);
          }else{
            sessionRef.current=saved;setSession(saved);
          }
        }
      }catch{}
    }
    const previousName=safeRead('coop-ai-game-name');if(previousName)setName(previousName);
    try{const previousAvatar=JSON.parse(safeRead('coop-ai-game-avatar')||'null');if(previousAvatar&&typeof previousAvatar==='object')setAvatar(normalizeWardrobe(previousAvatar))}catch{}
    if(initialRole==='player'&&query.get('studio')==='1'&&!sessionRef.current){
      try{
        const raw=safeRead(STUDIO_TRANSFER_KEY);
        const transfer=validateStudioTransfer(JSON.parse(raw||'null'));
        if(transfer){
          setName(transfer.name);
          setAvatar(normalizeWardrobe(transfer.avatar,true));
          localStorage.removeItem(STUDIO_TRANSFER_KEY);
        }
      }catch{}
    }
    // A single teaching session: create the instructor's private room automatically.
    // The room identifier is carried only in the QR link, never typed by learners.
    if(initialRole==='host'&&!sessionRef.current&&!busyRef.current&&!openingFreshHost.current)void send('create');
    setSound(safeRead('coop-ai-game-sound')!=='off');
    setMotion(!window.matchMedia('(prefers-reduced-motion: reduce)').matches);
    return()=>window.clearInterval(id);
  },[initialRole]);
  useEffect(()=>{sessionRef.current=session;setPendingChoice(null)},[session]);
  useEffect(()=>{
    if(!session)return;
    let disposed=false,tick:number|undefined,request:AbortController|null=null;
    const thisGeneration=++generation.current;
    async function poll(){
      request=new AbortController();const started=Date.now();
      const timeout=window.setTimeout(()=>request?.abort(),4500);
      try{
        const response=await fetch('/api/game?room='+encodeURIComponent(session!.room),{headers:{Authorization:'Bearer '+session!.token},cache:'no-store',signal:request.signal});
        const data=await response.json() as ApiResponse;
        if(disposed||thisGeneration!==generation.current)return;
        if(!response.ok){if(response.status===401||response.status===404){
          // Another host opened a fresh class and retired this room.
          // NEVER keep the prior students' pictures or scoreboard on screen.
          snapshotRef.current=null;setSnapshot(null);setQr('');setJoinUrl('');
          setError(session!.role==='host'
            ?'ห้องก่อนหน้าสิ้นสุดแล้ว หากต้องการสอนอีกครั้งให้กด “เริ่มเกมใหม่” ครับ'
            :'ห้องก่อนหน้าสิ้นสุดแล้ว กรุณาสแกน QR Code ใหม่จากผู้สอนครับ');
          setShowRecovery(true);
        }throw new Error(data.error||'เชื่อมต่อไม่ได้')}
        const state=(data.snapshot||data) as Snapshot;acceptState(state,started,Date.now());
      }catch{if(!disposed)setNetwork('offline')}
      finally{window.clearTimeout(timeout);if(!disposed)tick=window.setTimeout(poll,850)}
    }
    void poll();
    return()=>{disposed=true;request?.abort();if(tick)window.clearTimeout(tick)};
  },[session]);
  useEffect(()=>{
    if(!session||session.role!=='host')return;
    const url=window.location.origin+'/play?room='+encodeURIComponent(session.room);setJoinUrl(url);
    let disposed=false;
    QRCode.toDataURL(url,{width:320,margin:4,errorCorrectionLevel:'M',color:{dark:'#243777',light:'#ffffff'}}).then(value=>{if(!disposed)setQr(value)}).catch(()=>{if(!disposed)setQr('')});
    return()=>{disposed=true};
  },[session]);
  useEffect(()=>{
    const stamp=snapshot?.room.roundId+':'+snapshot?.room.questionIndex+':'+timer;
    if(timeOpen&&timer<=5&&stamp!==lastBeep.current){lastBeep.current=stamp;beep(440+(5-timer)*70,.1)}
    if(snapshot?.room.phase==='reveal'){
      const key=snapshot.room.roundId+':'+snapshot.room.questionIndex;
      if(lastEffect.current!==key){lastEffect.current=key;beep(740,.2)}
    }
  },[timer,timeOpen,snapshot?.room.roundId,snapshot?.room.questionIndex,snapshot?.room.phase,beep]);
  useEffect(()=>{
    if(!isHost||!narrationEnabled||!snapshot||!['question','closed','reveal'].includes(snapshot.room.phase)){
      stopNarration();return;
    }
    const key=snapshot.room.code+':'+snapshot.room.roundId+':'+snapshot.room.questionIndex+':'+(snapshot.room.phase==='reveal'?'reveal':'question');
    if(narrationKey.current===key)return;
    narrationKey.current=key;
    narrateSnapshot(snapshot,snapshot.room.phase==='reveal'?'reveal':'question');
  },[isHost,narrationEnabled,snapshot?.room.code,snapshot?.room.roundId,snapshot?.room.questionIndex,snapshot?.room.phase,narrateSnapshot,stopNarration]);
  useEffect(()=>()=>{if(voiceTrack.current)voiceTrack.current.pause();if(typeof window!=='undefined'&&'speechSynthesis' in window)window.speechSynthesis.cancel()},[]);
  useEffect(()=>{setPendingChoice(null)},[snapshot?.room.roundId,snapshot?.room.questionIndex]);
  useEffect(()=>{const sync=()=>setProjectorFullscreen(Boolean(document.fullscreenElement));document.addEventListener('fullscreenchange',sync);return()=>document.removeEventListener('fullscreenchange',sync)},[]);
  useEffect(()=>{if(snapshot&&snapshot.room.phase!=='lobby')setEditingProfile(false)},[snapshot?.room.phase]);
  async function send(action:string,extra:Record<string,unknown>={}){
    if(busyRef.current)return false;busyRef.current=true;unlockAudio();setBusy(true);setError('');
    // Call .play() inside the actual instructor click event so browsers don't
    // block autoplay after the asynchronous room API response.
    if(sessionRef.current?.role==='host'&&narrationEnabled&&(action==='start'||action==='next')){
      const nextNumber=action==='start'?1:(snapshotRef.current?.room.questionIndex??0)+2;
      if(nextNumber>=1&&nextNumber<=15){
        if(voiceTrack.current)voiceTrack.current.pause();
        const recording=new Audio(voiceUrls.current[nextNumber-1]||'/voice/Q'+String(nextNumber).padStart(2,'0')+'.mp3');
        recording.preload='auto';
        recording.onplaying=()=>setNarrationBusy(true);
        recording.onended=()=>{setNarrationBusy(false);if(voiceTrack.current===recording)voiceTrack.current=null;};
        recording.onerror=()=>setNarrationNotice('ไม่พบไฟล์เสียง Q'+String(nextNumber).padStart(2,'0')+'.mp3');
        voiceTrack.current=recording;
        void recording.play().catch(()=>setNarrationNotice('กด “อ่านซ้ำ” เพื่ออนุญาตการเล่นเสียง'));
      }
    }
    const requestGeneration=generation.current,requestSession=sessionRef.current;
    const started=Date.now();const controller=new AbortController();const timeout=window.setTimeout(()=>controller.abort(),8000);
    try{
      const current=sessionRef.current;
      const payload={action,...(current?{room:current.room,roundId:snapshot?.room.roundId,questionIndex:snapshot?.room.questionIndex}:{}),...((action==='start'||action==='next')?{recordedNarration:voiceReady&&narrationEnabled}:{}),...extra};
      const response=await fetch('/api/game',{method:'POST',headers:{'Content-Type':'application/json',...(current?{Authorization:'Bearer '+current.token}:{})},body:JSON.stringify(payload),signal:controller.signal});
      const data=await response.json() as ApiResponse;
      if(requestGeneration!==generation.current||requestSession!==sessionRef.current)return false;
      if(!response.ok){if(data.snapshot)acceptState(data.snapshot,started,Date.now());throw new Error(data.error||'ทำรายการไม่สำเร็จ')}
      if(data.token&&data.roomCode&&data.role){
        if(action==='newroom'){
          stopNarration();narrationKey.current='';
          setQr('');setJoinUrl('');setPendingChoice(null);setShowRecovery(false);setNetwork('connecting');
        }
        const value:Session={token:data.token,room:data.roomCode,role:data.role};
        sessionRef.current=value;setSession(value);safeWrite(sessionKey(data.role),JSON.stringify(value));
        if(value.role==='host')rememberHostTab(value.room);
      }
      const state=data.snapshot||(data.room?data as Snapshot:undefined);
      if(state)acceptState(state,started,Date.now());
      return true;
    }catch(e){if(requestGeneration!==generation.current||requestSession!==sessionRef.current)return;setError(e instanceof Error&&e.name==='AbortError'?'การเชื่อมต่อช้า กำลังตรวจสถานะล่าสุด กรุณารอสักครู่':e instanceof Error?e.message:'เชื่อมต่อไม่ได้');
      if(action==='answer')setPendingChoice(null);
      return false;
    }finally{window.clearTimeout(timeout);busyRef.current=false;setBusy(false)}
  }
  async function startFreshTeachingSession(previous:Session){
    // Fresh browser navigation must not silently resume prior people. Delete
    // the previous room with a server-authorized host action, then display
    // only the newly-created lobby and its new QR. Refreshing the same tab is
    // intentionally treated differently to avoid losing a class mid-round.
    if(busyRef.current)return;
    busyRef.current=true;setBusy(true);setError('');
    const controller=new AbortController();
    const timeout=window.setTimeout(()=>controller.abort(),12000);
    try{
      let response=await fetch('/api/game',{
        method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+previous.token},
        body:JSON.stringify({action:'newroom',room:previous.room}),signal:controller.signal
      });
      // If another instructor tab already retired this room, its old token
      // is invalid. Create a new empty lobby; do not restore stale players.
      if(response.status===401||response.status===404){
        response=await fetch('/api/game',{
          method:'POST',headers:{'Content-Type':'application/json'},
          body:JSON.stringify({action:'create'}),signal:controller.signal
        });
      }
      const data=await response.json() as ApiResponse;
      if(!response.ok)throw new Error(data.error||'เปิดห้องใหม่ไม่สำเร็จ');
      if(!data.token||!data.roomCode||data.role!=='host'||!data.snapshot||
         data.snapshot.players.length!==0||data.snapshot.room.phase!=='lobby'||
         data.roomCode===previous.room)throw new Error('ห้องใหม่ไม่ว่าง กรุณาลองเปิดเกมใหม่อีกครั้ง');
      const fresh:Session={token:data.token,room:data.roomCode,role:'host'};
      narrationKey.current='';setQr('');setJoinUrl('');
      sessionRef.current=fresh;setSession(fresh);
      safeWrite(sessionKey('host'),JSON.stringify(fresh));
      rememberHostTab(fresh.room);
      acceptState(data.snapshot,Date.now(),Date.now());
    }catch(err){
      // Never display the previous class as a "new" class after failure.
      setNetwork('offline');
      setError(err instanceof Error?err.message:'สร้างห้องใหม่ไม่สำเร็จ กรุณาลองอีกครั้ง');
    }finally{
      window.clearTimeout(timeout);
      openingFreshHost.current=false;busyRef.current=false;setBusy(false);
    }
  }
  function join(){
    const code=roomInput.toUpperCase().trim(),playerName=name.trim();
    if(!/^[A-Z0-9]{6}$/.test(code)){setError('กรุณาสแกน QR Code บนจอผู้สอนอีกครั้งครับ');return}
    if(!playerName){setError('ตั้งชื่อผู้เล่นก่อนครับ');return}
    safeWrite('coop-ai-game-name',playerName);safeWrite('coop-ai-game-avatar',JSON.stringify(avatar));
    void send('join',{room:code,name:playerName,avatar});
  }
  function leave(){
    // Rejoining creates a second scoreboard entry. Profiles are now edited in place.
    stopNarration();setNarrationEnabled(false);narrationKey.current='';
    const oldInvitation='';
    const keepInvitation=false;
    generation.current++;try{localStorage.removeItem(sessionKey(role))}catch{}
    if(role==='host')clearHostTab();
    sessionRef.current=null;snapshotRef.current=null;setSession(null);setSnapshot(null);setError('');setShowRecovery(false);setNetwork('connecting');
    setRoomInput(keepInvitation?oldInvitation:'');
    setPendingChoice(null);setEditingProfile(false);setResetDialog(false);setLeaveDialog(false);setQr('');setJoinUrl('');
  }
  async function saveProfile(){
    const updated=name.trim();
    if(!updated){setError('กรุณาตั้งชื่อผู้เล่น');return}
    if(await send('profile',{name:updated,avatar})){
      safeWrite('coop-ai-game-name',updated);
      safeWrite('coop-ai-game-avatar',JSON.stringify(avatar));
      setEditingProfile(false);
    }
  }
  function restartHost(){
    // A saved instructor credential can expire between training days.
    // Release only this browser's stale session before opening a fresh QR invitation.
    leave();
    void send('create');
  }
  async function toggleProjectorFullscreen(){
    if(role!=='host')return;
    try{
      if(document.fullscreenElement)await document.exitFullscreen();
      else if(document.documentElement.requestFullscreen)await document.documentElement.requestFullscreen();
      else setError('เบราว์เซอร์นี้ไม่รองรับโหมดเต็มจอ กด F11 บนคอมพิวเตอร์แทนได้ครับ');
    }catch{setError('เปิดเต็มจอไม่ได้ กด F11 บนคอมพิวเตอร์เพื่อขยายหน้าจอแทนได้ครับ')}
  }
  function downloadResults(){
    if(!isHost||!finished||!snapshot?.leaderboard)return;
    const blob=new Blob([scoreCsv(snapshot.leaderboard)],{type:'text/csv;charset=utf-8'});
    const url=URL.createObjectURL(blob);
    const anchor=document.createElement('a');
    const date=new Date();
    const datePart=[date.getFullYear(),String(date.getMonth()+1).padStart(2,'0'),String(date.getDate()).padStart(2,'0')].join('-');
    anchor.href=url;anchor.download='AI-Assessment-Results-'+datePart+'.csv';
    document.body.appendChild(anchor);anchor.click();anchor.remove();
    window.setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  async function copyJoin(){
    try{await navigator.clipboard.writeText(joinUrl);setCopied(true);window.setTimeout(()=>setCopied(false),2000)}
    catch{setError('คัดลอกลิงก์ไม่ได้ แต่ผู้เรียนยังสแกน QR Code ได้ตามปกติครับ')}
  }
  function chooseAnswer(choice:number){
    if(busyRef.current||!canInteract||!timeOpen||snapshot?.ownAnswer||pendingChoice!==null)return;
    setPendingChoice(choice);void send('answer',{choice});
  }
  const own=snapshot?.players.find(p=>p.id===snapshot.caller.playerId);
  const ownResult=snapshot?.results?.find(p=>p.playerId===snapshot.caller.playerId);
  const finished=snapshot?.room.phase==='finished';
  const reveal=snapshot?.room.phase==='reveal';
  const closed=snapshot?.room.phase==='closed'||(snapshot?.room.phase==='question'&&timer===0);
  const answered=snapshot?.players.filter(p=>p.answered).length||0;
  const rankedPlayers=[...(snapshot?.players||[])].sort((a,b)=>b.score-a.score||a.name.localeCompare(b.name,'th'));

  // The instructor countdown lives in the separate right-hand console, not the
  // question column. This leaves the entire question card for readable Thai copy.
  const questionLength=snapshot?.question?.question.length||0;
  const longestOption=Math.max(0,...(snapshot?.question?.options||[]).map(option=>option.length));
  const denseQuestion=questionLength>115||longestOption>90;
  const packedRoster=(snapshot?.players.length||0)>=12;
  function toggleNarration(){
    if(narrationEnabled){setNarrationEnabled(false);stopNarration();return;}
    if(!voiceReady){setNarrationNotice('กรุณานำเข้า MP3 ให้ครบ 15 ข้อก่อนเปิดเสียงพากย์');return;}
    if(!snapshot)return;
    const currentMode=snapshot.room.phase==='reveal'?'reveal':'question';
    if(narrateSnapshot(snapshot,currentMode)){
      narrationKey.current=snapshot.room.code+':'+snapshot.room.roundId+':'+snapshot.room.questionIndex+':'+snapshot.room.phase;
      setNarrationEnabled(true);
    }
  }
  function repeatNarration(){
    if(!snapshot)return;
    narrateSnapshot(snapshot,snapshot.room.phase==='reveal'?'reveal':'question');
  }
  const countdownNode=<div className={'countdown '+(timer<=5&&!reveal?'urgent':'')} style={{'--remaining':(reveal?1:timer/10)} as React.CSSProperties} role="timer" aria-label={reveal?'เฉลยแล้ว':narrationRemaining>0?'กำลังเปิดเสียงอ่านโจทย์': 'เหลือ '+timer+' วินาที'}><span className="timer-kicker" aria-hidden="true">{reveal?'เฉลยแล้ว':narrationRemaining>0?'🔊 กำลังพากย์':timer<=5?'⚡ เร็วเข้า!':'เวลาเหลือ'}</span><span className="timer-value">{reveal?'✓':narrationRemaining>0?'♪':timer}</span><small>{reveal?'เฉลย':narrationRemaining>0?'ฟังโจทย์ก่อนเริ่มจับเวลา':'วินาที'}</small></div>;
  return <main className={'game-shell '+(motion?'motion-on':'motion-off')} data-role={role}>
    <ArenaLights celebrate={reveal||finished}/>
    <header className="topbar">
      <div className="brand"><Image src={LOGO_SRC} width={58} height={61} sizes="58px" priority alt={'โลโก้ '+COOPERATIVE_NAME}/><span><small>{COOPERATIVE_NAME}</small><strong>ประเมินความเข้าใจ AI</strong></span></div>
      <div className="preferences">
        {isHost&&<button type="button" className="icon-button new-game-top" disabled={busy} onClick={()=>setResetDialog(true)}>↻ เริ่มเกมใหม่</button>}
        {role==='host'&&<label className={'icon-button voice-pack-import '+(voiceReady?'ready':'')} title="เลือก ZIP เสียงพากย์ได้โดยตรง หรือเลือก MP3 ทั้ง 15 ไฟล์">
          <input type="file" accept=".zip,application/zip,.mp3,audio/mpeg" multiple disabled={voiceImporting} onChange={e=>{void importVoiceSelection(Array.from(e.target.files||[]));e.currentTarget.value='';}}/>
          {voiceImporting?'กำลังติดตั้งเสียง…':voiceReady?'🎙 เสียงโจทย์พร้อม ✓':'🎙 ใส่ ZIP เสียงโจทย์'}
        </label>}
        {role==='host'&&voiceReady&&<button type="button" className="icon-button voice-test-header" onClick={testRecordedVoice}>{voiceTesting?'🔊 กำลังทดสอบ…':'▶ ทดสอบเสียง'}</button>}
        {role==='host'&&<button className="icon-button fullscreen-toggle" type="button" aria-pressed={projectorFullscreen} onClick={()=>void toggleProjectorFullscreen()}>{projectorFullscreen?'↙ ออกจากเต็มจอ':'⛶ เต็มจอโปรเจคเตอร์'}</button>}
        <button className="icon-button" type="button" aria-label={sound?'ปิดเสียงเอฟเฟกต์':'เปิดเสียงเอฟเฟกต์'} aria-pressed={sound} onClick={()=>{unlockAudio();setSound(v=>{safeWrite('coop-ai-game-sound',v?'off':'on');return !v})}}>{sound?'♪ เอฟเฟกต์เปิด':'♪ เอฟเฟกต์ปิด'}</button>
        <button className="icon-button" type="button" aria-label="เปิดหรือปิดการเคลื่อนไหว" aria-pressed={motion} onClick={()=>setMotion(v=>!v)}>{motion?'✦ เอฟเฟกต์เปิด':'✦ เอฟเฟกต์ปิด'}</button>
      </div>
    </header>
    {error&&<div className="notice error" role="alert">{error}</div>}
    {narrationNotice&&role==='host'&&<div className="narration-notice" role="status">{narrationNotice}<button type="button" aria-label="ปิดคำแนะนำเสียงอ่าน" onClick={()=>setNarrationNotice('')}>×</button></div>}
    {session&&<div className={'connection '+network} role="status"><i/>{network==='online'?'เชื่อมต่อแล้ว':network==='offline'?'กำลังเชื่อมต่อใหม่… กรุณารอสักครู่':'กำลังเชื่อมต่อเกม…'} {showRecovery&&<button type="button" onClick={isHost?restartHost:leave}>{isHost?'เริ่มเกมใหม่':'กลับไปสแกน QR ใหม่'}</button>}</div>}

    {!session&&role==='choose'&&<section className="welcome entry-stage enter">
      <div className="entry-copy"><div className="eyebrow"><i/> COOPERATIVE • AI ARENA</div><h1>ประเมิน<br/><em>ความเข้าใจ AI</em></h1><p className="entry-description">เข้าเวทีแห่งไอเดีย ท้าทายความเข้าใจ<br/>และเรียนรู้พลังของ AI ไปด้วยกัน</p><RulesStrip/><div className="entry-actions"><a className="button primary" href="/play">เข้าร่วมภารกิจ <span>↗</span></a><a className="button secondary" href="/host">เปิดเวทีผู้สอน <span>→</span></a></div><p className="small-note">เล่นผ่านมือถือ · ไม่ต้องสมัครสมาชิก</p></div>
      <div className="hero-stage"><div className="orbit-ring"/><span className="stage-label">YOUR NEXT MISSION</span><Avatar options={initialAvatar()} className="hero-avatar" interactive motion={motion}/><div className="stage-platform"/><div className="stage-id"><i/> AI EXPLORER <span>01</span></div></div>
    </section>}
    {!session&&role==='host'&&<section className="single-host-welcome card" aria-label="หน้าผู้สอน">
      <div className="eyebrow">สำหรับผู้สอน · แสดงขึ้นโปรเจคเตอร์</div>
      <h1>ประเมินความเข้าใจ AI</h1>
      <p>กำลังเตรียม QR Code ให้ผู้เรียนสแกนเข้าร่วมอัตโนมัติ</p>
      <RulesStrip/>
      <div className="host-loading"><span className="host-loading-dot"/> {busy?'กำลังเปิดเกม…':'หาก QR Code ยังไม่ขึ้น กดปุ่มด้านล่าง'}</div>
      <button className="button primary" type="button" disabled={busy} onClick={()=>void send('create')}>{busy?'กำลังเตรียมเกม…':'เปิดเกมและแสดง QR Code'}</button>
      <p className="small-note">ผู้เรียนไม่ต้องใส่รหัสห้องหรือลงทะเบียน</p>
    </section>}
    {!session&&role==='player'&&(!/^[A-Z0-9]{6}$/.test(roomInput)?<section className="scan-needed card">
      <div className="eyebrow">สำหรับผู้เรียน</div>
      <h1>ประเมินความเข้าใจ AI</h1>
      <p>ใช้กล้องโทรศัพท์สแกน QR Code ที่แสดงบนจอโปรเจคเตอร์ของผู้สอน เพื่อเลือกตัวละครและเข้าเล่นได้เลย</p>
      <p className="small-note">ไม่ต้องกรอกรหัสห้อง ไม่ต้องสมัครสมาชิก</p>
    </section>:<section className="customizer quick-player enter">
      <div className="customizer-preview">
        <div className="eyebrow">สำหรับผู้เรียน</div>
        <h1>เลือกตัวละคร<br/><em>แล้วเข้าเล่นเลย</em></h1>
        <div className="character-stage"><Avatar options={avatar} className="avatar-preview" motion={false}/></div>
        <div className="character-name"><strong>{name.trim()||'ตัวละครของฉัน'}</strong></div>
      </div>
      <form className="wardrobe card" onSubmit={e=>{e.preventDefault();join()}}>
        <div className="wardrobe-heading"><h2>เลือกตัวละครและตั้งชื่อ</h2><p>แค่ 2 ขั้นตอน แล้วรอผู้สอนเริ่มเกม</p></div>
        <SimpleWardrobe avatar={avatar} onChange={setAvatar}/>
        <div className="join-fields"><label htmlFor="quick-player-name">2. ชื่อผู้เล่น<input id="quick-player-name" autoComplete="nickname" maxLength={24} placeholder="พิมพ์ชื่อเล่นของคุณ" value={name} onChange={e=>setName(e.target.value)}/></label></div>
        <button className="button primary join-button" type="submit" disabled={busy||!name.trim()}>{busy?'กำลังเข้าร่วม…':'เข้าเล่นเกม →'}</button>
        <p className="small-note">ไม่ต้องสมัครสมาชิก ไม่ต้องใส่รหัสห้อง</p>
      </form>
    </section>)}
    {session&&snapshot&&snapshot.room.phase==='lobby'&&<section className={'lobby '+(isHost?'host-lobby':'player-lobby')}>
      <div className="card lobby-main enter"><div className="badge">{isHost?'✦ ถ่ายทอดสดห้องเรียน AI':'YOU ARE IN'}</div><h1>{isHost?'ประเมินความเข้าใจ AI':'เตรียมพร้อม ภารกิจกำลังเริ่ม'}</h1>{isHost&&<><p className="showcase-subtitle">เกมประเมินความเข้าใจ AI แบบตอบไว · เล่นพร้อมกันบนมือถือ</p><div className="stage-stat-line" aria-label="กติกาเกม"><span>◆ 15 คำถาม</span><span>◷ ฟังจบแล้วตอบ 10 วินาที</span><span>★ ตอบถูก 1 คะแนน</span></div></>}
        {isHost&&<div className={'voice-setup-panel '+(voiceReady?'ready':'need-voice')} role="group" aria-label="ตั้งค่าเสียงอ่านโจทย์">
          <div className="voice-setup-copy"><strong>{voiceReady?'🎙 เสียงอ่านโจทย์พร้อมใช้งาน':'🔈 ยังไม่มีเสียงอ่านโจทย์'}</strong><span>{voiceReady?'ติดตั้งครบ 15 ข้อแล้ว เริ่มเกมจะเล่นเสียงให้อัตโนมัติ':'กดนำเข้า ZIP เสียงพากย์ไฟล์เดียว จากนั้นกดทดลองฟัง'}</span></div>
          <label className="voice-setup-upload"><input type="file" accept=".zip,application/zip,.mp3,audio/mpeg" multiple disabled={voiceImporting} onChange={e=>{void importVoiceSelection(Array.from(e.target.files||[]));e.currentTarget.value='';}}/>{voiceImporting?'กำลังติดตั้ง…':voiceReady?'เปลี่ยนชุดเสียง ZIP':'🎙 เลือก ZIP เสียงโจทย์'}</label>
          <button type="button" className="voice-setup-test" disabled={!voiceReady||voiceImporting} onClick={testRecordedVoice}>{voiceTesting?'🔊 กำลังเล่นเสียงข้อ 1':'▶ ทดลองฟังข้อ 1'}</button>
        </div>}
        {isHost?<><div className="join-ticket simple-join-ticket"><div className="qr">{qr?<img src={qr} alt="QR สำหรับผู้เล่นเข้าห้อง"/>:<span>กำลังสร้าง QR…</span>}</div><div className="arena-ticket-content"><span className="arena-ticket-eyebrow">SCAN • CREATE • PLAY</span><h2>สแกน QR Code เพื่อเข้าเล่น</h2><p>ใช้มือถือสแกนแล้วเข้าร่วมได้ทันที</p><div className="arena-join-steps" aria-label="วิธีเข้าร่วม"><span><b>01</b> สแกน QR</span><span><b>02</b> เลือกตัวละคร</span><span><b>03</b> ตั้งชื่อ</span></div><strong className="room-code sr-only">{session.room}</strong><button className="button secondary" type="button" onClick={()=>void copyJoin()}>{copied?'คัดลอกแล้ว ✓':'คัดลอกลิงก์สำหรับผู้เรียน'}</button><input className="join-url sr-only" aria-label="ลิงก์ผู้เล่น" value={joinUrl} readOnly onFocus={e=>e.target.select()}/></div></div><button className="button primary" disabled={!canInteract||snapshot.players.length===0} onClick={()=>void send('start')}>เริ่มเกมกับผู้เล่น {snapshot.players.length} คน {voiceReady?'พร้อมเสียงพากย์ ✓':'(ไม่มีเสียงโจทย์)'} →</button></>
        :<>{editingProfile?<form className="inline-profile-form" onSubmit={e=>{e.preventDefault();void saveProfile()}}>
          <h2>แก้ไขตัวละครและชื่อ</h2>
          <SimpleWardrobe avatar={avatar} onChange={setAvatar}/>
          <label htmlFor="edit-player-name">ชื่อผู้เล่น<input id="edit-player-name" maxLength={24} autoComplete="nickname" value={name} onChange={e=>setName(e.target.value)} placeholder="ชื่อเล่นของคุณ"/></label>
          <div className="inline-profile-actions"><button className="button secondary" type="button" onClick={()=>setEditingProfile(false)}>ยกเลิก</button><button className="button primary" disabled={!canInteract||!name.trim()} type="submit">{busy?'กำลังบันทึก…':'บันทึกตัวละครและชื่อ'}</button></div>
        </form>:<><Avatar options={own?.avatar||avatar} className="waiting-avatar" interactive motion={motion}/><h2>{own?.name||name}</h2><p>รอผู้สอนเริ่มเกม · หลังฟังโจทย์มีเวลาตอบ 10 วินาที</p>
          <button className="button secondary edit-player-profile" type="button" onClick={()=>{if(own){setName(own.name);setAvatar(normalizeWardrobe(own.avatar))}setEditingProfile(true)}}>เปลี่ยนชื่อ / ตัวละคร</button>
          <div className="waiting-dots" aria-label="กำลังรอผู้สอน"><i/><i/><i/></div></>}</>}
      </div>
      <div className="card roster-panel"><h2>ผู้เข้าร่วม <span>{snapshot.players.length} คน</span></h2><div className="roster">{snapshot.players.map(p=><div className="mini-player" key={p.id}><Avatar options={p.avatar}/><strong title={p.name}>{p.name}</strong></div>)}</div>{snapshot.players.length===0&&(isHost?<div className="arena-empty-stage" role="status"><div className="arena-empty-visual" aria-hidden="true"><span className="arena-stage-halo"/><span className="arena-holo-person"/><span className="arena-holo-person"/><span className="arena-holo-person"/></div><div className="arena-empty-copy"><span className="arena-live-kicker"><i/> READY FOR PLAYERS</span><strong>เวทีพร้อมต้อนรับ!</strong><p>เมื่อผู้เรียนสแกน QR Code ตัวละครจะปรากฏบนเวทีนี้ทันที</p></div><div className="arena-empty-chips"><span>✦ ร่วมเล่นแบบสด</span><span>✦ แสดงตัวละครสด</span></div></div>:<p>รอผู้เรียนสแกน QR Code ครับ</p>)}</div>
    </section>}

    {session&&snapshot&&snapshot.room.phase!=='lobby'&&!finished&&<section className={'question-layout '+(isHost?'host-question':'player-question')+(isHost&&reveal?' reveal-mode':'')+(isHost&&denseQuestion&&!reveal?' dense-question':'')+(isHost&&packedRoster&&!reveal?' packed-roster':'')}>
      <div className="card question-card enter" key={snapshot.room.roundId+':'+snapshot.room.questionIndex}>
        <div className="question-meta"><span className="badge">ข้อ {(snapshot.question?.number||snapshot.room.questionIndex+1)} / 15</span>{isHost?<div className="narration-controls"><button type="button" className={'narrate-button '+(narrationEnabled?'enabled':'')} aria-pressed={narrationEnabled} onClick={toggleNarration}>{narrationEnabled?'🔊 เสียงพากย์เปิด':'🔇 เปิดเสียงพากย์'}</button>{narrationEnabled&&<button type="button" className="narrate-button" onClick={repeatNarration}>↻ อ่านซ้ำ</button>}{narrationBusy&&<span className="narration-speaking">🔊 กำลังอ่านโจทย์…</span>}</div>:countdownNode}</div>
        <div className="mission-progress" aria-label={'ความคืบหน้า ข้อ '+(snapshot.room.questionIndex+1)+' จาก 15'}>{Array.from({length:15},(_,i)=><i key={i} className={i<snapshot.room.questionIndex?'complete':i===snapshot.room.questionIndex?'current':''}/>)}</div>
        <p className="topic"><span>คำถาม {String(snapshot.room.questionIndex+1).padStart(2,'0')}</span> {snapshot.question?.topic}</p><h1>{snapshot.question?.question}</h1>
        <div className="answer-grid">{snapshot.question?.options.map((option,i)=>{
          const picked=snapshot.ownAnswer?.choice===i||pendingChoice===i;
          const correct=reveal&&snapshot.correctAnswer===i;
          return <button key={i} className={'answer answer-'+i+(picked?' picked':'')+(correct?' correct':'')+(reveal&&picked&&!correct?' wrong':'')} disabled={!!isHost||!timeOpen||!canInteract||snapshot.ownAnswer!=null||pendingChoice!==null} onClick={()=>chooseAnswer(i)}><span className="answer-letter">{correct?'✓':letters[i]}</span><span>{option}</span>{picked&&!reveal&&<span className="picked-mark">✓</span>}</button>
        })}</div>
        {!isHost&&!reveal&&<p className="answer-status" role="status">{snapshot.ownAnswer?'ส่งคำตอบแล้ว รอเฉลยครับ':pendingChoice!==null?'กำลังส่งคำตอบ…':closed?'หมดเวลาแล้ว รอผู้สอนเปิดเฉลย' :narrationRemaining>0?'กำลังฟังเสียงโจทย์ · จากนั้นมีเวลาตอบเต็ม 10 วินาที':'เลือกคำตอบที่เหมาะสมที่สุดหนึ่งข้อ'}</p>}
        {isHost&&!reveal&&<div className="host-controls"><span>ตอบแล้ว <strong>{answered} / {snapshot.players.length}</strong> คน</span><button className="button primary" disabled={!canInteract} onClick={()=>void send('reveal')}>{timeOpen?'ปิดรับคำตอบและเปิดเฉลย':'เปิดเฉลย ✦'}</button></div>}
        {reveal&&<div className="explanation"><h2>คำตอบ: {letters[snapshot.correctAnswer??0]} · {snapshot.question?.options[snapshot.correctAnswer??0]}</h2><p>{snapshot.explanation}</p></div>}
        {reveal&&!isHost&&<div className={'own-result '+(ownResult?.status||'unanswered')} role="status"><strong>{ownResult?.status==='correct'?'ตอบถูก! เก่งมาก ✦':ownResult?.status==='incorrect'?'ข้อนี้ยังไม่ถูก ลองดูเฉลยกัน':'ข้อนี้ไม่ได้ตอบ ไม่เป็นไร เรียนรู้ไปด้วยกัน'}</strong><span>คะแนนตอนนี้ {ownResult?.score??own?.score??0} / 15</span><Avatar options={own?.avatar||avatar}/><p>รอผู้สอนเริ่มข้อถัดไป</p></div>}
        {reveal&&isHost&&<div className="host-controls"><span>อ่านเฉลยและคุยทบทวนได้เต็มที่</span><button className="button primary" disabled={!canInteract} onClick={()=>void send(snapshot.room.questionIndex===14?'finish':'next')}>{snapshot.room.questionIndex===14?'ดูสรุปคะแนน 🏆':'เริ่มข้อถัดไป →'}</button></div>}
      </div>
      {isHost&&<aside className="card question-roster">{!reveal&&<div className="projector-timer-wrap">{countdownNode}</div>}<h2>{reveal?'ผลคำตอบข้อนี้':'คะแนนสะสม'} {!reveal&&<span className="host-score-count">ส่งคำตอบแล้ว {answered} / {snapshot.players.length}</span>}</h2>
        {!reveal&&<div className="live-score-stage" aria-label="สถานะการตอบคำถามแบบสด">
          <div className="live-score-stats">
            <span className="live-indicator"><i/> LIVE SCORE</span>
            <span className="live-player-count">{snapshot.players.length} <small>ผู้เล่น</small></span>
            <span className="live-answer-count">{answered}<small>ตอบแล้ว</small></span>
          </div>
          <div className="answer-meter" role="progressbar" aria-label="สัดส่วนผู้เล่นที่ส่งคำตอบ" aria-valuenow={answered} aria-valuemin={0} aria-valuemax={snapshot.players.length} style={{'--answer-percent':(snapshot.players.length?Math.round(answered/snapshot.players.length*100):0)+'%'} as React.CSSProperties}><span/></div>
          <p className="live-score-hint">{(rankedPlayers[0]?.score??0)>0?'✦ คะแนนนำขณะนี้: '+rankedPlayers.filter(p=>p.score===rankedPlayers[0]?.score).map(p=>p.name).slice(0,2).join(' / ')+(rankedPlayers.filter(p=>p.score===rankedPlayers[0]?.score).length>2?' และคนอื่น':'')+' · '+rankedPlayers[0]?.score+'/15':answered===snapshot.players.length?'ผู้เรียนส่งคำตอบครบแล้ว ✨':'กำลังรอคำตอบจากผู้เรียน'}</p>
        </div>}
        {!reveal&&snapshot.players.length>0&&snapshot.players.length<=3&&<div className="score-spotlight" aria-label="ผู้เล่นบนเวที">
          {rankedPlayers.slice(0,3).map((player,index)=><div className="spotlight-person" key={player.id}>
            <div className="spotlight-avatar"><Avatar options={player.avatar} motion={motion}/></div>
            <div className="spotlight-meta"><small>ผู้เล่น {String(index+1).padStart(2,'0')}</small><strong>{player.name}</strong><b>{player.score}<span> / 15</span></b></div>
            <span className={'spotlight-state '+(player.answered?'done':'waiting')}>{player.answered?'✓ ตอบแล้ว':'รอคำตอบ'}</span>
          </div>)}
        </div>}
        {reveal?<div className="reveal-board">
          <div className="reveal-summary" aria-label="จำนวนผู้เรียนในแต่ละผลคำตอบ">
            <span className="summary-correct">✓ ตอบถูก <b>{snapshot.results?.filter(r=>r.status==='correct').length||0}</b></span>
            <span className="summary-incorrect">✕ ตอบผิด <b>{snapshot.results?.filter(r=>r.status==='incorrect').length||0}</b></span>
            <span className="summary-unanswered">– ไม่ได้ตอบ <b>{snapshot.results?.filter(r=>r.status==='unanswered').length||0}</b></span>
            <span className="summary-total">ทั้งหมด {snapshot.results?.length||0} คน</span>
          </div>
          <div className="reveal-tiles" role="list" aria-label="ผลคำตอบผู้เรียนทั้งหมด">
            {([...snapshot.results||[]].sort((a,b)=>({correct:0,incorrect:1,unanswered:2}[a.status]-{correct:0,incorrect:1,unanswered:2}[b.status]))).map(r=>
              <div className={'reveal-person '+r.status} data-answer-status={r.status} role="listitem" key={r.playerId} title={r.name+' · '+(r.status==='correct'?'ตอบถูก':r.status==='incorrect'?'ตอบผิด':'ไม่ได้ตอบ')}>
                <div className="reveal-avatar"><Avatar options={r.avatar} motion={motion}/></div>
                <div className="reveal-details"><strong>{r.name}</strong><small>{r.status==='correct'?'✓ ตอบถูก':r.status==='incorrect'?'✕ ตอบผิด':'– ไม่ได้ตอบ'} {r.choice==null?'':' · '+letters[r.choice]}</small></div>
                <b className="reveal-points">{r.score}<span>/15</span></b>
              </div>)}
          </div>
        </div>
        :<div className={'roster host-scored-roster '+(snapshot.players.length<=3?'few-players':'many-players')+(packedRoster?' packed-players':'')} style={packedRoster?{'--packed-rows':Math.ceil(snapshot.players.length/3),'--cast-rows':Math.ceil(snapshot.players.length/5)} as React.CSSProperties:undefined} role="list" aria-label={'คะแนนและสถานะผู้เรียน '+snapshot.players.length+' คน'}>{rankedPlayers.map(p=><div className={'mini-player '+(p.answered?'answered':'')+(p.score>0&&p.score===rankedPlayers[0]?.score?' cast-leader':'')} key={p.id} role="listitem" title={p.name+' · '+p.score+' คะแนน · '+(p.answered?'ตอบแล้ว':'ยังไม่ตอบ')}><Avatar options={p.avatar}/><strong>{p.name}</strong><small><b>{p.score} / 15</b><span className="packed-answer-state" aria-label={p.answered?'ตอบแล้ว':'ยังไม่ตอบ'}>{p.answered?'✓':'•'}</span><span className="roster-verbose-state"> · {p.answered?'ตอบแล้ว ✓':'ยังไม่ตอบ'}</span></small></div>)}</div>}
      </aside>}
    </section>}

    {session&&snapshot&&finished&&<section className="results-page">
      <div className="card finish-heading enter"><div className="eyebrow">สรุปผลการประเมิน</div><h1>ทุกไอเดียมีพลัง <em>นี่คือทีมของเรา</em></h1><p>ผลคะแนนสะท้อนความเข้าใจพื้นฐาน AI ไม่ใช่การรับรองทักษะปฏิบัติหรือความเชี่ยวชาญ</p>
        {isHost&&<div className="result-host-actions"><button className="button primary result-reset-button" type="button" disabled={busy} onClick={()=>setResetDialog(true)}>↻ เริ่มเกมใหม่</button><button className="button secondary" type="button" onClick={downloadResults}>↓ ดาวน์โหลดคะแนน CSV</button></div>}
        <div className="result-level-overview" aria-label="เกณฑ์ระดับความเข้าใจ AI และจำนวนผู้เรียนแต่ละระดับ">
          <div className="result-level-summary tier-explorer"><strong>นักสำรวจ AI</strong><span>0–5 คะแนน · {snapshot.leaderboard?.filter(p=>p.score<=5).length||0} คน</span></div>
          <div className="result-level-summary tier-builder"><strong>นักต่อยอด AI</strong><span>6–10 คะแนน · {snapshot.leaderboard?.filter(p=>p.score>=6&&p.score<=10).length||0} คน</span></div>
          <div className="result-level-summary tier-aware"><strong>นักรู้ทัน AI</strong><span>11–15 คะแนน · {snapshot.leaderboard?.filter(p=>p.score>=11).length||0} คน</span></div>
        </div>
        {!isHost&&own&&<div className="personal-finish"><div className="result-personal-avatar"><Avatar options={own.avatar}/></div><div><h2>{own.name}</h2><strong className="big-score">{own.score}<small> / 15</small></strong><div className={'result-level-chip tier-'+levelTier(own.score)}>ระดับ: {level(own.score)}</div><p className="level-feedback">{levelFeedback(own.score)}</p></div></div>}
        <div className="podium compact-podium" role="list" aria-label="สามอันดับคะแนนสูงสุด">{snapshot.leaderboard?.filter(p=>p.rank<=3).slice(0,3).map(p=><div className={'podium-person rank-'+p.rank} role="listitem" key={p.id}><span className="result-rank">{p.rank===1?'🏆':'#'+p.rank}</span><div className="result-podium-avatar"><Avatar options={p.avatar}/></div><div className="result-podium-detail"><h2>{p.name}</h2><strong>{p.score} <small>/ 15</small></strong><span className={'result-level-chip tier-'+levelTier(p.score)}>{level(p.score)}</span></div></div>)}</div>
      </div>
      <div className="card scoreboard"><div className="scoreboard-heading"><h2>คะแนนและระดับของผู้เรียนทุกคน <span>{snapshot.players.length} คน</span></h2>{isHost&&<button type="button" className="button secondary export-results" onClick={downloadResults}>↓ ดาวน์โหลดผลคะแนน CSV</button>}</div><div className="score-table" role="table" aria-label="คะแนนผู้เล่นทั้งหมด"><div className="score-row table-heading" role="row"><span>อันดับ</span><span>ผู้เล่น</span><span>คะแนน</span><span>ระดับ</span></div>{snapshot.leaderboard?.map(p=><div className={'score-row '+(p.id===snapshot.caller.playerId?'me':'')} role="row" key={p.id}><strong role="cell">{p.rank}</strong><span className="score-player" role="cell"><span className="result-score-avatar"><Avatar options={p.avatar}/></span><span><strong>{p.name}</strong><small>ถูก {p.correctCount} · ผิด {p.incorrectCount} · ไม่ตอบ {p.unansweredCount}</small><span className={'result-level-inline tier-'+levelTier(p.score)}>ระดับ: {level(p.score)}</span></span></span><strong className="score-value" role="cell">{p.score}<small>/15</small></strong><span className={'result-level-chip score-level tier-'+levelTier(p.score)} role="cell">{level(p.score)}</span></div>)}</div>
        <p className="small-note">ระดับคำนวณจากจำนวนคำตอบถูกเต็ม 15 คะแนน ไม่ใช่การรับรองความเชี่ยวชาญ · คะแนนเท่ากันใช้อันดับร่วมกันครับ</p><div className="level-guide"><span><b>0–5</b> นักสำรวจ AI</span><span><b>6–10</b> นักต่อยอด AI</span><span><b>11–15</b> นักรู้ทัน AI</span></div>
      </div>
    </section>}
    {session&&isHost&&<footer className="host-footer session-footer"><span>{isHost?'ผู้สอนควบคุมคำถามและคะแนน':'ต้องการกลับไปเลือกตัวละครหรือตั้งชื่อใหม่?'}</span><div className="session-actions">{isHost&&!finished&&<button className="button ghost" disabled={!snapshot||busy} onClick={()=>setResetDialog(true)}>↻ เริ่มเกมใหม่</button>}{isHost&&<button className="button secondary" disabled={busy} onClick={()=>setLeaveDialog(true)}>ออกจากเกม</button>}</div></footer>}
    {leaveDialog&&<div className="modal-backdrop"><section className="card reset-modal" role="dialog" aria-modal="true" aria-labelledby="leave-title"><h2 id="leave-title">ออกจากเกมผู้สอนใช่ไหม?</h2><p>คุณจะไม่สามารถกลับมาควบคุมรอบเดิมบนเบราว์เซอร์นี้ได้<br/>คะแนนและคำตอบที่บันทึกไว้จะไม่ถูกลบ<br/>หากต้องการสอนใหม่ สามารถเปิดเกมอีกครั้งได้</p><div className="entry-actions"><button className="button secondary" autoFocus onClick={()=>setLeaveDialog(false)}>ยังอยู่ในห้อง</button><button className="button primary" disabled={busy} onClick={leave}>ยืนยัน ออกจากห้อง</button></div></section></div>}
    {resetDialog&&<div className="modal-backdrop"><section className="card reset-modal" role="dialog" aria-modal="true" aria-labelledby="reset-title"><h2 id="reset-title">เริ่มเกมใหม่และล้างผู้เล่นทั้งหมด?</h2><p>จะสร้างห้องว่างและ QR Code ใหม่ พร้อมลบรายชื่อ ตัวละคร คะแนน และคำตอบของห้องเดิม<br/><strong>ผู้เรียนทุกคนต้องสแกน QR Code ใหม่</strong><br/>หากต้องการเก็บผลคะแนน ให้ดาวน์โหลด CSV ก่อนยืนยัน</p><div className="entry-actions"><button className="button secondary" autoFocus onClick={()=>setResetDialog(false)}>ยังไม่เริ่มใหม่</button><button className="button primary" disabled={busy} onClick={()=>{setResetDialog(false);void send('newroom')}}>ยืนยัน สร้างห้องใหม่</button></div></section></div>}
  </main>;
}
