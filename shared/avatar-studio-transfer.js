import {AVATAR_OPTIONS} from './avatar.js';

export const STUDIO_DRAFT_KEY='coop-ai-avatar-studio-draft-v1';
export const STUDIO_NAME_KEY='coop-ai-avatar-studio-name-v1';
export const STUDIO_TRANSFER_KEY='coop-ai-avatar-studio-transfer-v1';
const keys=Object.keys(AVATAR_OPTIONS);
export function cleanStudioName(value){
 if(typeof value!=='string')return '';
 return Array.from(value.trim()).slice(0,24).join('');
}
export function cleanStudioAvatar(value){
 if(!value||typeof value!=='object'||Array.isArray(value))return null;
 const id=value.presetId;
 if(typeof id!=='string'||!/^[MF](0[1-9]|10)$/.test(id))return null;
 const gender=id.startsWith('M')?'male':'female';
 if(value.bodyStyle!==gender)return null;
 const result={presetId:id,bodyStyle:gender};
 for(const key of keys){
  if(key==='bodyStyle')continue;
  const entry=value[key];
  if(typeof entry!=='string'||!AVATAR_OPTIONS[key].some(option=>option.value===entry))return null;
  result[key]=entry;
 }
 if(gender==='male'&&result.bottomStyle==='skirt')result.bottomStyle='pants';
 return result;
}
export function validateStudioTransfer(value){
 if(!value||typeof value!=='object'||Array.isArray(value)||value.version!==1)return null;
 const name=cleanStudioName(value.name);
 const avatar=cleanStudioAvatar(value.avatar);
 return name&&avatar?{version:1,name,avatar}:null;
}
