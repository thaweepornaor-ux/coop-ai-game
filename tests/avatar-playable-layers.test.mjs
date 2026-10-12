import test from 'node:test';
import assert from 'node:assert/strict';
import {playableAvatarLayers,AVATAR_DRAW_ORDER} from '../shared/avatar-playable-layers.js';
import {PNG_PARTS} from '../shared/avatar-png-catalog.js';

const choices={bodyStyle:'male',hairStyle:'shoulder',shirtStyle:'jacket',bottomStyle:'pants',shoeColor:'white',glassesStyle:'none'};
const at={x:50,y:50,scale:45};
const readyPart=(value,src)=>({value,src,ready:true,aligned:true,playable:true,position:{...at}});

function completeCatalog(){
 return {
  body:[readyPart('male','/avatar-parts/body-male.png')],
  face:[readyPart('male','/avatar-parts/face-male.png')],
  hair:[readyPart('shoulder','/avatar-parts/hair.png')],
  top:[readyPart('jacket','/avatar-parts/jacket.png')],
  bottom:[readyPart('pants','/avatar-parts/pants.png')],
  shoes:[readyPart('white','/avatar-parts/shoes.png')],
  glasses:[readyPart('round','/avatar-parts/glasses.png')]
 };
}
test('approved full PNG outfit is returned in correct layer order',()=>{
 const out=playableAvatarLayers(choices,completeCatalog());
 assert.equal(out.ready,true);
 assert.deepEqual(out.layers.map(layer=>layer.category),['body','bottom','shoes','top','face','hair']);
 assert.deepEqual(AVATAR_DRAW_ORDER,['body','bottom','shoes','top','face','hair','glasses']);
});
test('missing position must not render a partial PNG body',()=>{
 const catalog=completeCatalog();
 delete catalog.top[0].position;
 const out=playableAvatarLayers(choices,catalog);
 assert.equal(out.ready,false);
 assert.ok(out.issues.includes('position:top'));
 assert.deepEqual(out.layers,[]);
});
test('out-of-range position and missing body never render a partial stack',()=>{
 const catalog=completeCatalog();
 catalog.face[0].position={x:101,y:40,scale:45};
 assert.equal(playableAvatarLayers(choices,catalog).ready,false);
 catalog.face[0].position=at;
 catalog.body=[];
 const result=playableAvatarLayers(choices,catalog);
 assert.equal(result.ready,false);
 assert.ok(result.issues.includes('body-base'));
});
test('optional glasses included only when chosen; bald character needs no hair',()=>{
 const catalog=completeCatalog();
 const withGlasses=playableAvatarLayers({...choices,glassesStyle:'round'},catalog);
 assert.equal(withGlasses.ready,true);
 assert.equal(withGlasses.layers.at(-1).category,'glasses');
 const bald=playableAvatarLayers({...choices,hairStyle:'bald'},catalog);
 assert.equal(bald.ready,true);
 assert.ok(!bald.layers.some(layer=>layer.category==='hair'));
});
test('today\'s tiny mixed-gender trial art cannot replace main avatar',()=>{
 const result=playableAvatarLayers(choices,PNG_PARTS);
 assert.equal(result.ready,false);
 assert.deepEqual(result.layers,[]);
});
