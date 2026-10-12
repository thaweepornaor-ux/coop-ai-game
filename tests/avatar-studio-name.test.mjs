import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const source=readFileSync(new URL('../app/avatar-studio/page.tsx',import.meta.url),'utf8');

test('avatar studio name is independent of appearance preset',()=>{
 assert.match(source,/const \[characterName,setCharacterName\]=useState\(''\)/);
 assert.match(source,/const nameKey='coop-ai-avatar-studio-name-v1'/);
 assert.match(source,/\{cleanName\(characterName\)\|\|'ตัวละครของคุณ'\}/);
 assert.match(source,/maxLength=\{24\}/);
});
test('avatar name is restored, saved and cleared with draft controls',()=>{
 assert.match(source,/setCharacterName\(cleanName\(localStorage\.getItem\(nameKey\)\|\|localStorage\.getItem\('coop-ai-game-name'\)\)\)/);
 assert.match(source,/localStorage\.setItem\(nameKey,cleanName\(characterName\)\)/);
 assert.match(source,/setCharacterName\(''\)/);
 assert.match(source,/Array\.from\(value\.trim\(\)\)\.slice\(0,24\)/);
});
test('appearance preset changes do not overwrite custom name',()=>{
 const apply=source.slice(source.indexOf(' const preset=(person:'),source.indexOf(' const save='));
 assert.ok(apply.includes('setAvatar('));
 assert.ok(!apply.includes('setCharacterName('));
});
