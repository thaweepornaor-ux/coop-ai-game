import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {AVATAR_OPTIONS} from '../shared/avatar.js';
import {PNG_PARTS} from '../shared/avatar-png-catalog.js';
const source=readFileSync(new URL('../app/components/avatar.tsx',import.meta.url),'utf8');

test('ready PNG wardrobe asset aliases match actual selectable values',()=>{
 const shirtValues=new Set(AVATAR_OPTIONS.shirtStyle.map(v=>v.value));
 const shoeValues=new Set(AVATAR_OPTIONS.shoeColor.map(v=>v.value));
 assert.ok(shirtValues.has('jacket'));
 assert.ok(shoeValues.has('white'));
 assert.equal(PNG_PARTS.top.find(p=>p.value==='overshirt')?.ready,true);
 assert.equal(PNG_PARTS.shoes.find(p=>p.value==='sneakers')?.ready,true);
 assert.match(source,/p\.value==='overshirt'\?'jacket':p\.value/);
 assert.match(source,/p\.value==='sneakers'\?'white':p\.value/);
});
test('unapproved PNG crops cannot replace the playable full avatar',()=>{
 assert.match(source,/p\.ready===true&&p\.aligned===true/);
 for(const group of Object.values(PNG_PARTS))for(const part of group)assert.equal(part.aligned,false);
});
