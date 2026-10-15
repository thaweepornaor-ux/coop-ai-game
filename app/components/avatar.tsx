'use client';
import {useMemo,useState} from 'react';
import {renderAvatar} from '../../shared/avatar.js';
import {PNG_PARTS} from '../../shared/avatar-png-catalog.js';
import {playableAvatarLayers} from '../../shared/avatar-playable-layers.js';
import type {AvatarChoices} from '../../shared/avatar.js';
export {AVATAR_OPTIONS} from '../../shared/avatar.js';
export type {AvatarChoices,AvatarOption,AvatarOptionKey} from '../../shared/avatar.js';
export interface AvatarProps {options?:AvatarChoices|Record<string,unknown>;className?:string;interactive?:boolean;motion?:boolean;pose?:'stand'|'wave'|'celebrate'|'think'|'confident';}
type LoadedState='loading'|'ok'|'error';
/**
 * PNG layer mode requires a complete aligned set; until then the fully-selectable
 * SVG fallback renders ALL chosen clothing, hair and glasses without hiding parts.
 */
export function Avatar({options={},className,pose='stand'}:AvatarProps){
 const v=options as Record<string,unknown>;
 const stack=playableAvatarLayers(v,PNG_PARTS);
 const parts=stack.layers;
 const complete=stack.ready;
 const [loaded,setLoaded]=useState<Record<string,LoadedState>>({});
 const signature=parts.map(p=>p?.src||'?').join('|');
 const everyLoaded=pose==='stand'&&complete&&parts.every(p=>p&&loaded[signature+'|'+p.src]==='ok');
 const fallback=useMemo(()=>renderAvatar({...options,pose}),[JSON.stringify(options),pose]);
 return <div className={className} role="img" aria-label="ตัวละครผู้เล่น" style={{position:'relative',aspectRatio:'3 / 4',width:'100%',height:'100%',display:'grid',placeItems:'center'}}>
  {!everyLoaded&&<div style={{width:'100%',height:'100%'}} dangerouslySetInnerHTML={{__html:fallback}}/>}
  {pose==='stand'&&complete&&<div key={signature} aria-hidden="true" style={{position:'absolute',inset:0,opacity:everyLoaded?1:0,pointerEvents:'none'}}>
    {parts.filter((p):p is NonNullable<typeof p>=>!!p).map((part,index)=><img key={part.src} src={part.src} alt="" onLoad={e=>{const img=e.currentTarget;void img.decode().then(()=>setLoaded(prev=>({...prev,[signature+'|'+part.src]:'ok'}))).catch(()=>setLoaded(prev=>({...prev,[signature+'|'+part.src]:'error'})));}} onError={()=>setLoaded(prev=>({...prev,[signature+'|'+part.src]:'error'}))} decoding="async" style={{position:'absolute',left:part.position!.x+'%',top:part.position!.y+'%',width:part.position!.scale+'%',height:'auto',maxHeight:'65%',transform:'translate(-50%,-50%)',objectFit:'contain',zIndex:index+1}}/>)}
  </div>}
 </div>;
}
