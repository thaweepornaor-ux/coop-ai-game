'use client';
import {useMemo,useState} from 'react';
import {renderAvatar} from '../../shared/avatar.js';
import {PNG_PARTS} from '../../shared/avatar-png-catalog.js';
import type { AvatarChoices } from '../../shared/avatar.js';
export { AVATAR_OPTIONS } from '../../shared/avatar.js';
export type { AvatarChoices, AvatarOption, AvatarOptionKey } from '../../shared/avatar.js';
export interface AvatarProps {options?:AvatarChoices|Record<string,unknown>;className?:string;interactive?:boolean;motion?:boolean;}
/** Front-facing 2D avatar: show genuine image parts when present, SVG only as a fallback. */
export function Avatar({options={},className}:AvatarProps){
 const [missing,setMissing]=useState<Record<string,boolean>>({});
 const v=options as Record<string,unknown>;
 const gender=v.bodyStyle==='female'?'female':'male';
 const face=PNG_PARTS.face.find(p=>p.value===gender)!;
 const hairstyle=String(v.hairStyle||'');
 const hair=hairstyle==='bald'?undefined:PNG_PARTS.hair.find(p=>p.value===(gender==='female'?'halfup':'blonde'));
 const top=PNG_PARTS.top.find(p=>p.value===(gender==='female'?'cream':'denim'));
 const bottom=PNG_PARTS.bottom.find(p=>p.value===(gender==='female'?'skirt':'chinos'));
 const shoes=PNG_PARTS.shoes.find(p=>p.value==='sneakers');
 const layers=[bottom,shoes,top,face,hair].filter((x):x is NonNullable<typeof x>=>!!x);
 const fallback=useMemo(()=>renderAvatar(options),[JSON.stringify(options)]);
 const primaryMissing=missing[face.src];
 return <div className={className} role="img" aria-label="ตัวละครผู้เล่น" style={{position:'relative',aspectRatio:'3 / 4',width:'100%',height:'100%',display:'grid',placeItems:'center'}}>
  {primaryMissing&&<div style={{width:'100%',height:'100%'}} dangerouslySetInnerHTML={{__html:fallback}} />}
  {!primaryMissing&&layers.map((part,index)=><img key={part.src} src={part.src} alt="" onError={()=>setMissing(prev=>({...prev,[part.src]:true}))} style={{display:missing[part.src]?'none':'block',position:'absolute',inset:0,width:'100%',height:'100%',objectFit:'contain',zIndex:index+1,pointerEvents:'none'}}/>)}
 </div>;
}
