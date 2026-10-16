#!/usr/bin/env node
// Local visual QA contact sheet. No game routes, publishing or user data.
import {writeFileSync,mkdirSync,readFileSync} from 'node:fs';
import {join} from 'node:path';
import {renderAvatar} from '../shared/avatar.js';

const poses=['stand','wave','celebrate','think','confident'];
const fullMatrix=process.argv.includes('--all');
const validate=process.argv.includes('--validate');
const allOutfits=process.argv.includes('--outfits');
const shirtStyles=allOutfits?['tshirt','polo','shirt','jacket']:['polo'];
// Read committed preset definitions so the expanded sheet checks the actual
// hairstyle, color, glasses and clothing choices rather than stand-in defaults.
const catalog=readFileSync(new URL('../shared/characters.ts',import.meta.url),'utf8');
const match=catalog.match(/export const CHARACTERS:CharacterPreset\[\]\s*=\s*(\[[\s\S]*?\]);/);
if(!match)throw new Error('Cannot locate committed character presets');
const presets=JSON.parse(match[1]);
const people=(fullMatrix?presets:presets.filter(p=>['M01','F01'].includes(p.id))).map(p=>({
 bodyStyle:p.gender,presetId:p.id,hairStyle:p.hairStyle,hairColor:p.hairColor,
 shirtColor:p.shirtColor,skinTone:p.skinTone,bottomStyle:p.bottomStyle,
 bottomColor:p.bottomColor,glassesStyle:p.glasses?(p.glassesStyle==='round'?'round':'rectangle'):'none'
}));
const escape=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const cards=[];
const audited=[];
for(const person of people) for(const pose of poses) for(const shirtStyle of shirtStyles) {
 const options={...person,shirtStyle,pose,materialPrefix:'proof-'+person.presetId+'-'+pose+(allOutfits?'-'+shirtStyle:'')};
 const svg=renderAvatar(options);
 audited.push({id:person.presetId,pose,shirtStyle,svg});
 cards.push('<article data-preset="'+escape(person.presetId)+'" data-pose="'+escape(pose)+'" data-shirt="'+escape(shirtStyle)+'" data-review="unreviewed"><div class="portrait">'+svg+'</div><strong>'+escape(person.presetId)+' — '+escape(pose)+(allOutfits?' — '+escape(shirtStyle):'')+'</strong><label class="review-label">Art review <select class="review-status" aria-label="Art review status for '+escape(person.presetId)+' '+escape(pose)+' '+escape(shirtStyle)+'"><option value="unreviewed">Not reviewed</option><option value="approved">Looks correct</option><option value="anatomy">Hand / anatomy issue</option><option value="sleeve">Sleeve / shoulder issue</option><option value="other">Other visual issue</option></select></label></article>');
}
const html='<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'+
 '<title>Avatar pose review (not a release)</title><style>'+
 '*{box-sizing:border-box}body{font-family:system-ui,sans-serif;margin:24px;color:#17233e;background:#eaf0f8}'+
 'h1{font-size:24px}.note{font-size:15px;margin-bottom:22px}.grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:14px}'+
 'article{background:white;border:1px solid #c8d5e5;padding:12px;border-radius:14px;text-align:center;min-width:0}'+
 '.portrait{height:220px;display:flex;justify-content:center;align-items:center;overflow:hidden;border-radius:10px;background:#f2f7ff}'+
 '.portrait svg{height:100%!important;width:auto!important;max-width:100%!important;overflow:hidden!important}strong{display:block;padding-top:10px}'+
 '.review-label{display:flex;gap:6px;align-items:center;justify-content:center;font-size:12px;margin-top:8px}.review-status{font-size:12px;max-width:100%;min-height:30px}article[data-review="anatomy"],article[data-review="sleeve"],article[data-review="other"]{outline:2px solid #c87442}article[data-review="approved"]{outline:2px solid #459775}'+
 '.toolbar{display:flex;gap:12px;flex-wrap:wrap;align-items:center;background:white;border:1px solid #c8d5e5;padding:12px;border-radius:12px;margin-bottom:16px;position:sticky;top:0;z-index:2}.toolbar select{min-height:38px;font:inherit}.toolbar label{font-weight:600}.toolbar output{font-size:14px;color:#486079}article[hidden]{display:none!important}.portrait{position:relative}'+
 '@media(max-width:650px){body{margin:12px}.grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.portrait{height:175px}}'+
 '</style><h1>Avatar pose QA — male / female × five poses</h1>'+
 '<p class="note">Check shoulder-to-sleeve contact, wrists/fingers, continuity, feet, hairstyle, and equal framing. Not proof of visual acceptance.</p>'+
 '<div class="toolbar"><label>Preset <select id="preset-filter"><option value="all">All 20 presets</option>'+people.map(p=>'<option value="'+escape(p.presetId)+'">'+escape(p.presetId)+'</option>').join('')+'</select></label><label>Shirt <select id="shirt-filter">'+shirtStyles.map(x=>'<option value="'+escape(x)+'"'+(x==='polo'?' selected':'')+'>'+escape(x)+'</option>').join('')+'</select></label><label>Pose <select id="pose-filter"><option value="all">All poses</option>'+poses.map(p=>'<option value="'+escape(p)+'">'+escape(p)+'</option>').join('')+'</select></label><button id="export-review" type="button">Export review CSV</button><output id="visible-count"></output></div>'+ 
 '<main class="grid">'+cards.join('')+'</main><script>const preset=document.getElementById("preset-filter"),shirt=document.getElementById("shirt-filter"),poseFilter=document.getElementById("pose-filter"),cards=[...document.querySelectorAll("article")];const escapeCsv=v=>String(v).replaceAll(String.fromCharCode(34),String.fromCharCode(34,34));document.querySelectorAll(".review-status").forEach(select=>select.addEventListener("change",()=>{select.closest("article").dataset.review=select.value;apply()}));function apply(){let n=0;for(const card of cards){card.hidden=(preset.value!=="all"&&card.dataset.preset!==preset.value)||card.dataset.shirt!==shirt.value||(poseFilter.value!=="all"&&card.dataset.pose!==poseFilter.value);if(!card.hidden)n++}document.getElementById("visible-count").textContent=n+" visible / "+cards.length+" generated; "+cards.filter(c=>c.dataset.review!=="unreviewed").length+" reviewed"}preset.addEventListener("change",apply);shirt.addEventListener("change",apply);poseFilter.addEventListener("change",apply);document.getElementById("export-review").addEventListener("click",()=>{const rows=[["preset","pose","shirt","review"],...cards.map(c=>[c.dataset.preset,c.dataset.pose,c.dataset.shirt,c.dataset.review])];const csv=rows.map(cols=>cols.map(v=>String.fromCharCode(34)+escapeCsv(v)+String.fromCharCode(34)).join(",")).join("\\r\\n");const a=document.createElement("a");a.href=URL.createObjectURL(new Blob([csv],{type:"text/csv;charset=utf-8"}));a.download="avatar-art-review.csv";a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)});apply();</script></html>';
const outputDir=process.env.COOP_AVATAR_QA_OUTPUT_DIR||'artifacts/avatar-qa';
mkdirSync(outputDir,{recursive:true});
writeFileSync(join(outputDir,allOutfits?'all-outfits-contact-sheet.html':fullMatrix?'all-presets-contact-sheet.html':'pose-contact-sheet.html'),html,'utf8');
console.log('Wrote avatar pose review ('+cards.length+' poses; full='+fullMatrix+')');

if(validate){
 const faults=[];
 for(const {id,pose,shirtStyle,svg} of audited){
  const label=id+'/'+pose+'/'+shirtStyle;
  if(!svg.includes('viewBox="0 0 160 220"'))faults.push(label+' missing figure bounds');
  if((svg.match(/data-sleeve-side=/g)||[]).length!==2)faults.push(label+' incomplete shirt sleeves');
  if(/fill="none" fill="none"/.test(svg))faults.push(label+' duplicate SVG fill attributes');
  if(/NaN|undefined|<script/.test(svg))faults.push(label+' invalid markup value');
  if(!svg.includes('id="proof-'+id+'-'+pose+(allOutfits?'-'+shirtStyle:'')+'-skin-lit"'))faults.push(label+' material mismatch');
  const ids=[...svg.matchAll(/\\bid="([^"]+)"/g)].map(m=>m[1]);
  if(new Set(ids).size!==ids.length)faults.push(label+' duplicated material/clip ID');
  for(const match of svg.matchAll(/url\\(#([^)]*)\\)/g)){
    if(!ids.includes(match[1]))faults.push(label+' unresolved SVG paint or clip reference '+match[1]);
  }
  if((svg.match(/data-avatar-part="sleeve-cuff"/g)||[]).length!==2)faults.push(label+' incomplete cuff hems');
  if((svg.match(/data-avatar-part="left-forearm"/g)||[]).length!==1||(svg.match(/data-avatar-part="right-forearm"/g)||[]).length!==1)faults.push(label+' incomplete forearm silhouette');
 }
 if(faults.length){console.error(faults.join('\n'));process.exitCode=1;}
 else console.log('Validated all '+audited.length+' figure SVGs (structural only; review images manually).');
}
