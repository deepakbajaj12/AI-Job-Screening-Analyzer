import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react-swc'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/health': { target: process.env.VITE_API_BASE_URL || 'http://backend:8000', changeOrigin: true },
      '/version': { target: process.env.VITE_API_BASE_URL || 'http://backend:8000', changeOrigin: true },
      '/metrics': { target: process.env.VITE_API_BASE_URL || 'http://backend:8000', changeOrigin: true },
      '/analyze': { target: process.env.VITE_API_BASE_URL || 'http://backend:8000', changeOrigin: true },
      '/tasks': { target: process.env.VITE_API_BASE_URL || 'http://backend:8000', changeOrigin: true },
      '/coaching': { target: process.env.VITE_API_BASE_URL || 'http://backend:8000', changeOrigin: true },
      '/admin': { target: process.env.VITE_API_BASE_URL || 'http://backend:8000', changeOrigin: true },
      '/internal': { target: process.env.VITE_API_BASE_URL || 'http://backend:8000', changeOrigin: true },
      '/generate-cover-letter': { target: process.env.VITE_API_BASE_URL || 'http://backend:8000', changeOrigin: true },
      '/generate-interview-questions': { target: process.env.VITE_API_BASE_URL || 'http://backend:8000', changeOrigin: true },
      '/generate-networking-message': { target: process.env.VITE_API_BASE_URL || 'http://backend:8000', changeOrigin: true }
    }
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/setupTests.ts'
  }
})
