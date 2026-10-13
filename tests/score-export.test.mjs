import test from 'node:test';
import assert from 'node:assert/strict';
import {scoreCsv} from '../shared/score-export.js';

test('Thai CSV is Excel readable and contains the full scoring breakdown',()=>{
 const csv=scoreCsv([{rank:1,name:'ทดสอบ, "เอไอ"',score:12,correctCount:12,incorrectCount:2,unansweredCount:1,level:'นักรู้ทัน AI'}]);
 assert.ok(csv.startsWith('\ufeff'));
 assert.equal(csv.split('\r\n').filter(Boolean).length,2);
 assert.match(csv,/ชื่อผู้เรียน/);
 assert.match(csv,/"ทดสอบ, ""เอไอ"""/);
 assert.match(csv,/"12","12","2","1","นักรู้ทัน AI"/);
});
test('arbitrary user names cannot execute spreadsheet formulas',()=>{
 const names=['=HYPERLINK("https://evil.example")','+SUM(1,1)','-1+2','@SUM(A1)',' =2+2'];
 const csv=scoreCsv(names.map((name,i)=>({rank:i+1,name,score:0})));
 for(const name of names){
  const escaped=name.replace(/"/g,'""').trim();
  assert.ok(csv.includes('"\''+escaped+'"'),'Must neutralize '+name);
 }
 assert.ok(!csv.includes('"=HYPERLINK'));
});
test('scores cannot overflow assessment limits and leaderboard must exist',()=>{
 assert.throws(()=>scoreCsv(null),TypeError);
 const csv=scoreCsv([{rank:1,name:'ปิง',score:999,correctCount:999,incorrectCount:-4,unansweredCount:null}]);
 assert.ok(csv.includes('"15","15","0","0"'));
 assert.equal(scoreCsv([]).split('\r\n').filter(Boolean).length,1);
});
