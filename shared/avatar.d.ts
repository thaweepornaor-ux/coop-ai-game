export type AvatarOptionKey =
  | 'bodyStyle' | 'skinTone' | 'hairStyle' | 'hairColor'
  | 'shirtStyle' | 'shirtColor' | 'bottomStyle' | 'bottomColor'
  | 'shoeColor' | 'glassesStyle' | 'hatStyle' | 'hatColor';

export interface AvatarOption {
  readonly value: string;
  readonly label: string;
  readonly color?: string;
}

export type AvatarChoices = Partial<Record<AvatarOptionKey | "presetId", string>>;
export declare const AVATAR_OPTIONS: Readonly<Record<AvatarOptionKey, readonly AvatarOption[]>>;
export declare function renderAvatar(options?: AvatarChoices | Record<string, unknown>): string;
