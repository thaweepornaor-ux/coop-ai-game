export declare const STUDIO_DRAFT_KEY:string;
export declare const STUDIO_NAME_KEY:string;
export declare const STUDIO_TRANSFER_KEY:string;
export declare function cleanStudioName(value:unknown):string;
export declare function cleanStudioAvatar(value:unknown):Record<string,string>|null;
export declare function validateStudioTransfer(value:unknown):{version:1;name:string;avatar:Record<string,string>}|null;
