/** UTF-8 CSV for the trainer. No data is sent to a third-party service. */
const number=(value,maximum=15)=>Number.isSafeInteger(value)?Math.min(maximum,Math.max(0,value)):0;
const cell=(value)=>{
  let text=String(value??'').replace(/[\u0000-\u001f\u007f]/g,' ').trim();
  // Spreadsheet import must never evaluate learner-controlled names as formulas.
  if(/^[=+@\-]/.test(text))text="'"+text;
  return '"'+text.replace(/"/g,'""')+'"';
};
export function scoreCsv(leaderboard){
 if(!Array.isArray(leaderboard))throw new TypeError('Expected a leaderboard');
 const header=['อันดับ','ชื่อผู้เรียน','คะแนน (เต็ม 15)','ตอบถูก','ตอบผิด','ไม่ได้ตอบ','ระดับความเข้าใจ'];
 const rows=leaderboard.map(person=>[
  number(person.rank,100000),person.name,number(person.score),
  number(person.correctCount),number(person.incorrectCount),
  number(person.unansweredCount),person.level||''
 ]);
 // BOM ensures that Excel imports Thai text as UTF-8 without mojibake.
 return '\ufeff'+[header,...rows].map(row=>row.map(cell).join(',')).join('\r\n')+'\r\n';
}
