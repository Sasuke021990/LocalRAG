import { initChat } from './views/chat.js';
import { initKnowledgeBase } from './views/knowledgeBase.js';
import { fetchHealth, fetchCategories, fetchDocuments } from './api.js';

document.addEventListener('DOMContentLoaded', () => {
    initChat();
    initKnowledgeBase();
    pollStatus();

    const navCards = document.querySelectorAll('.nav-card');
    const viewSections = document.querySelectorAll('.view-section');

    navCards.forEach(card => {
        card.addEventListener('click', () => {
            navCards.forEach(c => c.classList.remove('border-[#10e8b8]', '!bg-white/[0.08]'));
            card.classList.add('border-[#10e8b8]', '!bg-white/[0.08]');

            viewSections.forEach(v => v.classList.add('hidden'));
            const target = document.getElementById(card.dataset.target);
            target?.classList.remove('hidden');

            document.getElementById('views-container')?.scrollIntoView({ behavior: 'smooth', block: 'start' });

            // Lazy-load Swagger UI the first time the API card is clicked
            if (card.dataset.target === 'api-view') {
                loadSwaggerUI();
            }
        });
    });
});

async function pollStatus() {
    const statusDocs = document.getElementById('status-docs');
    const statusCats = document.getElementById('status-cats');
    const apiStatus = document.getElementById('api-status');

    async function update() {
        try {
            await fetchHealth();
            apiStatus.innerHTML = '<span class="w-2 h-2 rounded-full bg-[#10e8b8]"></span><span class="text-[#10e8b8]">API Online</span>';

            const [catData, docData] = await Promise.all([fetchCategories(), fetchDocuments()]);
            statusDocs.textContent = docData.total ?? (docData.documents?.length ?? '—');
            statusCats.textContent = catData.total ?? (catData.categories?.length ?? '—');
        } catch (_) {
            apiStatus.innerHTML = '<span class="w-2 h-2 rounded-full bg-red-500"></span><span class="text-red-400">API Offline</span>';
        }
    }

    update();
    setInterval(update, 15000);
}

function loadSwaggerUI() {
    const container = document.getElementById('swagger-ui-container');
    if (!container || container.dataset.loaded === 'true') return;
    container.dataset.loaded = 'true';

    container.innerHTML = '<div class="flex items-center justify-center h-48 text-slate-400 text-sm">Loading API docs…</div>';

    // Inject Swagger UI CDN script once
    const script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js';
    script.onload = () => {
        container.innerHTML = '';
        window.SwaggerUIBundle({
            url: '/api/openapi.json',   // proxied to http://backend:8000/openapi.json
            dom_id: '#swagger-ui-container',
            deepLinking: true,
            presets: [
                window.SwaggerUIBundle.presets.apis,
                window.SwaggerUIBundle.SwaggerUIStandalonePreset
            ],
            layout: 'BaseLayout',
        });
    };
    script.onerror = () => {
        container.innerHTML = '<div class="flex flex-col items-center justify-center h-48 gap-3 text-slate-400 text-sm"><p>Could not load Swagger UI. Check your internet connection.</p><a href="/api/openapi.json" target="_blank" class="text-[#10e8b8] underline text-xs">View raw OpenAPI JSON ↗</a></div>';
    };
    document.head.appendChild(script);
}
