'use client';
import {useEffect,useState} from 'react';
import {PNG_PARTS} from '../../shared/avatar-png-catalog.js';

type Part = {src:string;label:string;ready:boolean;aligned:boolean};
type Category = 'face'|'hair'|'top'|'bottom'|'shoes';
const order:Category[]=['bottom','shoes','top','face','hair'];
const labels:Record<Category,string>={face:'ใบหน้า',hair:'ทรงผม',top:'เสื้อ',bottom:'กางเกง',shoes:'รองเท้า'};
const storageKey='coop-ai-game-png-alignment-v1';
const selectionKey='coop-ai-game-png-selections-v1';
const defaults:Record<Category,{x:number;y:number;scale:number}>={
 face:{x:50,y:22,scale:40},hair:{x:50,y:14,scale:46},
 top:{x:50,y:51,scale:60},bottom:{x:50,y:73,scale:52},shoes:{x:50,y:92,scale:38}
};

/** An isolated alignment workspace. Never replaces the playable avatar. */
export function PngAssemblyPreview({gender}:{gender:'male'|'female'}){
 const [picked,setPicked]=useState<Partial<Record<Category,string>>>({});
 const [positions,setPositions]=useState(defaults);
 const [editing,setEditing]=useState<Category>('face');
 const [saved,setSaved]=useState('');
 const [broken,setBroken]=useState<string[]>([]);
 const [hidden,setHidden]=useState<Category[]>([]);
 const [opacity,setOpacity]=useState(100);
 const [exporting,setExporting]=useState(false);
 useEffect(()=>{
  try {
   const raw=localStorage.getItem(storageKey);
   if(!raw)return;
   const decoded=JSON.parse(raw) as unknown;
   if(!decoded||typeof decoded!=='object')return;
   const data=decoded as Record<string,unknown>;
   const verified={} as typeof defaults;
   for(const category of order){
    const item=data[category];
    if(!item||typeof item!=='object')return;
    const v=item as Record<string,unknown>;
    if(!(['x','y','scale'] as const).every(key=>typeof v[key]==='number'&&Number.isFinite(v[key])&&v[key]>=0&&v[key]<=100))return;
    verified[category]={x:v.x as number,y:v.y as number,scale:v.scale as number};
   }
   setPositions(verified);
   setSaved('โหลดตำแหน่งที่บันทึกไว้แล้ว');
  }catch{}
 },[]);
 useEffect(()=>{
  try{
   const raw=localStorage.getItem(selectionKey);
   if(!raw)return;
   const value=JSON.parse(raw) as unknown;
   if(!value||typeof value!=='object'||Array.isArray(value))return;
   const data=value as Record<string,unknown>;
   const valid:Partial<Record<Category,string>>={};
   for(const category of order){
    const src=data[category];
    if(typeof src==='string'&&PNG_PARTS[category].some(part=>part.ready&&part.src===src))valid[category]=src;
   }
   // The selected face follows the current gender; do not resurrect a saved opposite-gender face.
   delete valid.face;
   setPicked(valid);
  }catch{}
 },[]);
 const save=()=>{
  try{localStorage.setItem(storageKey,JSON.stringify(positions));localStorage.setItem(selectionKey,JSON.stringify({...picked,face:undefined}));setSaved('บันทึกตำแหน่งและภาพที่เลือกไว้บนอุปกรณ์นี้แล้ว');}
  catch{setSaved('ไม่สามารถบันทึกบนอุปกรณ์นี้ได้');}
 };
 const lists=Object.fromEntries(order.map(category=>[category,PNG_PARTS[category].filter(p=>p.ready)])) as Record<Category,Part[]>;
 const active=(category:Category)=>category==='face'
  ? lists.face.find(p=>p.src.endsWith('/'+gender+'.png'))
  : lists[category].find(p=>p.src===picked[category])||lists[category][0];
 const exportComposite=async()=>{
  setExporting(true);
  try{
   const canvas=document.createElement('canvas');
   canvas.width=600;canvas.height=800;
   const ctx=canvas.getContext('2d');
   if(!ctx)throw new Error('Canvas unavailable');
   // Export the real sprite layers, not the SVG fallback.
   for(const category of order){
    const part=active(category);
    if(!part||hidden.includes(category)||broken.includes(part.src))continue;
    const image=new Image();
    image.src=part.src;
    await image.decode();
    const pos=positions[category];
    const width=canvas.width*pos.scale/100;
    const height=Math.min(width*image.naturalHeight/image.naturalWidth,canvas.height*0.65);
    const drawWidth=height===canvas.height*0.65?height*image.naturalWidth/image.naturalHeight:width;
    ctx.globalAlpha=editing===category?opacity/100:1;
    ctx.drawImage(image,canvas.width*pos.x/100-drawWidth/2,canvas.height*pos.y/100-height/2,drawWidth,height);
   }
   ctx.globalAlpha=1;
   const blob=await new Promise<Blob>((resolve,reject)=>canvas.toBlob(value=>value?resolve(value):reject(new Error('PNG export failed')),'image/png'));
   const url=URL.createObjectURL(blob);
   const anchor=document.createElement('a');
   anchor.href=url;anchor.download='coop-avatar-png-preview.png';
   anchor.click();
   URL.revokeObjectURL(url);
   setSaved('ส่งออกภาพประกอบ PNG สำหรับตรวจสอบแล้ว (ยังไม่ใช้เป็นตัวละครหลัก)');
  }catch{
   setSaved('ส่งออก PNG ไม่สำเร็จ กรุณาตรวจสอบไฟล์ภาพที่เลือก');
  }finally{setExporting(false);}
 };
 const current=positions[editing];
 const update=(key:'x'|'y'|'scale',v:number)=>setPositions(prev=>({...prev,[editing]:{...prev[editing],[key]:v}}));
 return <section aria-label="ทดลองจัดตำแหน่งภาพ PNG" style={{marginTop:20,padding:16,border:'1px solid #92a5ae',borderRadius:16}}>
  <h3>ทดลองประกอบภาพ PNG จริง</h3>
  <p style={{fontSize:12}}>พื้นที่ทดลองแยกจากตัวละครที่ใช้เล่น ภาพบางชิ้นยังไม่ตรงสัดส่วน ต้องปรับก่อนนำไปใช้จริง</p>
  <div style={{position:'relative',margin:'14px auto',width:'min(100%,280px)',aspectRatio:'3 / 4',borderRadius:12,background:'linear-gradient(#eef5f5,#d6e5ed)',overflow:'hidden'}}>
    {order.map((category,i)=>{const part=active(category);const a=positions[category];return part&&!broken.includes(part.src)&&!hidden.includes(category)?<img key={category} src={part.src} alt={part.label} onError={()=>setBroken(prev=>prev.includes(part.src)?prev:[...prev,part.src])} style={{position:'absolute',width:a.scale+'%',height:'auto',maxHeight:'65%',objectFit:'contain',opacity:editing===category?opacity/100:1,left:a.x+'%',top:a.y+'%',transform:'translate(-50%,-50%)',zIndex:i+1,pointerEvents:'none'}}/>:null})}
  </div>
  {broken.length>0&&<div role="alert" style={{fontSize:12,color:'#a12626'}}>โหลดภาพบางชิ้นไม่สำเร็จ: {broken.length} ภาพ <button type="button" onClick={()=>setBroken([])} style={{padding:6,marginLeft:6}}>ลองโหลดภาพอีกครั้ง</button></div>}
  <label style={{display:'block',fontSize:13}}>ชิ้นส่วนที่ต้องการปรับ
   <select value={editing} onChange={e=>setEditing(e.target.value as Category)} style={{display:'block',width:'100%',padding:8}}>
    {order.map(key=><option key={key} value={key}>{labels[key]}</option>)}
   </select>
  </label>
  {editing!=='face'&&lists[editing].length>1&&<label style={{display:'block',marginTop:8}}>เลือกภาพ
   <select value={active(editing)?.src||''} onChange={e=>setPicked(prev=>({...prev,[editing]:e.target.value}))} style={{display:'block',width:'100%',padding:8}}>
    {lists[editing].map(part=><option key={part.src} value={part.src}>{part.label}</option>)}
   </select>
  </label>}
  <label style={{display:'block',marginTop:10,fontSize:13}}>
   <input type="checkbox" checked={!hidden.includes(editing)} onChange={e=>setHidden(prev=>e.target.checked?prev.filter(x=>x!==editing):[...prev.filter(x=>x!==editing),editing])}/>
   {' '}แสดงภาพ{labels[editing]}
  </label>
  <label style={{display:'block',marginTop:10,fontSize:13}}>ความโปร่งใสขณะปรับชิ้นส่วน: {opacity}%
   <input type="range" min={20} max={100} step={5} value={opacity} onChange={e=>setOpacity(Number(e.target.value))} style={{display:'block',width:'100%'}}/>
  </label>
  {(['x','y','scale'] as const).map(key=><label key={key} style={{display:'block',marginTop:10,fontSize:13}}>{key==='x'?'แนวนอน':key==='y'?'แนวตั้ง':'ขนาด'}: {current[key]}%
    <input type="range" min={key==='scale'?10:0} max={key==='scale'?100:100} value={current[key]} onChange={e=>update(key,Number(e.target.value))} style={{display:'block',width:'100%'}}/>
  </label>)}
  <div style={{display:'flex',gap:8,flexWrap:'wrap',marginTop:10}}>
   <button type="button" onClick={save} style={{padding:9}}>บันทึกตำแหน่งและภาพ</button>
   <button type="button" disabled={exporting} onClick={exportComposite} style={{padding:9}}>{exporting?"กำลังสร้าง PNG...":"ส่งออกภาพประกอบ PNG"}</button>
   <button type="button" onClick={()=>{setPositions(defaults);setPicked({});setSaved('คืนตำแหน่งและภาพเริ่มต้นแล้ว (ยังไม่ได้บันทึก)')}} style={{padding:9}}>คืนตำแหน่งเริ่มต้น</button>
  </div>
  {saved&&<p role="status" style={{fontSize:12}}>{saved}</p>}
 </section>;
}
