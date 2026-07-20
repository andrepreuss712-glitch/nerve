// Phase 04.7.2 — Founder Cost Dashboard client-side tab switcher + charts.
(function() {
  // ── CSRF-Token Helper ─────────────────────────────────────────────────────
  function getCsrfToken() {
    var m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.getAttribute('content') : '';
  }
  // Expose for future POST calls from this module
  window._adminGetCsrfToken = getCsrfToken;
  const tabs = document.querySelectorAll('.fcd-tab');
  const panels = document.querySelectorAll('.fcd-panel');

  function activate(name) {
    tabs.forEach(t => t.classList.toggle('active', t.dataset.tab === name));
    panels.forEach(p => { p.hidden = (p.id !== 'panel-' + name); });
    if (location.hash !== '#' + name) history.replaceState(null, '', '#' + name);
  }

  tabs.forEach(t => t.addEventListener('click', () => activate(t.dataset.tab)));

  const fromHash = (location.hash || '').replace('#', '');
  const initial = fromHash || window.FCD_INITIAL_TAB || 'uebersicht';
  activate(initial);

  // Period picker — reload on change
  const p = document.getElementById('fcd-period');
  if (p) p.addEventListener('change', () => {
    const url = new URL(location.href);
    url.searchParams.set('period', p.value);
    location.href = url.toString();
  });

  // Overview KPIs + Charts
  window.FCD = window.FCD || {};
  window.FCD.loadOverview = async function(period) {
    const r = await fetch('/admin/dashboard/api/overview?period=' + encodeURIComponent(period));
    if (!r.ok) return;
    const data = await r.json();
    document.querySelectorAll('[data-kpi]').forEach(el => {
      const key = el.dataset.kpi;
      if (data.kpis && data.kpis[key] !== undefined) el.textContent = data.kpis[key];
    });
    // KOSTEN-1 W3: Skip-Zaehler. N > 0 ist ein ALARM-Zustand, keine Kennzahl — deshalb
    // wechselt die Kachel sichtbar in den Warn-Zustand und nennt die verletzenden Tripel.
    // Ohne das WAS (provider/model/unit_type) waere die Zahl nicht handlungsfaehig.
    const skips = data.cost_log_skips;
    if (skips) {
      const kachel = document.getElementById('fcd-kpi-skips');
      const wert   = document.querySelector('[data-kpi="cost_skips"]');
      const detail = document.getElementById('fcd-skips-detail');
      if (wert) wert.textContent = String(skips.total || 0);
      if (kachel) kachel.classList.toggle('fcd-alarm', (skips.total || 0) > 0);
      if (detail) {
        detail.textContent = (skips.total || 0) > 0
          ? (skips.triples || []).map(t => `${t.triple} (${t.count}x)`).join(' · ')
          : 'seit Deploy, pro Prozess (Soll: 0)';
      }
    }
    if (data.mrr_costs_12m) FCD.renderMrrCosts(data.mrr_costs_12m);
    if (data.margin_12m) FCD.renderMarginChart(data.margin_12m);
  };

  window.FCD.renderMrrCosts = function(series) {
    const el = document.getElementById('fcd-chart-mrr-costs');
    if (!el || !window.Chart) return;
    new Chart(el, {
      type: 'bar',
      data: {
        labels: series.labels,
        datasets: [
          { label: 'MRR (€)', data: series.mrr, backgroundColor: '#00D4AA' },
          { label: 'Kosten (€)', data: series.costs, type: 'line', borderColor: '#ef4444' },
        ]
      },
      options: { responsive: true, maintainAspectRatio: false }
    });
  };

  window.FCD.renderMarginChart = function(series) {
    const el = document.getElementById('fcd-chart-margin');
    if (!el || !window.Chart) return;
    new Chart(el, {
      type: 'line',
      data: { labels: series.labels, datasets: [{ label: 'Marge %', data: series.values, borderColor: '#00D4AA', tension: 0.2 }] },
      options: { responsive: true, maintainAspectRatio: false, scales: { y: { min: 0, max: 100 } } }
    });
  };

  const wrap = document.querySelector('.fcd-wrap');
  const period = wrap ? wrap.dataset.period : '';
  if (window.FCD.loadOverview && period) window.FCD.loadOverview(period);
})();
