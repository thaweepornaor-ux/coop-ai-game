import test from 'node:test';
import assert from 'node:assert/strict';
import { renderAvatar } from '../shared/avatar.js';

const poses = ['stand', 'wave', 'celebrate', 'think', 'confident'];
const genders = ['male', 'female'];
const shirts = ['tshirt', 'polo', 'shirt', 'jacket'];

test('every playable pose uses two closed pose-aware fabric sleeves for all outfits', () => {
  for (const bodyStyle of genders) for (const pose of poses) for (const shirtStyle of shirts) {
    const svg = renderAvatar({bodyStyle, pose, shirtStyle, shirtColor: 'indigo'});
    const group = svg.match(/<g data-avatar-part="pose-sleeves">([\s\S]*?)<\/g>/);
    assert.ok(group, `missing sleeve group: ${bodyStyle}/${pose}/${shirtStyle}`);
    const shapes = [...group[1].matchAll(/<path data-sleeve-side="(left|right)" d="([^"]+)"[^>]+\/>/g)];
    assert.deepEqual(shapes.map(shape => shape[1]), ['left', 'right']);
    for (const shape of shapes) {
      assert.match(shape[2], /Z$/, 'fabric outlines must be closed');
      assert.match(shape[0], /fill="url\(#avatar-shirt-lit\)"/);
    }
    assert.doesNotMatch(svg, /M46 113L55 118M105 118L114 113/, 'fixed legacy seam must not return');
    assert.doesNotMatch(svg, /stroke-width="12"/, 'wide painted sleeve strokes obscure anatomy');
  }
});

test('raised arm fabric differs from neutral arm fabric', () => {
 const neutral = renderAvatar({pose: 'stand'});
 for(const pose of ['wave', 'celebrate', 'think', 'confident']) {
   const candidate = renderAvatar({pose});
   const find = svg => svg.match(/<g data-avatar-part="pose-sleeves">([\s\S]*?)<\/g>/)?.[1];
   assert.notEqual(find(candidate), find(neutral), `${pose} needs specific sleeve outlines`);
 }
});
