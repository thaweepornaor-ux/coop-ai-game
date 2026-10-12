import test from 'node:test';
import assert from 'node:assert/strict';
import {avatarLayerRect,AVATAR_CANVAS_WIDTH,AVATAR_CANVAS_HEIGHT} from '../shared/avatar-png-layout.js';

test('ordinary landscape image keeps requested scale and center',()=>{
 const rect=avatarLayerRect(400,200,{x:50,y:50,scale:50});
 assert.deepEqual(rect,{left:150,top:325,width:300,height:150});
});
test('portrait image obeys max layer height and maintains ratio',()=>{
 const rect=avatarLayerRect(200,800,{x:50,y:50,scale:100});
 assert.equal(rect.height,AVATAR_CANVAS_HEIGHT*.65);
 assert.equal(rect.width,130);
 assert.equal(rect.left,235);
 assert.equal(rect.top,140);
});
test('custom canvas dimensions scale consistently',()=>{
 const r=avatarLayerRect(100,100,{x:25,y:75,scale:40},300,400);
 assert.deepEqual(r,{left:15,top:240,width:120,height:120});
});
test('invalid dimensions and saved percentages reject bad inputs',()=>{
 for(const args of [[0,100,{x:50,y:50,scale:50}],[100,0,{x:50,y:50,scale:50}],[100,100,{x:-1,y:50,scale:50}],[100,100,{x:50,y:50,scale:0}],[100,100,{x:50,y:NaN,scale:50}]])
  assert.throws(()=>avatarLayerRect(...args),RangeError);
 assert.equal(AVATAR_CANVAS_WIDTH,600);
});
