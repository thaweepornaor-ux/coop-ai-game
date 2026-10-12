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
