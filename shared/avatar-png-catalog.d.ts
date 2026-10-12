export interface PngPart { readonly value:string;readonly label:string;readonly src:string;readonly ready:boolean;readonly aligned:boolean;playable?:boolean; }
export declare const PNG_PARTS: Readonly<{body:readonly PngPart[];face:readonly PngPart[];hair:readonly PngPart[];top:readonly PngPart[];bottom:readonly PngPart[];shoes:readonly PngPart[];glasses:readonly PngPart[]}>;
export declare const PNG_ASSETS_DIRECTORY:string;
