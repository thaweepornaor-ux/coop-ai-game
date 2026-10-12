import {PNG_PARTS} from './avatar-png-catalog.js';

/** Check the exact player's PNG outfit, not whether the catalog has a random sample for each group. */
export function avatarSelectionReadiness(choices,catalog=PNG_PARTS){
 const reasons=[];
 const isSafePart=p=>p&&typeof p.src==='string'&&/^\/avatar-parts\/[a-zA-Z0-9_-]+\.png$/.test(p.src);
 const body=catalog.body?.find(p=>p.value===choices?.bodyStyle&&p.ready&&p.aligned&&p.playable!==false&&isSafePart(p));
 if(!body)reasons.push('body-base');
 const required=[
  ['face',choices?.bodyStyle],
  ['top',choices?.shirtStyle],
  ['bottom',choices?.bottomStyle],
  ['shoes',choices?.shoeColor]
 ];
 if(choices?.hairStyle!=='bald')required.push(['hair',choices?.hairStyle]);
 if(choices?.glassesStyle&&choices.glassesStyle!=='none')required.push(['glasses',choices.glassesStyle]);
 const aliases={top:{overshirt:'jacket'},shoes:{sneakers:'white'}};
 const selected=body?[body]:[];
 for(const [group,value] of required){
  const parts=catalog[group]||[];
  const candidates=parts.filter(p=>(aliases[group]?.[p.value]||p.value)===value&&p.ready&&p.playable!==false&&isSafePart(p));
  const part=candidates.find(p=>p.aligned)||candidates[0];
  if(!part){reasons.push('missing:'+group);continue;}
  if(!part.aligned)reasons.push('unaligned:'+group);
  selected.push(part);
 }
 if(new Set(selected.map(p=>p.src)).size!==selected.length)reasons.push('duplicate-layer');
 return {ready:reasons.length===0,reasons,selected};
}
