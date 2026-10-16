import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const avatar=readFileSync(new URL('../app/components/avatar.tsx',import.meta.url),'utf8');
const css=readFileSync(new URL('../app/globals.css',import.meta.url),'utf8');
test('live avatar uses the game motion toggle rather than animating all previews',()=>{
 assert.match(avatar,/svgOnly=false,motion=false/);
 assert.match(avatar,/motion\?'game-avatar-motion game-avatar-motion-'\+pose/);
 assert.match(css,/\.game-avatar-motion-wave>div/);
 assert.match(css,/\.game-avatar-motion-celebrate>div/);
 assert.match(css,/prefers-reduced-motion:reduce\)\{\.game-avatar-motion>div\{animation:none!important/);
 assert.match(css,/\.motion-off \.game-avatar-motion>div\{animation:none!important/);
});
