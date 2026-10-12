import test from 'node:test';
import assert from 'node:assert/strict';
import {avatarSelectionReadiness} from '../shared/avatar-selection-readiness.js';
import {PNG_PARTS} from '../shared/avatar-png-catalog.js';
const choices={bodyStyle:'male',hairStyle:'shoulder',shirtStyle:'jacket',bottomStyle:'pants',shoeColor:'white',glassesStyle:'none'};
test('existing authentic thumbnail PNGs cannot go live without alignment and body',()=>{
 const result=avatarSelectionReadiness(choices);
 assert.equal(result.ready,false);
 assert.ok(result.reasons.includes('body-base'));
 assert.ok(result.reasons.includes('unaligned:face'));
 assert.ok(!result.reasons.includes('missing:shoes'));
 assert.ok(!result.reasons.includes('missing:top'));
});
test('glasses missing is required only when player has selected glasses',()=>{
 const no=avatarSelectionReadiness(choices);
 const yes=avatarSelectionReadiness({...choices,glassesStyle:'round'});
 assert.equal(no.reasons.includes('missing:glasses'),false);
 assert.equal(yes.reasons.includes('missing:glasses'),true);
});
test('correct gender and specific garment are required instead of any unrelated upload',()=>{
 const female=avatarSelectionReadiness({...choices,bodyStyle:'female',shirtStyle:'polo'});
 assert.ok(female.reasons.includes('missing:top'));
 const noHair=avatarSelectionReadiness({...choices,hairStyle:'bald'});
 assert.equal(noHair.reasons.includes('missing:hair'),false);
});
test('a fully prepared selected outfit can pass even if other catalog entries are unapproved',()=>{
 const catalog=Object.fromEntries(Object.entries(PNG_PARTS).map(([k,v])=>[k,v.map(p=>({...p,aligned:p.ready}))]));
 const result=avatarSelectionReadiness(choices,catalog,{hasBodyBase:true});
 assert.equal(result.ready,true);
 assert.deepEqual(result.reasons,[]);
});
