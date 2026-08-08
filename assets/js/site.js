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

  async function loadTrade() {
    try {
      const res = await fetch('/data/trade.json', {cache:'no-store'});
      if (!res.ok) return;
      const data = await res.json();
      document.querySelectorAll('[data-last-updated]').forEach(el => el.textContent = data.last_updated || 'Awaiting first sync');
      document.querySelectorAll('[data-latest-month]').forEach(el => el.textContent = data.latest_month || 'Awaiting first sync');
      const live = data.status === 'live';
      document.querySelectorAll('[data-status]').forEach(el => {
        el.textContent = live ? 'Live Census data' : 'Awaiting first Census sync';
        if (live) el.classList.add('live');
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
          return `<tr><td><strong>${cat.label}</strong><br><span class="small">${cat.scope_note}</span></td><td><span class="code">${cat.code}</span></td><td>${money(last?.general_imports)}</td><td>${money(last?.consumption_imports)}</td></tr>`;
        }).join('');
      }

      const countries = document.querySelector('[data-country-list]');
      if (countries) {
        countries.innerHTML = (primary.countries || []).slice(0,10).map(c => `<div class="country-row"><span>${c.name}</span><span class="amount">${money(c.general_imports)}</span></div>`).join('') || '<p class="small">No country data available.</p>';
      }
      const canvas = document.querySelector('[data-trade-chart]');
      if (canvas) drawChart(canvas, primary.series || []);
    } catch (err) {
      console.warn('Trade data unavailable', err);
    }
  }

  function drawChart(canvas, series) {
    if (!series.length) return;
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    const width = Math.max(320, rect.width);
    const height = 280;
    canvas.width = width * dpr; canvas.height = height * dpr;
    const ctx = canvas.getContext('2d'); ctx.scale(dpr,dpr);
    const pad = {l:52,r:14,t:20,b:42};
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
    }); ctx.stroke();
    const every = Math.max(1, Math.ceil(series.length/6));
    series.forEach((d,i) => { if (i % every !== 0 && i !== series.length-1) return; const x=pad.l+(width-pad.l-pad.r)*(series.length===1?0:i/(series.length-1)); ctx.fillStyle='#6f6a61'; ctx.save(); ctx.translate(x,height-18); ctx.rotate(-.35); ctx.fillText(d.month,0,0); ctx.restore(); });
  }
  window.addEventListener('resize', () => { const c=document.querySelector('[data-trade-chart]'); if(c) loadTrade(); }, {passive:true});
  loadTrade();
})();
