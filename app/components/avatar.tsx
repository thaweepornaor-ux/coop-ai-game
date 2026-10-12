'use client';
import {useMemo,useState} from 'react';
import {renderAvatar} from '../../shared/avatar.js';
import {PNG_PARTS} from '../../shared/avatar-png-catalog.js';
import type {AvatarChoices} from '../../shared/avatar.js';
export {AVATAR_OPTIONS} from '../../shared/avatar.js';
export type {AvatarChoices,AvatarOption,AvatarOptionKey} from '../../shared/avatar.js';
export interface AvatarProps {options?:AvatarChoices|Record<string,unknown>;className?:string;interactive?:boolean;motion?:boolean;}
type LoadedState='loading'|'ok'|'error';
/**
 * PNG layer mode requires a complete aligned set; until then the fully-selectable
 * SVG fallback renders ALL chosen clothing, hair and glasses without hiding parts.
 */
export function Avatar({options={},className}:AvatarProps){
 const v=options as Record<string,unknown>;
 const gender=v.bodyStyle==='female'?'female':'male';
 const face=PNG_PARTS.face.find(p=>p.value===gender);
 const hair=PNG_PARTS.hair.find(p=>p.value===String(v.hairStyle));
 const top=PNG_PARTS.top.find(p=>p.value===String(v.shirtStyle));
 const bottom=PNG_PARTS.bottom.find(p=>p.value===String(v.bottomStyle));
 const shoes=PNG_PARTS.shoes.find(p=>p.value===String(v.shoeColor));
 const eyewear=PNG_PARTS.glasses.find(p=>p.value===String(v.glassesStyle));
 const parts=[face,top,bottom,shoes,...(v.hairStyle==='bald'?[]:[hair]),...(v.glassesStyle==='none'||!v.glassesStyle?[]:[eyewear])];
 // Do not compose thumbnail crops at arbitrary shared full-frame coordinates.
 const complete=parts.every(p=>p&&p.ready===true&&p.aligned===true);
 const [loaded,setLoaded]=useState<Record<string,LoadedState>>({});
 const signature=parts.map(p=>p?.src||'?').join('|');
 const everyLoaded=complete&&parts.every(p=>p&&loaded[p.src]==='ok');
 const fallback=useMemo(()=>renderAvatar(options),[JSON.stringify(options)]);
 return <div className={className} role="img" aria-label="ตัวละครผู้เล่น" style={{position:'relative',aspectRatio:'3 / 4',width:'100%',height:'100%',display:'grid',placeItems:'center'}}>
  {!everyLoaded&&<div style={{width:'100%',height:'100%'}} dangerouslySetInnerHTML={{__html:fallback}}/>}
  {complete&&<div key={signature} aria-hidden="true" style={{position:'absolute',inset:0,opacity:everyLoaded?1:0,pointerEvents:'none'}}>
    {parts.filter((p):p is NonNullable<typeof p>=>!!p).map((part,index)=><img key={part.src} src={part.src} alt="" onLoad={()=>setLoaded(prev=>({...prev,[part.src]:'ok'}))} onError={()=>setLoaded(prev=>({...prev,[part.src]:'error'}))} style={{position:'absolute',inset:0,width:'100%',height:'100%',objectFit:'contain',zIndex:index+1}}/>)}
  </div>}
 </div>;
}
