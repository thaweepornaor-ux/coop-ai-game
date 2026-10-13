export interface ScoreRow {
 rank:number;
 name:string;
 score:number;
 correctCount:number;
 incorrectCount:number;
 unansweredCount:number;
 level?:string;
}
export function scoreCsv(leaderboard:readonly ScoreRow[]):string;
