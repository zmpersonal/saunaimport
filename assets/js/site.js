(() => {
  const money = (n) => {
    if (n == null || Number.isNaN(Number(n))) return '—';
    n = Number(n);
    if (n >= 1e9) return `$${(n/1e9).toFixed(n >= 10e9 ? 1 : 2)}B`;
    if (n >= 1e6) return `$${(n/1e6).toFixed(n >= 10e6 ? 1 : 2)}M`;
    if (n >= 1e3) return `$${(n/1e3).toFixed(1)}K`;
    return `$${n.toLocaleString()}`;
  };
  const pct = (n) => n == null || !Number.isFinite(Number(n)) ? '—' : `${Number(n) >= 0 ? '+' : ''}${Number(n).toFixed(1)}%`;
  const monthLabel = (value) => {
    if (!/^\d{4}-\d{2}$/.test(value || '')) return value || '—';
    const [y,m] = value.split('-').map(Number);
    return new Intl.DateTimeFormat('en-US', {month:'long', year:'numeric', timeZone:'UTC'}).format(new Date(Date.UTC(y,m-1,1)));
  };
  const dateLabel = (value) => {
    if (!value) return '—';
    const d = new Date(value);
    return Number.isNaN(d.getTime()) ? value : new Intl.DateTimeFormat('en-US', {month:'long', day:'numeric', year:'numeric'}).format(d);
  };

  let cachedData = null;

  async function loadTrade() {
    try {
      const res = await fetch('/data/trade.json', {cache:'no-store'});
      if (!res.ok) return;
      cachedData = await res.json();
      enhance(cachedData);
    } catch (err) {
      // The committed HTML contains a complete static fallback; a failed fetch
      // should never replace it with an error state.
      console.warn('Trade data enhancement unavailable', err);
    }
  }

  function enhance(data) {
    document.querySelectorAll('[data-last-updated]').forEach(el => el.textContent = dateLabel(data.last_updated));
    document.querySelectorAll('[data-latest-month]').forEach(el => el.textContent = monthLabel(data.latest_month));
    const live = data.status === 'live';
    document.querySelectorAll('[data-status]').forEach(el => {
      el.textContent = live ? 'Live Census data' : 'Data unavailable';
      el.classList.toggle('live', live);
    });
    if (!live || !data.categories?.length) return;

    const primary = data.categories[0];
    const latest = primary.series?.[primary.series.length - 1];
    const prev12 = primary.series?.[primary.series.length - 13];
    const yoy = latest && prev12 && prev12.general_imports ? (latest.general_imports / prev12.general_imports - 1) * 100 : null;
    document.querySelectorAll('[data-primary-value]').forEach(el => el.textContent = money(latest?.general_imports));
    document.querySelectorAll('[data-primary-yoy]').forEach(el => el.textContent = pct(yoy));
    document.querySelectorAll('[data-country-count]').forEach(el => el.textContent = String(primary.countries?.length || 0));

    const table = document.querySelector('[data-category-table]');
    if (table) {
      table.innerHTML = data.categories.map(cat => {
        const last = cat.series?.[cat.series.length - 1];
        return `<tr><td><strong>${escapeHtml(cat.label)}</strong><br><span class="small">${escapeHtml(cat.scope_note)}</span></td><td><span class="code">${escapeHtml(cat.code)}</span></td><td>${money(last?.general_imports)}</td><td>${money(last?.consumption_imports)}</td><td><a href="/classifications/${encodeURIComponent(cat.slug)}.html">Context</a></td></tr>`;
      }).join('');
    }

    const countries = document.querySelector('[data-country-list]');
    if (countries) {
      countries.innerHTML = (primary.countries || []).slice(0,10).map(c => `<div class="country-row"><span>${escapeHtml(c.name)}</span><span class="amount">${money(c.general_imports)}</span></div>`).join('') || '<p class="small">No country data available.</p>';
    }
    const canvas = document.querySelector('[data-trade-chart]');
    if (canvas) drawChart(canvas, primary.series || []);
  }

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>'"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]));
  }

  function drawChart(canvas, series) {
    if (!series.length) return;
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    const width = Math.max(320, rect.width);
    const height = 280;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    const ctx = canvas.getContext('2d');
    ctx.scale(dpr,dpr);
    const pad = {l:56,r:14,t:20,b:42};
    const vals = series.map(d => Number(d.general_imports || 0));
    const max = Math.max(...vals, 1) * 1.08;
    ctx.clearRect(0,0,width,height);
    ctx.strokeStyle = '#d8d0c3'; ctx.lineWidth = 1;
    ctx.fillStyle = '#6f6a61'; ctx.font = '11px system-ui';
    for (let i=0;i<5;i++) {
      const y = pad.t + (height-pad.t-pad.b) * i/4;
      ctx.beginPath(); ctx.moveTo(pad.l,y); ctx.lineTo(width-pad.r,y); ctx.stroke();
      const val = max * (1-i/4); ctx.fillText(money(val), 4, y+4);
    }
    ctx.strokeStyle = '#c95e2e'; ctx.lineWidth = 2.5; ctx.beginPath();
    series.forEach((d,i) => {
      const x = pad.l + (width-pad.l-pad.r) * (series.length===1?0:i/(series.length-1));
      const y = pad.t + (height-pad.t-pad.b) * (1 - Number(d.general_imports || 0)/max);
      i ? ctx.lineTo(x,y) : ctx.moveTo(x,y);
    });
    ctx.stroke();
    const every = Math.max(1, Math.ceil(series.length/6));
    series.forEach((d,i) => {
      if (i % every !== 0 && i !== series.length-1) return;
      const x = pad.l+(width-pad.l-pad.r)*(series.length===1?0:i/(series.length-1));
      ctx.fillStyle='#6f6a61'; ctx.save(); ctx.translate(x,height-18); ctx.rotate(-.35); ctx.fillText(d.month,0,0); ctx.restore();
    });
  }

  let resizeTimer;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      if (!cachedData?.categories?.length) return;
      const c = document.querySelector('[data-trade-chart]');
      if (c) drawChart(c, cachedData.categories[0].series || []);
    }, 120);
  }, {passive:true});

  loadTrade();
})();
