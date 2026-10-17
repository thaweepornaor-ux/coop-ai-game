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

test('live character preview and all wardrobe options are visible without nested scrolling',()=>{
 const src=readFileSync('app/components/simple-wardrobe.tsx','utf8');
 const css=readFileSync('app/globals.css','utf8');
 const previewCss=readFileSync('app/live-avatar-preview.css','utf8');
 assert.match(src,/id="character-customization"/);
 assert.match(src,/className="quick-options"/);
 assert.match(src,/className="wardrobe-live-preview"/);
 assert.match(src,/choices\.map/);
 assert.doesNotMatch(src,/wardrobe-edit-action|customizationFocus|customizer-highlight/);
 assert.match(css,/\.quick-options\{[^}]*max-height:none;overflow:visible/);
 assert.match(previewCss,/position:sticky;top:0/);
});
