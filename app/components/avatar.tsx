'use client';
import {useEffect,useMemo,useRef,useState} from 'react';
import { renderAvatar } from '../../shared/avatar.js';
import type { AvatarChoices } from '../../shared/avatar.js';
export { AVATAR_OPTIONS } from '../../shared/avatar.js';
export type { AvatarChoices, AvatarOption, AvatarOptionKey } from '../../shared/avatar.js';
export interface AvatarProps {options?:AvatarChoices|Record<string,unknown>;className?:string;interactive?:boolean;motion?:boolean;}
export function Avatar({options={},className,interactive=false,motion=true}:AvatarProps){
 const container=useRef<HTMLDivElement>(null),canvas=useRef<HTMLCanvasElement>(null);const[thumbnail,setThumbnail]=useState<{key:string;url:string}|null>(null),[failed,setFailed]=useState(false),[visible,setVisible]=useState(interactive),[contextLost,setContextLost]=useState(false),[contextEpoch,setContextEpoch]=useState(0);const serialized=JSON.stringify(options);
 // Display a lightweight, wardrobe-aware image immediately while WebGL thumbnails are queued.
 const fallbackUrl=useMemo(()=> 'data:image/svg+xml;charset=utf-8,'+encodeURIComponent(renderAvatar(JSON.parse(serialized))),[serialized]);
 const previewUrl=thumbnail?.key===serialized?thumbnail.url:fallbackUrl;
 useEffect(()=>{if(interactive)setContextLost(false);const element=canvas.current;if(!element)return;const lost=(e:Event)=>{e.preventDefault();setContextLost(true);};const restored=()=>{setContextLost(false);setFailed(false);setContextEpoch(v=>v+1);};element.addEventListener('webglcontextlost',lost);element.addEventListener('webglcontextrestored',restored);return()=>{element.removeEventListener('webglcontextlost',lost);element.removeEventListener('webglcontextrestored',restored);};},[interactive]);
 useEffect(()=>{if(!container.current)return;const observer=new IntersectionObserver(([entry])=>setVisible(entry.isIntersecting),{rootMargin:'120px'});observer.observe(container.current);return()=>observer.disconnect();},[]);
 useEffect(()=>{if(!visible)return;let cancelled=false;const controller=new AbortController();import('../../shared/avatar3d').then(m=>m.renderThumbnail(JSON.parse(serialized),controller.signal)).then(url=>{if(!cancelled)setThumbnail({key:serialized,url});}).catch(()=>{if(!cancelled){const svg=renderAvatar(JSON.parse(serialized));setThumbnail({key:serialized,url:'data:image/svg+xml;charset=utf-8,'+encodeURIComponent(svg)});}});return()=>{cancelled=true;controller.abort();};},[serialized,visible,contextEpoch]);
 useEffect(()=>{
  if(!interactive||!canvas.current||!visible||contextLost)return;let cancelled=false,cleanup=()=>{};
  import('../../shared/avatar3d').then(m=>{if(cancelled||!canvas.current)return;try{
   const{renderer,scene,camera}=m.createStudio(canvas.current),model=m.createCharacter(JSON.parse(serialized));scene.add(model);setFailed(renderer.isSoftware);let frame=0,angle=-.12,dragging=false,activePointer=-1,lastX=0,lastDraw=0;const element=canvas.current;
   const draw=()=>{if(renderer.isContextLost)return;model.rotation.y=angle;renderer.render(scene,camera);};
   const resize=()=>{const bounds=element.getBoundingClientRect();if(bounds.width>0&&bounds.height>0){renderer.setPixelRatio(Math.min(devicePixelRatio||1,1.5));renderer.setSize(bounds.width,bounds.height,false);draw();}};const observer=new ResizeObserver(resize);observer.observe(element);resize();
   const down=(e:PointerEvent)=>{if(activePointer!==-1||(e.pointerType==='mouse'&&e.button!==0))return;try{element.setPointerCapture(e.pointerId);}catch{return;}activePointer=e.pointerId;dragging=true;lastX=e.clientX;};
   const move=(e:PointerEvent)=>{if(dragging&&e.pointerId===activePointer){angle+=(e.clientX-lastX)*.012;lastX=e.clientX;draw();}};const up=(e:PointerEvent)=>{if(e.pointerId===activePointer){dragging=false;activePointer=-1;if(e.type==='pointerup'&&element.hasPointerCapture(e.pointerId))element.releasePointerCapture(e.pointerId);}};
   element.addEventListener('pointerdown',down);element.addEventListener('pointermove',move);element.addEventListener('pointerup',up);element.addEventListener('pointercancel',up);element.addEventListener('lostpointercapture',up);
   const enabled=!renderer.isSoftware&&motion&&!matchMedia('(prefers-reduced-motion: reduce)').matches;
   const animate=(t:number)=>{if(document.hidden){frame=0;return;}if(t-lastDraw>=80){lastDraw=t;if(!dragging)model.poseTime=t*.001;draw();}frame=requestAnimationFrame(animate);};
   const visibility=()=>{if(document.hidden){cancelAnimationFrame(frame);frame=0;}else if(enabled&&!frame)frame=requestAnimationFrame(animate);};document.addEventListener('visibilitychange',visibility);
   void renderer.ready.then(()=>{if(!cancelled)draw();}).catch(()=>{if(!cancelled)setFailed(true);});if(enabled&&!document.hidden)frame=requestAnimationFrame(animate);else draw();
   cleanup=()=>{observer.disconnect();cancelAnimationFrame(frame);document.removeEventListener('visibilitychange',visibility);element.removeEventListener('pointerdown',down);element.removeEventListener('pointermove',move);element.removeEventListener('pointerup',up);element.removeEventListener('pointercancel',up);element.removeEventListener('lostpointercapture',up);m.disposeCharacter(model);renderer.dispose();};
  }catch{setFailed(true);}}).catch(()=>{if(!cancelled)setFailed(true);});return()=>{cancelled=true;cleanup();};
 },[serialized,interactive,motion,visible,contextLost,contextEpoch]);
 return <div ref={container} className={className} style={{position:'relative',aspectRatio:'3 / 4'}}>
  {<img src={previewUrl} alt="ตัวละครผู้เล่น" decoding="async" loading="lazy" style={{width:'100%',height:'100%',objectFit:'contain',display:'block'}}/>}
  {interactive&&<canvas ref={canvas} aria-label="ตัวละครสามมิติ ลากเพื่อหมุนดูชุด" style={{position:'absolute',inset:0,width:'100%',height:'100%',touchAction:'pan-y',cursor:'grab',opacity:failed||contextLost?0:1}}/>}
 </div>;
}
