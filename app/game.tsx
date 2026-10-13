'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import QRCode from 'qrcode';
import Image from 'next/image';
import { Avatar, AVATAR_OPTIONS } from './components/avatar';
import { normalizeWardrobe } from '../shared/avatar-registry';
import {STUDIO_TRANSFER_KEY,validateStudioTransfer} from '../shared/avatar-studio-transfer.js';
import { SimpleWardrobe } from './components/simple-wardrobe';
import { LOGO_SRC, COOPERATIVE_NAME } from '../shared/brand';

type Role='choose'|'host'|'player';
type Session={room:string;token:string;role:'host'|'player'};
type Person={id:string;name:string;avatar:Record<string,string>;score:number;level?:string;answered?:boolean};
type Result={playerId:string;name:string;avatar:Record<string,string>;choice:number|null;correct:boolean|null;status:'correct'|'incorrect'|'unanswered';score:number};
type Leader=Person&{rank:number;correctCount:number;incorrectCount:number;unansweredCount:number};
type Snapshot={serverNow:number;caller:{role:'host'|'player';playerId?:string};room:{code:string;phase:'lobby'|'question'|'closed'|'reveal'|'finished';questionIndex:number;roundId:number;deadline:number|null};question?:{number:number;topic:string;question:string;options:readonly string[]};players:Person[];ownAnswer?:{choice:number;submittedAt:number}|null;results?:Result[];correctAnswer?:number;explanation?:string;leaderboard?:Leader[]};
type ApiResponse={roomCode?:string;token?:string;role?:'host'|'player';snapshot?:Snapshot;error?:string;code?:string}&Partial<Snapshot>;
const letters=['ก','ข','ค'];
const keys=Object.keys(AVATAR_OPTIONS) as (keyof typeof AVATAR_OPTIONS)[];
const initialAvatar=()=>({...Object.fromEntries(keys.map(k=>[k,AVATAR_OPTIONS[k][0].value])),shirtColor:'white',bodyStyle:'male',presetId:'M01',bottomStyle:'pants',bottomColor:'navy',shoeColor:'white',hairStyle:'sidepart',glassesStyle:'none'});
const level=(n:number)=>n<=5?'นักสำรวจ AI':n<=10?'นักต่อยอด AI':'นักรู้ทัน AI';
const levelFeedback=(n:number)=>n<=5?'เริ่มจากงานร่างข้อความ แล้วฝึกบอก AI ให้เข้าใจงานที่ต้องการ':n<=10?'เข้าใจหลายเรื่องแล้ว ลองฝึกให้บริบทและตรวจคำตอบกับข้อมูลต้นทาง':'พื้นฐานแน่น ลองเลือกงานสหกรณ์หนึ่งงานที่ตรวจผลได้ แล้วนำ AI มาช่วย';
const safeRead=(key:string)=>{try{return localStorage.getItem(key)}catch{return null}};
const safeWrite=(key:string,value:string)=>{try{localStorage.setItem(key,value)}catch{}};
const sessionKey=(role:Role)=>'coop-ai-game-session-'+role;

function ArenaLights({celebrate=false}:{celebrate?:boolean}) {
 return <div className="arena-lighting" aria-hidden="true"><div className="spotlight spotlight-left"/><div className="spotlight spotlight-right"/><div className="arena-grid"/><div className="studio-sparkles">{Array.from({length:14},(_,i)=><i className="studio-sparkle" key={i} style={{left:((i*37+7)%94+3)+'%',top:((i*53+11)%88+6)+'%',width:(4+i%3*2)+'px',height:(4+i%3*2)+'px',animationDelay:-(i*.7)+'s',animationDuration:(4.8+i%5*1.2)+'s'}}/>)}</div>{celebrate&&<div className="confetti-burst">{Array.from({length:16},(_,i)=><i key={i} style={{left:(8+i*6)+'%',animationDelay:(i%4)*.15+'s',background:i%3===0?'#cbe997':i%3===1?'#46dbb5':'#e7c46a'}}/>)}</div>}</div>;
}
function RulesStrip(){return <div className="rules-strip"><div><b>15</b><span>คำถาม AI</span></div><div><b>15<small> วิ</small></b><span>ต่อหนึ่งคำถาม</span></div><div><b>1<small> แต้ม</small></b><span>เมื่อตอบถูก</span></div></div>}
export default function Game({initialRole='choose'}:{initialRole?:Role}){
  const [role,setRole]=useState<Role>(initialRole),[session,setSession]=useState<Session|null>(null);
  const [snapshot,setSnapshot]=useState<Snapshot|null>(null);
  const [roomInput,setRoomInput]=useState(''),[name,setName]=useState(''),[avatar,setAvatar]=useState<Record<string,string>>(initialAvatar);
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[network,setNetwork]=useState<'connecting'|'online'|'offline'>('connecting');
  const [now,setNow]=useState(Date.now()),[qr,setQr]=useState(''),[joinUrl,setJoinUrl]=useState('');
  const [sound,setSound]=useState(true),[motion,setMotion]=useState(true),[pendingChoice,setPendingChoice]=useState<number|null>(null),[resetDialog,setResetDialog]=useState(false),[leaveDialog,setLeaveDialog]=useState(false);
  const [copied,setCopied]=useState(false),[showRecovery,setShowRecovery]=useState(false);
  const offset=useRef(0),lastSync=useRef(0),generation=useRef(0),sessionRef=useRef<Session|null>(null);
  const snapshotRef=useRef<Snapshot|null>(null),busyRef=useRef(false);
  const audio=useRef<AudioContext|null>(null),lastBeep=useRef(''),lastEffect=useRef('');
  const timer= snapshot?.room.deadline ? Math.max(0,Math.ceil((snapshot.room.deadline-(now+offset.current))/1000)):15;
  const timeOpen=snapshot?.room.phase==='question'&&timer>0;
  const isHost=session?.role==='host';
  const canInteract=network==='online'&&now-lastSync.current<4500&&!busy;

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
      try{const saved=JSON.parse(safeRead(sessionKey(initialRole))||'null') as Session|null;
      if(saved&&saved.role===initialRole&&saved.token&&(!code||saved.room===code)){sessionRef.current=saved;setSession(saved)}}catch{}
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
    if(initialRole==='host'&&!sessionRef.current&&!busyRef.current)void send('create');
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
        if(!response.ok){if(response.status===401||response.status===404){setError(session!.role==='host'?'การเชื่อมต่อเกมเดิมหมดอายุ กด “เริ่มเกมใหม่” เพื่อแสดง QR Code ใหม่ครับ':'ไม่สามารถกลับเข้าเกมนี้ได้ กรุณาสแกน QR Code ของผู้สอนอีกครั้งครับ');setShowRecovery(true)}throw new Error(data.error||'เชื่อมต่อไม่ได้')}
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
  useEffect(()=>{setPendingChoice(null)},[snapshot?.room.roundId,snapshot?.room.questionIndex]);
  async function send(action:string,extra:Record<string,unknown>={}){
    if(busyRef.current)return;busyRef.current=true;unlockAudio();setBusy(true);setError('');
    const requestGeneration=generation.current,requestSession=sessionRef.current;
    const started=Date.now();const controller=new AbortController();const timeout=window.setTimeout(()=>controller.abort(),8000);
    try{
      const current=sessionRef.current;
      const payload={action,...(current?{room:current.room,roundId:snapshot?.room.roundId,questionIndex:snapshot?.room.questionIndex}:{}),...extra};
      const response=await fetch('/api/game',{method:'POST',headers:{'Content-Type':'application/json',...(current?{Authorization:'Bearer '+current.token}:{})},body:JSON.stringify(payload),signal:controller.signal});
      const data=await response.json() as ApiResponse;
      if(requestGeneration!==generation.current||requestSession!==sessionRef.current)return;
      if(!response.ok){if(data.snapshot)acceptState(data.snapshot,started,Date.now());throw new Error(data.error||'ทำรายการไม่สำเร็จ')}
      if(data.token&&data.roomCode&&data.role){
        const value:Session={token:data.token,room:data.roomCode,role:data.role};
        sessionRef.current=value;setSession(value);safeWrite(sessionKey(data.role),JSON.stringify(value));
      }
      const state=data.snapshot||(data.room?data as Snapshot:undefined);
      if(state)acceptState(state,started,Date.now());
    }catch(e){if(requestGeneration!==generation.current||requestSession!==sessionRef.current)return;setError(e instanceof Error&&e.name==='AbortError'?'การเชื่อมต่อช้า กำลังตรวจสถานะล่าสุด กรุณารอสักครู่':e instanceof Error?e.message:'เชื่อมต่อไม่ได้');
      if(action==='answer')setPendingChoice(null);
    }finally{window.clearTimeout(timeout);busyRef.current=false;setBusy(false)}
  }
  function join(){
    const code=roomInput.toUpperCase().trim(),playerName=name.trim();
    if(!/^[A-Z0-9]{6}$/.test(code)){setError('กรุณาสแกน QR Code บนจอผู้สอนอีกครั้งครับ');return}
    if(!playerName){setError('ตั้งชื่อผู้เล่นก่อนครับ');return}
    safeWrite('coop-ai-game-name',playerName);safeWrite('coop-ai-game-avatar',JSON.stringify(avatar));
    void send('join',{room:code,name:playerName,avatar});
  }
  function leave(){
    generation.current++;try{localStorage.removeItem(sessionKey(role))}catch{}
    sessionRef.current=null;snapshotRef.current=null;setSession(null);setSnapshot(null);setError('');setShowRecovery(false);setNetwork('connecting');setRoomInput('');setPendingChoice(null);setResetDialog(false);setLeaveDialog(false);setQr('');setJoinUrl('');
  }
  function restartHost(){
    // A saved instructor credential can expire between training days.
    // Release only this browser's stale session before opening a fresh QR invitation.
    leave();
    void send('create');
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

  return <main className={'game-shell '+(motion?'motion-on':'motion-off')} data-role={role}>
    <ArenaLights celebrate={reveal||finished}/>
    <header className="topbar">
      <a className="brand" href="/"><Image src={LOGO_SRC} width={58} height={61} sizes="58px" priority alt={'โลโก้ '+COOPERATIVE_NAME}/><span><small>{COOPERATIVE_NAME}</small><strong>ประเมินความเข้าใจ AI</strong></span></a>
      <div className="preferences">
        <button className="icon-button" type="button" aria-label={sound?'ปิดเสียง':'เปิดเสียง'} aria-pressed={sound} onClick={()=>{unlockAudio();setSound(v=>{safeWrite('coop-ai-game-sound',v?'off':'on');return !v})}}>{sound?'♪ เสียงเปิด':'♪ เสียงปิด'}</button>
        <button className="icon-button" type="button" aria-label="เปิดหรือปิดการเคลื่อนไหว" aria-pressed={motion} onClick={()=>setMotion(v=>!v)}>{motion?'✦ เอฟเฟกต์เปิด':'✦ เอฟเฟกต์ปิด'}</button>
      </div>
    </header>
    {error&&<div className="notice error" role="alert">{error}</div>}
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
      <div className="card lobby-main enter"><div className="badge">{isHost?'รอผู้เรียนเข้าร่วม':'YOU ARE IN'}</div><h1>{isHost?'สแกนเพื่อเข้าร่วมเกม':'เตรียมพร้อม ภารกิจกำลังเริ่ม'}</h1>
        {isHost?<><div className="join-ticket simple-join-ticket"><div className="qr">{qr?<img src={qr} alt="QR สำหรับผู้เล่นเข้าห้อง"/>:<span>กำลังสร้าง QR…</span>}</div><div><h2>สแกน QR Code เพื่อเข้าเล่น</h2><p>เลือกตัวละคร → ตั้งชื่อ → รอเริ่มเกม</p><strong className="room-code sr-only">{session.room}</strong><button className="button secondary" type="button" onClick={()=>void copyJoin()}>{copied?'คัดลอกแล้ว ✓':'คัดลอกลิงก์สำหรับผู้เรียน'}</button><input className="join-url sr-only" aria-label="ลิงก์ผู้เล่น" value={joinUrl} readOnly onFocus={e=>e.target.select()}/></div></div><button className="button primary" disabled={!canInteract||snapshot.players.length===0} onClick={()=>void send('start')}>เริ่มเกมกับผู้เล่น {snapshot.players.length} คน →</button></>
        :<><Avatar options={own?.avatar||avatar} className="waiting-avatar" interactive motion={motion}/><h2>{own?.name||name}</h2><p>ผู้สอนจะเป็นคนเริ่มเกม<br/>ข้อละ 15 วินาที ตอบถูกได้ 1 คะแนน</p><div className="waiting-dots" aria-label="กำลังรอผู้สอน"><i/><i/><i/></div></>}
      </div>
      <div className="card roster-panel"><h2>ผู้เข้าร่วม <span>{snapshot.players.length} คน</span></h2><div className="roster">{snapshot.players.map(p=><div className="mini-player" key={p.id}><Avatar options={p.avatar}/><strong>{p.name}</strong></div>)}</div>{snapshot.players.length===0&&<p>รอผู้เรียนสแกน QR Code ครับ</p>}</div>
    </section>}

    {session&&snapshot&&snapshot.room.phase!=='lobby'&&!finished&&<section className={'question-layout '+(isHost?'host-question':'player-question')}>
      <div className="card question-card enter" key={snapshot.room.roundId+':'+snapshot.room.questionIndex}>
        <div className="question-meta"><span className="badge">ข้อ {(snapshot.question?.number||snapshot.room.questionIndex+1)} / 15</span><div className={'countdown '+(timer<=5&&!reveal?'urgent':'')} style={{'--remaining':(reveal?1:timer/15)} as React.CSSProperties} role="timer" aria-label={reveal?'เฉลยแล้ว':'เหลือ '+timer+' วินาที'}>{reveal?'✓':timer}<small>{reveal?'เฉลย':'วินาที'}</small></div></div>
        <div className="mission-progress" aria-label={'ความคืบหน้า ข้อ '+(snapshot.room.questionIndex+1)+' จาก 15'}>{Array.from({length:15},(_,i)=><i key={i} className={i<snapshot.room.questionIndex?'complete':i===snapshot.room.questionIndex?'current':''}/>)}</div>
        <p className="topic"><span>คำถาม {String(snapshot.room.questionIndex+1).padStart(2,'0')}</span> {snapshot.question?.topic}</p><h1>{snapshot.question?.question}</h1>
        <div className="answer-grid">{snapshot.question?.options.map((option,i)=>{
          const picked=snapshot.ownAnswer?.choice===i||pendingChoice===i;
          const correct=reveal&&snapshot.correctAnswer===i;
          return <button key={i} className={'answer answer-'+i+(picked?' picked':'')+(correct?' correct':'')+(reveal&&picked&&!correct?' wrong':'')} disabled={!!isHost||!timeOpen||!canInteract||snapshot.ownAnswer!=null||pendingChoice!==null} onClick={()=>chooseAnswer(i)}><span className="answer-letter">{correct?'✓':letters[i]}</span><span>{option}</span>{picked&&!reveal&&<span className="picked-mark">✓</span>}</button>
        })}</div>
        {!isHost&&!reveal&&<p className="answer-status" role="status">{snapshot.ownAnswer?'ส่งคำตอบแล้ว รอเฉลยครับ':pendingChoice!==null?'กำลังส่งคำตอบ…':closed?'หมดเวลาแล้ว รอผู้สอนเปิดเฉลย':'เลือกคำตอบที่เหมาะสมที่สุดหนึ่งข้อ'}</p>}
        {isHost&&!reveal&&<div className="host-controls"><span>ตอบแล้ว <strong>{answered} / {snapshot.players.length}</strong> คน</span><button className="button primary" disabled={!canInteract} onClick={()=>void send('reveal')}>{timeOpen?'ปิดรับคำตอบและเปิดเฉลย':'เปิดเฉลย ✦'}</button></div>}
        {reveal&&<div className="explanation"><h2>คำตอบ: {letters[snapshot.correctAnswer??0]} · {snapshot.question?.options[snapshot.correctAnswer??0]}</h2><p>{snapshot.explanation}</p></div>}
        {reveal&&!isHost&&<div className={'own-result '+(ownResult?.status||'unanswered')} role="status"><strong>{ownResult?.status==='correct'?'ตอบถูก! เก่งมาก ✦':ownResult?.status==='incorrect'?'ข้อนี้ยังไม่ถูก ลองดูเฉลยกัน':'ข้อนี้ไม่ได้ตอบ ไม่เป็นไร เรียนรู้ไปด้วยกัน'}</strong><span>คะแนนตอนนี้ {ownResult?.score??own?.score??0} / 15</span><Avatar options={own?.avatar||avatar}/><p>รอผู้สอนเริ่มข้อถัดไป</p></div>}
        {reveal&&isHost&&<div className="host-controls"><span>อ่านเฉลยและคุยทบทวนได้เต็มที่</span><button className="button primary" disabled={!canInteract} onClick={()=>void send(snapshot.room.questionIndex===14?'finish':'next')}>{snapshot.room.questionIndex===14?'ดูสรุปคะแนน 🏆':'เริ่มข้อถัดไป →'}</button></div>}
      </div>
      {isHost&&<aside className="card question-roster"><h2>{reveal?'ผลคำตอบข้อนี้':'คะแนนสะสม'} {!reveal&&<span className="host-score-count">ส่งคำตอบแล้ว {answered} / {snapshot.players.length}</span>}</h2>
        {reveal?<div className="reveal-groups">{(['correct','incorrect','unanswered'] as const).map(status=><div className={'result-group '+status} key={status}><h3>{status==='correct'?'✓ ตอบถูก':status==='incorrect'?'↻ ตอบผิด':'— ไม่ได้ตอบ'} <span>{snapshot.results?.filter(r=>r.status===status).length||0} คน</span></h3>{snapshot.results?.filter(r=>r.status===status).map(r=><div className="result-person" key={r.playerId}><Avatar options={r.avatar}/><span>{r.name}<small>{r.choice==null?'ไม่ได้เลือก':('เลือก '+letters[r.choice])}</small></span><strong>{r.score} คะแนน</strong></div>)}</div>)}</div>
        :<div className="roster host-scored-roster">{rankedPlayers.map(p=><div className={'mini-player '+(p.answered?'answered':'')} key={p.id}><Avatar options={p.avatar}/><strong>{p.name}</strong><small><b>{p.score} / 15</b> · {p.answered?'ตอบแล้ว ✓':'ยังไม่ตอบ'}</small></div>)}</div>}
      </aside>}
    </section>}

    {session&&snapshot&&finished&&<section className="results-page">
      <div className="card finish-heading enter"><div className="eyebrow">สรุปผลการประเมิน</div><h1>ทุกไอเดียมีพลัง<br/><em>นี่คือทีมของเรา</em></h1><p>ผลสะท้อนความเข้าใจพื้นฐาน AI จากคำถามชุดนี้<br/>ไม่ใช่การรับรองทักษะปฏิบัติหรือความเชี่ยวชาญ</p>
        {!isHost&&own&&<div className="personal-finish"><Avatar options={own.avatar}/><div><h2>{own.name}</h2><strong className="big-score">{own.score}<small> / 15</small></strong><div className="level-badge">{level(own.score)}</div><p className="level-feedback">{levelFeedback(own.score)}</p></div></div>}
        {<div className="podium">{snapshot.leaderboard?.filter(p=>p.rank<=3).slice(0,3).map(p=><div className={'podium-person rank-'+p.rank} key={p.id}><span>{String(p.rank).padStart(2,'0')}</span><Avatar options={p.avatar}/><h2>{p.name}</h2><strong>{p.score} / 15</strong></div>)}</div>}
      </div>
      <div className="card scoreboard"><h2>คะแนนทุกคน <span>{snapshot.players.length} คน</span></h2><div className="score-table" role="table" aria-label="คะแนนผู้เล่นทั้งหมด"><div className="score-row table-heading" role="row"><span>อันดับ</span><span>ผู้เล่น</span><span>คะแนน</span><span>ระดับ</span></div>{snapshot.leaderboard?.map(p=><div className={'score-row '+(p.id===snapshot.caller.playerId?'me':'')} role="row" key={p.id}><strong role="cell">{p.rank}</strong><span className="score-player" role="cell"><Avatar options={p.avatar}/><span><strong>{p.name}</strong><small>ถูก {p.correctCount} · ผิด {p.incorrectCount} · ไม่ตอบ {p.unansweredCount}</small></span></span><strong className="score-value" role="cell">{p.score}<small>/15</small></strong><span className="level-badge" role="cell">{level(p.score)}</span></div>)}</div>
        <p className="small-note">คะแนนเท่ากันใช้อันดับร่วมกันครับ</p><div className="level-guide"><span><b>0–5</b> นักสำรวจ AI</span><span><b>6–10</b> นักต่อยอด AI</span><span><b>11–15</b> นักรู้ทัน AI</span></div>
      </div>
    </section>}
    {session&&<footer className="host-footer session-footer"><span>{isHost?'ผู้สอนควบคุมคำถามและคะแนน':'ต้องการกลับไปเลือกตัวละครหรือตั้งชื่อใหม่?'}</span><div className="session-actions">{isHost&&<button className="button ghost" disabled={!snapshot||busy} onClick={()=>setResetDialog(true)}>↻ เริ่มรอบใหม่</button>}<button className="button secondary" disabled={busy} onClick={()=>isHost?setLeaveDialog(true):leave()}>ออกจากเกม</button></div></footer>}
    {leaveDialog&&<div className="modal-backdrop"><section className="card reset-modal" role="dialog" aria-modal="true" aria-labelledby="leave-title"><h2 id="leave-title">ออกจากเกมผู้สอนใช่ไหม?</h2><p>คุณจะไม่สามารถกลับมาควบคุมรอบเดิมบนเบราว์เซอร์นี้ได้<br/>คะแนนและคำตอบที่บันทึกไว้จะไม่ถูกลบ<br/>หากต้องการสอนใหม่ สามารถเปิดเกมอีกครั้งได้</p><div className="entry-actions"><button className="button secondary" autoFocus onClick={()=>setLeaveDialog(false)}>ยังอยู่ในห้อง</button><button className="button primary" disabled={busy} onClick={leave}>ยืนยัน ออกจากห้อง</button></div></section></div>}
    {resetDialog&&<div className="modal-backdrop"><section className="card reset-modal" role="dialog" aria-modal="true" aria-labelledby="reset-title"><h2 id="reset-title">เริ่มรอบใหม่ไหม?</h2><p>คะแนนและคำตอบรอบนี้จะถูกล้าง<br/>ชื่อกับตัวละครของทุกคนยังอยู่</p><div className="entry-actions"><button className="button secondary" autoFocus onClick={()=>setResetDialog(false)}>ยังไม่เริ่มใหม่</button><button className="button primary" disabled={busy} onClick={()=>{setResetDialog(false);void send('reset')}}>ยืนยัน เริ่มรอบใหม่</button></div></section></div>}
  </main>;
}
