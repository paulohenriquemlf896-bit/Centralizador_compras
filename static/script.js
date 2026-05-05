/**
 * script.js — Utilitários JavaScript globais do sistema Central de Compras
 * FIX 13: Centralizado para evitar duplicação nos templates HTML.
 * Inclua em todos os templates com:
 *   <script src="{{ url_for('static', filename='script.js') }}"></script>
 */

/* ══════════════════════════════════════════════════════════════════════════
 * 1. SISTEMA DE NOTIFICAÇÕES (Toast flutuante)
 * Uso: mostrarNotificacao("Mensagem", "sucesso" | "erro" | "info")
 * ══════════════════════════════════════════════════════════════════════════ */
function mostrarNotificacao(texto, tipo) {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        document.body.appendChild(container);
    }

    const div = document.createElement('div');
    const cls = tipo === 'erro' ? 'toast-bg-erro'
               : tipo === 'info' ? 'toast-bg-info'
               : 'toast-bg-sucesso';
    div.className = `toast-custom ${cls}`;
    div.innerText = texto;
    container.appendChild(div);

    setTimeout(() => {
        div.style.transition = 'opacity 0.5s';
        div.style.opacity = '0';
        setTimeout(() => div.remove(), 500);
    }, 3000);
}

/* ══════════════════════════════════════════════════════════════════════════
 * 2. DEBOUNCE
 * Uso: debounce(fn, 400) — retorna versão "atrasada" da função fn
 * ══════════════════════════════════════════════════════════════════════════ */
function debounce(fn, delay) {
    let t;
    return function (...args) {
        clearTimeout(t);
        t = setTimeout(() => fn.apply(this, args), delay);
    };
}

/* ══════════════════════════════════════════════════════════════════════════
 * 3. NAVEGAÇÃO COM ENTER EM CAMPOS DE FORMULÁRIO
 * Chame enableEnterNavigation(selector) para ativar num conjunto de inputs.
 * Uso: enableEnterNavigation('.inputs-navegaveis')
 * ══════════════════════════════════════════════════════════════════════════ */
function enableEnterNavigation(selector, skipSelector) {
    document.addEventListener('keydown', function (event) {
        if (event.key !== 'Enter') return;
        if (event.target.tagName === 'TEXTAREA') return;
        if (skipSelector && event.target.matches(skipSelector)) return;

        event.preventDefault();
        const inputs = Array.from(
            document.querySelectorAll(`${selector}:not([disabled])`)
        ).filter(el => !el.closest('.linha-oculta'));

        const index = inputs.indexOf(event.target);
        if (index > -1 && index < inputs.length - 1) {
            inputs[index + 1].focus();
            if (inputs[index + 1].select) inputs[index + 1].select();
        }
    });
}

/* ══════════════════════════════════════════════════════════════════════════
 * 4. DASHBOARD ADMIN: Sistema de abas com setas
 * Inicializado automaticamente se existir .card-periodo na página.
 * ══════════════════════════════════════════════════════════════════════════ */
(function initDashboardTabs() {
    const tabs       = ['filiais', 'fabricantes'];
    const tabTitles  = { filiais: '📍 Status das Filiais', fabricantes: '🏭 Fabricantes do Grupo' };
    const currentIdx = {};

    function switchTab(cardIndex) {
        const tab = tabs[currentIdx[cardIndex]];
        tabs.forEach((t, i) => {
            const el = document.getElementById(`${t}-${cardIndex}`);
            if (el) el.classList.toggle('active', i === currentIdx[cardIndex]);
        });

        const body = document.getElementById(`filiais-${cardIndex}`)
                     ?.closest('.card-body');
        body?.querySelectorAll('.tab-dot').forEach((dot, i) => {
            dot.classList.toggle('active', i === currentIdx[cardIndex]);
        });

        const title = document.getElementById(`tab-title-${cardIndex}`);
        if (title) title.textContent = tabTitles[tab];

        const prev = document.getElementById(`prev-${cardIndex}`);
        const next = document.getElementById(`next-${cardIndex}`);
        if (prev) prev.disabled = currentIdx[cardIndex] === 0;
        if (next) next.disabled = currentIdx[cardIndex] === tabs.length - 1;
    }

    // Expõe globalmente para os onclick inline do template
    window.nextTab = function (idx) {
        if (currentIdx[idx] < tabs.length - 1) { currentIdx[idx]++; switchTab(idx); }
    };
    window.previousTab = function (idx) {
        if (currentIdx[idx] > 0) { currentIdx[idx]--; switchTab(idx); }
    };

    document.addEventListener('DOMContentLoaded', () => {
        document.querySelectorAll('.card-periodo').forEach((_, idx) => {
            currentIdx[idx] = 0;
            switchTab(idx);
        });
    });
})();
