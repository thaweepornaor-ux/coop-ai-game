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

test('confident pose has separate hands with defined digits on both sides',()=>{
 for(const bodyStyle of genders){
  const svg=renderAvatar({pose:'confident',bodyStyle});
  for(const side of ['left','right']){
   const hand=svg.match(new RegExp('<g data-avatar-part="'+side+'-confident-hand">([\\s\\S]*?)<\\/g>'));
   assert.ok(hand, side+' hand missing');
   assert.match(hand[1],/data-avatar-part="closed-hand"/);
   assert.match(hand[1],/<path/);
  }
 }
});

test('every sleeve is finished by a pose-aligned soft cuff, not a disconnected dark outline',()=>{
 for(const pose of poses)for(const bodyStyle of genders){
  const svg=renderAvatar({pose,bodyStyle});
  assert.equal((svg.match(/data-avatar-part="sleeve-fold"/g)||[]).length,2,'two shoulder-to-cuff fabric fold highlights');
  assert.equal((svg.match(/data-avatar-part="sleeve-cuff"/g)||[]).length,2,`${pose}/${bodyStyle}: two visible fabric hems`);
  assert.equal((svg.match(/data-avatar-part="sleeve-cuff"[^>]*stroke-opacity="0.5"/g)||[]).length,2,'polo shirt cuffs use their fabric-specific soft seam');
  assert.doesNotMatch(svg,/stroke-width="12"/,'no tubular sleeve overlays');
 }
});
