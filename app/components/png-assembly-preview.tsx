'use client';
import {useEffect,useState} from 'react';
import {PNG_PARTS} from '../../shared/avatar-png-catalog.js';
import {avatarLayerRect,AVATAR_CANVAS_WIDTH,AVATAR_CANVAS_HEIGHT} from '../../shared/avatar-png-layout.js';
import {validateAssemblySnapshot,PNG_ASSEMBLY_VERSION} from '../../shared/avatar-png-snapshot.js';
import {avatarArtReadiness} from '../../shared/avatar-art-readiness.js';

type Part = {src:string;label:string;ready:boolean;aligned:boolean;gender?:'male'|'female';playable?:boolean};
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
 const [dimensions,setDimensions]=useState<Record<string,{width:number;height:number}>>({});
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
    if(typeof src==='string'&&PNG_PARTS[category].some(part=>part.ready&&part.playable!==false&&part.src===src&&(!part.gender||part.gender===gender)))valid[category]=src;
   }
   // The selected face follows the current gender; do not resurrect a saved opposite-gender face.
   delete valid.face;
   setPicked(valid);
  }catch{}
 },[gender]);
 const save=()=>{
  try{localStorage.setItem(storageKey,JSON.stringify(positions));localStorage.setItem(selectionKey,JSON.stringify({...picked,face:undefined}));setSaved('บันทึกตำแหน่งและภาพที่เลือกไว้บนอุปกรณ์นี้แล้ว');}
  catch{setSaved('ไม่สามารถบันทึกบนอุปกรณ์นี้ได้');}
 };
 const lists=Object.fromEntries(order.map(category=>[category,PNG_PARTS[category].filter(p=>p.ready&&p.playable!==false&&(!p.gender||p.gender===gender))])) as Record<Category,Part[]>;
 const missing=order.filter(category=>lists[category].length===0);
 const active=(category:Category)=>category==='face'
  ? lists.face.find(p=>p.src.endsWith('/'+gender+'.png'))
  : lists[category].find(p=>p.src===picked[category])||lists[category][0];
 const importSettings=async(file:File|undefined)=>{
  if(!file)return;
  try{
   if(file.size>64*1024)throw new Error('File too large');
   const raw=await file.text();
   const snapshot=validateAssemblySnapshot(JSON.parse(raw));
   if(snapshot.gender!==gender)throw new Error('Different character gender');
   setPositions(snapshot.positions);
   setPicked({...snapshot.selected,face:undefined});
   setHidden([]);
   setBroken([]);
   setOpacity(100);
   setSaved('นำเข้าค่าตำแหน่งและชิ้นส่วน PNG สำเร็จ (ยังไม่ได้บันทึกลงอุปกรณ์)');
  }catch{
   setSaved('นำเข้า JSON ไม่สำเร็จ: ตรวจสอบเพศ ข้อมูลตำแหน่ง และไฟล์ PNG ที่อัปโหลด');
  }
 };
 const exportSettings=()=>{
  try{
   const selected=Object.fromEntries(order.map(category=>[category,active(category)?.src]));
   const snapshot=validateAssemblySnapshot({version:PNG_ASSEMBLY_VERSION,gender,positions,selected});
   const blob=new Blob([JSON.stringify(snapshot,null,2)],{type:'application/json'});
   const url=URL.createObjectURL(blob);
   const anchor=document.createElement('a');
   anchor.href=url;
   anchor.download='coop-avatar-layout-'+gender+'.json';
   document.body.appendChild(anchor);
   anchor.click();
   anchor.remove();
   window.setTimeout(()=>URL.revokeObjectURL(url),1000);
   setSaved('ส่งออกข้อมูลชิ้นส่วนและตำแหน่งแล้ว สามารถนำไปใช้ปรับตัวละครจริงได้');
  }catch{
   setSaved('ส่งออกข้อมูลไม่ได้: ยังมีภาพหรือค่าตำแหน่งไม่ครบ');
  }
 };
 const exportComposite=async()=>{
  setExporting(true);
  try{
   if(missing.length>0)throw new Error('Incomplete gender-compatible PNG layer set');
   if(hidden.length>0)throw new Error('Hidden layers cannot be exported as a complete character');
   if(opacity!==100)throw new Error('A translucent layer cannot be exported as a complete character');
   const selectedParts=order.map(category=>active(category));
   if(selectedParts.some(part=>!part||broken.includes(part.src)))throw new Error('Missing or failed PNG layer');
   const canvas=document.createElement('canvas');
   canvas.width=AVATAR_CANVAS_WIDTH;canvas.height=AVATAR_CANVAS_HEIGHT;
   const ctx=canvas.getContext('2d');
   if(!ctx)throw new Error('Canvas unavailable');
   // Export the real sprite layers, not the SVG fallback.
   for(const category of order){
    const part=active(category);
    if(!part)throw new Error('Incomplete PNG layer');
    if(broken.includes(part.src))throw new Error('Failed PNG layer');
    const image=new Image();
    image.src=part.src;
    await image.decode();
    const rect=avatarLayerRect(image.naturalWidth,image.naturalHeight,positions[category],canvas.width,canvas.height);
    ctx.globalAlpha=editing===category?opacity/100:1;
    ctx.drawImage(image,rect.left,rect.top,rect.width,rect.height);
   }
   ctx.globalAlpha=1;
   const blob=await new Promise<Blob>((resolve,reject)=>canvas.toBlob(value=>value?resolve(value):reject(new Error('PNG export failed')),'image/png'));
   const url=URL.createObjectURL(blob);
   const anchor=document.createElement('a');
   anchor.href=url;anchor.download='coop-avatar-png-preview.png';
   document.body.appendChild(anchor);
   anchor.click();
   anchor.remove();
   window.setTimeout(()=>URL.revokeObjectURL(url),1000);
   setSaved('ส่งออกภาพประกอบ PNG สำหรับตรวจสอบแล้ว (ยังไม่ใช้เป็นตัวละครหลัก)');
  }catch{
   setSaved('ส่งออก PNG ไม่สำเร็จ: ต้องแสดงทุกชิ้นส่วน โหลดภาพได้ครบ และตั้งความโปร่งใสเป็น 100%');
  }finally{setExporting(false);}
 };
 const current=positions[editing];
 const update=(key:'x'|'y'|'scale',v:number)=>setPositions(prev=>({...prev,[editing]:{...prev[editing],[key]:v}}));
 return <section aria-label="ทดลองจัดตำแหน่งภาพ PNG" style={{marginTop:20,padding:16,border:'1px solid #92a5ae',borderRadius:16}}>
  <h3>ทดลองประกอบภาพ PNG จริง</h3>
  {missing.length>0&&<p role="alert" style={{fontSize:12,color:'#9c412f'}}>ยังไม่มีชิ้นส่วน PNG ที่ตรงกับตัวละครนี้: {missing.map(key=>labels[key]).join(' / ')} ภาพที่ยังไม่ครบจะไม่เปิดใช้ในเกม</p>}
  <p style={{fontSize:12}}>พื้นที่ทดลองแยกจากตัวละครที่ใช้เล่น ภาพบางชิ้นยังไม่ตรงสัดส่วน และบางเพศยังไม่มีเสื้อหรือรองเท้า PNG ที่ตรงชุด จึงยังส่งออกชุดสมบูรณ์ไม่ได้</p>
  {!avatarArtReadiness(PNG_PARTS,{gender}).ready&&<p role="note" style={{fontSize:12,color:'#8b4912'}}>ภาพที่นำเข้ายังไม่มีร่างกายเต็มตัวและแว่นตา PNG ที่พร้อมใช้งาน ภาพที่ประกอบเป็นเพียงตัวอย่างสำหรับตรวจสัดส่วน ยังไม่ใช่ตัวละครเกมฉบับสมบูรณ์</p>}
  <div style={{position:'relative',margin:'14px auto',width:'min(100%,280px)',aspectRatio:'3 / 4',borderRadius:12,background:'linear-gradient(#eef5f5,#d6e5ed)',overflow:'hidden'}}>
    {order.map((category,i)=>{const part=active(category);const a=positions[category];return part&&!broken.includes(part.src)&&!hidden.includes(category)?<img key={category} src={part.src} alt={part.label} onLoad={e=>{const width=e.currentTarget.naturalWidth,height=e.currentTarget.naturalHeight;setDimensions(prev=>prev[part.src]?.width===width&&prev[part.src]?.height===height?prev:{...prev,[part.src]:{width,height}});}} onError={()=>setBroken(prev=>prev.includes(part.src)?prev:[...prev,part.src])} style={(()=>{const d=dimensions[part.src];const r=d?avatarLayerRect(d.width,d.height,a):null;return {position:'absolute' as const,width:r?100*r.width/AVATAR_CANVAS_WIDTH+'%':a.scale+'%',height:r?100*r.height/AVATAR_CANVAS_HEIGHT+'%':'auto',maxHeight:'65%',objectFit:'contain' as const,opacity:editing===category?opacity/100:1,left:r?100*r.left/AVATAR_CANVAS_WIDTH+'%':a.x+'%',top:r?100*r.top/AVATAR_CANVAS_HEIGHT+'%':a.y+'%',transform:r?'none':'translate(-50%,-50%)',zIndex:i+1,pointerEvents:'none' as const};})()}/>:null})}
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
   <button type="button" onClick={exportSettings} style={{padding:9}}>ส่งออกค่าจัดตำแหน่ง JSON</button>
   <label style={{padding:9,border:'1px solid #92a5ae',borderRadius:6,cursor:'pointer'}}>นำเข้าค่าจัดตำแหน่ง JSON
    <input type="file" accept=".json,application/json" aria-label="นำเข้าไฟล์จัดตำแหน่ง PNG" onChange={e=>{const file=e.currentTarget.files?.[0];void importSettings(file);e.currentTarget.value='';}} style={{display:'block',maxWidth:190}} />
   </label>
   <button type="button" disabled={exporting} onClick={exportComposite} style={{padding:9}}>{exporting?"กำลังสร้าง PNG...":"ส่งออกภาพประกอบ PNG"}</button>
   <button type="button" onClick={()=>{setPositions(defaults);setPicked({});setSaved('คืนตำแหน่งและภาพเริ่มต้นแล้ว (ยังไม่ได้บันทึก)')}} style={{padding:9}}>คืนตำแหน่งเริ่มต้น</button>
  </div>
  {saved&&<p role="status" style={{fontSize:12}}>{saved}</p>}
 </section>;
}
