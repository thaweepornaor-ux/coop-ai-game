import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
test('real character selector has reference-style selectable cards while retaining accessibility',()=>{
 const css=readFileSync('app/live-avatar-preview.css','utf8');
 assert.match(css,/\.quick-character\[aria-pressed="true"\]/);
 assert.match(css,/\.quick-character:focus-visible/);
 assert.match(css,/radial-gradient\(ellipse at 50% 38%/);
 assert.match(css,/\.wardrobe-live-avatar\{/);
 assert.match(css,/@media\(prefers-reduced-motion:reduce\)/);
});
