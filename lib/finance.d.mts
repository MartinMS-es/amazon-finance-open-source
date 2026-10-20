export const markets:Record<string,string>;
export const categories:string[];
export const currencies:string[];
export function money(value:unknown):number;
export function csvParse(text:string):Record<string,string>[];
export function normalizeRow(row:any):any;
export function exportCsv(rows:any[]):string;
export function csvEscape(value:unknown):string;
export function summarize(rows:any[]):{sales:number;refunds:number;fees:number;net:number};
export function matchCandidates(doc:any,rows:any[]):any[];

