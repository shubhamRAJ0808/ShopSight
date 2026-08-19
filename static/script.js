// ════════════════════════════════════════════════════════════
//  ShopSight — script.js v4
//  Multi-page · Light/Dark Theme · Profile · Responsive
// ════════════════════════════════════════════════════════════

// ── Live Clock ────────────────────────────────────────────
function updateClock() {
  const t = new Date().toLocaleString('en-IN', {
    hour:'2-digit', minute:'2-digit', second:'2-digit',
    day:'2-digit', month:'short', year:'numeric'
  });
  ['live-time','live-time-side','live-time-ml'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.textContent = t;
  });
}
setInterval(updateClock, 1000);
updateClock();

// ── THEME ────────────────────────────────────────────────
let isDark = localStorage.getItem('xyz-theme') !== 'light';

function applyTheme(dark) {
  isDark = dark;
  document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
  localStorage.setItem('xyz-theme', dark ? 'dark' : 'light');

  // Update all theme buttons
  document.querySelectorAll('.topbar-theme-btn').forEach(btn => {
    btn.textContent = dark ? '🌙 Dark' : '☀ Light';
  });

  // Update profile toggle
  const profileToggle = document.getElementById('themeToggle');
  const profileLabel  = document.getElementById('themeLabel');
  if (profileToggle) {
    profileToggle.classList.toggle('on', dark);
    if (profileLabel) profileLabel.textContent = dark ? '🌙 Dark Mode' : '☀ Light Mode';
  }

  // Rebuild charts to match new theme
  Chart.defaults.color = dark ? '#4d6480' : '#64748b';
  rebuildAllCharts();
}

function toggleTheme() {
  applyTheme(!isDark);
}

// Theme is applied inside DOMContentLoaded to avoid premature chart rebuilds

// ── SIDEBAR (mobile) ──────────────────────────────────────
function toggleSidebar() {
  const sb = document.getElementById('sidebar');
  const ov = document.getElementById('sidebarOverlay');
  sb.classList.toggle('open');
  ov.classList.toggle('visible');
}
function closeSidebar() {
  document.getElementById('sidebar').classList.remove('open');
  document.getElementById('sidebarOverlay').classList.remove('visible');
}

// ── PAGE NAVIGATION ───────────────────────────────────────
const PAGE_IDS = ['overview','ml','filters','records','add'];
let currentPage = 'overview';

function showPage(pageId, navBtn) {
  // Hide all pages
  PAGE_IDS.forEach(id => {
    const el = document.getElementById('page-' + id);
    if (el) { el.classList.remove('active'); }
  });

  // Show target page
  const target = document.getElementById('page-' + pageId);
  if (target) {
    target.classList.add('active');
    target.classList.remove('fade-in');
    void target.offsetWidth; // force reflow
    target.classList.add('fade-in');
  }

  // Update nav buttons
  document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
  if (navBtn) navBtn.classList.add('active');

  currentPage = pageId;
  closeSidebar();

  // Rebuild charts for newly visible page
  if (pageId === 'filters') {
    destroyChart('rev2');
    destroyChart('dnt2');
    setTimeout(() => { buildAnalyticsCharts(); }, 100);
  }
  if (pageId === 'ml') {
    // Destroy stale chart first, then rebuild after page is fully visible
    destroyChart('ml');
    setTimeout(() => { buildMLChart(); }, 100);
  }

  // Scroll to top
  window.scrollTo(0, 0);
}

// ── PROFILE MODAL ─────────────────────────────────────────
// Profile fields are now a real <form> that posts to /profile/update and is
// rendered server-side from the database, scoped to the logged-in user — so
// there's nothing left to load/save on the client.
function openProfile() {
  document.getElementById('profileModal').classList.add('open');
}
function closeProfile() {
  document.getElementById('profileModal').classList.remove('open');
}
// Close on overlay click
document.getElementById('profileModal').addEventListener('click', function(e) {
  if (e.target === this) closeProfile();
});

// ── TOAST ─────────────────────────────────────────────────
function showToast(msg, type='') {
  const existing = document.querySelector('.toast');
  if (existing) existing.remove();

  const t = document.createElement('div');
  t.className = 'toast ' + type;
  t.innerHTML = `<span class="toast-icon">${type==='success'?'✓':'ℹ'}</span>${msg}`;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 2500);
}

// ════════════════════════════════════════════════════════════
//  CHARTS
// ════════════════════════════════════════════════════════════

Chart.defaults.font.family = "'Outfit', sans-serif";
Chart.defaults.font.size   = 12;

// Two palettes: the dark-theme colors are bright/light so they pop against
// the near-black background; the light-theme colors are the deeper,
// more saturated versions so they still have contrast against a white
// background instead of washing out. getColors()/getLineColors() pick the
// right one live, based on the current theme.
const COLORS_DARK  = ['#4f8ef7','#22d3a0','#a78bfa','#fb923c','#f87171','#38bdf8','#facc15','#34d399'];
const COLORS_LIGHT = ['#2563eb','#059669','#7c3aed','#d97706','#dc2626','#0284c7','#ca8a04','#0d9488'];
function getColors() { return isDark ? COLORS_DARK : COLORS_LIGHT; }
const fmt = v => v >= 1000 ? '₹'+(v/1000).toFixed(0)+'K' : '₹'+v;

// Store chart instances
const charts = {};

function destroyChart(id) {
  if (charts[id]) { charts[id].destroy(); delete charts[id]; }
}

function getGridColor() {
  return isDark ? '#1e2d45' : '#dce3ef';
}
function getTickColor() {
  return isDark ? '#4d6480' : '#64748b';
}

// ── ML Forecast Chart ─────────────────────────────────────
function buildMLChart() {
  destroyChart('ml');
  const mlCtx = document.getElementById('mlForecastChart');
  if (!mlCtx || !ALL_FC_LABELS.length) return;

  const [c1, c2, c3] = getColors();
  // Fill opacity is bumped noticeably in light mode — the same low-alpha
  // wash that reads as a subtle glow on a near-black background nearly
  // disappears on white, which is what was making the chart look flat/dull.
  const fillAlpha = isDark ? '14' : '26';

  charts['ml'] = new Chart(mlCtx, {
    type: 'line',
    data: {
      labels: ALL_FC_LABELS,
      datasets: [
        {
          label: 'Actual Revenue',
          data: HIST_SERIES.map(v => v !== null ? Number(v) : null),
          borderColor: c1, backgroundColor: c1 + fillAlpha,
          borderWidth: 2.5, pointRadius: 3, pointBackgroundColor: c1,
          fill: true, tension: 0.4, spanGaps: false,
        },
        {
          label: 'LR Forecast',
          data: LR_SERIES.map(v => v !== null ? Number(v) : null),
          borderColor: c2, backgroundColor: c2 + fillAlpha,
          borderWidth: 2.5, borderDash: [6,3], pointRadius: 4,
          pointBackgroundColor: c2, fill: false, tension: 0.4, spanGaps: false,
        },
        {
          label: 'MA Forecast',
          data: MA_SERIES.map(v => v !== null ? Number(v) : null),
          borderColor: c3, backgroundColor: c3 + fillAlpha,
          borderWidth: 2, borderDash: [4,4], pointRadius: 4,
          pointBackgroundColor: c3, fill: false, tension: 0.4, spanGaps: false,
        }
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: getTickColor(), boxWidth: 12, padding: 16 } },
        tooltip: {
          mode: 'index', intersect: false,
          callbacks: {
            label: function(ctx) {
              if (ctx.raw === null || ctx.raw === undefined) return '';
              const v = Number(ctx.raw);
              const idx = ctx.dataIndex;
              const histLen = MONTHLY_VALUES.length;
              let suffix = '';
              if (ctx.dataset.label === 'LR Forecast' && idx >= histLen) suffix = ' 📈 ML';
              else if (ctx.dataset.label === 'MA Forecast' && idx >= histLen) suffix = ' 〰 ML';
              else if (ctx.dataset.label === 'Actual Revenue') suffix = ' ✓';
              return ' ₹' + v.toLocaleString('en-IN') + suffix;
            },
            title: function(items) {
              const idx = items[0].dataIndex;
              const histLen = MONTHLY_VALUES.length;
              const lbl = ALL_FC_LABELS[idx] || '';
              return lbl + (idx >= histLen ? '  🤖 Forecast' : '  📊 Historical');
            }
          }
        }
      },
      scales: {
        x: { grid:{color: getGridColor()}, ticks:{color: getTickColor()} },
        y: { grid:{color: getGridColor()}, beginAtZero: false,
             ticks:{ color: getTickColor(), callback: fmt } }
      },
      interaction: { mode:'index', intersect:false }
    }
  });
}

// ── Revenue + Doughnut (Overview page) ───────────────────
const periodMap = {
  all: PERIOD_ALL, today: PERIOD_TODAY,
  yesterday: PERIOD_YESTERDAY, week: PERIOD_WEEK, month: PERIOD_MONTH,
};

function buildRevenueChart(canvasId, chartKey, data) {
  destroyChart(chartKey);
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  const hasData = data && data.labels && data.labels.length > 0;
  charts[chartKey] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: hasData ? data.labels : ['No data'],
      datasets: [{
        label: 'Revenue (₹)',
        data: hasData ? data.rev.map(Number) : [0],
        backgroundColor: getColors().map(c => c + (isDark ? '28' : '3a')), borderColor: getColors(),
        borderWidth: 2, borderRadius: 6,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: ctx => ' ₹'+Number(ctx.raw).toLocaleString('en-IN') } }
      },
      scales: {
        x: { grid:{color: getGridColor()}, ticks:{color: getTickColor()} },
        y: { grid:{color: getGridColor()}, beginAtZero:true, ticks:{color: getTickColor(), callback:fmt} }
      }
    }
  });
}

function buildDoughnutChart(canvasId, chartKey) {
  destroyChart(chartKey);
  const ctx = document.getElementById(canvasId);
  if (!ctx || !CHART_LABELS.length) return;
  charts[chartKey] = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: CHART_LABELS,
      datasets: [{
        data: CHART_QTY.map(Number),
        backgroundColor: getColors().map(c => c+'bb'),
        borderColor: isDark ? '#0f1623' : '#ffffff', borderWidth: 3, hoverOffset: 8,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false, cutout: '60%',
      plugins: {
        legend: { position:'bottom', labels:{color: getTickColor(), boxWidth:11, padding:10, font:{size:11}} }
      }
    }
  });
}

function buildOverviewCharts() {
  buildRevenueChart('revenueChart', 'rev1', PERIOD_ALL);
  buildDoughnutChart('doughnutChart', 'dnt1');
}

function buildAnalyticsCharts() {
  buildRevenueChart('revenueChart2', 'rev2', PERIOD_ALL);
  buildDoughnutChart('doughnutChart2', 'dnt2');
}

function rebuildAllCharts() {
  // Only rebuild ML chart if its page is currently active (canvas needs visible dimensions)
  const mlPage = document.getElementById('page-ml');
  if (charts['ml'] && mlPage && mlPage.classList.contains('active')) buildMLChart();
  if (charts['rev1']) buildRevenueChart('revenueChart', 'rev1', PERIOD_ALL);
  if (charts['dnt1']) buildDoughnutChart('doughnutChart', 'dnt1');
  if (charts['rev2']) buildRevenueChart('revenueChart2', 'rev2', PERIOD_ALL);
  if (charts['dnt2']) buildDoughnutChart('doughnutChart2', 'dnt2');
}

// ── Tab buttons (both pages) ─────────────────────────────
function initTabButtons(containerSelector, canvasId, chartKey) {
  document.querySelectorAll(containerSelector + ' .tab-btn').forEach(btn => {
    btn.addEventListener('click', function() {
      this.closest('.chart-card').querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      this.classList.add('active');
      buildRevenueChart(canvasId, chartKey, periodMap[this.dataset.period] || PERIOD_ALL);
    });
  });
}

// ── PAGINATION ───────────────────────────────────────────
const allRows  = Array.from(document.querySelectorAll('#tableBody tr'));
const pgSelect = document.getElementById('pageSizeSelect');
const pgWrap   = document.getElementById('pagination');
const searchEl = document.getElementById('searchBox');
let curPage = 1, pgSize = 25, filtered = allRows;

function renderTable() {
  const s = (curPage-1)*pgSize, e = s+pgSize;
  filtered.forEach((r,i) => r.style.display = (i>=s&&i<e)?'':'none');
  buildPagination();
}
function buildPagination() {
  if (!pgWrap) return;
  const total = Math.ceil(filtered.length / pgSize);
  pgWrap.innerHTML = '';
  if (total <= 1) return;
  const mk = (lbl, pg, dis, act) => {
    const b = document.createElement('button');
    b.className = 'pg-btn'+(act?' active':'');
    b.textContent = lbl; b.disabled = dis;
    b.onclick = () => { curPage=pg; renderTable(); };
    return b;
  };
  pgWrap.appendChild(mk('← Prev', curPage-1, curPage===1, false));
  for (let i=1; i<=total; i++) {
    if (i===1||i===total||(i>=curPage-2&&i<=curPage+2)) {
      pgWrap.appendChild(mk(i, i, false, i===curPage));
    } else if (i===curPage-3||i===curPage+3) {
      const d=document.createElement('span');
      d.textContent='…'; d.style.cssText='padding:6px 4px;color:#4d6480;font-size:12px;';
      pgWrap.appendChild(d);
    }
  }
  pgWrap.appendChild(mk('Next →', curPage+1, curPage===total, false));
}
if (searchEl) {
  searchEl.addEventListener('input', function() {
    const q = this.value.toLowerCase();
    filtered = allRows.filter(r => (r.dataset.product||'').includes(q));
    allRows.forEach(r => r.style.display='none');
    curPage = 1; renderTable();
  });
}
if (pgSelect) {
  pgSelect.addEventListener('change', function() {
    pgSize=parseInt(this.value); curPage=1; renderTable();
  });
}

// ── Accuracy bar animate ──────────────────────────────────
function animateAccBar() {
  const fill = document.querySelector('.acc-fill');
  if (fill) {
    const w = fill.style.width;
    fill.style.width = '0%';
    setTimeout(() => { fill.style.width = w; }, 300);
  }
}

// ── INIT ─────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function() {

  // Apply saved theme FIRST (inside DOMContentLoaded so DOM exists)
  applyTheme(isDark);

  // Build initial charts
  buildOverviewCharts();
  buildMLChart();

  // Tab listeners for overview page
  initTabButtons('#page-overview', 'revenueChart', 'rev1');

  // Tab listeners for filters/analytics page
  initTabButtons('#page-filters', 'revenueChart2', 'rev2');

  // Pagination
  renderTable();

  // Animate accuracy bar
  animateAccBar();

  // Entrance animations
  document.querySelectorAll('.kpi-card,.period-card,.ml-kpi-card').forEach((el,i)=>{
    el.style.opacity='0'; el.style.transform='translateY(16px)';
    el.style.transition=`opacity .45s ${i*.04}s ease, transform .45s ${i*.04}s ease`;
    requestAnimationFrame(()=>requestAnimationFrame(()=>{
      el.style.opacity='1'; el.style.transform='translateY(0)';
    }));
  });

  // Close sidebar on outside click (desktop resize guard)
  window.addEventListener('resize', () => {
    if (window.innerWidth > 768) closeSidebar();
  });

});