import { defineConfig } from 'vite';
import { resolve } from 'node:path';

// Two built pages: the landing hub (/) and the film (/film/).
// /paper/ and /notebook/ are copied into public/ by scripts/collect.mjs.
export default defineConfig({
  build: {
    target: 'es2022',
    chunkSizeWarningLimit: 900,
    rollupOptions: { input: { main: resolve(__dirname, 'index.html'), film: resolve(__dirname, 'film/index.html') } },
  },
});
