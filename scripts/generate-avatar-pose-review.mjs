#!/usr/bin/env node
// Local visual QA contact sheet. No game routes, publishing or user data.
import {writeFileSync,mkdirSync} from 'node:fs';
import {renderAvatar} from '../shared/avatar.js';

const poses=['stand','wave','celebrate','think','confident'];
const fullMatrix=process.argv.includes('--all');
const people=[
 {bodyStyle:'male',presetId:'M01',hairStyle:'sidepart',shirtColor:'indigo',skinTone:'warm'},
 {bodyStyle:'female',presetId:'F01',hairStyle:'long',shirtColor:'teal',skinTone:'tan'}
];
if(fullMatrix){
 for(const gender of ['male','female']) for(let number=2;number<=10;number++){
  const id=(gender==='male'?'M':'F')+String(number).padStart(2,'0');
  people.push({bodyStyle:gender,presetId:id,hairStyle:gender==='male'?'short':'bob',shirtColor:gender==='male'?'indigo':'teal',skinTone:'warm'});
 }
}
const escape=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const cards=[];
for(const person of people) for(const pose of poses) {
 const options={...person,shirtStyle:'polo',pose,materialPrefix:'proof-'+person.presetId+'-'+pose};
 cards.push('<article><div class="portrait">'+renderAvatar(options)+'</div><strong>'+escape(person.presetId)+' — '+escape(pose)+'</strong></article>');
}
const html='<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'+
 '<title>Avatar pose review (not a release)</title><style>'+
 '*{box-sizing:border-box}body{font-family:system-ui,sans-serif;margin:24px;color:#17233e;background:#eaf0f8}'+
 'h1{font-size:24px}.note{font-size:15px;margin-bottom:22px}.grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:14px}'+
 'article{background:white;border:1px solid #c8d5e5;padding:12px;border-radius:14px;text-align:center;min-width:0}'+
 '.portrait{height:220px;display:flex;justify-content:center;align-items:center;overflow:hidden;border-radius:10px;background:#f2f7ff}'+
 '.portrait svg{height:100%!important;width:auto!important;max-width:100%!important;overflow:hidden!important}strong{display:block;padding-top:10px}'+
 '@media(max-width:650px){body{margin:12px}.grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.portrait{height:175px}}'+
 '</style><h1>Avatar pose QA — male / female × five poses</h1>'+
 '<p class="note">Check shoulder-to-sleeve contact, wrists/fingers, continuity, feet, hairstyle, and equal framing. Not proof of visual acceptance.</p>'+
 '<main class="grid">'+cards.join('')+'</main></html>';
mkdirSync('artifacts/avatar-qa',{recursive:true});
writeFileSync('artifacts/avatar-qa/pose-contact-sheet.html',html,'utf8');
console.log('Wrote artifacts/avatar-qa/pose-contact-sheet.html ('+cards.length+' poses)');
