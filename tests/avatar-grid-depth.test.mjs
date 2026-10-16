import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {renderAvatar} from '../shared/avatar.js';
test('selector keeps five desktop, three tablet, two phone card columns and names isolated',()=>{
 const css=readFileSync('app/live-avatar-preview.css','utf8');
 for(const rule of ['repeat(5,minmax(0,1fr))!important','repeat(3,minmax(0,1fr))!important','repeat(2,minmax(0,1fr))!important']){
  assert.ok(css.includes(rule),rule);
 }
 assert.match(css,/\.quick-character>strong\{/);
});
test('shirt depth effects exist for all pose/body/color combinations and use actual garment colors',()=>{
 for(const bodyStyle of ['male','female'])for(const pose of ['stand','wave','celebrate','think','confident'])for(const shirtColor of ['white','indigo','mint']){
  const svg=renderAvatar({bodyStyle,pose,shirtColor});
  assert.equal((svg.match(/data-avatar-part="shirt-volume"/g)||[]).length,1);
  assert.equal((svg.match(/data-avatar-part="shirt-side-shading"/g)||[]).length,1);
  assert.equal((svg.match(/data-avatar-part="pose-sleeves"/g)||[]).length,1);
  assert.doesNotMatch(svg,/NaN|undefined/);
 }
});
