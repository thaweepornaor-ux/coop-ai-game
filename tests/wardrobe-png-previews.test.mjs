import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const source=readFileSync(new URL('../app/components/wardrobe.tsx',import.meta.url),'utf8');

test('wardrobe previews use only genuinely committed images',()=>{
 assert.match(source,/PNG_PARTS\.face\.some\(part=>part\.value===gender&&part\.ready\)/);
 assert.match(source,/PNG_PARTS\.hair\.filter\(part=>part\.ready\)/);
 assert.match(source,/PNG_PARTS\.bottom\.filter\(part=>part\.ready\)/);
});
test('actual cropped assets are labelled as previews, not a composed avatar',()=>{
 assert.match(source,/ตัวอย่างทรงผม PNG ที่นำเข้าแล้ว/);
 assert.match(source,/ตัวอย่างกางเกง PNG ที่นำเข้าแล้ว/);
 assert.match(source,/กำลังปรับตำแหน่งเพื่อประกอบกับชุด/);
});

test('real PNG hair and pants previews are interactive wardrobe choices',()=>{
 assert.match(source,/onClick=\{\(\) => change\('hairStyle',part\.value\)\}/);
 assert.match(source,/onClick=\{\(\) => change\('bottomStyle',part\.value\)\}/);
 assert.match(source,/aria-pressed=\{avatar\.hairStyle === part\.value\}/);
 assert.match(source,/aria-pressed=\{avatar\.bottomStyle === part\.value\}/);
});

test('uploaded shirt and shoe thumbnails select valid wardrobe styles',()=>{
 assert.match(source,/onClick=\{\(\) => change\('shirtStyle','jacket'\)\}/);
 assert.match(source,/onClick=\{\(\) => change\('shoeColor','white'\)\}/);
 assert.match(source,/aria-pressed=\{avatar\.shirtStyle === 'jacket'\}/);
 assert.match(source,/aria-pressed=\{avatar\.shoeColor === 'white'\}/);
});
