import { RELEASE_MANIFEST } from '../../shared/release-manifest.js';

// Serve release identity through the application router, not static asset routing.
// The SHA is stamped before the build, then bundled into this route.
export function GET() {
 return Response.json(RELEASE_MANIFEST,{headers:{'Cache-Control':'no-store, max-age=0','X-Content-Type-Options':'nosniff'}});
}
