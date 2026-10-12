import {PNG_PARTS} from './avatar-png-catalog.js';
export const REQUIRED_AVATAR_GROUPS=Object.freeze(['face','hair','top','bottom','shoes','glasses']);
/**
 * Distinguish importable PNG art from a complete playable character.
 * A body rig/base is required: isolated heads and garments cannot form a full person.
 */
export function avatarArtReadiness(catalog=PNG_PARTS,{hasBodyBase=false,gender}={}){
 if(gender!==undefined&&gender!=='male'&&gender!=='female')throw new TypeError('Invalid avatar gender');
 const compatible=part=>part?.ready===true&&part.playable!==false&&(!gender||!part.gender||part.gender===gender);
 const missing=[];
 if(!hasBodyBase)missing.push('body-base');
 for(const category of REQUIRED_AVATAR_GROUPS){
  const options=catalog[category];
  if(!Array.isArray(options)||!options.some(compatible))missing.push(category);
 }
 const unaligned=REQUIRED_AVATAR_GROUPS.filter(category=>Array.isArray(catalog[category])&&catalog[category].some(part=>compatible(part)&&part.aligned!==true));
 return {ready:missing.length===0&&unaligned.length===0,missing,unaligned};
}
