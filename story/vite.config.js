import { defineConfig } from 'vite';
import { resolve } from 'node:path';

// Three built pages: the landing hub (/), the film (/film/) and the JAA paper (/paper/).
// /paper/archive/, /paper/venues/, /notebook/ and /code/ are copied into public/ by scripts/collect.mjs.
export default defineConfig({
  build: {
    target: 'es2022',
    chunkSizeWarningLimit: 900,
    rollupOptions: { input: { main: resolve(__dirname, 'index.html'), film: resolve(__dirname, 'film/index.html'), paper: resolve(__dirname, 'paper/index.html') } },
  },
});
