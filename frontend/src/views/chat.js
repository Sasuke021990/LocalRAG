import { sendQuery } from '../api.js';

export function initChat() {
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const chatMessages = document.getElementById('chat-messages');
    const chatMetadata = document.getElementById('chat-metadata');
    const processingTimeEl = document.getElementById('processing-time');
    const topKSlider = document.getElementById('top-k');
    const topKVal = document.getElementById('top-k-val');
    const useReranker = document.getElementById('use-reranker');
    const chatWelcome = document.getElementById('chat-welcome');

    if (!chatForm) return;

    // Sync slider label
    topKSlider.addEventListener('input', () => {
        topKVal.textContent = topKSlider.value;
    });

    // Allow Shift+Enter for newline, Enter to submit
    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            chatForm.dispatchEvent(new Event('submit'));
        }
    });

    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const query = chatInput.value.trim();
        if (!query) return;

        chatWelcome?.remove();
        appendMessage('user', query);
        chatInput.value = '';
        chatInput.rows = 2;

        processingTimeEl.textContent = '';
        const loadingId = appendLoading();

        try {
            const topK = parseInt(topKSlider.value);
            const rerankTopK = useReranker.checked ? Math.max(1, Math.ceil(topK / 2)) : 0;
            
            // POST /query {query, top_k, rerank_top_k}
            const res = await sendQuery(query, topK, rerankTopK);
            document.getElementById(loadingId)?.remove();

            appendMessage('ai', res.answer || 'No answer generated.');

            // processing_time: 0.0 means served from cache
            if (res.processing_time === 0) {
                processingTimeEl.textContent = '⚡ Cache hit';
                processingTimeEl.className = 'text-xs text-[#10e8b8]';
            } else {
                processingTimeEl.textContent = `${(res.processing_time * 1000).toFixed(0)}ms`;
                processingTimeEl.className = 'text-xs text-slate-500';
            }

            // sources: [{file_name, category, chunk_index, score, content}]
            updateMetadata(res.sources || []);
        } catch (err) {
            document.getElementById(loadingId)?.remove();
            appendMessage('error', err.message);
        }
    });

    function appendMessage(type, text) {
        const isUser = type === 'user';
        const isError = type === 'error';
        const wrap = document.createElement('div');
        wrap.className = `flex items-start gap-3 ${isUser ? 'flex-row-reverse' : ''}`;

        const avatar = document.createElement('div');
        avatar.className = `w-7 h-7 rounded-full flex items-center justify-center shrink-0 text-xs font-bold ${
            isUser ? 'bg-blue-500/20 text-blue-400' :
            isError ? 'bg-red-500/20 text-red-400' :
            'bg-[#10e8b8]/20 text-[#10e8b8]'
        }`;
        avatar.textContent = isUser ? 'U' : isError ? '!' : 'AI';

        const bubble = document.createElement('div');
        bubble.className = `border rounded-2xl px-4 py-3 text-sm max-w-[80%] whitespace-pre-wrap leading-relaxed ${
            isUser ? 'bg-blue-600/15 border-blue-500/20 rounded-tr-sm text-slate-200' :
            isError ? 'bg-red-500/10 border-red-500/20 text-red-400' :
            'bg-white/5 border-white/10 rounded-tl-sm text-slate-200'
        }`;
        bubble.textContent = text;

        wrap.appendChild(avatar);
        wrap.appendChild(bubble);
        chatMessages.appendChild(wrap);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function appendLoading() {
        const id = 'loading-' + Date.now();
        const wrap = document.createElement('div');
        wrap.id = id;
        wrap.className = 'flex items-start gap-3';
        wrap.innerHTML = `
            <div class="w-7 h-7 rounded-full bg-[#10e8b8]/20 text-[#10e8b8] flex items-center justify-center text-xs font-bold shrink-0">AI</div>
            <div class="bg-white/5 border border-white/10 rounded-2xl rounded-tl-sm px-4 py-3 flex items-center gap-1.5">
                <span class="w-1.5 h-1.5 bg-[#10e8b8] rounded-full animate-bounce" style="animation-delay:0s"></span>
                <span class="w-1.5 h-1.5 bg-[#10e8b8] rounded-full animate-bounce" style="animation-delay:.15s"></span>
                <span class="w-1.5 h-1.5 bg-[#10e8b8] rounded-full animate-bounce" style="animation-delay:.3s"></span>
            </div>`;
        chatMessages.appendChild(wrap);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        return id;
    }

    function updateMetadata(sources) {
        if (!sources.length) {
            chatMetadata.innerHTML = '<p class="text-slate-500 text-xs text-center pt-6">No sources retrieved.</p>';
            return;
        }
        chatMetadata.innerHTML = sources.map((s, i) => `
            <div class="bg-white/[0.04] border border-white/10 rounded-xl p-3 text-xs space-y-2">
                <div class="flex items-center justify-between">
                    <span class="bg-[#10e8b8]/15 text-[#10e8b8] px-2 py-0.5 rounded font-semibold">[${i + 1}]</span>
                    <span class="text-slate-400 font-mono">${s.score != null ? s.score.toFixed(4) : ''}</span>
                </div>
                <p class="text-slate-300 leading-relaxed line-clamp-4">${s.content || ''}</p>
                <div class="flex items-center gap-2 text-slate-500 border-t border-white/10 pt-2">
                    <svg class="w-3 h-3 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                    </svg>
                    <span class="truncate">${s.file_name}</span>
                    <span class="shrink-0 bg-white/5 px-1.5 py-0.5 rounded text-[10px]">${s.category}</span>
                </div>
            </div>`).join('');
    }
}
