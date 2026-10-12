import { AVATAR_OPTIONS } from './avatar.js';
import { CHARACTERS, characterFor } from './characters';
export const WARDROBE_KEYS = Object.keys(AVATAR_OPTIONS) as (keyof typeof AVATAR_OPTIONS)[];
const defaults: Record<string,string>={bodyStyle:'male',skinTone:'warm',hairStyle:'sidepart',hairColor:'brown',shirtStyle:'tshirt',shirtColor:'lightgreen',bottomStyle:'pants',bottomColor:'charcoal',shoeColor:'black',glassesStyle:'none',hatStyle:'none',hatColor:'navy'};
/** One flat catalogue contract for the API and every display context. */
export function normalizeWardrobe(value:Record<string,unknown>,strict=false):Record<string,string>{
 if(strict){for(const key of Object.keys(value))if(key!=='presetId'&&!WARDROBE_KEYS.includes(key as keyof typeof AVATAR_OPTIONS))throw new Error('ไม่รับข้อมูลนอกชุดแต่งตัว');}
 let id=value.presetId;
 if(id!==undefined&&(typeof id!=='string'||!CHARACTERS.some(c=>c.id===id)))throw new Error('แบบตัวละครไม่อยู่ในรายการ');
 const body=String(value.bodyStyle||'male');
 if(!id)id=characterFor(body).id;
 const preset=characterFor(id);
 if(strict&&value.bodyStyle!==undefined&&body!==preset.gender)throw new Error('เพศและแบบตัวละครไม่ตรงกัน');
 const out:Record<string,string>={presetId:preset.id};
 for(const key of WARDROBE_KEYS){
  if(key==='bodyStyle'){out[key]=preset.gender;continue;}
  const supplied=value[key];
  if(strict&&supplied!==undefined&&(typeof supplied!=='string'||!AVATAR_OPTIONS[key].some(o=>o.value===supplied)))throw new Error('ตัวเลือกชุดแต่งตัวไม่อยู่ในรายการ');
  out[key]=typeof supplied==='string'&&AVATAR_OPTIONS[key].some(o=>o.value===supplied)?supplied:defaults[key];
 }
 return out;
}
