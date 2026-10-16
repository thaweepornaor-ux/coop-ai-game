import test from 'node:test';import assert from 'node:assert/strict';import {readFileSync} from 'node:fs';
const game=readFileSync('app/game.tsx','utf8');
const wardrobe=readFileSync('app/components/simple-wardrobe.tsx','utf8');
test('every real learner, teacher, waiting, quiz and scoreboard avatar shares one aligned SVG rig',()=>{
 const figures=[...game.matchAll(/<Avatar\b[^>]*\/>/g)].map(x=>x[0]);
 assert.ok(figures.length>=11,'the real game must preserve all avatar placements');
 for(const tag of figures)assert.match(tag,/\bsvgOnly\b/,'mismatched PNG overlay in '+tag);
 for(const className of ['waiting-avatar','spotlight-avatar','reveal-avatar','result-personal-avatar','result-podium-avatar','result-score-avatar']){
  assert.ok(game.includes(className),'missing required gameplay avatar scene '+className);
 }
});
test('external preset changes restore correct pose without interrupting outfit and manual pose changes',()=>{
 assert.match(wardrobe,/useEffect\(\(\)=>\{setPreviewPose\(poseForAvatarPreset\(avatar\.presetId\)\)\},\[avatar\.presetId\]\)/);
 assert.match(wardrobe,/onClick=\{\(\)=>setPreviewPose\(item\.value\)\}/);
 assert.match(wardrobe,/options=\{selectedId===c\.id\?avatar:/);
});
