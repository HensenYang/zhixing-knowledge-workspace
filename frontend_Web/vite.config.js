import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
export default defineConfig({plugins:[react()],server:{host:'127.0.0.1',port:5174,strictPort:true,proxy:{'/api':{target:process.env.WORKSPACE_API_TARGET || 'http://127.0.0.1:8001',changeOrigin:true}}},build:{rollupOptions:{output:{manualChunks:{react:['react','react-dom','react-router-dom'],canvas:['@xyflow/react'],graph:['cytoscape'],markdown:['react-markdown','remark-gfm','remark-math','rehype-katex'],math:['katex']}}}}})
