import { fetchCategories, createCategory, uploadDocument, fetchDocuments, deleteDocument } from '../api.js';

export function initKnowledgeBase() {
    const categoryList = document.getElementById('category-list');
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const uploadCatSelect = document.getElementById('upload-category-select');
    const newCategoryForm = document.getElementById('new-category-form');
    const newCategoryInput = document.getElementById('new-category-input');
    const docTableBody = document.getElementById('doc-table-body');
    const refreshBtn = document.getElementById('refresh-docs-btn');

    if (!categoryList || !dropZone) return;

    loadCategories().catch(err => console.error('loadCategories failed:', err));
    loadDocuments().catch(err => console.error('loadDocuments failed:', err));

    // ── Category Management ──────────────────────────────
    async function loadCategories() {
        const data = await fetchCategories();
        const cats = data.categories || data || [];

        if (!cats.length) {
            categoryList.innerHTML = '<li class="text-slate-500 text-xs text-center py-4">No categories yet.</li>';
        } else {
            categoryList.innerHTML = cats.map(cat => `
                <li data-category="${cat}"
                    class="category-item flex items-center gap-2 px-3 py-2 text-sm text-slate-300 hover:bg-white/5 rounded-lg cursor-pointer transition-colors">
                    <svg class="w-4 h-4 text-[#10e8b8] shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"/>
                    </svg>
                    <span class="truncate">${cat}</span>
                </li>`).join('');

            categoryList.querySelectorAll('.category-item').forEach(li => {
                li.addEventListener('click', () => {
                    categoryList.querySelectorAll('.category-item').forEach(el => el.classList.remove('bg-white/10', 'text-white'));
                    li.classList.add('bg-white/10', 'text-white');
                    loadDocuments(li.dataset.category);
                });
            });
        }

        const options = cats.map(c => `<option value="${c}">${c}</option>`).join('');
        if (uploadCatSelect) uploadCatSelect.innerHTML = options || '<option value="General">General</option>';
        const chatCatFilter = document.getElementById('category-filter');
        if (chatCatFilter) chatCatFilter.innerHTML = '<option value="">All categories</option>' + options;
    }

    newCategoryForm?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const name = newCategoryInput.value.trim();
        if (!name) return;
        try {
            await createCategory(name);
            newCategoryInput.value = '';
            await loadCategories();
        } catch (err) {
            showNotification(`Error creating category: ${err.message}`, 'error');
        }
    });

    // ── Document Library ─────────────────────────────────
    async function loadDocuments(filterCategory = null) {
        docTableBody.innerHTML = '<tr><td colspan="5" class="text-center text-slate-500 py-8 text-xs">Loading…</td></tr>';
        try {
            const data = await fetchDocuments();
            let docs = data.documents || [];
            if (filterCategory) docs = docs.filter(d => d.category === filterCategory);

            if (!docs.length) {
                docTableBody.innerHTML = '<tr><td colspan="5" class="text-center text-slate-500 py-8 text-xs">No documents found.</td></tr>';
                return;
            }

            docTableBody.innerHTML = docs.map(doc => {
                const date = doc.processed_at ? new Date(doc.processed_at).toLocaleDateString() : '—';
                return `
                <tr class="border-t border-white/5 hover:bg-white/[0.02] transition-colors">
                    <td class="px-4 py-3">
                        <div class="flex items-center gap-2">
                            <svg class="w-4 h-4 text-slate-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                            </svg>
                            <span class="text-slate-200 truncate max-w-[180px]" title="${doc.file_name}">${doc.file_name}</span>
                        </div>
                    </td>
                    <td class="px-4 py-3">
                        <span class="bg-[#10e8b8]/10 text-[#10e8b8] px-2 py-0.5 rounded text-[11px] font-medium">${doc.category}</span>
                    </td>
                    <td class="px-4 py-3 text-slate-400">${doc.chunk_count}</td>
                    <td class="px-4 py-3 text-slate-500">${date}</td>
                    <td class="px-4 py-3">
                        <button data-file="${doc.file_name}" data-cat="${doc.category}"
                            class="delete-doc-btn text-slate-500 hover:text-red-400 transition-colors cursor-pointer">
                            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                            </svg>
                        </button>
                    </td>
                </tr>`;
            }).join('');

            docTableBody.querySelectorAll('.delete-doc-btn').forEach(btn => {
                btn.addEventListener('click', async () => {
                    if (!confirm(`Delete "${btn.dataset.file}" from category "${btn.dataset.cat}"?`)) return;
                    try {
                        await deleteDocument(btn.dataset.file, btn.dataset.cat);
                        await loadDocuments(filterCategory);
                    } catch (err) {
                        showNotification(`Error: ${err.message}`, 'error');
                    }
                });
            });
        } catch (err) {
            docTableBody.innerHTML = `<tr><td colspan="5" class="text-center text-red-400 py-8 text-xs">Failed to load documents: ${err.message}</td></tr>`;
        }
    }

    refreshBtn?.addEventListener('click', () => loadDocuments());

    // ── File Upload ──────────────────────────────────────
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('border-[#10e8b8]/50', 'bg-[#10e8b8]/5');
    });
    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('border-[#10e8b8]/50', 'bg-[#10e8b8]/5');
    });
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('border-[#10e8b8]/50', 'bg-[#10e8b8]/5');
        if (e.dataTransfer.files.length) handleUpload(e.dataTransfer.files[0]);
    });
    dropZone.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length) handleUpload(e.target.files[0]);
    });

    async function handleUpload(file) {
        const cat = uploadCatSelect?.value || 'General';
        const chunkSize = document.getElementById('chunk-size')?.value || 512;
        const chunkOverlap = document.getElementById('chunk-overlap')?.value || 50;

        // Create a progress card
        const card = createProgressCard(file.name, cat);
        document.getElementById('documents-list').prepend(card);

        try {
            // 1. POST /upload — returns immediately
            await uploadDocument(file, cat, chunkSize, chunkOverlap);

            // 2. Animate progress bar via SSE (backend streams 10 fake steps over ~5s)
            const taskId = `task-${Date.now()}`;
            streamProgressSSE(taskId, card);

            // 3. Poll /documents until the file appears (real completion signal)
            pollForCompletion(file.name, cat, card);

        } catch (err) {
            setCardError(card, err.message);
        }

        fileInput.value = '';
    }

    // ── Progress Card ────────────────────────────────────
    function createProgressCard(fileName, category) {
        const card = document.createElement('div');
        card.className = 'border border-[#10e8b8]/30 bg-[#10e8b8]/5 rounded-xl p-4 space-y-3';
        card.innerHTML = `
            <div class="flex items-center justify-between text-xs">
                <div class="flex items-center gap-2 text-slate-200 font-medium truncate">
                    <svg class="w-4 h-4 text-[#10e8b8] shrink-0 animate-pulse" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"/>
                    </svg>
                    <span class="truncate max-w-[200px]" title="${fileName}">${fileName}</span>
                </div>
                <span class="text-slate-400 shrink-0 ml-2">${category}</span>
            </div>
            <!-- Progress bar -->
            <div class="w-full bg-white/10 rounded-full h-1.5 overflow-hidden">
                <div class="progress-bar bg-[#10e8b8] h-1.5 rounded-full transition-all duration-500" style="width: 0%"></div>
            </div>
            <!-- Stage label -->
            <div class="flex items-center justify-between text-[11px] text-slate-400">
                <span class="stage-label">Uploading…</span>
                <span class="progress-pct text-[#10e8b8] font-semibold">0%</span>
            </div>`;
        return card;
    }

    const STAGES = [
        'Uploading…', 'Validating file…', 'Parsing document…',
        'Chunking text…', 'Generating embeddings…', 'Generating embeddings…',
        'Generating embeddings…', 'Storing in Redis…', 'Saving backup…', 'Finalising…'
    ];

    function streamProgressSSE(taskId, card) {
        // The backend SSE endpoint streams 10 steps × 0.5s with any task_id
        const evtSource = new EventSource(`/api/progress/${taskId}`);
        card._evtSource = evtSource;

        evtSource.addEventListener('progress', (e) => {
            try {
                const data = JSON.parse(e.data);
                const pct = data.progress ?? 0;
                const stageIdx = Math.floor((pct / 100) * STAGES.length);
                setCardProgress(card, Math.min(pct, 90), STAGES[stageIdx] || 'Processing…');
            } catch (_) {}
        });

        evtSource.addEventListener('complete', () => {
            evtSource.close();
        });

        evtSource.onerror = () => {
            evtSource.close();
        };
    }

    function pollForCompletion(fileName, category, card) {
        // Poll every 3 seconds; stop after 5 minutes
        const MAX_POLLS = 100;
        let polls = 0;

        const interval = setInterval(async () => {
            polls++;
            if (polls > MAX_POLLS) {
                clearInterval(interval);
                setCardError(card, 'Timed out — check Document Library manually.');
                return;
            }

            try {
                const data = await fetchDocuments();
                const docs = data.documents || [];
                const found = docs.find(d => d.file_name === fileName && d.category === category);
                if (found) {
                    clearInterval(interval);
                    card._evtSource?.close();
                    setCardDone(card, fileName, found.chunk_count);
                    // Refresh the table
                    setTimeout(() => loadDocuments(), 500);
                }
            } catch (_) {
                // ignore transient errors, keep polling
            }
        }, 3000);
    }

    function setCardProgress(card, pct, label) {
        const bar = card.querySelector('.progress-bar');
        const stageEl = card.querySelector('.stage-label');
        const pctEl = card.querySelector('.progress-pct');
        if (bar) bar.style.width = `${pct}%`;
        if (stageEl) stageEl.textContent = label;
        if (pctEl) pctEl.textContent = `${Math.round(pct)}%`;
    }

    function setCardDone(card, fileName, chunkCount) {
        card.className = 'border border-green-500/30 bg-green-500/5 rounded-xl p-4 space-y-3';
        card.innerHTML = `
            <div class="flex items-center justify-between text-xs">
                <div class="flex items-center gap-2 text-green-400 font-medium">
                    <svg class="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
                    </svg>
                    <span class="truncate max-w-[220px]">${fileName}</span>
                </div>
                <span class="text-slate-400">${chunkCount} chunks</span>
            </div>
            <div class="w-full bg-white/10 rounded-full h-1.5">
                <div class="bg-green-400 h-1.5 rounded-full" style="width: 100%"></div>
            </div>
            <p class="text-[11px] text-green-400">✓ Indexed successfully</p>`;
        setTimeout(() => card.remove(), 8000);
    }

    function setCardError(card, message) {
        card._evtSource?.close();
        card.className = 'border border-red-500/30 bg-red-500/5 rounded-xl p-4';
        card.innerHTML = `
            <div class="flex items-center gap-2 text-red-400 text-xs">
                <svg class="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                </svg>
                <span>${message}</span>
            </div>`;
        setTimeout(() => card.remove(), 8000);
    }

    function showNotification(message, type = 'error') {
        const el = document.createElement('div');
        el.className = `border rounded-lg px-3 py-2 text-xs ${type === 'error' ? 'border-red-500/30 text-red-400 bg-red-500/5' : 'border-[#10e8b8]/30 text-[#10e8b8] bg-[#10e8b8]/5'}`;
        el.textContent = message;
        document.getElementById('documents-list')?.prepend(el);
        setTimeout(() => el.remove(), 6000);
    }
}
