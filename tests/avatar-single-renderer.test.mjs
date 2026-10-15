import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { renderAvatar } from '../shared/avatar.js';

test('React Avatar always uses a single SVG renderer across neutral and posed states', () => {
 const source=readFileSync(new URL('../app/components/avatar.tsx',import.meta.url),'utf8');
 assert.match(source, /renderAvatar\(/);
 assert.doesNotMatch(source, /playableAvatarLayers|PNG_PARTS|everyLoaded|<img\b/, 'mixed PNG and SVG rendering changes character appearance between poses');
 for(const pose of ['stand','wave','celebrate','think','confident']){
  const svg=renderAvatar({pose,bodyStyle:'female',hairStyle:'long',hairColor:'silver',shirtStyle:'polo',shirtColor:'teal',glassesStyle:'round'});
  assert.match(svg, /pose-sleeves/);
  assert.match(svg, /#409E91/i, 'selected shirt color should persist in every pose');
  assert.match(svg, /#A7ABB6/i, 'selected hair color should persist in every pose');
 }
});
