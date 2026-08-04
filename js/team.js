// Runtime overlay: pulls season leg content + (optionally) a team's config from
// Supabase and personalizes the static pages. With no config or no ?team=, the
// pages behave exactly like the static build.
(function () {
  const cfg = window.OTO_CONFIG || {};
  if (!cfg.url || !cfg.anonKey || !window.supabase) return;
  const db = window.supabase.createClient(cfg.url, cfg.anonKey);

  const params = new URLSearchParams(location.search);
  const slug = (params.get('team') || '').toLowerCase();

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => [...document.querySelectorAll(sel)];
  const escHtml = (t) => { const d = document.createElement('div'); d.textContent = t; return d.innerHTML; };

  async function activeSeason() {
    const { data } = await db.from('seasons').select('id,year').eq('active', true).limit(1);
    return data && data[0];
  }

  // ---- leg content overlay (admin-edited wording + flags) ----
  async function applyLegContent(seasonId) {
    const { data: legs } = await db.from('legs').select('n,beta,tags,team_rating,surface_text').eq('season_id', seasonId);
    if (!legs) return;
    for (const l of legs) {
      const card = $(`#leg-${l.n}`);
      if (!card) continue;
      const beta = card.querySelector('.beta');
      if (beta && l.beta) beta.innerHTML = '<span class="src">team beta</span>' + escHtml(l.beta);
      const tagrow = card.querySelector('.tagrow');
      if (tagrow) tagrow.innerHTML = (l.tags || []).map(t => `<span class="chip warn">⚠ ${escHtml(t)}</span>`).join('');
      const surf = card.querySelector('.surftext');
      if (surf && l.surface_text) surf.textContent = l.surface_text;
    }
  }

  // ---- team overlay ----
  async function applyTeam(seasonId) {
    const { data: teams } = await db.from('teams').select('*').eq('season_id', seasonId).eq('slug', slug).limit(1);
    const team = teams && teams[0];
    if (!team) return;

    // wrong variant? bounce to the right one (65 pages live under /65/)
    const here65 = typeof RACE_ID !== 'undefined' && RACE_ID === '65';
    if (team.race === '65' && !here65) { location.href = '65/' + location.pathname.split('/').pop() + location.search; return; }
    if (team.race !== '65' && here65) { location.href = '../' + location.pathname.split('/').pop() + location.search; return; }

    const [{ data: runners }, { data: assigns }] = await Promise.all([
      db.from('runners').select('slot,name,pace_min_per_mi').eq('team_id', team.id),
      db.from('assignments').select('leg,slot').eq('team_id', team.id),
    ]);
    const names = {}; (runners || []).forEach(r => { if (r.name) names[r.slot] = r.name; });
    const slotOf = {}; (assigns || []).forEach(a => { slotOf[a.leg] = a.slot; });
    const N = team.n_runners || 6;
    const defSlot = (n) => ((n - 1) % N) + 1;
    const legSlot = (n) => slotOf[n] || defSlot(n);
    const label = (s) => names[s] ? `${s}-${names[s]}` : `Slot ${s}`;

    // branding
    $$('.brand').forEach(el => el.textContent = team.name);
    const kicker = $('.kicker'); if (kicker) kicker.textContent = `${team.name.toUpperCase()} · RACE GUIDE`;
    document.title = `${team.name} — ${document.title.split('—').pop().trim()}`;

    // per-leg slot + runner name on cards, jump chips, chart bars, table rows
    $$('.leg').forEach(el => {
      const n = Number(el.id.replace('leg-', ''));
      el.dataset.slot = legSlot(n);
      const rn = el.querySelector('.runner-name');
      if (rn) rn.innerHTML = `<b>${escHtml(names[legSlot(n)] || '—')}</b>`;
    });
    $$('.jumprow a').forEach(el => {
      const n = Number((el.getAttribute('href') || '').replace('#leg-', ''));
      if (n) el.dataset.slot = legSlot(n);
    });
    $$('.skb').forEach(el => {
      const n = Number((el.getAttribute('href') || '').split('#leg-').pop());
      if (n) el.dataset.slot = legSlot(n);
    });
    $$('#index tbody tr[data-n]').forEach(tr => { tr.dataset.slot = legSlot(Number(tr.dataset.n)); });

    // runner filter bar (legs page): rebuild for this team
    const navrows = $$('nav.top .navrow');
    if ($('.jumprow') && typeof filterSlot === 'function') {
      let row = $('#teamFilterRow');
      if (!row) {
        row = document.createElement('div');
        row.className = 'navrow'; row.id = 'teamFilterRow';
        navrows[0].after(row);
      }
      row.innerHTML = '<span class="rowlabel">Runner</span>' +
        `<button class="filterbtn active" data-slot="0">All runners</button>` +
        Array.from({length: N}, (_, i) => `<button class="filterbtn" data-slot="${i + 1}">${escHtml(label(i + 1))}</button>`).join('');
      row.querySelectorAll('.filterbtn').forEach(b => b.addEventListener('click', () => filterSlot(Number(b.dataset.slot), b)));
    }

    // pace + wave -> timeline (respect a local override if the team set one on this device)
    if (typeof applyPlan === 'function' && !localStorage.getItem('oto_pace')) {
      const start = team.wave_start ? team.wave_start.split(':').reduce((h, m) => Number(h) * 60 + Number(m)) : PLAN.start;
      applyPlan(Number(team.pace_min_per_mi) || PLAN.pace, start);
      const paceIn = $('#paceIn'), startIn = $('#startIn');
      if (paceIn) { const p = Number(team.pace_min_per_mi) || PLAN.pace; paceIn.value = `${Math.floor(p)}:${String(Math.round(p % 1 * 60)).padStart(2, '0')}`; }
      if (startIn && team.wave_start) startIn.value = team.wave_start;
    }

    // race-day dropdown runner names
    $$('#rdLeg option').forEach(o => {
      const n = Number(o.value); const nm = names[legSlot(n)];
      if (nm) { o.dataset.runner = nm; o.textContent = o.textContent.replace(/—.*$/, `— ${nm}`); }
    });

    // planner (overview): recompute with real assignments
    const tb = $('#plantbody');
    if (tb && typeof LEGDATA !== 'undefined') {
      const slots = [];
      for (let s = 1; s <= N; s++) {
        const legs = LEGDATA.filter(l => legSlot(l.n) === s);
        if (!legs.length) { slots.push({s, legs, mi: 0, gain: 0, pts: 0}); continue; }
        slots.push({s, legs,
          mi: legs.reduce((a, l) => a + l.dist, 0),
          gain: legs.reduce((a, l) => a + l.gain, 0),
          pts: legs.reduce((a, l) => a + l.pts, 0)});
      }
      const am = slots.reduce((a, x) => a + x.mi, 0) / N || 1, ag = slots.reduce((a, x) => a + x.gain, 0) / N || 1,
            ap = slots.reduce((a, x) => a + x.pts, 0) / N || 1;
      slots.forEach(x => x.score = x.mi / am + x.gain / ag + x.pts / ap);
      const top = Math.max(...slots.map(x => x.score)) || 1;
      slots.sort((a, b) => b.score - a.score);
      tb.innerHTML = slots.map((x, i) => {
        const idx = Math.round(100 * x.score / top);
        const hardest = x.legs.length ? x.legs.reduce((a, l) => (l.pts > a.pts || (l.pts === a.pts && l.gain > a.gain)) ? l : a) : null;
        const dots = x.legs.map(l => `<span class="dotc" style="background:${l.color}" title="Leg ${l.n} · ${escHtml(l.name)} · ${l.lbl}"></span>`).join('');
        return `<tr><td class="c"><b>${i + 1}</b></td><td class="c"><b>${x.s}</b></td>` +
          `<td class="runner-name"><b>${escHtml(names[x.s] || '—')}</b></td>` +
          `<td>${x.legs.map(l => l.n).join(', ')}</td><td class="r">${x.mi.toFixed(1)}</td>` +
          `<td class="r">${x.gain.toLocaleString()}</td><td class="nowrap">${dots}</td>` +
          `<td><div class="meterwrap"><div class="meter"><div class="fill" style="width:${idx}%"></div></div><span class="mval">${idx}</span></div></td>` +
          (hardest ? `<td>Leg ${hardest.n} · ${escHtml(hardest.name)} (${hardest.lbl} · +${hardest.gain.toLocaleString()} ft)</td>` : '<td>—</td>');
      }).join('');
    }

    // nav: settings link for this team
    const tabs = $('.navtabs');
    if (tabs && !$('#settingsTab')) {
      const a = document.createElement('a');
      a.id = 'settingsTab';
      a.href = (typeof RACE_ID !== 'undefined' && RACE_ID === '65' ? '../' : '') + 'settings.html?team=' + encodeURIComponent(slug);
      a.textContent = 'Team settings';
      tabs.appendChild(a);
    }
    // keep ?team= on internal nav links
    $$('nav.top a[href$="index.html"], nav.top a[href$="overview.html"]').forEach(a => {
      a.href = a.getAttribute('href') + '?team=' + encodeURIComponent(slug);
    });
  }

  (async () => {
    try {
      const season = await activeSeason();
      if (!season) return;
      await applyLegContent(season.id);
      if (slug) await applyTeam(season.id);
    } catch (e) { console.warn('OTO overlay skipped:', e); }
  })();
})();
