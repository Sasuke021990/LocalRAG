export const API_BASE = '/api';

async function request(path, options = {}) {
    const res = await fetch(`${API_BASE}${path}`, options);
    if (!res.ok) {
        let msg = `HTTP ${res.status}`;
        try { const j = await res.json(); msg = j.detail || j.message || msg; } catch (_) {}
        throw new Error(msg);
    }
    return res.json();
}

// GET /categories → {categories: [...], total: N}
export function fetchCategories() {
    return request('/categories');
}

// POST /categories {name}
export function createCategory(name) {
    return request('/categories', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name })
    });
}

// GET /documents → {documents: [...], total: N}
export function fetchDocuments() {
    return request('/documents');
}

// DELETE /documents/{file_name}?category=
export function deleteDocument(fileName, category) {
    return request(`/documents/${encodeURIComponent(fileName)}?category=${encodeURIComponent(category)}`, {
        method: 'DELETE'
    });
}

// POST /upload (multipart form)
export function uploadDocument(file, category = 'General', chunkSize = 512, chunkOverlap = 50) {
    const form = new FormData();
    form.append('file', file);
    form.append('category', category);
    form.append('chunk_size', chunkSize);
    form.append('chunk_overlap', chunkOverlap);
    return request('/upload', { method: 'POST', body: form });
}

// POST /query → {answer, sources, processing_time}
export function sendQuery(query, topK = 5, rerankTopK = 3) {
    return request('/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, top_k: topK, rerank_top_k: rerankTopK })
    });
}

// GET /health
export function fetchHealth() {
    return request('/health');
}
