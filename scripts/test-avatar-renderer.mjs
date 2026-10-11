import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { createHash } from 'node:crypto';
const require=createRequire(import.meta.url),wranglerRequire=createRequire(require.resolve('wrangler'));
const {build}=wranglerRequire('esbuild');
await build({entryPoints:['shared/avatar3d.ts'],outfile:'.sites-runtime/avatar-render-test.mjs',bundle:true,platform:'node',format:'esm'});
await build({entryPoints:['shared/characters.ts'],outfile:'.sites-runtime/avatar-catalogue-test.mjs',bundle:true,platform:'node',format:'esm'});
const {createCharacter,disposeCharacter}=await import('../.sites-runtime/avatar-render-test.mjs');
const {CHARACTERS}=await import('../.sites-runtime/avatar-catalogue-test.mjs');
const fingerprint=x=>createHash('sha256').update(JSON.stringify(x)).digest('hex');
const signatures=[];
for(const p of CHARACTERS){
 const model=createCharacter({presetId:p.id,bodyStyle:p.gender,shirtStyle:'tshirt',shirtColor:'white',bottomStyle:'pants',hatStyle:'none'});
 const meshes=[];model.traverse(o=>{if(o.geometry){assert.equal(o.geometry.vertices.every(Number.isFinite),true,p.id+' vertices');assert.equal(o.geometry.normals.every(Number.isFinite),true,p.id+' normals');assert.match(o.material.color,/^#[0-9a-f]{6}$/i);meshes.push(o);}});
 assert.ok(meshes.length<120,p.id+' model budget');
 signatures.push(fingerprint(meshes.map(o=>({v:o.geometry.vertices,n:o.geometry.normals,p:o.position,s:o.scale,c:o.material.color}))));
 disposeCharacter(model);
}
assert.equal(new Set(signatures).size,20,'twenty distinct geometries at identical clothes/color');
const shirtColors=['lightgreen','white','red','gray','charcoal','blueviolet'];
const expected=['#A7CE98','#F2F3EE','#C74745','#93999F','#30343B','#545994'];
for(let i=0;i<6;i++){
 const m=createCharacter({presetId:'F08',bodyStyle:'female',shirtStyle:'tshirt',shirtColor:shirtColors[i]});
 const colors=[];m.traverse(o=>{if(o.material)colors.push(o.material.color)});assert.ok(colors.includes(expected[i]));assert.ok(colors.includes('#F4CEB5')||colors.includes('#DFAC86'),'skin retains own material');disposeCharacter(m);
}
const styles=['tshirt','polo','shirt','jacket'].map(shirtStyle=>{const m=createCharacter({presetId:'M03',bodyStyle:'male',shirtStyle});const signature=fingerprint(m.children.map(o=>({v:o.geometry?.vertices,c:o.material?.color})));disposeCharacter(m);return signature;});assert.equal(new Set(styles).size,4);
for(const hatStyle of ['none','cap','bucket','beret'])for(const bottomStyle of ['pants','skirt']){const m=createCharacter({presetId:'F10',bodyStyle:'female',hatStyle,bottomStyle});assert.ok(m.children.length>10);disposeCharacter(m);}
console.log('3D geometry checks passed:20 unique presets, finite smooth normals/materials,6 independent shirt colors,4 tops,2 bottoms,4 hats; bounded mesh count. GPU/device tests not performed.');
