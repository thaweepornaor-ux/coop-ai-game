import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const lab=readFileSync(new URL('../app/components/png-assembly-preview.tsx',import.meta.url),'utf8');
const wardrobe=readFileSync(new URL('../app/components/wardrobe.tsx',import.meta.url),'utf8');
test('real PNG experiment is embedded in character selection, not game Avatar renderer',()=>{
 assert.match(wardrobe,/import \{ PngAssemblyPreview \} from '\.\/png-assembly-preview'/);
 assert.match(wardrobe,/<PngAssemblyPreview gender=\{gender\}\/>/);
 assert.match(lab,/Never replaces the playable avatar/);
});
test('workbench only offers uploaded parts and has x/y/scale controls',()=>{
 assert.match(lab,/filter\(p=>p\.ready\)/);
 assert.match(lab,/\['bottom','shoes','top','face','hair'\]/);
 for(const key of ['x','y','scale'])assert.ok(lab.includes(key));
 assert.match(lab,/type="range"/);
});

test('alignment settings can be saved and restored with bounded values',()=>{
 assert.match(lab,/localStorage\.getItem\(storageKey\)/);
 assert.match(lab,/localStorage\.setItem\(storageKey,JSON\.stringify\(positions\)\)/);
 assert.match(lab,/Number\.isFinite\(v\[key\]\)/);
 assert.match(lab,/setPositions\(verified\)/);
 assert.match(lab,/บันทึกตำแหน่ง/);
});

test('saved selected PNG part names are restored from verified uploaded assets only',()=>{
 assert.match(lab,/localStorage\.getItem\(selectionKey\)/);
 assert.match(lab,/localStorage\.setItem\(selectionKey,JSON\.stringify\(\{\.\.\.picked,face:undefined\}\)\)/);
 assert.match(lab,/PNG_PARTS\[category\]\.some\(part=>part\.ready&&part\.src===src\)/);
 assert.match(lab,/setPicked\(valid\)/);
});

test('face image follows selected gender and reset clears old image choices',()=>{
 assert.match(lab,/delete valid\.face/);
 assert.match(lab,/category==='face'/);
 assert.match(lab,/endsWith\('\/'\+gender\+'\.png'\)/);
 assert.match(lab,/setPicked\(\{\}\)/);
});

test('broken PNGs are hidden and reported instead of displaying broken image icons',()=>{
 assert.match(lab,/onError=\{\(\)=>setBroken\(/);
 assert.match(lab,/!broken\.includes\(part\.src\)/);
 assert.match(lab,/role="alert"/);
});

test('failed PNG layers can be explicitly retried after a transient load error',()=>{
 assert.match(lab,/onClick=\{\(\)=>setBroken\(\[\]\)\}/);
 assert.match(lab,/ลองโหลดภาพอีกครั้ง/);
});

test('alignment preview can temporarily hide and fade individual layers',()=>{
 assert.match(lab,/!hidden\.includes\(category\)/);
 assert.match(lab,/opacity:editing===category\?opacity\/100:1/);
 assert.match(lab,/type="checkbox"/);
 assert.match(lab,/แสดงภาพ\{labels\[editing\]\}/);
});

test('reviewer can export an actual layered PNG at stable dimensions',()=>{
 assert.match(lab,/canvas\.width=AVATAR_CANVAS_WIDTH;canvas\.height=AVATAR_CANVAS_HEIGHT/);
 assert.match(lab,/await image\.decode\(\)/);
 assert.match(lab,/ctx\.drawImage\(/);
 assert.match(lab,/canvas\.toBlob\(/);
 assert.match(lab,/anchor\.download='coop-avatar-png-preview\.png'/);
 assert.match(lab,/disabled=\{exporting\}/);
});

test('preview and export share one tested geometry calculation',()=>{
 assert.match(lab,/avatarLayerRect\(image\.naturalWidth,image\.naturalHeight,positions\[category\],canvas\.width,canvas\.height\)/);
 assert.match(lab,/avatarLayerRect\(d\.width,d\.height,a\)/);
 assert.match(lab,/onLoad=\{e=>\{const width=e\.currentTarget\.naturalWidth,height=e\.currentTarget\.naturalHeight/);
});

test('alignment lab exports only validated PNG snapshot JSON for approval',()=>{
 assert.match(lab,/validateAssemblySnapshot\(\{version:PNG_ASSEMBLY_VERSION,gender,positions,selected\}\)/);
 assert.match(lab,/JSON\.stringify\(snapshot,null,2\)/);
 assert.match(lab,/anchor\.download='coop-avatar-layout-'\+gender\+'\.json'/);
 assert.match(lab,/onClick=\{exportSettings\}/);
});

test('validated PNG JSON import rejects incorrect gender and unverified assets',()=>{
 assert.match(lab,/const snapshot=validateAssemblySnapshot\(JSON\.parse\(raw\)\)/);
 assert.match(lab,/if\(snapshot\.gender!==gender\)throw/);
 assert.match(lab,/setPositions\(snapshot\.positions\)/);
 assert.match(lab,/setPicked\(\{\.\.\.snapshot\.selected,face:undefined\}\)/);
 assert.match(lab,/file\.size>64\*1024/);
 assert.match(lab,/accept="\.json,application\/json"/);
});
