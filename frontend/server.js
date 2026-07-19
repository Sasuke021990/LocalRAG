const express = require('express');
const { createProxyMiddleware } = require('http-proxy-middleware');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3000;
const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';
// If the backend requires an API key, inject it here server-side so it
// never reaches the browser bundle.
const API_KEY = process.env.API_KEY || '';

// Proxy /api/* → backend (strip /api prefix)
// e.g. /api/categories → http://backend:8000/categories
app.use('/api', createProxyMiddleware({
    target: BACKEND_URL,
    changeOrigin: true,
    pathRewrite: { '^/api': '' },
    on: {
        proxyReq: (proxyReq) => {
            if (API_KEY) proxyReq.setHeader('x-api-key', API_KEY);
        },
    },
}));

// Proxy /swagger/* → backend (strip /swagger prefix)
// Used by the embedded iframe: /swagger/docs → http://backend:8000/docs
app.use('/swagger', createProxyMiddleware({
    target: BACKEND_URL,
    changeOrigin: true,
    pathRewrite: { '^/swagger': '' }
}));

// Serve Vite production build
app.use(express.static(path.join(__dirname, 'dist')));

// SPA fallback
app.get('/*splat', (req, res) => {
    res.sendFile(path.join(__dirname, 'dist', 'index.html'));
});

app.listen(PORT, () => {
    console.log(`Express server running on http://localhost:${PORT}`);
    console.log(`Proxying /api/* → ${BACKEND_URL}`);
    console.log(`Proxying /swagger/* → ${BACKEND_URL}`);
});
