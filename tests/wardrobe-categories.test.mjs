import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const source=readFileSync(new URL('../app/components/wardrobe.tsx',import.meta.url),'utf8');
const header=source.split('/** Selection icons')[0];
const names=[...header.matchAll(/label: '(ตัวละคร|ทรงผม|เสื้อผ้า|รองเท้า|แว่นตา)'/g)].map(x=>x[1]);

test('wardrobe navigation has exactly the five agreed categories',()=>{
 assert.deepEqual(names,['ตัวละคร','ทรงผม','เสื้อผ้า','รองเท้า','แว่นตา']);
});
test('clothing category edits tops, bottoms and separate colors',()=>{
 for(const key of ['shirtStyle','shirtColor','bottomStyle','bottomColor'])
  assert.match(source,new RegExp(key));
 assert.match(source,/change\('bottomStyle', option\.value\)/);
 assert.match(source,/change\('bottomColor', option\.value\)/);
});
