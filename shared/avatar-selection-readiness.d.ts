import type {AvatarChoices} from './avatar.js';
export interface AvatarSelectionReadiness {ready:boolean;reasons:string[];selected:Array<{value:string;label:string;gender?:'male'|'female';src:string;ready:boolean;aligned:boolean;playable?:boolean}>}
export function avatarSelectionReadiness(choices:Partial<AvatarChoices>|Record<string,unknown>,catalog?:Record<string,Array<{value:string;label:string;src:string;ready:boolean;aligned:boolean}>>):AvatarSelectionReadiness;
