'use client';
import {useEffect,useState} from 'react';
import {Avatar,AVATAR_OPTIONS,type AvatarOptionKey} from './avatar';
import {CHARACTERS,type CharacterPreset} from '../../shared/characters';
import {normalizeWardrobe} from '../../shared/avatar-registry';

const choices: {key:AvatarOptionKey;label:string;max?:number}[]=[
 {key:'skinTone',label:'สีผิว'}, {key:'hairStyle',label:'ทรงผม'}, {key:'hairColor',label:'สีผม'},
 {key:'shirtStyle',label:'แบบเสื้อ'}, {key:'shirtColor',label:'สีเสื้อ'},
 {key:'bottomStyle',label:'กางเกง / กระโปรง'},{key:'shoeColor',label:'สีรองเท้า'},
 {key:'glassesStyle',label:'แว่นตา'}
];
const previewPoses=[
 {value:'stand',label:'ยืน'}, {value:'wave',label:'ทักทาย'},
 {value:'think',label:'คิด'}, {value:'confident',label:'มั่นใจ'},
 {value:'celebrate',label:'ดีใจ'}
] as const;
export function SimpleWardrobe({avatar,onChange}:{avatar:Record<string,string>;onChange:(next:Record<string,string>)=>void}){
 const [gender,setGender]=useState<'male'|'female'>(avatar.bodyStyle==='female'?'female':'male');
 useEffect(()=>{setGender(avatar.bodyStyle==='female'?'female':'male')},[avatar.bodyStyle]);
 const [previewPose,setPreviewPose]=useState<(typeof previewPoses)[number]['value']>('stand');
 const selectedId=avatar.presetId;
 const activePreset=CHARACTERS.find(c=>c.id===selectedId);
 const activePoseLabel=previewPoses.find(p=>p.value===previewPose)?.label||'ยืน';
 const selectPreset=(person:CharacterPreset)=>{
   const next=normalizeWardrobe({...avatar,presetId:person.id,bodyStyle:person.gender,
     skinTone:person.skinTone,hairStyle:person.hairStyle,hairColor:person.hairColor,
     glassesStyle:person.glasses?(person.glassesStyle==='round'?'round':'rectangle'):'none',
     bottomStyle:person.bottomStyle,shirtColor:person.shirtColor,bottomColor:person.bottomColor});
   onChange(next);
 };
 const chooseGender=(next:'male'|'female')=>{
   setGender(next);
   if(avatar.bodyStyle!==next){
     const first=CHARACTERS.find(c=>c.gender===next);
     if(first)selectPreset(first);
   }
 };
 const change=(key:AvatarOptionKey,value:string)=>{
   const next={...avatar,[key]:value};
   if(next.bodyStyle==='male'&&next.bottomStyle==='skirt')next.bottomStyle='pants';
   onChange(normalizeWardrobe(next));
 };
 return <div className="quick-wardrobe" aria-label="เลือกตัวละครและแต่งตัว">
   <div className="quick-title"><strong>1. เลือกตัวละคร</strong><span>แตะรูปที่ชอบได้เลย</span></div>
   <div className="quick-gender" role="group" aria-label="เลือกตัวละครชายหรือหญิง">
     <button type="button" aria-pressed={gender==='male'} onClick={()=>chooseGender('male')}>ตัวละครชาย</button>
     <button type="button" aria-pressed={gender==='female'} onClick={()=>chooseGender('female')}>ตัวละครหญิง</button>
   </div>
   <div className="quick-characters" aria-label={gender==='male'?'ตัวละครผู้ชาย':'ตัวละครผู้หญิง'}>
    {CHARACTERS.filter(c=>c.gender===gender).map((c,index)=><button type="button" key={c.id}
      className={'quick-character'+(selectedId===c.id?' selected':'')}
      aria-label={c.label+(selectedId===c.id?' เลือกอยู่':'')}
      aria-pressed={selectedId===c.id} onClick={()=>selectPreset(c)}>
      <span className="quick-character-portrait"><Avatar options={{...avatar,
        bodyStyle:c.gender,presetId:c.id,skinTone:c.skinTone,hairStyle:c.hairStyle,
        hairColor:c.hairColor,shirtColor:c.shirtColor,bottomStyle:c.bottomStyle,bottomColor:c.bottomColor,glassesStyle:c.glasses?(c.glassesStyle==='round'?'round':'rectangle'):'none',
        hatStyle:'none'}} pose={(['wave','confident','think','stand','celebrate'] as const)[index%5]} motion={false}/></span>
      <strong>{c.label}</strong>
      {selectedId===c.id&&<span className="quick-check" aria-hidden="true">✓</span>}
    </button>)}
   </div>
   <div className="quick-customize-title"><strong>ปรับแต่งตัวละคร</strong><span>เลือกทรงผม เสื้อผ้า สีผิว และแว่นตาได้เลย</span></div>
   <div className="quick-options">
     <div className="wardrobe-live-preview" aria-label="ตัวละครตัวอย่างที่เปลี่ยนตามการปรับแต่ง">
       <div className="wardrobe-live-avatar"><Avatar options={avatar} pose={previewPose} motion={false}/></div>
       <div className="wardrobe-live-caption"><strong>ตัวละครของฉัน{activePreset?' — '+activePreset.label:''}</strong><span>ท่า{activePoseLabel} · แต่งตัวและตรวจแขนเสื้อ มือ นิ้ว ได้ทันที</span></div>
       <span className="wardrobe-live-indicator">● เปลี่ยนทันที</span>
       <div className="wardrobe-pose-choices" role="group" aria-label="ทดลองท่าทางตัวละคร">
        {previewPoses.map(item=><button key={item.value} type="button" aria-pressed={previewPose===item.value} onClick={()=>setPreviewPose(item.value)}>{item.label}</button>)}
       </div>
     </div>
     {choices.map(({key,label})=><fieldset key={key}>
        <legend>{label}</legend>
        <div className="quick-option-list">
         {AVATAR_OPTIONS[key].filter(o=>!(avatar.bodyStyle==='male'&&key==='bottomStyle'&&o.value==='skirt')).map(option=>
           <button type="button" key={option.value} aria-pressed={avatar[key]===option.value}
             onClick={()=>change(key,option.value)}
             title={option.label}>{option.color&&<i style={{backgroundColor:option.color}}/>}{option.label}</button>)}
        </div>
     </fieldset>)}
   </div>
 </div>;
}
