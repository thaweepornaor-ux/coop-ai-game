import {avatarLayerRect} from './avatar-png-layout.js';
import {PNG_PARTS} from './avatar-png-catalog.js';

export const PNG_ASSEMBLY_CATEGORIES=Object.freeze(['bottom','shoes','top','face','hair']);
export const PNG_ASSEMBLY_VERSION=1;

/** Validate a portable artwork alignment snapshot before any game integration. */
export function validateAssemblySnapshot(input){
 if(!input||typeof input!=='object'||Array.isArray(input)||input.version!==PNG_ASSEMBLY_VERSION)throw new TypeError('Unsupported PNG alignment snapshot');
 if(input.gender!=='male'&&input.gender!=='female')throw new TypeError('Invalid gender');
 const positions={},selected={};
 for(const category of PNG_ASSEMBLY_CATEGORIES){
  const position=input.positions?.[category];
  // Geometry helper is the authoritative range validator.
  avatarLayerRect(1,1,position);
  positions[category]={x:position.x,y:position.y,scale:position.scale};
  const source=input.selected?.[category];
  if(category==='face'){
   const face=PNG_PARTS.face.find(part=>part.ready&&part.value===input.gender);
   if(!face)throw new TypeError('Gender face is not uploaded');
   selected.face=face.src;
  }else{
   if(typeof source!=='string'||!PNG_PARTS[category].some(part=>part.ready&&part.src===source))throw new TypeError('Unverified PNG layer: '+category);
   selected[category]=source;
  }
 }
 return {version:PNG_ASSEMBLY_VERSION,gender:input.gender,positions,selected};
}
