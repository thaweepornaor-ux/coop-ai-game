import type { ProductionManifest } from './avatar-production-contract.mjs';

/**
 * Keep the current renderer active. Genuine Rain/Snow export inventory is still
 * pending. Add reviewed, SHA-verified bindings here only after the production
 * GLB, identity/wardrobe coverage, deformation and browser checks pass.
 */
export const PRODUCTION_AVATAR_ENABLED: boolean = false;
export const PRODUCTION_AVATAR_MANIFEST: ProductionManifest | null = null;
