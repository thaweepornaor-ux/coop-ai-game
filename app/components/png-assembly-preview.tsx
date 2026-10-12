'use client';
import {useState} from 'react';
import {PNG_PARTS} from '../../shared/avatar-png-catalog.js';

type Part = {src:string;label:string;ready:boolean;aligned:boolean};
type Category = 'face'|'hair'|'top'|'bottom'|'shoes';
const order:Category[]=['bottom','shoes','top','face','hair'];
const labels:Record<Category,string>={face:'ใบหน้า',hair:'ทรงผม',top:'เสื้อ',bottom:'กางเกง',shoes:'รองเท้า'};
const defaults:Record<Category,{x:number;y:number;scale:number}>={
 face:{x:50,y:22,scale:40},hair:{x:50,y:14,scale:46},
 top:{x:50,y:51,scale:60},bottom:{x:50,y:73,scale:52},shoes:{x:50,y:92,scale:38}
};

/** An isolated alignment workspace. Never replaces the playable avatar. */
export function PngAssemblyPreview({gender}:{gender:'male'|'female'}){
 const [picked,setPicked]=useState<Partial<Record<Category,string>>>({});
 const [positions,setPositions]=useState(defaults);
 const [editing,setEditing]=useState<Category>('face');
 const lists=Object.fromEntries(order.map(category=>[category,PNG_PARTS[category].filter(p=>p.ready)])) as Record<Category,Part[]>;
 const active=(category:Category)=>lists[category].find(p=>p.src===picked[category])||lists[category].find(p=>category==='face'&&p.src.endsWith('/'+gender+'.png'))||lists[category][0];
 const current=positions[editing];
 const update=(key:'x'|'y'|'scale',v:number)=>setPositions(prev=>({...prev,[editing]:{...prev[editing],[key]:v}}));
 return <section aria-label="ทดลองจัดตำแหน่งภาพ PNG" style={{marginTop:20,padding:16,border:'1px solid #92a5ae',borderRadius:16}}>
  <h3>ทดลองประกอบภาพ PNG จริง</h3>
  <p style={{fontSize:12}}>พื้นที่ทดลองแยกจากตัวละครที่ใช้เล่น ภาพบางชิ้นยังไม่ตรงสัดส่วน ต้องปรับก่อนนำไปใช้จริง</p>
  <div style={{position:'relative',margin:'14px auto',width:'min(100%,280px)',aspectRatio:'3 / 4',borderRadius:12,background:'linear-gradient(#eef5f5,#d6e5ed)',overflow:'hidden'}}>
    {order.map((category,i)=>{const part=active(category);const a=positions[category];return part?<img key={category} src={part.src} alt={part.label} style={{position:'absolute',width:a.scale+'%',height:'auto',maxHeight:'65%',objectFit:'contain',left:a.x+'%',top:a.y+'%',transform:'translate(-50%,-50%)',zIndex:i+1,pointerEvents:'none'}}/>:null})}
  </div>
  <label style={{display:'block',fontSize:13}}>ชิ้นส่วนที่ต้องการปรับ
   <select value={editing} onChange={e=>setEditing(e.target.value as Category)} style={{display:'block',width:'100%',padding:8}}>
    {order.map(key=><option key={key} value={key}>{labels[key]}</option>)}
   </select>
  </label>
  {lists[editing].length>1&&<label style={{display:'block',marginTop:8}}>เลือกภาพ
   <select value={active(editing)?.src||''} onChange={e=>setPicked(prev=>({...prev,[editing]:e.target.value}))} style={{display:'block',width:'100%',padding:8}}>
    {lists[editing].map(part=><option key={part.src} value={part.src}>{part.label}</option>)}
   </select>
  </label>}
  {(['x','y','scale'] as const).map(key=><label key={key} style={{display:'block',marginTop:10,fontSize:13}}>{key==='x'?'แนวนอน':key==='y'?'แนวตั้ง':'ขนาด'}: {current[key]}%
    <input type="range" min={key==='scale'?10:0} max={key==='scale'?100:100} value={current[key]} onChange={e=>update(key,Number(e.target.value))} style={{display:'block',width:'100%'}}/>
  </label>)}
  <button type="button" onClick={()=>setPositions(defaults)} style={{marginTop:10,padding:9}}>คืนตำแหน่งเริ่มต้น</button>
 </section>;
}
