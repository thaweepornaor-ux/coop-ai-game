import test from 'node:test';
import assert from 'node:assert/strict';
import {AVATAR_OPTIONS, renderAvatar} from '../shared/avatar.js';

test('wardrobe has exactly four optional glasses choices', () => {
 assert.deepEqual(AVATAR_OPTIONS.glassesStyle.map(x=>x.value), ['none','round','rectangle','aviator']);
});
test('different eyewear variants render distinct SVG and never print user input', () => {
 const variants=['none','round','rectangle','aviator'].map(glassesStyle=>renderAvatar({glassesStyle}));
 assert.equal(new Set(variants).size,4);
 for(const svg of variants) assert.match(svg,/^<svg[\s\S]*<\/svg>$/);
 assert.equal(renderAvatar({glassesStyle:'<script>alert(1)</script>'}),variants[0]);
});
test('legacy avatar remains valid when eyewear is absent',()=>{
 assert.equal(renderAvatar({bodyStyle:'male'}),renderAvatar({bodyStyle:'male',glassesStyle:'none'}));
});
