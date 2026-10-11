import type { AnimationName, ProductionManifest } from './avatar-production-contract.mjs';
export interface HeroController {
  updateSelection(selection: Record<string, unknown>): void;
  play(name: AnimationName): void;
  rotate(delta: number): void;
  setMotion(value: boolean): void;
  setVisible(value: boolean): void;
  dispose(): void;
}
export interface ThumbnailLease { url: string; release(): void; }
export function prepareProductionCatalog(manifest: ProductionManifest, options?: { mode?: 'production' | 'staging' }): Promise<{ revision: string; mode: 'production' | 'staging'; release(): void }>;
export function createProductionHero(canvas: HTMLCanvasElement, selection: Record<string, unknown>, options: {
  manifest: ProductionManifest; signal?: AbortSignal; motion?: boolean; visible?: boolean; mode?: 'production' | 'staging';
  onState?: (state: 'ready' | 'context-lost') => void;
}): Promise<HeroController>;
export function acquireProductionThumbnail(selection: Record<string, unknown>, options: {
  manifest: ProductionManifest; signal?: AbortSignal; mode?: 'production' | 'staging';
}): Promise<ThumbnailLease>;
export function disposeUnusedProductionResources(): void;
