/* ═══════════════════════════════════════════════
   EXPENSE TRACKER PRO v3 — Main Application Logic
   ═══════════════════════════════════════════════ */

(() => {
'use strict';

// ─── Categories & Constants ───
const CATEGORIES = [
    { name: 'Food', emoji: '🍔' }, { name: 'Transport', emoji: '🚗' },
    { name: 'Shopping', emoji: '🛍️' }, { name: 'Bills', emoji: '📱' },
    { name: 'Health', emoji: '💊' }, { name: 'Education', emoji: '📚' },
    { name: 'Entertainment', emoji: '🎮' }, { name: 'Groceries', emoji: '🛒' },
    { name: 'Rent', emoji: '🏠' }, { name: 'Travel', emoji: '✈️' },
    { name: 'Fitness', emoji: '💪' }, { name: 'Coffee', emoji: '☕' },
    { name: 'Gifts', emoji: '🎁' }, { name: 'Insurance', emoji: '🛡️' },
    { name: 'Savings', emoji: '🏦' }, { name: 'Other', emoji: '📦' }
];
const INCOME_CATS = [
    { name: 'Salary', emoji: '💰' }, { name: 'Freelance', emoji: '💻' },
    { name: 'Investment', emoji: '📈' }, { name: 'Gift', emoji: '🎉' },
    { name: 'Refund', emoji: '↩️' }, { name: 'Other', emoji: '💵' }
];
const PAYMENTS = ['Cash', 'UPI', 'Card', 'Net Banking', 'Wallet', 'Cheque', 'Crypto', 'Other'];
const INCOME_SOURCES = ['Bank Transfer', 'Cash', 'UPI', 'Cheque', 'PayPal', 'Crypto', 'Other'];

// ─── State ───
let expenses = [], incomes = [], recurring = [], budgets = {}, goal = 0, settings = {};
let currentEditId = null, currentType = 'expense';
let calYear, calMonth, calSelectedDay;
let analyticsPeriod = 'month';
let swipeStartX = 0, swipeCard = null;
let chartInstances = {};

// ─── Storage Keys ───
const SK = { exp: 'exp_v2', inc: 'inc_v2', rec: 'rec_v2', bud: 'bud_v2', goal: 'goal_v2', set: 'set_v2' };

// ─── DOM Helpers ───
const $ = id => document.getElementById(id);
const $$ = sel => document.querySelectorAll(sel);

// ─── Init ───
function init() {
    loadData();
    migrateV1();
    initSettings();
    initSplash();
    initTabs();
    initAddModal();
    initIncomeModal();
    initBudgetModal();
    initGoalModal();
    initRecurringModal();
    initSettingsModal();
    initDetailModal();
    initCalendar();
    initAnalytics();
    initSearch();
    processRecurring();
    updateAll();
    setHeaderDate();
}

// ─── Data Persistence ───
function loadData() {
    try {
        expenses = JSON.parse(localStorage.getItem(SK.exp)) || [];
        incomes = JSON.parse(localStorage.getItem(SK.inc)) || [];
        recurring = JSON.parse(localStorage.getItem(SK.rec)) || [];
        budgets = JSON.parse(localStorage.getItem(SK.bud)) || {};
        goal = JSON.parse(localStorage.getItem(SK.goal)) || 0;
        settings = JSON.parse(localStorage.getItem(SK.set)) || {};
    } catch (e) { console.error('Load error', e); }
}
function save() {
    localStorage.setItem(SK.exp, JSON.stringify(expenses));
    localStorage.setItem(SK.inc, JSON.stringify(incomes));
    localStorage.setItem(SK.rec, JSON.stringify(recurring));
    localStorage.setItem(SK.bud, JSON.stringify(budgets));
    localStorage.setItem(SK.goal, JSON.stringify(goal));
    localStorage.setItem(SK.set, JSON.stringify(settings));
}
function migrateV1() {
    const old = localStorage.getItem('expenses');
    if (old && expenses.length === 0) {
        try {
            const arr = JSON.parse(old);
            expenses = arr.map(e => ({ ...e, id: e.id || uid(), payment: e.payment || 'Cash', notes: e.notes || '' }));
            save();
            localStorage.removeItem('expenses');
        } catch (e) {}
    }
}

// ─── Utilities ───
function uid() { return Date.now().toString(36) + Math.random().toString(36).slice(2, 8); }
function currency() { return settings.currency || '₹'; }
function fmt(n) { return currency() + Math.abs(n).toLocaleString('en-IN', { minimumFractionDigits: 0, maximumFractionDigits: 2 }); }
function today() { return new Date().toISOString().slice(0, 10); }
function monthKey(d) { return d.slice(0, 7); }
function weekStart() {
    const d = new Date(); d.setDate(d.getDate() - d.getDay());
    return d.toISOString().slice(0, 10);
}
function clamp(v, min, max) { return Math.max(min, Math.min(max, v)); }

// ─── Splash ───
function initSplash() {
    createSplashParticles();
    setTimeout(() => {
        $('splash').classList.add('hidden');
        $('app').classList.remove('hidden');
        triggerPageAnimations();
    }, 1800);
}
function createSplashParticles() {
    const c = $('splashParticles');
    for (let i = 0; i < 20; i++) {
        const p = document.createElement('div');
        p.style.cssText = `position:absolute;width:${2 + Math.random() * 4}px;height:${2 + Math.random() * 4}px;background:var(--accent);border-radius:50%;left:${Math.random() * 100}%;top:${Math.random() * 100}%;opacity:${0.2 + Math.random() * 0.4};animation:float ${3 + Math.random() * 4}s ease-in-out infinite ${Math.random() * 3}s;`;
        c.appendChild(p);
    }
}

// ─── Header ───
function setHeaderDate() {
    const d = new Date();
    $('headerDate').textContent = d.toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric' });
}

// ─── Tabs ───
function initTabs() {
    $$('.tab[data-tab]').forEach(t => t.addEventListener('click', () => switchTab(t.dataset.tab)));
    $$('.link-btn[data-tab]').forEach(b => b.addEventListener('click', () => switchTab(b.dataset.tab)));
}
function switchTab(tab) {
    $$('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
    $$('.page').forEach(p => {
        const isActive = p.id === 'page-' + tab;
        p.classList.toggle('active', isActive);
        if (isActive) {
            p.classList.add('page-enter');
            p.addEventListener('animationend', () => p.classList.remove('page-enter'), { once: true });
            retriggerAnimations(p);
        }
    });
    if (tab === 'analytics') updateAnalytics();
    if (tab === 'calendar') renderCalendar();
    if (tab === 'budget') updateBudgetPage();
}
function triggerPageAnimations() {
    document.querySelectorAll('.page.active .animate-in').forEach(el => {
        el.style.animation = 'none';
        el.offsetHeight;
        el.style.animation = '';
    });
}
function retriggerAnimations(page) {
    page.querySelectorAll('.animate-in').forEach(el => {
        el.style.animation = 'none';
        el.offsetHeight;
        el.style.animation = '';
    });
}

// ─── Settings ───
function initSettings() {
    if (settings.dark === undefined) settings.dark = true;
    applyTheme();
    $('currencySymbol').textContent = currency();
}
function applyTheme() {
    document.body.classList.toggle('light-theme', !settings.dark);
}
function initSettingsModal() {
    $('btnSettings').addEventListener('click', () => {
        $('settingCurrency').value = settings.currency || '₹';
        $('settingDark').checked = settings.dark !== false;
        toggleOverlay('settingsOverlay', true);
    });
    $('btnSettingsClose').addEventListener('click', () => toggleOverlay('settingsOverlay', false));
    $('settingCurrency').addEventListener('change', e => {
        settings.currency = e.target.value;
        $('currencySymbol').textContent = currency();
        save(); updateAll();
    });
    $('settingDark').addEventListener('change', e => {
        settings.dark = e.target.checked;
        applyTheme(); save();
    });
    $('btnExportAll').addEventListener('click', exportCSV);
    $('btnImport').addEventListener('click', () => $('fileImport').click());
    $('fileImport').addEventListener('change', importCSV);
    $('btnClearAll').addEventListener('click', () => {
        if (confirm('Clear ALL data? This cannot be undone.')) {
            expenses = []; incomes = []; recurring = []; budgets = {}; goal = 0;
            save(); updateAll(); toast('All data cleared');
            toggleOverlay('settingsOverlay', false);
        }
    });
}

// ─── Add/Edit Modal ───
function initAddModal() {
    $('btnAdd').addEventListener('click', () => openAddModal());
    $('btnModalClose').addEventListener('click', closeAddModal);
    $('btnModalSave').addEventListener('click', saveExpense);
    $$('.type-btn').forEach(b => b.addEventListener('click', () => {
        currentType = b.dataset.type;
        $$('.type-btn').forEach(x => x.classList.toggle('active', x === b));
        renderCategoryGrid();
        $('receiptGroup').style.display = currentType === 'expense' ? '' : 'none';
    }));
    renderCategoryGrid();
    renderPaymentChips();
    initReceipt();
}

function openAddModal(editItem, type) {
    currentEditId = editItem ? editItem.id : null;
    currentType = type || (editItem ? (editItem.source ? 'income' : 'expense') : 'expense');
    $('modalTitle').textContent = currentEditId ? 'Edit' : 'Add Expense';
    $$('.type-btn').forEach(b => b.classList.toggle('active', b.dataset.type === currentType));
    renderCategoryGrid();
    $('receiptGroup').style.display = currentType === 'expense' ? '' : 'none';

    if (editItem) {
        $('inputAmount').value = editItem.amount;
        $('inputDate').value = editItem.date;
        $('inputDesc').value = editItem.description || '';
        $('inputNotes').value = editItem.notes || '';
        $('inputRecurring').checked = editItem.recurring || false;
        setTimeout(() => {
            const catName = editItem.category || editItem.source;
            const catEl = document.querySelector(`.cat-item[data-cat="${catName}"]`);
            if (catEl) catEl.click();
            const payEl = document.querySelector(`.pay-chip[data-pay="${editItem.payment || editItem.paymentMode || ''}"]`);
            if (payEl) payEl.click();
        }, 50);
        if (editItem.receipt) {
            $('receiptPreview').src = editItem.receipt;
            $('receiptPreview').classList.remove('hidden');
            $('receiptPlaceholder').classList.add('hidden');
            $('receiptRemove').classList.remove('hidden');
        }
    } else {
        $('inputAmount').value = '';
        $('inputDate').value = today();
        $('inputDesc').value = '';
        $('inputNotes').value = '';
        $('inputRecurring').checked = false;
        clearReceipt();
        $$('.cat-item').forEach(c => c.classList.remove('selected'));
        $$('.pay-chip').forEach(c => c.classList.remove('selected'));
    }
    toggleOverlay('modalOverlay', true);
    setTimeout(() => $('inputAmount').focus(), 400);
}
function closeAddModal() { toggleOverlay('modalOverlay', false); currentEditId = null; }

function renderCategoryGrid() {
    const cats = currentType === 'income' ? INCOME_CATS : CATEGORIES;
    $('categoryGrid').innerHTML = cats.map(c =>
        `<div class="cat-item" data-cat="${c.name}"><span class="cat-emoji">${c.emoji}</span>${c.name}</div>`
    ).join('');
    $$('.cat-item').forEach(el => el.addEventListener('click', () => {
        $$('.cat-item').forEach(x => x.classList.remove('selected'));
        el.classList.add('selected');
    }));
}
function renderPaymentChips() {
    $('paymentChips').innerHTML = PAYMENTS.map(p =>
        `<div class="pay-chip" data-pay="${p}">${p}</div>`
    ).join('');
    $$('#paymentChips .pay-chip').forEach(el => el.addEventListener('click', () => {
        $$('#paymentChips .pay-chip').forEach(x => x.classList.remove('selected'));
        el.classList.add('selected');
    }));
}
function initReceipt() {
    $('receiptArea').addEventListener('click', () => $('receiptInput').click());
    $('receiptInput').addEventListener('change', e => {
        const file = e.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = () => {
            $('receiptPreview').src = reader.result;
            $('receiptPreview').classList.remove('hidden');
            $('receiptPlaceholder').classList.add('hidden');
            $('receiptRemove').classList.remove('hidden');
        };
        reader.readAsDataURL(file);
    });
    $('receiptRemove').addEventListener('click', e => { e.stopPropagation(); clearReceipt(); });
}
function clearReceipt() {
    $('receiptPreview').src = ''; $('receiptPreview').classList.add('hidden');
    $('receiptPlaceholder').classList.remove('hidden'); $('receiptRemove').classList.add('hidden');
    $('receiptInput').value = '';
}

function saveExpense() {
    const amount = parseFloat($('inputAmount').value);
    if (!amount || amount <= 0) { toast('Enter a valid amount'); return; }
    const selCat = document.querySelector('.cat-item.selected');
    if (!selCat) { toast('Select a category'); return; }
    const catName = selCat.dataset.cat;
    const date = $('inputDate').value || today();
    const desc = $('inputDesc').value.trim();
    const notes = $('inputNotes').value.trim();
    const payment = document.querySelector('#paymentChips .pay-chip.selected')?.dataset.pay || 'Cash';
    const isRecurring = $('inputRecurring').checked;
    const receipt = $('receiptPreview').src || '';

    if (currentType === 'income') {
        const item = { id: currentEditId || uid(), amount, source: catName, date, description: desc, paymentMode: payment };
        if (currentEditId) {
            const idx = incomes.findIndex(i => i.id === currentEditId);
            if (idx >= 0) incomes[idx] = item;
        } else {
            incomes.push(item);
        }
    } else {
        const cats = CATEGORIES;
        const catObj = cats.find(c => c.name === catName);
        const item = { id: currentEditId || uid(), amount, category: catName, emoji: catObj?.emoji || '📦', date, description: desc, notes, payment, recurring: isRecurring, receipt: receipt.startsWith('data:') ? receipt : '' };
        if (currentEditId) {
            const idx = expenses.findIndex(e => e.id === currentEditId);
            if (idx >= 0) expenses[idx] = item;
        } else {
            expenses.push(item);
            if (isRecurring && !recurring.find(r => r.category === catName && r.amount === amount)) {
                recurring.push({ id: uid(), category: catName, emoji: catObj?.emoji || '📦', amount, description: desc, payment, lastLogged: monthKey(date) });
            }
        }
    }
    save(); closeAddModal(); updateAll();
    if (!currentEditId) launchConfetti();
    toast(currentEditId ? 'Updated!' : 'Added!');
}

// ─── Income Modal ───
function initIncomeModal() {
    $('btnAddIncome').addEventListener('click', () => {
        $('incomeAmount').value = '';
        $('incomeDate').value = today();
        $('incomeDesc').value = '';
        renderIncomeSourceChips();
        toggleOverlay('incomeModalOverlay', true);
        setTimeout(() => $('incomeAmount').focus(), 400);
    });
    $('btnIncomeClose').addEventListener('click', () => toggleOverlay('incomeModalOverlay', false));
    $('btnIncomeSave').addEventListener('click', () => {
        const amount = parseFloat($('incomeAmount').value);
        if (!amount || amount <= 0) { toast('Enter a valid amount'); return; }
        const source = document.querySelector('#incomeSourceChips .pay-chip.selected')?.dataset.pay || 'Other';
        incomes.push({ id: uid(), amount, source, date: $('incomeDate').value || today(), description: $('incomeDesc').value.trim() });
        save(); toggleOverlay('incomeModalOverlay', false); updateAll();
        launchConfetti(); toast('Income added!');
    });
}
function renderIncomeSourceChips() {
    $('incomeSourceChips').innerHTML = INCOME_SOURCES.map(s =>
        `<div class="pay-chip" data-pay="${s}">${s}</div>`
    ).join('');
    $$('#incomeSourceChips .pay-chip').forEach(el => el.addEventListener('click', () => {
        $$('#incomeSourceChips .pay-chip').forEach(x => x.classList.remove('selected'));
        el.classList.add('selected');
    }));
}

// ─── Budget Modal ───
function initBudgetModal() {
    $('btnEditBudget').addEventListener('click', () => {
        $('budgetInputs').innerHTML = CATEGORIES.map(c => `
            <div class="budget-input-item">
                <div class="budget-input-label">${c.emoji} ${c.name}</div>
                <input type="number" class="form-input budget-input-field" data-cat="${c.name}" value="${budgets[c.name] || ''}" placeholder="0" inputmode="decimal">
            </div>
        `).join('');
        toggleOverlay('budgetModalOverlay', true);
    });
    $('btnBudgetClose').addEventListener('click', () => toggleOverlay('budgetModalOverlay', false));
    $('btnBudgetSave').addEventListener('click', () => {
        $$('.budget-input-field').forEach(inp => {
            const v = parseFloat(inp.value);
            if (v > 0) budgets[inp.dataset.cat] = v;
            else delete budgets[inp.dataset.cat];
        });
        save(); toggleOverlay('budgetModalOverlay', false); updateBudgetPage(); toast('Budgets saved!');
    });
}

// ─── Goal Modal ───
function initGoalModal() {
    $('btnEditGoal').addEventListener('click', () => {
        $('goalAmount').value = goal || '';
        toggleOverlay('goalModalOverlay', true);
    });
    $('btnGoalClose').addEventListener('click', () => toggleOverlay('goalModalOverlay', false));
    $('btnGoalSave').addEventListener('click', () => {
        goal = parseFloat($('goalAmount').value) || 0;
        save(); toggleOverlay('goalModalOverlay', false); updateBudgetPage(); toast('Goal saved!');
    });
}

// ─── Recurring Modal ───
function initRecurringModal() {
    $('btnManageRecurring').addEventListener('click', () => {
        renderRecurringManage();
        toggleOverlay('recurringModalOverlay', true);
    });
    $('btnRecurringClose').addEventListener('click', () => toggleOverlay('recurringModalOverlay', false));
}
function renderRecurringManage() {
    if (recurring.length === 0) {
        $('recurringManageList').innerHTML = '';
        $('recurringEmpty').style.display = '';
        return;
    }
    $('recurringEmpty').style.display = 'none';
    $('recurringManageList').innerHTML = recurring.map(r => `
        <div class="rec-item">
            <div class="rec-item-left"><span class="rec-item-emoji">${r.emoji}</span><div><div class="rec-item-name">${r.category}</div><div class="rec-item-amount">${fmt(r.amount)} / mo</div></div></div>
            <button class="rec-delete" data-id="${r.id}">✕</button>
        </div>
    `).join('');
    $$('.rec-delete').forEach(b => b.addEventListener('click', () => {
        recurring = recurring.filter(r => r.id !== b.dataset.id);
        save(); renderRecurringManage(); updateHome();
    }));
}
function processRecurring() {
    const mk = monthKey(today());
    let added = false;
    recurring.forEach(r => {
        if (r.lastLogged !== mk) {
            expenses.push({ id: uid(), amount: r.amount, category: r.category, emoji: r.emoji, date: today(), description: r.description || r.category + ' (auto)', payment: r.payment || 'Cash', recurring: true, notes: 'Auto-logged recurring' });
            r.lastLogged = mk;
            added = true;
        }
    });
    if (added) save();
}

// ─── Detail Modal ───
function initDetailModal() {
    $('btnDetailClose').addEventListener('click', () => toggleOverlay('detailOverlay', false));
    $('btnEditExpense').addEventListener('click', () => {
        toggleOverlay('detailOverlay', false);
        const item = expenses.find(e => e.id === currentEditId) || incomes.find(i => i.id === currentEditId);
        if (item) openAddModal(item, item.source ? 'income' : 'expense');
    });
    $('btnDeleteExpense').addEventListener('click', () => {
        if (!confirm('Delete this entry?')) return;
        expenses = expenses.filter(e => e.id !== currentEditId);
        incomes = incomes.filter(i => i.id !== currentEditId);
        save(); toggleOverlay('detailOverlay', false); updateAll();
        toast('Deleted');
    });
}
function showDetail(item, type) {
    currentEditId = item.id;
    const isExp = type === 'expense';
    const rows = [
        { l: 'Amount', v: (isExp ? '-' : '+') + fmt(item.amount) },
        { l: isExp ? 'Category' : 'Source', v: (item.emoji ? item.emoji + ' ' : '') + (item.category || item.source) },
        { l: 'Date', v: new Date(item.date).toLocaleDateString('en-US', { weekday: 'short', year: 'numeric', month: 'short', day: 'numeric' }) },
        { l: 'Description', v: item.description || '—' },
        { l: isExp ? 'Payment' : 'Mode', v: item.payment || item.paymentMode || '—' },
    ];
    if (item.notes) rows.push({ l: 'Notes', v: item.notes });
    let html = rows.map(r => `<div class="detail-row"><span class="detail-label">${r.l}</span><span class="detail-value">${sanitize(r.v)}</span></div>`).join('');
    if (item.receipt) html += `<div class="detail-receipt"><img src="${sanitize(item.receipt)}" alt="Receipt"></div>`;
    $('detailBody').innerHTML = html;
    toggleOverlay('detailOverlay', true);
}

// ─── Calendar ───
function initCalendar() {
    const now = new Date();
    calYear = now.getFullYear(); calMonth = now.getMonth(); calSelectedDay = now.getDate();
    $('calPrev').addEventListener('click', () => { calMonth--; if (calMonth < 0) { calMonth = 11; calYear--; } renderCalendar(); });
    $('calNext').addEventListener('click', () => { calMonth++; if (calMonth > 11) { calMonth = 0; calYear++; } renderCalendar(); });
}
function renderCalendar() {
    const mk = `${calYear}-${String(calMonth + 1).padStart(2, '0')}`;
    $('calMonthTitle').textContent = new Date(calYear, calMonth).toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
    const firstDay = new Date(calYear, calMonth, 1).getDay();
    const daysInMonth = new Date(calYear, calMonth + 1, 0).getDate();
    const todayDate = new Date();

    // Get daily totals
    const dayTotals = {};
    expenses.filter(e => e.date.startsWith(mk)).forEach(e => {
        const d = parseInt(e.date.slice(8));
        dayTotals[d] = (dayTotals[d] || 0) + e.amount;
    });
    const maxDay = Math.max(1, ...Object.values(dayTotals));

    let html = '<div class="cal-weekdays">' + ['S','M','T','W','T','F','S'].map(d => `<div class="cal-weekday">${d}</div>`).join('') + '</div><div class="cal-days">';
    for (let i = 0; i < firstDay; i++) html += '<div class="cal-day empty"></div>';
    for (let d = 1; d <= daysInMonth; d++) {
        const total = dayTotals[d] || 0;
        const isToday = d === todayDate.getDate() && calMonth === todayDate.getMonth() && calYear === todayDate.getFullYear();
        const isSel = d === calSelectedDay;
        let heat = '';
        if (total > 0) {
            const ratio = total / maxDay;
            heat = ratio < 0.33 ? 'heat-low' : ratio < 0.66 ? 'heat-mid' : 'heat-high';
        }
        html += `<div class="cal-day ${heat} ${isToday ? 'today' : ''} ${isSel ? 'selected' : ''}" data-day="${d}" style="animation-delay:${d * 0.02}s"><span>${d}</span>${total > 0 ? `<span class="cal-amount">${fmt(total)}</span>` : ''}</div>`;
    }
    html += '</div>';
    $('calendarGrid').innerHTML = html;

    $$('.cal-day:not(.empty)').forEach(el => el.addEventListener('click', () => {
        calSelectedDay = parseInt(el.dataset.day);
        $$('.cal-day').forEach(d => d.classList.remove('selected'));
        el.classList.add('selected');
        renderCalDayList();
    }));
    renderCalDayList();
    renderHistoryList();
}
function renderCalDayList() {
    const dateStr = `${calYear}-${String(calMonth + 1).padStart(2, '0')}-${String(calSelectedDay).padStart(2, '0')}`;
    const dayExps = expenses.filter(e => e.date === dateStr).sort((a, b) => b.amount - a.amount);
    $('calDayTitle').textContent = new Date(dateStr).toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric' });
    if (dayExps.length === 0) {
        $('calDayList').innerHTML = '';
        $('calEmpty').classList.remove('hidden');
    } else {
        $('calEmpty').classList.add('hidden');
        $('calDayList').innerHTML = dayExps.map((e, i) => txCardHTML(e, 'expense', i)).join('');
        bindTxCards($('calDayList'));
    }
}

// ─── Search / Filter ───
function initSearch() {
    $('searchInput').addEventListener('input', renderHistoryList);
    $('filterCategory').innerHTML = '<option value="">All Categories</option>' + CATEGORIES.map(c => `<option value="${c.name}">${c.emoji} ${c.name}</option>`).join('');
    $('filterPayment').innerHTML = '<option value="">All Payments</option>' + PAYMENTS.map(p => `<option value="${p}">${p}</option>`).join('');
    $('filterCategory').addEventListener('change', renderHistoryList);
    $('filterPayment').addEventListener('change', renderHistoryList);
    $('btnExport').addEventListener('click', exportCSV);
}
function renderHistoryList() {
    let list = [...expenses].sort((a, b) => b.date.localeCompare(a.date) || b.amount - a.amount);
    const q = ($('searchInput')?.value || '').toLowerCase();
    const fc = $('filterCategory')?.value;
    const fp = $('filterPayment')?.value;
    if (q) list = list.filter(e => (e.category + ' ' + (e.description || '')).toLowerCase().includes(q));
    if (fc) list = list.filter(e => e.category === fc);
    if (fp) list = list.filter(e => e.payment === fp);

    if (list.length === 0) {
        $('historyList').innerHTML = '';
        $('emptyHistory').classList.remove('hidden');
    } else {
        $('emptyHistory').classList.add('hidden');
        $('historyList').innerHTML = list.slice(0, 50).map((e, i) => txCardHTML(e, 'expense', i)).join('');
        bindTxCards($('historyList'));
    }
}

// ─── Transaction Card ───
function txCardHTML(item, type, idx) {
    const isExp = type === 'expense';
    const emoji = isExp ? item.emoji : (INCOME_CATS.find(c => c.name === item.source)?.emoji || '💵');
    const name = isExp ? item.category : item.source;
    const desc = item.description || '';
    const amtClass = isExp ? 'expense' : 'income';
    const prefix = isExp ? '-' : '+';
    const dateStr = new Date(item.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    const recBadge = item.recurring ? '<span class="tx-recurring-badge">🔄</span>' : '';
    return `<div class="tx-card" data-id="${item.id}" data-type="${type}" style="animation-delay:${(idx || 0) * 0.05}s">
        <div class="tx-swipe-bg">🗑️</div>
        <div class="tx-icon">${emoji}</div>
        <div class="tx-info"><div class="tx-cat">${sanitize(name)}${recBadge}</div><div class="tx-desc">${sanitize(desc)}</div></div>
        <div class="tx-right"><div class="tx-amount ${amtClass}">${prefix}${fmt(item.amount)}</div><div class="tx-date">${dateStr}</div></div>
    </div>`;
}
function bindTxCards(container) {
    container.querySelectorAll('.tx-card').forEach(card => {
        card.addEventListener('click', () => {
            const id = card.dataset.id;
            const type = card.dataset.type;
            const item = type === 'income' ? incomes.find(i => i.id === id) : expenses.find(e => e.id === id);
            if (item) showDetail(item, type);
        });
        // Swipe-to-delete
        card.addEventListener('touchstart', e => { swipeStartX = e.touches[0].clientX; swipeCard = card; }, { passive: true });
        card.addEventListener('touchmove', e => {
            if (!swipeCard || swipeCard !== card) return;
            const dx = swipeStartX - e.touches[0].clientX;
            if (dx > 10) {
                card.style.transform = `translateX(-${clamp(dx, 0, 80)}px)`;
                card.querySelector('.tx-swipe-bg').style.transform = `translateX(${80 - clamp(dx, 0, 80)}px)`;
            }
        }, { passive: true });
        card.addEventListener('touchend', () => {
            if (!swipeCard) return;
            const current = parseFloat(swipeCard.style.transform.replace(/[^-\d.]/g, '')) || 0;
            if (Math.abs(current) > 60) {
                const id = swipeCard.dataset.id;
                swipeCard.style.transform = 'translateX(-100%)';
                swipeCard.style.opacity = '0';
                setTimeout(() => {
                    expenses = expenses.filter(e => e.id !== id);
                    incomes = incomes.filter(i => i.id !== id);
                    save(); updateAll(); toast('Deleted');
                }, 300);
            } else {
                swipeCard.style.transform = '';
                swipeCard.querySelector('.tx-swipe-bg').style.transform = '';
            }
            swipeCard = null;
        });
    });
}

// ─── Update All ───
function updateAll() {
    updateHome();
    renderCalendar();
    updateBudgetPage();
    updateAnalytics();
}
function updateHome() {
    const mk = monthKey(today());
    const mExp = expenses.filter(e => e.date.startsWith(mk));
    const mInc = incomes.filter(i => i.date.startsWith(mk));
    const totalExp = mExp.reduce((s, e) => s + e.amount, 0);
    const totalInc = mInc.reduce((s, i) => s + i.amount, 0);
    const net = totalInc - totalExp;
    const todayExp = expenses.filter(e => e.date === today()).reduce((s, e) => s + e.amount, 0);
    const ws = weekStart();
    const weekExp = expenses.filter(e => e.date >= ws && e.date <= today()).reduce((s, e) => s + e.amount, 0);
    const dayOfMonth = new Date().getDate();
    const dailyAvg = dayOfMonth > 0 ? totalExp / dayOfMonth : 0;

    // Update hero
    $('netBalance').innerHTML = `<span class="${net >= 0 ? 'green-text' : 'red-text'}">${net >= 0 ? '' : '-'}${fmt(Math.abs(net))}</span>`;
    $('heroMonth').textContent = new Date().toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
    animateCounter($('monthIncome'), totalInc);
    animateCounter($('monthExpense'), totalExp);
    $('todayTotal').textContent = fmt(todayExp);

    // Rings
    const maxRing = Math.max(totalInc, totalExp, 1);
    animateRing($('incomeRing'), totalInc / maxRing);
    animateRing($('expenseRing'), totalExp / maxRing);
    animateRing($('todayRing'), totalExp > 0 ? todayExp / totalExp : 0);

    // Mini stats
    $('weekTotal').textContent = fmt(weekExp);
    $('dailyAvg').textContent = fmt(dailyAvg);
    $('txCount').textContent = mExp.length + mInc.length;

    // Streak
    updateStreak();

    // Insight
    updateHomeInsight(totalExp, totalInc, mExp);

    // Top categories
    renderTopCategories(mExp);

    // Recurring section
    renderRecurringHome();

    // Recent
    renderRecentList();

    // Notification badge
    checkNotifications(totalExp, totalInc);
}

// ─── Animated Counter ───
function animateCounter(el, target) {
    const c = currency();
    let start = 0;
    const duration = 800;
    const startTime = performance.now();
    function step(now) {
        const progress = Math.min((now - startTime) / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        const current = Math.round(start + (target - start) * eased);
        el.textContent = c + current.toLocaleString('en-IN');
        if (progress < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
}

// ─── Animate Ring ───
function animateRing(el, ratio) {
    const circum = 100;
    const offset = circum - (clamp(ratio, 0, 1) * circum);
    el.style.strokeDashoffset = offset;
}

// ─── Streak ───
function updateStreak() {
    let streak = 0;
    const d = new Date();
    while (true) {
        const ds = d.toISOString().slice(0, 10);
        if (expenses.some(e => e.date === ds) || incomes.some(i => i.date === ds)) {
            streak++;
            d.setDate(d.getDate() - 1);
        } else break;
        if (streak > 365) break;
    }
    $('streakText').textContent = `${streak} day streak`;
    $('streakBarFill').style.width = `${clamp(streak / 30, 0, 1) * 100}%`;
    if (streak >= 30) $('streakSub').textContent = '🏆 Incredible! 30+ day streak!';
    else if (streak >= 14) $('streakSub').textContent = '⚡ Amazing consistency!';
    else if (streak >= 7) $('streakSub').textContent = '🌟 One week strong!';
    else if (streak >= 3) $('streakSub').textContent = '👍 Keep going!';
    else $('streakSub').textContent = 'Log daily to build your streak!';

    // Fire particles
    const flames = $('streakFlames');
    flames.innerHTML = '';
    if (streak > 0) {
        const count = Math.min(streak, 15);
        for (let i = 0; i < count; i++) {
            const p = document.createElement('div');
            p.style.cssText = `position:absolute;bottom:0;left:${10 + Math.random() * 80}%;width:4px;height:4px;background:var(--orange);border-radius:50%;opacity:${0.3 + Math.random() * 0.4};animation:float ${2 + Math.random() * 2}s ease-in-out infinite ${Math.random() * 2}s;`;
            flames.appendChild(p);
        }
    }
}

// ─── Home Insight ───
function updateHomeInsight(totalExp, totalInc, mExp) {
    let text = 'Add expenses to get insights';
    if (mExp.length > 0) {
        const suggestions = [];
        if (totalExp > totalInc && totalInc > 0) suggestions.push(`Spending exceeds income by ${fmt(totalExp - totalInc)}`);
        const topCat = getTopCategory(mExp);
        if (topCat) suggestions.push(`Top category: ${topCat.emoji} ${topCat.name} (${fmt(topCat.total)})`);
        const dayOfMonth = new Date().getDate();
        const projected = (totalExp / dayOfMonth) * 30;
        suggestions.push(`Projected monthly: ${fmt(projected)}`);
        text = suggestions[Math.floor(Math.random() * suggestions.length)] || suggestions[0];
    }
    $('insightText').textContent = text;
}
function getTopCategory(exps) {
    const cats = {};
    exps.forEach(e => { cats[e.category] = (cats[e.category] || 0) + e.amount; });
    const top = Object.entries(cats).sort((a, b) => b[1] - a[1])[0];
    if (!top) return null;
    const catObj = CATEGORIES.find(c => c.name === top[0]);
    return { name: top[0], emoji: catObj?.emoji || '📦', total: top[1] };
}

// ─── Top Categories ───
function renderTopCategories(mExp) {
    const cats = {};
    mExp.forEach(e => { cats[e.category] = (cats[e.category] || 0) + e.amount; });
    const sorted = Object.entries(cats).sort((a, b) => b[1] - a[1]).slice(0, 5);
    $('topCategories').innerHTML = sorted.map(([name, total], i) => {
        const cat = CATEGORIES.find(c => c.name === name);
        return `<div class="category-chip" style="animation-delay:${i * 0.08}s">${cat?.emoji || '📦'} ${name} <span class="chip-amount">${fmt(total)}</span></div>`;
    }).join('');
    if (sorted.length === 0) $('topCategories').innerHTML = '<span style="color:var(--text-muted);font-size:13px">No expenses this month</span>';
}

// ─── Recurring Home ───
function renderRecurringHome() {
    if (recurring.length === 0) {
        $('recurringSection').style.display = 'none';
        return;
    }
    $('recurringSection').style.display = '';
    $('recurringList').innerHTML = recurring.slice(0, 3).map(r => `
        <div class="rec-item"><div class="rec-item-left"><span class="rec-item-emoji">${r.emoji}</span><div><div class="rec-item-name">${r.category}</div><div class="rec-item-amount">${fmt(r.amount)} / mo</div></div></div></div>
    `).join('');
}

// ─── Recent List ───
function renderRecentList() {
    const recent = [...expenses].sort((a, b) => b.date.localeCompare(a.date) || (b.id > a.id ? 1 : -1)).slice(0, 5);
    if (recent.length === 0) {
        $('recentList').innerHTML = '<div class="empty-state"><div class="empty-icon float-loop">💸</div><p>No expenses yet. Tap + to start!</p></div>';
    } else {
        $('recentList').innerHTML = recent.map((e, i) => txCardHTML(e, 'expense', i)).join('');
        bindTxCards($('recentList'));
    }
}

// ─── Notifications ───
function checkNotifications(totalExp, totalInc) {
    const totalBudget = Object.values(budgets).reduce((s, v) => s + v, 0);
    const show = totalBudget > 0 && totalExp > totalBudget * 0.8;
    $('notifBadge').classList.toggle('hidden', !show);
    $('btnNotifications').onclick = () => {
        if (show) toast('⚠️ You\'ve used ' + Math.round(totalExp / totalBudget * 100) + '% of your budget!');
        else toast('No new notifications');
    };
}

// ─── Analytics ───
function initAnalytics() {
    $$('.period-btn').forEach(b => b.addEventListener('click', () => {
        $$('.period-btn').forEach(x => x.classList.remove('active'));
        b.classList.add('active');
        analyticsPeriod = b.dataset.period;
        updateAnalytics();
    }));
}
function updateAnalytics() {
    const now = new Date();
    let startDate;
    if (analyticsPeriod === 'week') {
        startDate = new Date(now); startDate.setDate(now.getDate() - 7);
    } else if (analyticsPeriod === 'year') {
        startDate = new Date(now.getFullYear(), 0, 1);
    } else {
        startDate = new Date(now.getFullYear(), now.getMonth(), 1);
    }
    const sd = startDate.toISOString().slice(0, 10);
    const filtExp = expenses.filter(e => e.date >= sd);
    const filtInc = incomes.filter(i => i.date >= sd);

    renderIncomeExpenseChart(filtExp, filtInc);
    renderTrendChart(filtExp);
    renderCategoryChart(filtExp);
    renderPaymentChart(filtExp);
    renderInsights(filtExp, filtInc);
    renderStatsGrid(filtExp, filtInc);
}

function getChartColors() {
    const style = getComputedStyle(document.body);
    return {
        text: style.getPropertyValue('--text-dim').trim() || '#8888aa',
        grid: style.getPropertyValue('--border').trim() || 'rgba(100,100,160,0.15)',
        green: style.getPropertyValue('--green').trim() || '#00e09e',
        red: style.getPropertyValue('--red').trim() || '#ff4477',
        blue: style.getPropertyValue('--blue').trim() || '#5588ff',
        purple: style.getPropertyValue('--purple').trim() || '#aa66ff',
        orange: style.getPropertyValue('--orange').trim() || '#ff9944',
        yellow: style.getPropertyValue('--yellow').trim() || '#ffcc33',
    };
}

function chartDefaults() {
    const c = getChartColors();
    return {
        responsive: true, maintainAspectRatio: true, animation: { duration: 800, easing: 'easeOutQuart' },
        plugins: { legend: { display: false } },
        scales: {
            x: { ticks: { color: c.text, font: { size: 10 } }, grid: { color: c.grid } },
            y: { ticks: { color: c.text, font: { size: 10 } }, grid: { color: c.grid } }
        }
    };
}

function renderIncomeExpenseChart(exps, incs) {
    const c = getChartColors();
    const totalExp = exps.reduce((s, e) => s + e.amount, 0);
    const totalInc = incs.reduce((s, i) => s + i.amount, 0);
    if (chartInstances.ie) chartInstances.ie.destroy();
    chartInstances.ie = new Chart($('incomeExpenseChart'), {
        type: 'doughnut',
        data: { labels: ['Income', 'Expenses'], datasets: [{ data: [totalInc, totalExp], backgroundColor: [c.green, c.red], borderWidth: 0 }] },
        options: { responsive: true, maintainAspectRatio: true, cutout: '70%', animation: { animateScale: true, duration: 1000 }, plugins: { legend: { display: true, position: 'bottom', labels: { color: c.text, padding: 16 } } } }
    });
}
function renderTrendChart(exps) {
    const c = getChartColors();
    const daily = {};
    exps.forEach(e => { daily[e.date] = (daily[e.date] || 0) + e.amount; });
    const sorted = Object.entries(daily).sort((a, b) => a[0].localeCompare(b[0]));
    if (chartInstances.trend) chartInstances.trend.destroy();
    chartInstances.trend = new Chart($('trendChart'), {
        type: 'line',
        data: { labels: sorted.map(d => { const dt = new Date(d[0]); return dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }); }), datasets: [{ data: sorted.map(d => d[1]), borderColor: c.blue, backgroundColor: c.blue + '22', fill: true, tension: 0.4, pointRadius: 3, pointBackgroundColor: c.blue }] },
        options: { ...chartDefaults(), plugins: { legend: { display: false } } }
    });
}
function renderCategoryChart(exps) {
    const c = getChartColors();
    const cats = {};
    exps.forEach(e => { cats[e.category] = (cats[e.category] || 0) + e.amount; });
    const sorted = Object.entries(cats).sort((a, b) => b[1] - a[1]).slice(0, 8);
    const colors = [c.blue, c.red, c.green, c.orange, c.purple, c.yellow, '#ff6699', '#66ccff'];
    if (chartInstances.cat) chartInstances.cat.destroy();
    chartInstances.cat = new Chart($('categoryChart'), {
        type: 'doughnut',
        data: { labels: sorted.map(s => s[0]), datasets: [{ data: sorted.map(s => s[1]), backgroundColor: colors.slice(0, sorted.length), borderWidth: 0 }] },
        options: { responsive: true, maintainAspectRatio: true, cutout: '60%', animation: { animateRotate: true, duration: 1000 }, plugins: { legend: { display: true, position: 'bottom', labels: { color: c.text, padding: 12, font: { size: 11 } } } } }
    });
}
function renderPaymentChart(exps) {
    const c = getChartColors();
    const pays = {};
    exps.forEach(e => { pays[e.payment || 'Cash'] = (pays[e.payment || 'Cash'] || 0) + e.amount; });
    const sorted = Object.entries(pays).sort((a, b) => b[1] - a[1]);
    if (chartInstances.pay) chartInstances.pay.destroy();
    chartInstances.pay = new Chart($('paymentChart'), {
        type: 'bar',
        data: { labels: sorted.map(s => s[0]), datasets: [{ data: sorted.map(s => s[1]), backgroundColor: c.blue + '88', borderColor: c.blue, borderWidth: 1, borderRadius: 6 }] },
        options: { ...chartDefaults(), indexAxis: 'y' }
    });
}
function renderInsights(exps, incs) {
    const insights = generateInsights(exps, incs);
    $('insightsList').innerHTML = insights.length > 0
        ? insights.slice(0, 5).map((ins, i) => `<div class="insight-item" style="animation-delay:${i * 0.1}s"><span class="insight-item-icon">${ins.icon}</span><span class="insight-item-text">${ins.text}</span></div>`).join('')
        : '<div class="insight-item"><span class="insight-item-icon">📊</span><span class="insight-item-text">Add more entries for insights</span></div>';
}
function generateInsights(exps, incs) {
    const insights = [];
    const totalExp = exps.reduce((s, e) => s + e.amount, 0);
    const totalInc = incs.reduce((s, i) => s + i.amount, 0);
    if (totalExp === 0 && totalInc === 0) return insights;

    if (totalInc > totalExp) insights.push({ icon: '✅', text: `You saved ${fmt(totalInc - totalExp)} this period!` });
    else if (totalExp > totalInc && totalInc > 0) insights.push({ icon: '⚠️', text: `Spending exceeds income by ${fmt(totalExp - totalInc)}` });

    const cats = {};
    exps.forEach(e => { cats[e.category] = (cats[e.category] || 0) + e.amount; });
    const entries = Object.entries(cats).sort((a, b) => b[1] - a[1]);
    if (entries.length > 0) {
        const [topName, topVal] = entries[0];
        const pct = Math.round(topVal / totalExp * 100);
        const catObj = CATEGORIES.find(c => c.name === topName);
        insights.push({ icon: catObj?.emoji || '📊', text: `${topName} is your top expense at ${pct}% (${fmt(topVal)})` });
    }
    if (exps.length >= 7) {
        const last7 = exps.filter(e => e.date >= new Date(Date.now() - 7 * 86400000).toISOString().slice(0, 10));
        const prev7 = exps.filter(e => {
            const d = e.date;
            const s = new Date(Date.now() - 14 * 86400000).toISOString().slice(0, 10);
            const e7 = new Date(Date.now() - 7 * 86400000).toISOString().slice(0, 10);
            return d >= s && d < e7;
        });
        const sum7 = last7.reduce((s, e) => s + e.amount, 0);
        const sumP7 = prev7.reduce((s, e) => s + e.amount, 0);
        if (sumP7 > 0) {
            const change = Math.round((sum7 - sumP7) / sumP7 * 100);
            insights.push({ icon: change > 0 ? '📈' : '📉', text: `Week-over-week spending ${change > 0 ? 'up' : 'down'} ${Math.abs(change)}%` });
        }
    }
    const days = new Set(exps.map(e => e.date));
    if (days.size > 0) {
        const avg = totalExp / days.size;
        insights.push({ icon: '📅', text: `Average daily spend: ${fmt(avg)} across ${days.size} active days` });
    }
    return insights;
}
function renderStatsGrid(exps, incs) {
    const totalExp = exps.reduce((s, e) => s + e.amount, 0);
    const totalInc = incs.reduce((s, i) => s + i.amount, 0);
    const maxExp = exps.length > 0 ? Math.max(...exps.map(e => e.amount)) : 0;
    const cats = new Set(exps.map(e => e.category));
    const stats = [
        { icon: '💸', value: fmt(totalExp), label: 'Total Spent' },
        { icon: '💰', value: fmt(totalInc), label: 'Total Income' },
        { icon: '🔝', value: fmt(maxExp), label: 'Largest Expense' },
        { icon: '📁', value: cats.size, label: 'Categories Used' }
    ];
    $('statsGrid').innerHTML = stats.map((s, i) => `<div class="stat-card" style="animation-delay:${i * 0.1}s"><div class="stat-card-icon">${s.icon}</div><div class="stat-card-value">${s.value}</div><div class="stat-card-label">${s.label}</div></div>`).join('');
}

// ─── Budget Page ───
function updateBudgetPage() {
    const mk = monthKey(today());
    const mExp = expenses.filter(e => e.date.startsWith(mk));
    const totalBudget = Object.values(budgets).reduce((s, v) => s + v, 0);
    const totalSpent = mExp.reduce((s, e) => s + e.amount, 0);
    $('budgetTotalAmount').textContent = fmt(totalBudget);
    const pct = totalBudget > 0 ? Math.round(totalSpent / totalBudget * 100) : 0;
    const fill = $('budgetProgressFill');
    fill.style.width = clamp(pct, 0, 100) + '%';
    fill.style.background = pct > 90 ? 'var(--red)' : pct > 70 ? 'var(--orange)' : 'linear-gradient(90deg, var(--green), var(--blue))';
    $('budgetProgressText').textContent = `${pct}% used — ${fmt(totalSpent)} of ${fmt(totalBudget)}`;
    const daysLeft = new Date(new Date().getFullYear(), new Date().getMonth() + 1, 0).getDate() - new Date().getDate();
    $('budgetDaysLeft').textContent = `${daysLeft} days left in month`;

    // Category budgets
    const catSpend = {};
    mExp.forEach(e => { catSpend[e.category] = (catSpend[e.category] || 0) + e.amount; });
    const budgetEntries = Object.entries(budgets).sort((a, b) => a[0].localeCompare(b[0]));
    if (budgetEntries.length === 0) {
        $('budgetList').innerHTML = '<div class="empty-state"><div class="empty-icon float-loop">📋</div><p>No budgets set. Tap Edit to add.</p></div>';
    } else {
        $('budgetList').innerHTML = budgetEntries.map(([cat, amount], i) => {
            const spent = catSpend[cat] || 0;
            const p = Math.round(spent / amount * 100);
            const catObj = CATEGORIES.find(c => c.name === cat);
            const color = p > 90 ? 'var(--red)' : p > 70 ? 'var(--orange)' : 'var(--green)';
            return `<div class="budget-item" style="animation-delay:${i * 0.1}s"><div class="budget-item-header"><span class="budget-item-cat">${catObj?.emoji || '📦'} ${cat}</span><span class="budget-item-vals">${fmt(spent)} / ${fmt(amount)}</span></div><div class="budget-bar"><div class="budget-bar-fill animated-bar" style="width:${clamp(p, 0, 100)}%;background:${color};animation-delay:${0.3 + i * 0.1}s"></div></div></div>`;
        }).join('');
    }

    // Goal
    updateGoalCard();
}
function updateGoalCard() {
    if (!goal) {
        $('goalContent').innerHTML = '<p class="goal-placeholder">Set a monthly savings target</p>';
        return;
    }
    const mk = monthKey(today());
    const totalInc = incomes.filter(i => i.date.startsWith(mk)).reduce((s, i) => s + i.amount, 0);
    const totalExp = expenses.filter(e => e.date.startsWith(mk)).reduce((s, e) => s + e.amount, 0);
    const saved = totalInc - totalExp;
    const pct = Math.round(saved / goal * 100);
    const color = pct >= 100 ? 'var(--green)' : pct >= 50 ? 'var(--blue)' : 'var(--orange)';
    $('goalContent').innerHTML = `
        <div class="goal-bar"><div class="goal-bar-fill" style="width:${clamp(pct, 0, 100)}%;background:${color}"></div></div>
        <div class="goal-stat-row"><span>Saved</span><span>${fmt(Math.max(0, saved))}</span></div>
        <div class="goal-stat-row"><span>Target</span><span>${fmt(goal)}</span></div>
        <div class="goal-stat-row"><span>Progress</span><span>${pct}%</span></div>
    `;
}

// ─── Export / Import ───
function exportCSV() {
    let csv = 'Type,Date,Category/Source,Amount,Description,Payment,Notes\n';
    expenses.forEach(e => {
        csv += `Expense,${e.date},${e.category},${e.amount},"${(e.description || '').replace(/"/g, '""')}",${e.payment || ''},"${(e.notes || '').replace(/"/g, '""')}"\n`;
    });
    incomes.forEach(i => {
        csv += `Income,${i.date},${i.source},${i.amount},"${(i.description || '').replace(/"/g, '""')}",${i.paymentMode || ''},""\n`;
    });
    const blob = new Blob([csv], { type: 'text/csv' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `expenses_${today()}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
    toast('CSV exported!');
}
function importCSV(e) {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
        const lines = reader.result.split('\n').slice(1);
        let added = 0;
        lines.forEach(line => {
            if (!line.trim()) return;
            const parts = parseCSVLine(line);
            if (parts.length < 4) return;
            const [type, date, catOrSrc, amount, desc, pay, notes] = parts;
            const amt = parseFloat(amount);
            if (!amt) return;
            if (type === 'Expense') {
                const catObj = CATEGORIES.find(c => c.name === catOrSrc);
                expenses.push({ id: uid(), amount: amt, category: catOrSrc, emoji: catObj?.emoji || '📦', date, description: desc || '', payment: pay || 'Cash', notes: notes || '' });
            } else if (type === 'Income') {
                incomes.push({ id: uid(), amount: amt, source: catOrSrc, date, description: desc || '', paymentMode: pay || '' });
            }
            added++;
        });
        save(); updateAll();
        toast(`Imported ${added} entries!`);
    };
    reader.readAsText(file);
    e.target.value = '';
}
function parseCSVLine(line) {
    const result = [];
    let current = '';
    let inQuotes = false;
    for (let i = 0; i < line.length; i++) {
        const ch = line[i];
        if (ch === '"') {
            if (inQuotes && line[i + 1] === '"') { current += '"'; i++; }
            else inQuotes = !inQuotes;
        } else if (ch === ',' && !inQuotes) {
            result.push(current.trim());
            current = '';
        } else {
            current += ch;
        }
    }
    result.push(current.trim());
    return result;
}

// ─── Confetti ───
function launchConfetti() {
    const canvas = $('confetti');
    canvas.classList.remove('hidden');
    const ctx = canvas.getContext('2d');
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    const pieces = [];
    const colors = ['#ff4477', '#5588ff', '#00e09e', '#ff9944', '#aa66ff', '#ffcc33'];
    for (let i = 0; i < 80; i++) {
        pieces.push({
            x: canvas.width / 2 + (Math.random() - 0.5) * 200,
            y: canvas.height / 2,
            vx: (Math.random() - 0.5) * 12,
            vy: -8 - Math.random() * 8,
            size: 4 + Math.random() * 6,
            color: colors[Math.floor(Math.random() * colors.length)],
            rotation: Math.random() * 360,
            rotSpeed: (Math.random() - 0.5) * 10,
            gravity: 0.15 + Math.random() * 0.1
        });
    }
    let frame = 0;
    function draw() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        pieces.forEach(p => {
            p.x += p.vx;
            p.vy += p.gravity;
            p.y += p.vy;
            p.rotation += p.rotSpeed;
            p.vx *= 0.99;
            ctx.save();
            ctx.translate(p.x, p.y);
            ctx.rotate(p.rotation * Math.PI / 180);
            ctx.fillStyle = p.color;
            ctx.globalAlpha = Math.max(0, 1 - frame / 80);
            ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size * 0.6);
            ctx.restore();
        });
        frame++;
        if (frame < 80) requestAnimationFrame(draw);
        else { ctx.clearRect(0, 0, canvas.width, canvas.height); canvas.classList.add('hidden'); }
    }
    requestAnimationFrame(draw);
}

// ─── Modal Overlay Helper ───
function toggleOverlay(id, show) {
    const el = $(id);
    if (show) {
        el.classList.remove('hidden');
    } else {
        const modal = el.querySelector('.modal');
        if (modal) {
            modal.style.animation = 'modalOut 0.3s ease forwards';
            setTimeout(() => { el.classList.add('hidden'); modal.style.animation = ''; }, 300);
        } else {
            el.classList.add('hidden');
        }
    }
}

// ─── Toast ───
function toast(msg) {
    const el = $('toast');
    el.textContent = msg;
    el.classList.remove('hidden', 'toast-out');
    el.style.animation = 'none';
    el.offsetHeight;
    el.style.animation = '';
    clearTimeout(el._timeout);
    el._timeout = setTimeout(() => {
        el.classList.add('toast-out');
        setTimeout(() => el.classList.add('hidden'), 300);
    }, 2500);
}

// ─── Sanitize ───
function sanitize(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
}

// ─── Service Worker Registration ───
if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('sw.js').catch(() => {});
}

// ─── Start ───
document.addEventListener('DOMContentLoaded', init);

})();
