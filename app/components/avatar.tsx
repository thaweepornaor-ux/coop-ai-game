'use client';
import {useMemo} from 'react';
import {renderAvatar} from '../../shared/avatar.js';
import type { AvatarChoices } from '../../shared/avatar.js';
export { AVATAR_OPTIONS } from '../../shared/avatar.js';
export type { AvatarChoices, AvatarOption, AvatarOptionKey } from '../../shared/avatar.js';
export interface AvatarProps {options?:AvatarChoices|Record<string,unknown>;className?:string;interactive?:boolean;motion?:boolean;}
/** New reliable avatar preview. The rejected procedural 3D renderer is not used. */
export function Avatar({options={},className}:AvatarProps){
 const svg=useMemo(()=>renderAvatar(options),[JSON.stringify(options)]);
 return <div className={className} role="img" aria-label="ตัวละครผู้เล่น" style={{position:'relative',aspectRatio:'3 / 4',width:'100%',height:'100%',display:'grid',placeItems:'center'}} dangerouslySetInnerHTML={{__html:svg}}/>;
}
