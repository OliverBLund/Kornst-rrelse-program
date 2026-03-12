/* ═══════════════════════════════════════════════════════════════
   _shell.js — GrainSize Analysis Shell Builder
   Generates sidebar, menubar, toolbar, statusbar DOM for every
   concept HTML page. Import after _shared.css.

   Usage in a page:
     initShell({ activeTab: 'reports' });
   ═══════════════════════════════════════════════════════════════ */

/* ── Shared dataset registry ── */
const DATASETS = [
  {id:'welcome',  label:'Welcome',              icon:'house',   closable:false, special:true},
  {id:'dk07',     label:'Borehole_DK-07',       icon:'vial',    closable:true,  d50:'0.42',  k:'12.3',  fractions:47,  status:'ok'},
  {id:'gw24a',    label:'Sample_GW-2024-A',     icon:'vial',    closable:true,  d50:'0.18',  k:'3.1',   fractions:38,  status:'ok'},
  {id:'lc11',     label:'Core_LC-11',           icon:'vial',    closable:true,  d50:'0.89',  k:'48.7',  fractions:52,  status:'ok'},
  {id:'bh03',     label:'Borehole_BH-03',       icon:'vial',    closable:true,  d50:'0.31',  k:'7.2',   fractions:41,  status:'ok'},
  {id:'sp05',     label:'Soil_Profile_SP-05',   icon:'vial',    closable:true,  d50:'0.65',  k:'28.4',  fractions:29,  status:'warn', warn:'2 sieves below detection limit'},
  {id:'tr12',     label:'Trench_TR-12',         icon:'vial',    closable:true,  d50:'0.12',  k:'1.4',   fractions:33,  status:'ok'},
  {id:'cptu08',   label:'CPTU-08_Sample',       icon:'vial',    closable:true,  d50:'0.08',  k:'0.6',   fractions:22,  status:'ok'},
  {id:'dh14',     label:'Drillhole_DH-14',      icon:'vial',    closable:true,  d50:'1.20',  k:'112.3', fractions:55,  status:'ok'},
  {id:'ws22',     label:'WellScreen_WS-22',     icon:'vial',    closable:true,  d50:'0.55',  k:'21.8',  fractions:44,  status:'ok'},
  {id:'gp09',     label:'GravelPit_GP-09',      icon:'vial',    closable:true,  d50:'2.80',  k:'380.5', fractions:18,  status:'ok'},
  {id:'cl01',     label:'Clay_CL-01',           icon:'vial',    closable:true,  d50:'0.004', k:'0.002', fractions:62,  status:'warn', warn:'Cu > 500, method applicability limited'},
  {id:'rk15',     label:'RockCore_RK-15',       icon:'vial',    closable:true,  d50:'4.20',  k:'820.0', fractions:14,  status:'ok'},
];

/* Tab → page routing for cross-page navigation */
const TAB_ROUTES = {
  'individual': '02_tabs.html',
  'comparison': '02_tabs.html',
  'reports':    '03_reports_export.html',
  'export':     '03_reports_export.html',
};

let _currentId   = 'dk07';
let _activeTab   = 'individual';

/* ══════════════════════════════════════════════
   HTML BUILDERS
══════════════════════════════════════════════ */

function _menubarHTML() {
  return `
<div class="mb">
  <div class="mi">File
    <div class="dd">
      <div class="ddi"><i class="fa-regular fa-folder-open"></i>Open Files…<span class="k">Ctrl+O</span></div>
      <div class="ddi"><i class="fa-regular fa-file-lines"></i>Load Sample Data</div>
      <div class="dds"></div>
      <div class="ddi"><i class="fa-solid fa-file-export"></i>Export Results…<span class="k">Ctrl+E</span></div>
      <div class="ddi"><i class="fa-regular fa-image"></i>Export Plot…</div>
      <div class="dds"></div>
      <div class="ddi"><i class="fa-solid fa-right-from-bracket"></i>Exit<span class="k">Ctrl+Q</span></div>
    </div>
  </div>
  <div class="mi">Analysis
    <div class="dd">
      <div class="ddi"><i class="fa-solid fa-bolt"></i>Calculate K Values<span class="k">Ctrl+K</span></div>
      <div class="ddi"><i class="fa-solid fa-rotate"></i>Recalculate All</div>
      <div class="dds"></div>
      <div class="ddi"><i class="fa-solid fa-sliders"></i>Manage Porosity…</div>
      <div class="ddi"><i class="fa-solid fa-table-columns"></i>Update Comparison</div>
    </div>
  </div>
  <div class="mi">View
    <div class="dd">
      <div class="ddi"><i class="fa-solid fa-sidebar"></i>Toggle Panel<span class="k">Ctrl+B</span></div>
      <div class="dds"></div>
      <div class="ddi"><i class="fa-solid fa-chart-line"></i>Distribution Plot</div>
      <div class="ddi"><i class="fa-solid fa-chart-bar"></i>K-Values Chart</div>
    </div>
  </div>
  <div class="mi">Help
    <div class="dd">
      <div class="ddi"><i class="fa-solid fa-book"></i>Help Topics<span class="k">F1</span></div>
      <div class="ddi"><i class="fa-solid fa-flask"></i>Methods Overview</div>
      <div class="dds"></div>
      <div class="ddi"><i class="fa-solid fa-circle-info"></i>About</div>
    </div>
  </div>
  <span class="mb-sp"></span>
  <span style="font-size:11px;color:var(--text-muted);font-family:var(--fm);padding-right:4px">
    Grain Size Analysis — Hydraulic Conductivity Calculator
  </span>
</div>`;
}

function _sidebarHTML() {
  const samples = DATASETS.filter(d => !d.special);
  const cards = samples.map(d => {
    const isActive = d.id === _currentId;
    const isWarn   = d.status === 'warn';
    return `
    <div class="s-item${isActive ? ' active expanded' : ''}" id="si-${d.id}" data-id="${d.id}">
      <div class="s-item-main" onclick="_selSample('${d.id}')">
        <div class="s-ic"><i class="fa-solid fa-${d.icon}"></i></div>
        <div class="s-info">
          <div class="s-name">${d.label}</div>
          <div class="s-meta">D50 ${d.d50} mm · K̄ ${d.k} m/d</div>
        </div>
        <div class="s-led ${d.status}"></div>
        <button class="s-expand-btn" onclick="_toggleExpand(event,'${d.id}')">
          <i class="fa-solid fa-chevron-right"></i>
        </button>
      </div>
      <div class="s-detail">
        <div class="s-status-line${isWarn ? ' warn' : ''}">
          <i class="fa-solid fa-${isWarn ? 'triangle-exclamation' : 'check-circle'}"></i>
          ${isWarn ? d.warn : d.fractions + ' sieve fractions · All OK'}
        </div>
        <div class="s-act-row">
          <button class="s-act-btn"><i class="fa-solid fa-table"></i> Inspect</button>
          <button class="s-act-btn"><i class="fa-solid fa-terminal"></i> Log</button>
          <button class="s-act-btn"><i class="fa-solid fa-sliders"></i> Props</button>
          <button class="s-act-btn danger"><i class="fa-solid fa-xmark"></i> Remove</button>
        </div>
      </div>
    </div>`;
  }).join('');

  return `
<aside class="sb">
  <div class="sb-logo">
    <div class="logo-mark"><i class="fa-solid fa-layer-group"></i></div>
    <div class="logo-tx">
      <span class="logo-name">GrainSize</span>
      <span class="logo-sub">ANALYSIS · v0.9-β</span>
    </div>
  </div>

  <div class="sb-body">
    <div class="sb-sect">
      <span class="sb-sect-lbl">Files &amp; Samples</span>
      <button class="sb-sect-btn"><i class="fa-solid fa-plus"></i> Add</button>
    </div>
    <div class="sb-pad" style="padding-bottom:4px">
      <div class="drop">
        <i class="fa-solid fa-cloud-arrow-up"></i>
        <span class="drop-t">Drop files or click to browse</span>
        <span class="drop-s">CSV · XLSX · TXT</span>
      </div>
    </div>
    <div class="s-list" id="s-list">${cards}</div>

    <div class="sb-sect" style="margin-top:6px">
      <span class="sb-sect-lbl">Parameters</span>
    </div>
    <div class="p-rows">
      <div class="p-row">
        <span class="p-lbl"><i class="fa-solid fa-thermometer-half"></i>Temperature</span>
        <div class="p-field">
          <input class="p-in" type="number" value="20.0" step="0.5">
          <span class="p-unit">°C</span>
        </div>
      </div>
      <div class="p-row">
        <span class="p-lbl"><i class="fa-solid fa-circle-nodes"></i>Porosity</span>
        <div class="p-field">
          <input class="p-in" type="number" value="0.40" step="0.01">
          <span class="p-unit">—</span>
        </div>
      </div>
    </div>
    <button class="sb-btn">
      <i class="fa-solid fa-sliders"></i> Manage Per-Sample Porosity…
    </button>

    <div class="sb-sect" style="margin-top:6px">
      <span class="sb-sect-lbl">Actions</span>
    </div>
    <div style="padding:6px 0 2px">
      <button class="sb-btn go">
        <i class="fa-solid fa-bolt"></i> Calculate K Values
      </button>
    </div>

    <div class="sb-sect" style="margin-top:6px">
      <span class="sb-sect-lbl">Stratigraphy</span>
    </div>
    <div style="padding:6px 0 4px">
      <div class="strata">
        <div class="st-row st-r1"><div class="st-dot"></div>Topsoil / Fill</div>
        <div class="st-row st-r2"><div class="st-dot"></div>Fine Sand</div>
        <div class="st-row st-r3"><div class="st-dot"></div>Coarse Gravel</div>
        <div class="st-row st-r4"><div class="st-dot"></div>▼ Groundwater</div>
      </div>
    </div>
  </div>

  <div class="dtu-box">
    <div class="dtu-logo">DTU</div>
    <div class="dtu-info">
      <span class="dtu-prog">Grain Size Analysis</span>
      <span class="dtu-dept">Hydraulic Conductivity Calculator</span>
    </div>
  </div>

  <div class="sb-foot">
    <button class="sf-btn"><i class="fa-solid fa-book-open"></i>Help</button>
    <button class="sf-btn"><i class="fa-solid fa-gears"></i>Settings</button>
    <button class="sf-btn"><i class="fa-solid fa-circle-info"></i>About</button>
  </div>
</aside>`;
}

function _toolbarHTML(activeTab) {
  const tabs = [
    {id:'individual', icon:'chart-area',    label:'Individual Samples', badge: DATASETS.filter(d=>!d.special).length},
    {id:'comparison', icon:'code-compare',  label:'Comparison'},
    {id:'reports',    icon:'file-contract', label:'Reports'},
    {id:'export',     icon:'file-export',   label:'Export'},
  ];
  const tabsHTML = tabs.map(t => `
    <div class="tab${t.id === activeTab ? ' on' : ''}" onclick="_navTab('${t.id}')">
      <i class="fa-solid fa-${t.icon}"></i>${t.label}
      ${t.badge ? `<span class="t-badge">${t.badge}</span>` : ''}
    </div>`).join('');

  return `
<div class="tb">
  <div class="tb-tabs">${tabsHTML}</div>
  <div class="tb-sep"></div>
  <button class="tb-btn"><i class="fa-regular fa-folder-open"></i>&nbsp;Add Files</button>
  <button class="tb-btn go"><i class="fa-solid fa-bolt"></i>&nbsp;Calculate K</button>
  <div class="tb-sp"></div>
  <button class="tb-btn" style="margin-right:4px"><i class="fa-solid fa-book"></i>&nbsp;Help</button>
</div>`;
}

function _dsBarHTML() {
  const tabs = DATASETS.map(d => `
    <div class="ds-tab${d.id === _currentId ? ' on' : ''}" id="dt-${d.id}" data-id="${d.id}"
      onclick="_selSample('${d.id}')">
      <i class="fa-solid fa-${d.icon}"></i>&nbsp;${d.label}
      ${d.closable ? '<span class="dx" onclick="event.stopPropagation()">✕</span>' : ''}
    </div>`).join('');

  return `
<div class="ds-bar-outer" id="ds-bar-outer">
  <button class="ds-nav" id="ds-prev" onclick="_scrollTabs(-1)" disabled title="Scroll left">
    <i class="fa-solid fa-chevron-left"></i>
  </button>
  <div class="ds-scroll-wrap" id="ds-scroll-wrap">
    <div class="ds-bar" id="dsbar">${tabs}</div>
  </div>
  <button class="ds-nav" id="ds-next" onclick="_scrollTabs(1)" title="Scroll right">
    <i class="fa-solid fa-chevron-right"></i>
  </button>
  <div class="ds-more-wrap">
    <button class="ds-more-btn" id="ds-more-btn" onclick="_toggleDropdown()" style="display:none">
      <i class="fa-solid fa-ellipsis"></i><span id="ds-more-count"></span>
    </button>
    <div class="ds-dropdown-menu" id="ds-dropdown-menu"></div>
  </div>
</div>`;
}

function _statusbarHTML() {
  const ds = DATASETS.find(d => d.id === _currentId);
  return `
<div class="st">
  <div class="st-pill">
    <div class="led ok"></div>
    <span class="st-ready">Ready</span>
  </div>
  <div class="sseg"><span class="sk">SAMPLE</span><span class="sv hi" id="stsmp">${ds ? ds.label : '—'}</span></div>
  <div class="stsep"></div>
  <div class="sseg"><span class="sk">D50</span><span class="sv bl" id="std50">${ds ? ds.d50 + ' mm' : '—'}</span></div>
  <div class="stsep"></div>
  <div class="sseg"><span class="sk">K̄</span><span class="sv bl" id="stk">${ds ? ds.k + ' m/d' : '—'}</span></div>
  <div class="stsep"></div>
  <div class="sseg"><span class="sk">TEMP</span><span class="sv">20.0 °C</span></div>
  <div class="stsep"></div>
  <div class="sseg"><span class="sk">METHODS</span><span class="sv">14 / 14</span></div>
  <div class="stsep"></div>
  <div class="sseg"><span class="sk">DATASETS</span><span class="sv hi" id="st-datasets">${DATASETS.filter(d=>!d.special).length}</span></div>
  <div class="stsp"></div>
  <div class="st-ver">v0.9.0-beta</div>
</div>`;
}

/* ══════════════════════════════════════════════
   INIT
══════════════════════════════════════════════ */
function initShell(config = {}) {
  _activeTab = config.activeTab || 'individual';
  if (config.currentId) _currentId = config.currentId;

  const app  = document.querySelector('.app');
  const main = document.querySelector('.main');

  /* Insert shell elements */
  app.insertAdjacentHTML('afterbegin', _sidebarHTML());
  app.insertAdjacentHTML('afterbegin', _menubarHTML());
  app.insertAdjacentHTML('beforeend',  _statusbarHTML());

  /* Toolbar goes into .main before any page content */
  main.insertAdjacentHTML('afterbegin', _toolbarHTML(_activeTab));

  /* Dataset tab bar only when on Individual Samples page */
  if (_activeTab === 'individual' || _activeTab === 'comparison') {
    const firstChild = main.querySelector('.tb').nextSibling;
    main.querySelector('.tb').insertAdjacentHTML('afterend', _dsBarHTML());
    setTimeout(_updateNav, 100);
    _buildDropdown();
    const wrap = document.getElementById('ds-scroll-wrap');
    if (wrap) wrap.addEventListener('scroll', _updateNav);
  }

  /* Close dropdown on outside click */
  document.addEventListener('click', e => {
    if (!e.target.closest('.ds-more-wrap')) {
      const m = document.getElementById('ds-dropdown-menu');
      if (m) m.classList.remove('open');
    }
  });

  /* Page-level tab switching (within same page) — pages override _onPageTab */
  if (typeof _onPageInit === 'function') _onPageInit();
}

/* ══════════════════════════════════════════════
   EVENT HANDLERS (global, called from HTML)
══════════════════════════════════════════════ */

function _navTab(id) {
  /* Cross-page navigation for tabs on different HTML files */
  const page = TAB_ROUTES[id];
  const currentPage = window.location.pathname.split('/').pop() || 'index.html';
  if (page && page !== currentPage) {
    window.location.href = page + '?tab=' + id;
    return;
  }
  /* Same-page tab switch — delegate to page handler */
  if (typeof _onPageTab === 'function') _onPageTab(id);
}

function _selSample(id) {
  const ds = DATASETS.find(d => d.id === id);
  if (!ds) return;
  _currentId = id;

  /* Sidebar sync */
  document.querySelectorAll('.s-item').forEach(el => {
    const isThis = el.dataset.id === id;
    el.classList.toggle('active', isThis);
    if (isThis) el.classList.add('expanded');
  });

  /* Tab bar sync */
  document.querySelectorAll('.ds-tab').forEach(t => t.classList.toggle('on', t.dataset.id === id));

  /* Scroll active tab into view */
  const activeTab = document.getElementById('dt-' + id);
  const wrap = document.getElementById('ds-scroll-wrap');
  if (activeTab && wrap) {
    const tL = activeTab.offsetLeft, tR = tL + activeTab.offsetWidth;
    const wL = wrap.scrollLeft,      wR = wL + wrap.clientWidth;
    if (tL < wL) wrap.scrollLeft = tL - 8;
    else if (tR > wR) wrap.scrollLeft = tR - wrap.clientWidth + 8;
  }

  _updateNav();
  _buildDropdown();

  /* Status bar */
  if (!ds.special) {
    const s = document.getElementById('stsmp'); if (s) s.textContent = ds.label;
    const d = document.getElementById('std50'); if (d) d.textContent = ds.d50 + ' mm';
    const k = document.getElementById('stk');   if (k) k.textContent = ds.k + ' m/d';
  }

  if (typeof _onSampleChange === 'function') _onSampleChange(ds);
}

function _toggleExpand(evt, id) {
  evt.stopPropagation();
  const el = document.getElementById('si-' + id);
  if (el) el.classList.toggle('expanded');
}

function _scrollTabs(dir) {
  const wrap = document.getElementById('ds-scroll-wrap');
  if (wrap) { wrap.scrollBy({left: dir * 160, behavior: 'smooth'}); setTimeout(_updateNav, 220); }
}

function _updateNav() {
  const wrap = document.getElementById('ds-scroll-wrap');
  const bar  = document.getElementById('dsbar');
  if (!wrap || !bar) return;

  const prev = document.getElementById('ds-prev');
  const next = document.getElementById('ds-next');
  if (prev) prev.disabled = wrap.scrollLeft <= 1;
  if (next) next.disabled = wrap.scrollLeft >= bar.scrollWidth - wrap.clientWidth - 1;

  const wrapRect = wrap.getBoundingClientRect();
  let hidden = 0;
  document.querySelectorAll('.ds-tab').forEach(tab => {
    const r = tab.getBoundingClientRect();
    if (r.right > wrapRect.right + 4 || r.left < wrapRect.left - 4) hidden++;
  });
  const btn = document.getElementById('ds-more-btn');
  const cnt = document.getElementById('ds-more-count');
  if (btn) btn.style.display = hidden > 0 ? 'flex' : 'none';
  if (cnt) cnt.textContent = hidden > 0 ? '+' + hidden : '';
}

function _buildDropdown() {
  const menu = document.getElementById('ds-dropdown-menu');
  if (!menu) return;
  menu.innerHTML = DATASETS.filter(d => !d.special).map(d => `
    <div class="ds-dd-item${d.id === _currentId ? ' on' : ''}" onclick="_selSample('${d.id}');_closeDropdown()">
      <i class="fa-solid fa-vial"></i>
      <span>${d.label}</span>
      <span style="font-family:var(--fm);font-size:9.5px;color:var(--text-muted);margin-left:4px">${d.d50}mm</span>
      <div class="ds-dd-led ${d.status}" style="margin-left:auto"></div>
      ${d.id === _currentId ? '<i class="fa-solid fa-check ds-dd-check" style="margin-left:6px"></i>' : ''}
    </div>`).join('');
}

function _toggleDropdown() {
  const m = document.getElementById('ds-dropdown-menu');
  if (m) m.classList.toggle('open');
}
function _closeDropdown() {
  const m = document.getElementById('ds-dropdown-menu');
  if (m) m.classList.remove('open');
}
