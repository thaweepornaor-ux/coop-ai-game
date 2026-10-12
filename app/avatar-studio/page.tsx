'use client';
import {useEffect,useState} from 'react';
import {Avatar,AVATAR_OPTIONS,type AvatarOptionKey} from '../components/avatar';
import {CHARACTERS,type CharacterPreset} from '../../shared/characters';
import {renderAvatar} from '../../shared/avatar.js';

const storageKey='coop-ai-avatar-studio-draft-v1';
const nameKey='coop-ai-avatar-studio-name-v1';
const cleanName=(value:unknown)=>typeof value==='string'?Array.from(value.trim()).slice(0,24).join(''):'';
const fields:AvatarOptionKey[]=['skinTone','hairStyle','hairColor','shirtStyle','shirtColor','bottomStyle','bottomColor','shoeColor','glassesStyle','hatStyle','hatColor'];
const defaults:Record<string,string>={bodyStyle:'male',presetId:'M01',skinTone:'warm',hairStyle:'sidepart',hairColor:'black',shirtStyle:'polo',shirtColor:'lightgreen',bottomStyle:'pants',bottomColor:'navy',shoeColor:'white',glassesStyle:'none',hatStyle:'none',hatColor:'navy'};
const titles:Record<string,string>={skinTone:'สีผิว',hairStyle:'ทรงผม',hairColor:'สีผม',shirtStyle:'รูปแบบเสื้อ',shirtColor:'สีเสื้อ',bottomStyle:'กางเกง / กระโปรง',bottomColor:'สีท่อนล่าง',shoeColor:'สีรองเท้า',glassesStyle:'แว่นตา',hatStyle:'หมวก',hatColor:'สีหมวก'};
const valid=(key:AvatarOptionKey,value:unknown)=>typeof value==='string'&&AVATAR_OPTIONS[key].some(item=>item.value===value);
function clean(value:unknown){
 const result={...defaults};
 if(!value||typeof value!=='object'||Array.isArray(value))return result;
 const source=value as Record<string,unknown>;
 for(const field of ['bodyStyle',...fields] as AvatarOptionKey[])if(valid(field,source[field]))result[field]=source[field] as string;
 const preset=CHARACTERS.find(c=>c.id===source.presetId&&c.gender===result.bodyStyle);
 result.presetId=preset?.id||(result.bodyStyle==='female'?'F01':'M01');
 if(result.bodyStyle==='male'&&result.bottomStyle==='skirt')result.bottomStyle='pants';
 return result;
}
export default function AvatarStudio(){
 const [avatar,setAvatar]=useState<Record<string,string>>(defaults);
 const [characterName,setCharacterName]=useState('');
 const [status,setStatus]=useState('ตัวอย่างนี้ใช้ภาพวาด SVG ที่เปลี่ยนชุดได้จริง ภาพ PNG ที่ยังจัดตำแหน่งไม่เสร็จจะไม่ถูกแสดงแทน');
 useEffect(()=>{try{const raw=localStorage.getItem(storageKey);if(raw)setAvatar(clean(JSON.parse(raw)));setCharacterName(cleanName(localStorage.getItem(nameKey)));}catch{}},[]);
 const update=(key:AvatarOptionKey,value:string)=>setAvatar(before=>clean({...before,[key]:value}));
 const preset=(person:CharacterPreset)=>setAvatar(before=>clean({...before,bodyStyle:person.gender,presetId:person.id,skinTone:person.skinTone,hairStyle:person.hairStyle,hairColor:person.hairColor,glassesStyle:person.glasses?'round':'none',bottomStyle:person.bottomStyle,bottomColor:person.bottomColor,shirtColor:person.shirtColor}));
 const save=()=>{try{localStorage.setItem(storageKey,JSON.stringify(clean(avatar)));localStorage.setItem(nameKey,cleanName(characterName));setStatus('บันทึกชื่อตัวละครและชุดทดลองในเบราว์เซอร์นี้แล้ว (ยังไม่เปลี่ยนผู้เล่นในห้องเกม)');}catch{setStatus('บันทึกไม่สำเร็จ: เบราว์เซอร์ไม่อนุญาตให้เก็บข้อมูล');}};
 const reset=()=>{setAvatar({...defaults});setCharacterName('');setStatus('คืนค่าชุดเริ่มต้นแล้ว ยังไม่ได้บันทึก');};
 const exportSvg=()=>{
  try{
   const svg=renderAvatar(avatar);
   const blob=new Blob([svg],{type:'image/svg+xml;charset=utf-8'});
   const url=URL.createObjectURL(blob);
   const link=document.createElement('a');
   link.href=url;link.download='coop-ai-'+avatar.presetId+'-front.svg';document.body.appendChild(link);link.click();link.remove();
   window.setTimeout(()=>URL.revokeObjectURL(url),1000);
   setStatus('ส่งออกภาพ SVG หน้าตรงแล้ว (ภาพตัวอย่าง ไม่ใช่ PNG ต้นฉบับ)');
  }catch{setStatus('ส่งออก SVG ไม่สำเร็จ');}
 };

 const picked=CHARACTERS.find(c=>c.id===avatar.presetId);
 return <main style={{minHeight:'100vh',background:'#f0f4f7',color:'#21313c',padding:'24px 16px',fontFamily:'system-ui,sans-serif'}}>
  <div style={{maxWidth:1080,margin:'0 auto'}}>
   <header style={{marginBottom:20}}><a href="/" style={{color:'#285969'}}>← กลับหน้าเกม</a><h1 style={{fontSize:'clamp(24px,4vw,38px)',margin:'14px 0 8px'}}>ทดลองแต่งตัวละครหน้าตรง</h1><p>เลือกตัวละครชาย–หญิง แล้วเปลี่ยนผม สีผิว เสื้อ กางเกง รองเท้า และเครื่องประดับได้ทันที โดยไม่แก้ห้องเกมจริง</p></header>
   <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(min(100%,320px),1fr))',gap:20,alignItems:'start'}}>
    <section aria-label="ภาพตัวละคร" style={{background:'white',borderRadius:20,padding:20,position:'sticky',top:12,boxShadow:'0 6px 24px #21313c12'}}>
     <h2 style={{fontSize:18}}>{cleanName(characterName)||'ตัวละครของคุณ'} · {picked?.id||avatar.presetId}</h2>
     <div style={{maxWidth:330,margin:'0 auto',height:440,background:'linear-gradient(180deg,#f4faf9,#e0e9f0)',borderRadius:18,overflow:'hidden'}}><Avatar options={avatar} motion={false}/></div>
     <p style={{fontSize:13}}>ภาพตัวอย่าง SVG สำหรับทดสอบการเปลี่ยนชิ้นส่วน ไม่ใช่ภาพ CGI หรือภาพ PNG ที่ตรวจรับแล้ว</p>
     <div style={{display:'flex',gap:8,flexWrap:'wrap'}}><button type="button" onClick={save} style={{padding:'12px 18px',borderRadius:10,background:'#18594b',color:'white',border:0,cursor:'pointer'}}>บันทึกชุดทดลอง</button><button type="button" onClick={exportSvg} style={{padding:'12px 18px',borderRadius:10,cursor:'pointer'}}>ส่งออก SVG</button><button type="button" onClick={reset} style={{padding:'12px 18px',borderRadius:10,cursor:'pointer'}}>เริ่มใหม่</button></div>
     <p role="status" style={{fontSize:13}}>{status}</p>
    </section>
    <section aria-label="เครื่องมือแต่งตัว" style={{background:'white',borderRadius:20,padding:20,boxShadow:'0 6px 24px #21313c12'}}>
     <h2 style={{fontSize:18}}>เลือกตัวละคร · 20 แบบ</h2>
     <label style={{display:"block",fontWeight:600,marginBottom:16}}>ตั้งชื่อตัวละครของคุณ<input type="text" maxLength={24} autoComplete="off" placeholder="เช่น ปิง" value={characterName} onChange={e=>setCharacterName(cleanName(e.target.value))} style={{display:"block",width:"100%",boxSizing:"border-box",padding:12,marginTop:6,border:"1px solid #9cb4bc",borderRadius:10,fontSize:16}}/><small style={{fontWeight:400}}>ชื่อสูงสุด 24 ตัวอักษร · ไม่เปลี่ยนรหัส M01–M10 หรือ F01–F10</small></label>
     <div style={{display:'flex',gap:8,marginBottom:12}}>{(['male','female'] as const).map(g=><button type="button" aria-pressed={avatar.bodyStyle===g} key={g} onClick={()=>preset(CHARACTERS.find(c=>c.gender===g)!)} style={{flex:1,padding:12,borderRadius:10,border:'1px solid #9bb4bc',background:avatar.bodyStyle===g?'#d8ede5':'#fff',cursor:'pointer'}}>{g==='male'?'ชาย 10 แบบ':'หญิง 10 แบบ'}</button>)}</div>
     <div style={{display:'grid',gridTemplateColumns:'repeat(5,minmax(0,1fr))',gap:6,marginBottom:18}}>{CHARACTERS.filter(p=>p.gender===avatar.bodyStyle).map(p=><button key={p.id} type="button" aria-label={p.id+' '+p.label} aria-pressed={avatar.presetId===p.id} title={p.label} onClick={()=>preset(p)} style={{padding:'11px 2px',border:'1px solid #99adb5',borderRadius:9,background:avatar.presetId===p.id?'#cdebdc':'white',cursor:'pointer',fontSize:12}}>{p.id}</button>)}</div>
     {fields.map(key=><label key={key} style={{display:'block',marginBottom:14,fontWeight:600}}>{titles[key]}<select aria-label={titles[key]} value={avatar[key]} onChange={e=>update(key,e.target.value)} style={{display:'block',width:'100%',marginTop:5,padding:12,border:'1px solid #9cb4bc',borderRadius:10,background:'white',fontSize:15}}>{AVATAR_OPTIONS[key].map(option=><option value={option.value} key={option.value}>{option.label}</option>)}</select></label>)}
    </section>
   </div>
  </div>
 </main>;
}
