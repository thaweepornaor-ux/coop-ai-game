'use client';
import {useId,useMemo} from 'react';
import {renderAvatar} from '../../shared/avatar.js';
import type {AvatarChoices} from '../../shared/avatar.js';
export {AVATAR_OPTIONS} from '../../shared/avatar.js';
export type {AvatarChoices,AvatarOption,AvatarOptionKey} from '../../shared/avatar.js';
export interface AvatarProps {options?:AvatarChoices|Record<string,unknown>;className?:string;interactive?:boolean;motion?:boolean;pose?:'stand'|'wave'|'celebrate'|'think'|'confident';}
/**
 * One renderer for every game state. The former stand-only PNG overlay had
 * different proportions, clothing coverage and layering from posed SVG art,
 * so characters visibly changed identity when they waved or celebrated.
 * Keep all wardrobe choices and unique SVG gradient IDs unchanged.
 */
export function Avatar({options={},className,pose='stand'}:AvatarProps){
 const uniqueMaterialId=useId().replace(/[^a-zA-Z0-9_-]/g,'');
 const svg=useMemo(()=>renderAvatar({...options,pose,materialPrefix:'avatar-'+uniqueMaterialId}),[JSON.stringify(options),pose,uniqueMaterialId]);
 return <div className={className} role="img" aria-label="ตัวละครผู้เล่น" style={{position:'relative',aspectRatio:'3 / 4',width:'100%',height:'100%',display:'grid',placeItems:'center'}}>
  <div style={{width:'100%',height:'100%',overflow:'hidden'}} dangerouslySetInnerHTML={{__html:svg}}/>
 </div>;
}
