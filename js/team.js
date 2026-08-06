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
      const beta = card.querySelector('.beta2') || card.querySelector('.beta');
      if (beta && l.beta) beta.innerHTML = '<span class="src">team beta</span>' + escHtml(l.beta);
      const tagrow = card.querySelector('.tagrow');
      if (tagrow) tagrow.innerHTML = (l.tags || []).map(t => `<span class="chip warn">⚠ ${escHtml(t)}</span>`).join('');
      const surf = card.querySelector('.surfmeta span') || card.querySelector('.surftext');
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
    const paceBySlot = {}; (runners || []).forEach(r => { if (r.pace_min_per_mi) paceBySlot[r.slot] = Number(r.pace_min_per_mi); });
    const N = team.n_runners || 6;
    const defSlot = (n) => ((n - 1) % N) + 1;
    const legSlot = (n) => slotOf[n] || defSlot(n);
    const label = (s) => names[s] ? `${s}-${names[s]}` : `Slot ${s}`;

    // branding
    $$('.brand').forEach(el => el.textContent = team.name);
    const kicker = $('.kicker'); if (kicker) kicker.textContent = `${team.name.toUpperCase()} · RACE GUIDE`;
    document.title = `${team.name} — ${document.title.split('—').pop().trim()}`;

    // feed the shared UI state, then retag every leg element with its real slot
    if (window.GUIDE) {
      GUIDE.N = N;
      GUIDE.names = Object.assign({}, names);
      GUIDE.slotOf = Object.assign({}, slotOf);
      GUIDE.paces = Object.assign({}, paceBySlot);
    }
    $$('.lrow, .lx').forEach(el => {
      const n = Number(el.dataset.n);
      if (!n) return;
      el.dataset.slot = legSlot(n);
    });
    $$('.avslot').forEach(el => {
      const holder = el.closest('[data-n]');
      let sSlot = holder ? legSlot(Number(holder.dataset.n)) : Number(el.dataset.slot);
      el.dataset.slot = sSlot;
      if (window.GUIDE) el.textContent = GUIDE.initials(sSlot);
    });
    $$('.lx .assign').forEach(box => {
      const n = Number(box.closest('.lx').dataset.n);
      const rn = box.querySelector('.runner-name');
      if (rn) { rn.dataset.slot = legSlot(n); rn.textContent = names[legSlot(n)] || 'Slot ' + legSlot(n); }
    });
    $$('.skb').forEach(el => {
      const n = Number((el.getAttribute('href') || '').split('#leg-').pop());
      if (n) el.dataset.slot = legSlot(n);
    });
    $$('#legTableD tbody tr[data-n], #index tbody tr[data-n]').forEach(tr => { tr.dataset.slot = legSlot(Number(tr.dataset.n)); });
    if (window.GUIDE && document.getElementById('chipRow')) GUIDE.renderChips();

    // per-runner piecewise schedule: each leg takes dist × its runner's pace
    // (missing runner paces fall back to the team average)
    const teamPaceNum = Number(team.pace_min_per_mi) || PLAN.pace;
    if (typeof applyPlan === 'function' && typeof LEGDATA !== 'undefined') {
      const start0 = team.wave_start ? team.wave_start.split(':').reduce((h, m) => Number(h) * 60 + Number(m)) : PLAN.start;
      const ms = [0], ts = [0];
      let mm = 0, tt = 0;
      LEGDATA.forEach(l => {
        const pc = paceBySlot[legSlot(l.n)] || teamPaceNum;
        mm += l.dist; tt += l.dist * pc;
        ms.push(mm); ts.push(tt);
      });
      window.OTO_SCHED = {
        start: start0, total: tt,
        timeAtMile(mi) {
          if (mi <= 0) return this.start;
          if (mi >= ms[ms.length - 1]) return this.start + ts[ts.length - 1];
          let i = 1; while (ms[i] < mi) i++;
          return this.start + ts[i - 1] + (mi - ms[i - 1]) / (ms[i] - ms[i - 1]) * (ts[i] - ts[i - 1]);
        },
        mileAtTime(t) {
          const rel = t - this.start;
          if (rel <= 0) return 0;
          if (rel >= ts[ts.length - 1]) return ms[ms.length - 1];
          let i = 1; while (ts[i] < rel) i++;
          return ms[i - 1] + (rel - ts[i - 1]) / (ts[i] - ts[i - 1]) * (ms[i] - ms[i - 1]);
        }
      };
      // team pages: pace is derived from the roster, not editable — hide the ⏱ control
      const paceIn = $('#paceIn'), startIn = $('#startIn');
      if (paceIn && paceIn.closest('.planctl')) paceIn.closest('.planctl').style.display = 'none';
      if (startIn) startIn.value = team.wave_start || '';
      localStorage.removeItem('oto_pace'); localStorage.removeItem('oto_start');
      applyPlan(teamPaceNum, start0);
    }

    // race-day dropdown runner names + per-runner pace defaults
    $$('#rdLeg option').forEach(o => {
      const n = Number(o.value); const nm = names[legSlot(n)];
      if (nm) { o.dataset.runner = nm; o.textContent = o.textContent.replace(/—.*$/, `— ${nm}`); }
    });
    const rdPace = $('#rdPace'), rdLeg = $('#rdLeg');
    if (rdPace && rdLeg) {
      const setP = () => {
        const p = paceBySlot[legSlot(Number(rdLeg.value))] || Number(team.pace_min_per_mi) || PLAN.pace;
        rdPace.value = `${Math.floor(Math.round(p * 60) / 60)}:${String(Math.round(p * 60) % 60).padStart(2, '0')}`;
      };
      rdLeg.addEventListener('change', setP);
      setP();
    }

    // carry ?team= on the header nav
    $$('.hdr-nav a').forEach(a => {
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
