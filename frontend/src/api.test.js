import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
    createCategory,
    deleteDocument,
    fetchCategories,
    fetchDocuments,
    fetchHealth,
    sendQuery,
    uploadDocument,
} from './api.js';

function mockFetchOnce(status, body) {
    global.fetch = vi.fn().mockResolvedValue({
        ok: status >= 200 && status < 300,
        status,
        json: async () => body,
    });
}

beforeEach(() => {
    global.fetch = vi.fn();
});

afterEach(() => {
    vi.restoreAllMocks();
});

describe('fetchCategories', () => {
    it('GETs /api/categories and returns parsed JSON', async () => {
        mockFetchOnce(200, { categories: ['General'], total: 1 });
        const result = await fetchCategories();
        expect(global.fetch).toHaveBeenCalledWith('/api/categories', {});
        expect(result).toEqual({ categories: ['General'], total: 1 });
    });
});

describe('createCategory', () => {
    it('POSTs a JSON body with the category name', async () => {
        mockFetchOnce(200, { status: 'created', category: 'Finance' });
        await createCategory('Finance');
        expect(global.fetch).toHaveBeenCalledWith('/api/categories', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: 'Finance' }),
        });
    });
});

describe('fetchDocuments', () => {
    it('GETs /api/documents', async () => {
        mockFetchOnce(200, { documents: [], total: 0 });
        await fetchDocuments();
        expect(global.fetch).toHaveBeenCalledWith('/api/documents', {});
    });
});

describe('deleteDocument', () => {
    it('DELETEs with the file name and category as query params', async () => {
        mockFetchOnce(200, { status: 'deleted' });
        await deleteDocument('a b.pdf', 'My Docs');
        expect(global.fetch).toHaveBeenCalledWith(
            '/api/documents/a%20b.pdf?category=My%20Docs',
            { method: 'DELETE' }
        );
    });
});

describe('uploadDocument', () => {
    it('POSTs a multipart form with the file and options', async () => {
        mockFetchOnce(200, { status: 'processing_started' });
        const file = new Blob(['content']);
        await uploadDocument(file, 'Research', 256, 25);

        expect(global.fetch).toHaveBeenCalledTimes(1);
        const [url, options] = global.fetch.mock.calls[0];
        expect(url).toBe('/api/upload');
        expect(options.method).toBe('POST');
        expect(options.body).toBeInstanceOf(FormData);
        expect(options.body.get('category')).toBe('Research');
        expect(options.body.get('chunk_size')).toBe('256');
        expect(options.body.get('chunk_overlap')).toBe('25');
    });
});

describe('sendQuery', () => {
    it('POSTs the query with default top_k/rerank_top_k', async () => {
        mockFetchOnce(200, { answer: 'hi', sources: [], processing_time: 0.1 });
        await sendQuery('what is redis?');
        expect(global.fetch).toHaveBeenCalledWith('/api/query', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: 'what is redis?', top_k: 5, rerank_top_k: 3 }),
        });
    });
});

describe('fetchHealth', () => {
    it('GETs /api/health', async () => {
        mockFetchOnce(200, { status: 'healthy' });
        await fetchHealth();
        expect(global.fetch).toHaveBeenCalledWith('/api/health', {});
    });
});

describe('error handling', () => {
    it('throws with the server-provided detail message on non-2xx', async () => {
        mockFetchOnce(404, { detail: 'Document not found' });
        await expect(fetchDocuments()).rejects.toThrow('Document not found');
    });

    it('falls back to an HTTP status message when the body is not JSON', async () => {
        global.fetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 500,
            json: async () => { throw new Error('not json'); },
        });
        await expect(fetchDocuments()).rejects.toThrow('HTTP 500');
    });
});
