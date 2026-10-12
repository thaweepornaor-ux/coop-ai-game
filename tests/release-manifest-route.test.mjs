import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,readFileSync,existsSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {spawnSync} from 'node:child_process';

const stamp=new URL('../scripts/stamp-release.mjs',import.meta.url);
const route=new URL('../app/coop-release.json/route.ts',import.meta.url);
const sha='a'.repeat(40);

test('release stamping embeds exact sha in worker source without relying on public static assets',()=>{
 const cwd=mkdtempSync(join(tmpdir(),'coop-release-'));
 try{
  const run=spawnSync(process.execPath,[stamp.pathname,sha],{cwd,encoding:'utf8',timeout:4000});
  assert.equal(run.status,0,run.stderr);
  const source=readFileSync(join(cwd,'shared/release-manifest.js'),'utf8');
  assert.match(source,/export const RELEASE_MANIFEST=Object.freeze/);
  assert.ok(source.includes(sha));
  assert.equal(existsSync(join(cwd,'public/coop-release.json')),false,'No conflicting static route may be created');
 }finally{rmSync(cwd,{recursive:true,force:true});}
});
test('release stamping rejects malformed SHA and does not write identity',()=>{
 const cwd=mkdtempSync(join(tmpdir(),'coop-release-invalid-'));
 try{
  const run=spawnSync(process.execPath,[stamp.pathname,'not-a-sha'],{cwd,encoding:'utf8',timeout:4000});
  assert.equal(run.status,2);
  assert.equal(existsSync(join(cwd,'shared/release-manifest.js')),false);
 }finally{rmSync(cwd,{recursive:true,force:true});}
});
test('release route uses compiled identity with no-store headers',()=>{
 const source=readFileSync(route,'utf8');
 assert.match(source,/import \{ RELEASE_MANIFEST \} from '\.\.\/\.\.\/shared\/release-manifest\.js'/);
 assert.match(source,/Response\.json\(RELEASE_MANIFEST/);
 assert.match(source,/no-store/);
});
