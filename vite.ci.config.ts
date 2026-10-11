import { defineConfig } from 'vite';
import vinext from 'vinext';

process.env.CLOUDFLARE_CF_FETCH_ENABLED ??= 'false';
process.env.WRANGLER_SEND_METRICS ??= 'false';

export default defineConfig(async () => {
  const { cloudflare } = await import('@cloudflare/vite-plugin');
  return {
    server: { host: '127.0.0.1', port: 4173, strictPort: true },
    preview: { host: '127.0.0.1', port: 4173, strictPort: true },
    plugins: [
      vinext(),
      cloudflare({
        configPath: './wrangler.ci.jsonc',
        viteEnvironment: { name: 'rsc', childEnvironments: ['ssr'] },
        remoteBindings: false,
        persistState: { path: '.wrangler/ci-state' },
        inspectorPort: false,
      }),
    ],
  };
});
