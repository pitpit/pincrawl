import { defineConfig } from 'vite'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [
    tailwindcss(),
  ],
  build: {
    outDir: 'dist',
    rollupOptions: {
      input: '/src/main.ts',
      output: {
        assetFileNames: (assetInfo) => {
          if (assetInfo?.name?.endsWith('.css')) {
            return 'css/[name][extname]'
          }
          return 'css/[name][extname]'
        },
        chunkFileNames: 'js/[name].js',
        entryFileNames: 'js/[name].js',
      }
    }
  }
})