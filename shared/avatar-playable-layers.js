import {PNG_PARTS} from './avatar-png-catalog.js';
import {avatarSelectionReadiness} from './avatar-selection-readiness.js';
import {avatarLayerRect} from './avatar-png-layout.js';

export const AVATAR_DRAW_ORDER=Object.freeze(['body','bottom','shoes','top','face','hair','glasses']);

/** Build a playable image-layer stack only from a complete reviewed outfit.
 * No PNG is displayed in the game until every visible layer has valid coordinates.
 */
export function playableAvatarLayers(choices,catalog=PNG_PARTS){
 const result=avatarSelectionReadiness(choices,catalog);
 const issues=[...result.reasons], ordered=[];
 for(const category of AVATAR_DRAW_ORDER){
  const group=catalog[category]||[];
  for(const part of result.selected.filter(item=>group.includes(item))){
   if(!part.position){
    issues.push('position:'+category);
    continue;
   }
   try{
    avatarLayerRect(100,100,part.position);
    ordered.push({category,...part});
   }catch{
    issues.push('position:'+category);
   }
  }
 }
 if(ordered.length!==result.selected.length)issues.push('incomplete-layer-stack');
 return {ready:issues.length===0,issues,layers:issues.length===0?ordered:[]};
}
