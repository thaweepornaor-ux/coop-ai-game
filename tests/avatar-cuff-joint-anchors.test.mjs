import test from 'node:test';
import assert from 'node:assert/strict';
import {renderAvatar} from '../shared/avatar.js';

// Each exposed forearm begins at the same coordinate as its shirt cuff.
// Never reintroduce free-floating skin shapes painted behind a sleeve.
const anchors={
 stand:['M39 118','M121 118'],
 wave:['M30 93','M121 118'],
 celebrate:['M32 88','M128 88'],
 think:['M39 118','M120 118'],
 confident:['M40 118','M120 118']
};
test('actual two forearms are anchored to the two pose-aware cuffs in forty body and shirt combinations',()=>{
 for(const [pose,[left,right]] of Object.entries(anchors))for(const bodyStyle of ['male','female'])for(const shirtStyle of ['tshirt','polo','shirt','jacket']){
  const svg=renderAvatar({pose,bodyStyle,shirtStyle,skinTone:'tan'});
  const group=svg.match(/<g fill="url\(#avatar-skin-lit\)">([\s\S]*?)<\/g>/)?.[1]??'';
  assert.match(group,new RegExp('data-avatar-part="left-forearm" d="'+left));
  assert.match(group,new RegExp('data-avatar-part="right-forearm" d="'+right));
  assert.equal((group.match(/data-avatar-part="(left|right)-forearm"/g)||[]).length,2,pose+' exposed arms');
  assert.equal((svg.match(/data-avatar-part="sleeve-cuff"/g)||[]).length,2,pose+' fabric cuffs');
  assert.doesNotMatch(svg,/NaN|undefined/);
 }
});
