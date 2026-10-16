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

test('customize control scrolls to editable options and remains a real button',()=>{
 const src=readFileSync('app/components/simple-wardrobe.tsx','utf8');
 assert.match(src,/className="wardrobe-live-indicator wardrobe-edit-action" type="button"/);
 assert.match(src,/scrollIntoView\(\{behavior:"smooth",block:"start"\}\)/);
 assert.match(src,/id="character-customization"/);
 assert.match(src,/customizer-highlight/);
});
