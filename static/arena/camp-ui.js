(function () {
  'use strict';

  const A = window.ArenaApp, C = window.ArenaCampaign, E = A.E;
  const { $, $$, snd, toast } = A;
  const KEY = 'political_arena_camp_v2';
  const P = C.PLAYER;
  const TIER_NAME = { common: 'обычный', uncommon: 'редкий+', rare: 'редкий', epic: 'эпик', legendary: 'легенда' };
  const REASONS = {
    defeat: 'Столица пала — кампания проиграна.',
    time: 'Время вышло.',
    regions: `Ты удерживаешь ${C.WIN_REGIONS} регионов — половину карты.`,
    eliminated: 'Все соперники разгромлены.',
  };

  let scrollMem = 0;
  let G = null, sel = null, busy = false, view = null, diff = 'normal', pick = null, query = '', endWarned = false;
  const mem = {};

  function ls() { try { return window.localStorage; } catch (e) { return null; } }
  function save() {
    const v = JSON.stringify(G);
    try { const s = ls(); if (s) { s.setItem(KEY, v); return; } } catch (e) { }
    mem[KEY] = v;
  }
  function load() {
    try {
      const s = ls(), v = (s && s.getItem(KEY)) || mem[KEY];
      const g = v ? JSON.parse(v) : null;
      return g && g.v === 2 ? g : null;
    } catch (e) { return null; }
  }
  function wipe() { try { const s = ls(); if (s) s.removeItem(KEY); } catch (e) { } delete mem[KEY]; }

  const fd = (g, id) => C.fighterData(g, id);
  const cur = () => view || G;
  const pFaction = () => G.factions[P];
  const money = (n) => `${Math.round(n)}₲`;
  const pct = (x) => `${Math.round(x * 100)}%`;
  const regionName = (i) => G.regions[i].name;

  function modal(html, buttons, opts) {
    opts = opts || {};
    return new Promise(res => {
      const ov = $('#modalCamp'), body = $('#modalCampBody');
      body.className = 'modal modal-camp' + (opts.wide ? ' wide' : '');
      body.innerHTML = html + (buttons && buttons.length
        ? `<div class="modal-actions">${buttons.map(b => `<button class="${b.cls || 'btn-secondary'}" data-id="${b.id}">${b.label}</button>`).join('')}</div>` : '');
      ov.style.display = 'flex';
      const list = body.querySelector('.army-list');
      if (list && opts.keepScroll) list.scrollTop = scrollMem;
      ov.dataset.closable = opts.closable === false ? '' : '1';
      const done = (id) => { const l = body.querySelector('.army-list'); scrollMem = l ? l.scrollTop : 0; ov.style.display = 'none'; res(id); };
      ov._close = () => done('close');
      body.querySelectorAll('[data-id]').forEach(b => b.addEventListener('click', () => { snd('click'); done(b.dataset.id); }));
    });
  }
  function closeModal() { const ov = $('#modalCamp'); if (ov.style.display !== 'none' && ov._close) ov._close(); }

  function statBar(f) {
    return `<div class="cs"><span>HP <b>${f.hp}</b></span><span>ATK <b>${f.atk}</b></span><span>DEF <b>${f.def}</b></span><span>SPD <b>${f.spd}</b></span></div>`;
  }

  function lvlTag(ref) { return ref && ref.lvl ? `<span class="lvl">Ур.${ref.lvl}</span>` : ''; }

  function refreshMenu() {
    const g = load();
    const sub = $('#menuCampSub');
    if (g && !g.over) { sub.textContent = `▶ Продолжить: ход ${g.turn}, регионов ${C.regionsOf(g, P).length}/${C.WIN_REGIONS}`; sub.classList.add('has-save'); }
    else { sub.textContent = 'Новая кампания'; sub.classList.remove('has-save'); }
  }

  function openStart() {
    const g = load();
    const bar = $('#campContinue');
    if (g && !g.over) {
      bar.style.display = '';
      bar.innerHTML = `<div>У тебя есть незаконченная кампания: ход ${g.turn}, регионов ${C.regionsOf(g, P).length}, командир ${fd(g, g.factions[P].leaderId).name}.</div><button class="btn-primary" id="btnCampContinue">▶ ПРОДОЛЖИТЬ</button>`;
      $('#btnCampContinue').addEventListener('click', () => { snd('click'); G = g; openMap(false); });
    } else bar.style.display = 'none';
    renderDiff();
    renderStartGrid();
    $('#btnCampBegin').disabled = !pick;
    A.showScreen('campStart');
  }

  function renderDiff() {
    const row = $('#diffRow');
    row.innerHTML = '';
    Object.entries(C.DIFFS).forEach(([k, d]) => {
      const b = document.createElement('button');
      b.className = 'type-chip' + (k === diff ? ' active' : '');
      b.textContent = d.name;
      b.addEventListener('click', () => { diff = k; renderDiff(); snd('click'); });
      row.appendChild(b);
    });
    $('#diffNote').textContent = { easy: 'Соперники осторожнее и беднее. Для знакомства с игрой.', normal: 'Равные условия: соперники играют так же, как ты.', hard: 'Соперники богаче на 20%, стартуют с деньгами и нападают смелее.' }[diff];
  }

  function renderStartGrid() {
    const grid = $('#campGrid');
    grid.innerHTML = '';
    const q = query.toLowerCase();
    A.FIGHTERS.filter(f => !q || f.name.toLowerCase().includes(q) || f.type.toLowerCase().includes(q)).forEach(f => {
      const card = document.createElement('div');
      card.className = `fighter-card tier-${f.tier}` + (pick && pick.id === f.id ? ' selected' : '');
      card.style.setProperty('--card-gradient', f.gradient);
      card.innerHTML = A.cardHTML(f);
      A.attachImgFallback(card.querySelector('.fc-avatar'), f);
      card.addEventListener('click', () => {
        pick = f; snd('select');
        $('#campPicked').innerHTML = `<img class="slot-avatar" src="${A.avatarUrl(f)}" alt=""><span>Командир: <b>${f.name}</b> · ${f.type}</span>`;
        $('#btnCampBegin').disabled = false;
        renderStartGrid();
      });
      grid.appendChild(card);
    });
  }

  function begin() {
    if (!pick) return;
    G = C.newCampaign(pick.id, undefined, diff);
    save();
    snd('fightStart');
    openMap(true);
  }

  function openMap(intro) {
    sel = null; view = null; busy = false; endWarned = false;
    A.showScreen('map');
    renderAll();
    if (intro) showHelp();
    else turnBanner();
  }

  function renderAll() { renderHud(); renderMap(); renderLegend(); renderPanel(); }

  let shownGold = null;
  function tween(el, from, to, fmt) {
    if (from == null || from === to) { el.textContent = fmt(to); return; }
    const t0 = performance.now(), dur = 600;
    const step = (t) => {
      const k = Math.min(1, (t - t0) / dur);
      el.textContent = fmt(Math.round(from + (to - from) * k));
      if (k < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }

  function renderHud() {
    const st = C.status(G), f = pFaction();
    $('#hudTurn').textContent = `${Math.min(st.turn, st.maxTurns)}/${st.maxTurns}`;
    tween($('#hudGold'), shownGold, f.gold, money);
    shownGold = f.gold;
    const net = st.income - st.upkeep;
    $('#hudNet').textContent = `${net >= 0 ? '+' : '−'}${Math.abs(net)}/ход`;
    $('#hudNet').className = net >= 0 ? 'pos' : 'neg';
    $('#hudRegions').textContent = `${st.regions}/${C.WIN_REGIONS}`;
    $('#hudArmy').textContent = `${f.fighters.length}/${C.ARMY_MAX}`;
    const rivals = ['a', 'b', 'c'].filter(k => !G.factions[k].eliminated).length;
    $('#campGoal').innerHTML = `<b>Цель:</b> удерживай ${C.WIN_REGIONS} регионов из ${C.N} или разгроми всех соперников, захватив их столицы (${3 - rivals}/3). <b>Падёт твоя столица — поражение.</b>`;
  }

  function terrainBg(t) { return `terrain-${t}`; }

  function threatened(g, r) {
    if (r.owner !== P) return false;
    return C.neighbors(r.id).some(n => {
      const o = g.regions[n];
      return o.owner && o.owner !== P && o.garrison;
    });
  }

  function tileHTML(r, g) {
    const owner = r.owner ? g.factions[r.owner] : null;
    const T = C.TERRAIN[r.terrain];
    const isCap = owner && owner.capital === r.id;
    let unit;
    if (r.garrison) {
      const f = fd(g, r.garrison), ref = C.refOf(g, r.owner, r.garrison);
      unit = `<img class="t-img${ref && ref.wounded ? ' hurt' : ''}" src="${A.avatarUrl(f)}" alt="">`;
    } else if (!r.owner) unit = `<img class="t-img neutral" src="${A.avatarUrl(C.militia(r))}" alt="">`;
    else unit = '<span class="t-empty">пусто</span>';
    const stars = !r.owner ? `<span class="t-pow">${'★'.repeat(r.power < 1 ? 1 : r.power < 1.3 ? 2 : 3)}</span>` : '';
    const hurt = r.garrison && r.owner && (C.refOf(g, r.owner, r.garrison) || {}).wounded ? '<span class="t-wound">🩹</span>' : '';
    return `
      <span class="t-terrain">${T.icon}</span>
      ${isCap ? '<span class="t-cap">👑</span>' : ''}
      ${unit}${stars}${hurt}
      ${r.building ? `<span class="t-bld">${C.BUILDINGS[r.building].icon}</span>` : ''}
      <span class="t-name">${r.name}</span>`;
  }

  function renderMap() {
    const g = cur(), map = $('#campMap');
    const fresh = !map.children.length;
    map.innerHTML = '';
    g.regions.forEach(r => {
      const el = document.createElement('div');
      const owner = r.owner ? g.factions[r.owner] : null;
      el.className = `tile ${terrainBg(r.terrain)} ${r.owner ? 'owner-' + r.owner : 'neutral-land'}` +
        (r.id === sel ? ' selected' : '') + (threatened(g, r) ? ' threat' : '') + (fresh ? ' enter' : '');
      el.dataset.i = r.id;
      el.style.setProperty('--oc', owner ? owner.color : '#4a5070');
      if (fresh) el.style.animationDelay = (r.id * 18) + 'ms';
      el.innerHTML = tileHTML(r, g);
      map.appendChild(el);
    });
  }

  function renderLegend() {
    const g = cur();
    $('#campLegend').innerHTML = ['p', 'a', 'b', 'c'].map(k => {
      const f = g.factions[k], n = C.regionsOf(g, k).length;
      return `<span class="lg ${f.eliminated ? 'dead' : ''}" style="--oc:${f.color}"><i></i>${k === P ? 'Ты' : f.name.split(' ').slice(-1)[0]} <b>${f.eliminated ? '☠' : n}</b></span>`;
    }).join('') + `<span class="lg" style="--oc:#4a5070"><i></i>Ничьи <b>${C.regionsOf(g, null).length}</b></span>`;
  }

  function hint() {
    const f = pFaction();
    const bench = f.fighters.filter(r => C.locationOf(G, P, r.id) < 0 && !r.acted && !r.wounded);
    const neutralNear = G.regions.some(r => r.owner === null && C.neighbors(r.id).some(n => G.regions[n].owner === P));
    if (!G.regions[f.capital].garrison) return 'Столица без защитника: поставь туда бойца, иначе её займут без боя.';
    if (bench.length && neutralNear) return `${bench.length === 1 ? 'Боец ждёт' : 'Бойцы ждут'} в резерве: выбери ничейный регион рядом с твоими землями и атакуй.`;
    const cheapest = C.availableMercs(G)[0];
    if (cheapest && f.gold >= C.priceOf(cheapest) && f.fighters.length < C.ARMY_MAX) return 'Хватает денег нанять бойца: кнопка «Найм».';
    return 'Выбери регион на карте или заверши ход.';
  }

  function renderPanel() {
    const p = $('#campPanel');
    if (sel == null) { p.innerHTML = `<div class="pn-tip">💡 ${hint()}</div>`; return; }
    const r = G.regions[sel];
    p.innerHTML = r.owner === P ? ownPanel(r) : foePanel(r);
    p.classList.remove('pop'); void p.offsetWidth; p.classList.add('pop');
  }

  function regionHead(r) {
    const o = r.owner ? G.factions[r.owner] : null, T = C.TERRAIN[r.terrain];
    const cap = o && o.capital === r.id;
    return `<div class="pn-head" style="--oc:${o ? o.color : '#4a5070'}">
      <div class="pn-title">${T.icon} ${r.name}${cap ? ' 👑' : ''}</div>
      <div class="pn-sub">${T.name} · доход ${C.regionIncome(r)}₲ · ${o ? (r.owner === P ? 'твой регион' : 'земля: ' + o.name) : 'ничья земля'}${r.building ? ` · ${C.BUILDINGS[r.building].icon} ${C.BUILDINGS[r.building].name}` : ''}</div>
    </div>`;
  }

  function fighterRow(f, ref, extra) {
    return `<div class="pn-fighter"><img class="pn-img${ref && ref.wounded ? ' hurt' : ''}" src="${A.avatarUrl(f)}" alt="">
      <div class="pn-fi"><div class="pn-fname">${f.name} ${lvlTag(ref)} ${ref && ref.commander ? '<span class="lvl cmd">командир</span>' : ''}</div>
      ${statBar(f)}${extra || ''}</div></div>`;
  }

  function ownPanel(r) {
    const f = pFaction();
    let html = regionHead(r);
    if (r.garrison) {
      const ref = C.refOf(G, P, r.garrison), base = C.combatant(G, ref, r, true);
      const wound = ref.wounded ? `<div class="pn-warn">Ранен: ещё ${ref.wounded} ход. без полной силы</div>` : '';
      html += fighterRow(base.fighter, ref, wound + `<div class="pn-notes">${base.notes.join(' · ')}</div>`);
      const cost = ref.lvl >= C.MAX_LVL ? null : C.trainCost(ref);
      html += `<div class="pn-actions">
        <button class="btn-mini" data-act="train" ${cost == null || f.gold < cost ? 'disabled' : ''}>⬆ Тренировать ${cost == null ? '(макс.)' : money(cost)}</button>
        <button class="btn-mini" data-act="swap">🔁 Заменить</button>
        <button class="btn-mini" data-act="unassign" ${ref.acted ? 'disabled' : ''}>📤 В резерв</button></div>`;
    } else {
      html += `<div class="pn-warn">Гарнизона нет: соседи займут регион без боя.</div>
        <div class="pn-actions"><button class="btn-mini primary" data-act="assign">👤 Назначить бойца</button></div>`;
    }
    if (!r.building) {
      html += `<div class="pn-sub2">Построить:</div><div class="pn-actions">` +
        Object.entries(C.BUILDINGS).map(([k, b]) => `<button class="btn-mini" data-act="build" data-kind="${k}" ${f.gold < b.cost ? 'disabled' : ''} title="${b.desc}">${b.icon} ${b.name} ${money(b.cost)}</button>`).join('') +
        `</div><div class="pn-notes">${Object.values(C.BUILDINGS).map(b => `${b.icon} ${b.name}: ${b.desc}`).join(' · ')}</div>`;
    }
    return html;
  }

  function attackers(r) {
    const f = pFaction(), out = [];
    f.fighters.forEach(ref => {
      const pb = C.prepareBattle(G, P, ref.id, r.id);
      if (!pb.error) out.push({ ref, pb });
    });
    return out.sort((a, b) => b.pb.odds - a.pb.odds);
  }

  function foePanel(r) {
    const f = pFaction();
    let html = regionHead(r);
    const list = attackers(r), d = C.defenderOf(G, r);
    if (d) {
      const df = list.length ? list[0].pb.defender : C.combatant(G, d.ref, r, true).fighter;
      const dref = d.neutral ? null : d.ref;
      const notes = list.length ? (list[0].pb.notesDefender || []).join(' · ') : '';
      html += `<div class="pn-sub2">Защитник:</div>` + fighterRow(df, dref, notes ? `<div class="pn-notes">${notes}</div>` : '');
    } else html += '<div class="pn-tip ok">Регион пуст: можно занять без боя.</div>';

    if (list.length) {
      html += `<div class="pn-sub2">Кем атаковать:</div><div class="pn-attackers">` + list.map(({ ref, pb }) => {
        const loc = C.locationOf(G, P, ref.id);
        const where = loc < 0 ? 'резерв' : `из «${regionName(loc)}»`;
        const oc = pb.undefended ? 'free' : pb.odds >= 0.6 ? 'good' : pb.odds >= 0.45 ? 'mid' : 'bad';
        return `<button class="atk ${oc}" data-act="attack" data-id="${ref.id}"><img src="${A.avatarUrl(fd(G, ref.id))}" alt="">
          <span class="atk-n">${fd(G, ref.id).name}<small>${where}${ref.lvl ? ' · ур.' + ref.lvl : ''}</small></span>
          <span class="atk-p">${pb.undefended ? 'без боя' : pct(pb.odds)}</span></button>`;
      }).join('') + '</div>';
    } else {
      html += `<div class="pn-tip">${whyNoAttackers(r)}</div>`;
    }
    if (r.owner === null && C.neighbors(r.id).some(n => G.regions[n].owner === P)) {
      const price = C.buyPrice(G, r.id);
      html += `<div class="pn-actions"><button class="btn-mini" data-act="buy" ${f.gold < price ? 'disabled' : ''}>💰 Выкупить без боя ${money(price)}</button></div>`;
    }
    return html;
  }

  function whyNoAttackers(r) {
    const f = pFaction();
    const nearMine = C.neighbors(r.id).some(n => G.regions[n].owner === P);
    if (!nearMine) return 'Регион далеко: атаковать можно только то, что граничит с твоими землями.';
    if (!f.fighters.some(x => !x.acted && !x.wounded)) return 'Все бойцы уже действовали или ранены. Заверши ход.';
    return 'Нет подходящего бойца: гарнизон бьёт только соседние регионы, а резерв пуст. Найми бойца или освободи его из гарнизона.';
  }

  function onPanelClick(e) {
    const b = e.target.closest('[data-act]');
    if (!b || b.disabled || busy || sel == null) return;
    const r = G.regions[sel], act = b.dataset.act;
    if (act === 'train') done(C.train(G, P, r.garrison), 'Боец стал сильнее');
    else if (act === 'unassign') done(C.unassign(G, P, r.id), 'Боец в резерве: им можно атаковать любой приграничный регион');
    else if (act === 'build') done(C.build(G, P, r.id, b.dataset.kind), 'Построено');
    else if (act === 'assign') pickGarrison(r);
    else if (act === 'swap') pickGarrison(r);
    else if (act === 'attack') previewBattle(b.dataset.id, r.id);
    else if (act === 'buy') {
      const rep = C.buyRegion(G, P, r.id);
      if (rep.ok) { sfxCoin(); save(); renderAll(); flashTile(r.id, 'captured'); checkEnd(); } else { toast(rep.error); snd('error'); }
    }
  }

  function sfxCoin() { snd('coin'); }

  function done(res, okMsg) {
    if (res.ok) { snd('select'); if (okMsg) toast(okMsg); save(); renderAll(); }
    else { toast(res.error); snd('error'); }
  }

  async function pickGarrison(r) {
    const f = pFaction();
    const rows = f.fighters.filter(x => x.id !== r.garrison).map(ref => {
      const loc = C.locationOf(G, P, ref.id);
      const blocked = loc >= 0 && ref.acted;
      return `<button class="pick-row" data-id="${ref.id}" ${blocked ? 'disabled' : ''}><img src="${A.avatarUrl(fd(G, ref.id))}" alt="">
        <span><b>${fd(G, ref.id).name}</b> ${lvlTag(ref)}<small>${loc < 0 ? 'в резерве' : `в «${regionName(loc)}»${ref.acted ? ' · уже действовал' : ''}`}${ref.wounded ? ' · ранен' : ''}</small></span></button>`;
    }).join('');
    const id = await modal(`<h2>👤 КОГО ПОСТАВИТЬ В «${r.name.toUpperCase()}»</h2><div class="pick-list">${rows || '<p class="muted">Других бойцов нет. Найми кого-нибудь.</p>'}</div>`,
      [{ id: 'close', label: 'Отмена' }]);
    if (id === 'close') return;
    if (r.garrison) {
      const un = C.unassign(G, P, r.id);
      if (!un.ok) { toast(un.error); snd('error'); return; }
    }
    done(C.assign(G, P, id, r.id), 'Гарнизон назначен');
  }

  function fightCard(f, ref, tag, notes) {
    return `<div class="bp-card"><div class="bp-tag">${tag}</div><img src="${A.avatarUrl(f)}" alt=""><div class="bp-name">${f.name}</div>${statBar(f)}
      ${notes && notes.length ? `<div class="bp-notes">${notes.map(n => `<span>${n}</span>`).join('')}</div>` : ''}</div>`;
  }

  async function previewBattle(fid, toIdx) {
    const pb = C.prepareBattle(G, P, fid, toIdx);
    if (pb.error) { toast(pb.error); snd('error'); return; }
    const r = G.regions[toIdx];
    if (pb.undefended) {
      const id = await modal(`<h2>🏴 «${r.name.toUpperCase()}» ПУСТ</h2><p>${fd(G, fid).name} занимает регион без боя.</p>`,
        [{ id: 'go', label: 'ЗАНЯТЬ', cls: 'btn-primary' }, { id: 'close', label: 'Отмена' }]);
      if (id === 'go') afterBattle(C.resolveBattle(G, P, fid, toIdx, true));
      return;
    }
    const odds = pb.odds, dref = C.defenderOf(G, r);
    const html = `<h2>⚔️ БОЙ ЗА «${r.name.toUpperCase()}»</h2>
      <div class="bp-row">${fightCard(pb.attacker, C.refOf(G, P, fid), 'ТЫ', pb.notesAttacker)}<div class="bp-vs">VS</div>${fightCard(pb.defender, dref && dref.ref, 'ЗАЩИТНИК', pb.notesDefender)}</div>
      <div class="bp-odds"><div class="bp-bar"><i style="width:${pct(odds)}"></i></div><span>Шанс на победу ≈ ${pct(odds)} · в ручном бою ты читаешь подсказку и выбираешь удары сам, автобой считает за тебя</span></div>
      <div class="pn-notes">Победа: регион и добыча ₲. Поражение: боец ранен на ${C.WOUND_TURNS} хода и ослаблен.</div>`;
    const id = await modal(html, [
      { id: 'manual', label: '⚔️ В БОЙ (САМ)', cls: 'btn-primary' },
      { id: 'auto', label: '🎲 АВТОБОЙ' },
      { id: 'close', label: 'Отмена' },
    ], { wide: true });
    if (id === 'manual') manualBattle(pb, fid, toIdx);
    else if (id === 'auto') autoBattle(fid, toIdx);
  }

  function manualBattle(pb, fid, toIdx) {
    const r = G.regions[toIdx];
    A.runFight({
      fa: pb.attacker, fb: pb.defender, side: 'a', terrain: r.terrain, title: `Кампания · бой за «${r.name}»`,
      endText: (won) => won ? `«${r.name}» переходит к тебе` : `Боец ранен и выбывает на ${C.WOUND_TURNS} хода`,
      onDone: (res) => afterBattle(C.resolveBattle(G, P, fid, toIdx, res.user_won)),
    });
  }

  function autoBattle(fid, toIdx) {
    const r = G.regions[toIdx];
    const rng = E.createRng((Date.now() ^ (G.turn * 7919)) >>> 0);
    const rep = C.autoBattle(G, P, fid, toIdx, rng);
    if (!rep) return;
    if (!rep.replay) { afterBattle(rep); return; }
    A.playReplay(rep.replay, {
      side: 'a', terrain: r.terrain, title: `Автобой · «${r.name}»`, won: rep.captured, speed: 2,
      onDone: () => afterBattle(rep),
    });
  }

  function afterBattle(rep) {
    save();
    A.showScreen('map');
    sel = rep.captured ? rep.to : sel;
    renderAll();
    if (rep.captured) { snd('coin'); flashTile(rep.to, 'captured'); lootFloat(rep.to, `+${rep.loot}₲`); if (rep.capital) toast('Столица врага пала! Фракция разгромлена.'); }
    else toast(rep.text);
    checkEnd();
  }

  function tileEl(i) { return $(`#campMap .tile[data-i="${i}"]`); }
  function flashTile(i, cls) {
    const t = tileEl(i);
    if (!t) return;
    t.classList.remove(cls); void t.offsetWidth; t.classList.add(cls);
    setTimeout(() => t.classList.remove(cls), 1400);
  }
  function lootFloat(i, text) {
    const t = tileEl(i);
    if (!t) return;
    const el = document.createElement('div');
    el.className = 'loot-float'; el.textContent = text;
    t.appendChild(el);
    setTimeout(() => el.remove(), 1500);
  }

  function arrow(from, to, color) {
    const svg = $('#campArrows'), map = $('#campMap');
    if (from == null || from < 0 || !tileEl(from) || !tileEl(to)) { svg.innerHTML = ''; return; }
    const m = map.getBoundingClientRect(), a = tileEl(from).getBoundingClientRect(), b = tileEl(to).getBoundingClientRect();
    const x1 = a.left - m.left + a.width / 2, y1 = a.top - m.top + a.height / 2;
    const x2 = b.left - m.left + b.width / 2, y2 = b.top - m.top + b.height / 2;
    svg.setAttribute('viewBox', `0 0 ${m.width || 1} ${m.height || 1}`);
    svg.innerHTML = `<defs><marker id="ah" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="${color}"/></marker></defs>
      <line class="arrow-line" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${color}" stroke-width="4" marker-end="url(#ah)"/>`;
  }

  function applyToView(e) {
    const v = view;
    if (e.bought) { v.regions[e.region].owner = e.attacker; return; }
    if (!e.captured) return;
    const to = v.regions[e.region];
    const from = Object.values(v.regions).find(r => r.owner === e.attacker && r.garrison === e.fighterId);
    if (from) from.garrison = null;
    to.owner = e.attacker; to.garrison = e.fighterId;
    if (e.capital) {
      const lost = e.defender;
      v.regions.forEach(r => { if (r.owner === lost) { r.owner = null; r.garrison = null; r.building = null; } });
    }
  }

  async function playEvent(e) {
    const color = G.factions[e.attacker].color;
    const tk = $('#campTicker');
    tk.textContent = e.text;
    tk.style.setProperty('--oc', color);
    tk.classList.add('show');
    if (e.region != null) {
      arrow(e.from, e.region, color);
      if (tileEl(e.region)) tileEl(e.region).classList.add('target-flash');
    }
    await A.sleep(e.vsPlayer ? 700 : 520);
    applyToView(e);
    renderMap();
    $('#campArrows').innerHTML = '';
    if (e.captured || e.bought) { flashTile(e.region, 'captured'); snd(e.vsPlayer ? 'defeat' : 'click'); }
    renderLegend();
    if (e.vsPlayer && e.replay) {
      const id = await modal(`<h2>⚠️ НАПАДЕНИЕ</h2><p>${e.text}</p><p class="muted">${e.captured ? 'Защитник проиграл — регион потерян.' : 'Твой защитник отбился!'}</p>`,
        [{ id: 'watch', label: '▶ СМОТРЕТЬ БОЙ', cls: 'btn-primary' }, { id: 'skip', label: 'Дальше' }], { closable: false });
      if (id === 'watch') {
        await new Promise(res => A.playReplay(e.replay, {
          side: 'b', terrain: G.regions[e.region].terrain, title: `Оборона «${regionName(e.region)}»`, won: !e.captured,
          button: 'НА КАРТУ', onDone: res,
        }));
        A.showScreen('map');
        renderAll();
      }
    } else await A.sleep(220);
    tk.classList.remove('show');
  }

  async function endTurn() {
    if (busy || !G || G.over) return;
    if (checkEnd()) return;
    const cap = G.regions[pFaction().capital];
    if (!cap.garrison && !endWarned) { endWarned = true; toast('Столица без защитника! Нажми ещё раз, чтобы всё равно завершить ход.'); snd('error'); return; }
    endWarned = false;
    busy = true;
    $('#btnEndTurn').disabled = true;
    const goldBefore = pFaction().gold;
    view = JSON.parse(JSON.stringify(G));
    const res = C.endTurn(G);
    save();
    sel = null;
    renderMap(); renderLegend(); renderPanel();
    $('#campWait').classList.add('show');
    await A.sleep(450);
    for (const e of res.events) if (typeof e === 'object' && e.text) await playEvent(e);
    $('#campWait').classList.remove('show');
    view = null;
    shownGold = goldBefore;
    renderAll();
    busy = false;
    $('#btnEndTurn').disabled = false;
    if (checkEnd()) return;
    await turnReport(res);
    turnBanner();
  }

  async function turnReport(res) {
    const lines = res.events.filter(e => typeof e === 'string' && e.startsWith(pFaction().name));
    const events = res.events.filter(e => typeof e === 'object' && e.text);
    const mine = events.filter(e => e.vsPlayer);
    const others = events.filter(e => !e.vsPlayer && (e.captured || e.bought)).slice(0, 6);
    const inc = res.income || { income: 0, upkeep: 0 };
    const html = `<h2>ХОД ${G.turn}</h2>
      <div class="rep-money"><span>Доход <b class="pos">+${inc.income}₲</b></span><span>Содержание <b class="neg">−${inc.upkeep}₲</b></span><span>Казна <b>${pFaction().gold}₲</b></span></div>
      ${mine.length ? `<div class="rep-h">Нападения на тебя</div>${mine.map(e => `<div class="rep-line ${e.captured ? 'bad' : 'good'}">${e.captured ? '✗' : '✓'} ${e.text}</div>`).join('')}` : '<div class="rep-line good">На тебя не нападали.</div>'}
      ${others.length ? `<div class="rep-h">Что делали соперники</div>${others.map(e => `<div class="rep-line">• ${e.text}</div>`).join('')}` : ''}
      ${lines.length ? `<div class="rep-h">Казна</div>${lines.map(l => `<div class="rep-line bad">${l}</div>`).join('')}` : ''}`;
    await modal(html, [{ id: 'ok', label: 'ПРОДОЛЖИТЬ', cls: 'btn-primary' }]);
  }

  function turnBanner() {
    const b = $('#campBanner');
    b.textContent = `ХОД ${G.turn}`;
    b.classList.remove('show'); void b.offsetWidth; b.classList.add('show');
    setTimeout(() => b.classList.remove('show'), 1400);
  }

  function checkEnd() {
    const over = C.checkEnd(G);
    if (!over) return false;
    save();
    showEnd(over);
    return true;
  }

  async function showEnd(over) {
    const won = over.winner === P;
    const st = C.status(G);
    let reward = 0;
    if (won) { reward = over.reason === 'time' ? 120 : 250; A.S.grant(reward); A.refreshWallet(); }
    snd(won ? 'victory' : 'defeat');
    const html = `<div class="end-big ${won ? 'win' : 'lose'}">${won ? '🏆 ПОБЕДА' : '💀 ПОРАЖЕНИЕ'}</div>
      <p>${REASONS[over.reason] || ''}${over.reason === 'time' && !won ? ' Соперник удерживает больше регионов.' : ''}</p>
      <div class="rep-money"><span>Ходов <b>${Math.min(G.turn, C.MAX_TURNS)}</b></span><span>Регионов <b>${st.regions}</b></span><span>Армия <b>${pFaction().fighters.length}</b></span></div>
      ${won ? `<p class="pos">+${reward}₲ в кошелёк Арены</p>` : ''}`;
    const id = await modal(html, [{ id: 'new', label: 'НОВАЯ КАМПАНИЯ', cls: 'btn-primary' }, { id: 'menu', label: 'В меню' }], { closable: false });
    wipe();
    G = null;
    if (id === 'new') { pick = null; $('#campPicked').innerHTML = ''; openStart(); }
    else { A.showScreen('menu'); refreshMenu(); }
  }

  async function showArmy() {
    scrollMem = 0;
    for (;;) {
      const f = pFaction();
      const rows = f.fighters.map(ref => {
        const loc = C.locationOf(G, P, ref.id), d = fd(G, ref.id);
        const cost = ref.lvl >= C.MAX_LVL ? null : C.trainCost(ref);
        return `<div class="army-row"><img class="${ref.wounded ? 'hurt' : ''}" src="${A.avatarUrl(d)}" alt="">
          <div class="army-i"><b>${d.name}</b> ${lvlTag(ref)} ${ref.commander ? '<span class="lvl cmd">командир</span>' : ''}
          <small>${loc < 0 ? 'в резерве' : `гарнизон «${regionName(loc)}»`}${ref.wounded ? ` · ранен (${ref.wounded})` : ''}${ref.acted ? ' · действовал' : ''} · содержание ${ref.commander ? 0 : C.upkeepOf(d)}₲</small></div>
          <div class="army-btns">
            <button class="btn-mini" data-id="train:${ref.id}" ${cost == null || f.gold < cost ? 'disabled' : ''}>⬆ ${cost == null ? 'макс.' : money(cost)}</button>
            ${ref.commander ? '' : `<button class="btn-mini danger" data-id="fire:${ref.id}">✕</button>`}
          </div></div>`;
      }).join('');
      const id = await modal(`<h2>👥 АРМИЯ ${f.fighters.length}/${C.ARMY_MAX}</h2><div class="rep-money"><span>Казна <b>${money(f.gold)}</b></span><span>Доход <b class="pos">+${C.income(G, P)}</b></span><span>Содержание <b class="neg">−${C.upkeep(G, P)}</b></span></div><div class="army-list">${rows}</div>
        <p class="muted">Резерв атакует любой приграничный регион. Гарнизон держит регион и бьёт только соседей. Расформировать бойца можно только если он не командир.</p>`,
        [{ id: 'close', label: 'Закрыть' }], { wide: true, keepScroll: true });
      if (id === 'close') break;
      const [act, bid] = id.split(':');
      if (act === 'train') { const r = C.train(G, P, bid); if (r.ok) { snd('select'); save(); } else toast(r.error); }
      if (act === 'fire') { C.dismiss(G, P, bid); snd('click'); save(); }
    }
    renderAll();
  }

  async function showMercs() {
    scrollMem = 0;
    for (;;) {
      const f = pFaction(), list = C.availableMercs(G);
      const rows = list.map(m => {
        const price = C.priceOf(m), can = f.gold >= price && f.fighters.length < C.ARMY_MAX;
        return `<div class="army-row tier-${m.tier}"><img src="${A.avatarUrl(m)}" alt="">
          <div class="army-i"><b>${m.name}</b> <span class="lvl">${TIER_NAME[m.tier] || m.tier}</span><small>${m.type} · ${statText(m)} · содержание ${C.upkeepOf(m)}₲/ход</small></div>
          <div class="army-btns"><button class="btn-mini ${can ? 'primary' : ''}" data-id="hire:${m.id}" ${can ? '' : 'disabled'}>${money(price)}</button></div></div>`;
      }).join('');
      const id = await modal(`<h2>🛒 НАЁМНИКИ</h2><div class="rep-money"><span>Казна <b>${money(f.gold)}</b></span><span>Армия <b>${f.fighters.length}/${C.ARMY_MAX}</b></span></div>
        <div class="army-list">${rows || '<p class="muted">Свободных бойцов нет.</p>'}</div>
        <p class="muted">Наёмник получает жалованье каждый ход. Если казна опустеет, самый дешёвый уйдёт сам.</p>`, [{ id: 'close', label: 'Закрыть' }], { wide: true, keepScroll: true });
      if (id === 'close') break;
      const [, mid] = id.split(':');
      const r = C.recruit(G, P, mid);
      if (r.ok) { snd('coin'); save(); toast(`${fd(G, mid).name} в твоей армии. Поставь его в регион или атакуй из резерва.`); renderHud(); } else { toast(r.error); snd('error'); }
    }
    renderAll();
  }

  const statText = (f) => `HP ${f.hp} · ATK ${f.atk} · DEF ${f.def}`;

  async function showLog() {
    const lines = G.log.length ? G.log.map(l => `<div class="rep-line">${l}</div>`).join('') : '<p class="muted">Пока ничего не произошло.</p>';
    await modal(`<h2>📜 ЖУРНАЛ</h2><div class="army-list">${lines}</div>`, [{ id: 'close', label: 'Закрыть' }], { wide: true });
  }

  async function showHelp() {
    const html = `<h2>КАК ИГРАТЬ</h2><div class="help">
      <p><b>Цель.</b> Удерживай ${C.WIN_REGIONS} регионов из ${C.N} или захвати столицы всех трёх соперников. Падёт твоя столица (👑) — поражение.</p>
      <p><b>Ход.</b> Нажми на регион. Свой: поставь бойца, построй форт, рынок или базу, потренируй. Чужой или ничей: выбери, кем атаковать. Потом «Завершить ход»: соперники сходят и ты получишь доход.</p>
      <p><b>Бой.</b> 5 раундов. Перед каждым ударом соперник «намекает» на свой ход (верно в 60% случаев). Быстрый бьёт спец, спец бьёт тяжёлый, тяжёлый бьёт быстрый. Ульта доступна с 3-го раунда.</p>
      <p><b>Армия.</b> Ты командуешь одним командиром, но можно нанимать бойцов (кнопка «Найм»). Боец в резерве бьёт любой приграничный регион, гарнизон держит землю и бьёт соседей. Каждый боец действует раз в ход.</p>
      <p><b>Деньги.</b> Доход идёт с регионов. Наёмникам платишь жалованье каждый ход. Победа в бою даёт добычу, проигравший ранен на ${C.WOUND_TURNS} хода.</p>
      <p><b>Совет.</b> Не оставляй столицу пустой и не бросайся на сильного защитника: шанс виден до боя.</p></div>`;
    const id = await modal(html, [{ id: 'ok', label: 'ПОНЯТНО', cls: 'btn-primary' }, ...(G && !G.over ? [{ id: 'restart', label: 'Начать заново' }] : [])], { wide: true });
    if (id === 'restart') {
      const sure = await modal('<h2>Начать заново?</h2><p>Текущая кампания будет потеряна.</p>', [{ id: 'yes', label: 'Да, заново', cls: 'btn-primary' }, { id: 'no', label: 'Отмена' }]);
      if (sure === 'yes') { wipe(); G = null; pick = null; $('#campPicked').innerHTML = ''; openStart(); }
    }
  }

  function bind() {
    $('#menuCamp').addEventListener('click', () => { snd('click'); openStart(); });
    $('#btnCampBegin').addEventListener('click', begin);
    $('#btnCampBack').addEventListener('click', () => { snd('back'); A.showScreen('menu'); refreshMenu(); });
    let t = null;
    $('#campSearch').addEventListener('input', (e) => { clearTimeout(t); t = setTimeout(() => { query = e.target.value.trim(); renderStartGrid(); }, 120); });
    $('#campMap').addEventListener('click', (e) => {
      const tile = e.target.closest('.tile');
      if (!tile || busy) return;
      sel = sel === +tile.dataset.i ? null : +tile.dataset.i;
      snd('select');
      renderMap();
      renderPanel();
    });
    $('#campPanel').addEventListener('click', onPanelClick);
    $('#btnEndTurn').addEventListener('click', endTurn);
    $('#btnArmy').addEventListener('click', () => { if (!busy) { snd('click'); showArmy(); } });
    $('#btnMercs').addEventListener('click', () => { if (!busy) { snd('click'); showMercs(); } });
    $('#btnLog').addEventListener('click', () => { if (!busy) { snd('click'); showLog(); } });
    $('#btnHelp').addEventListener('click', () => { if (!busy) { snd('click'); showHelp(); } });
    $('#modalCamp').addEventListener('click', (e) => { const ov = $('#modalCamp'); if (e.target === ov && ov.dataset.closable) closeModal(); });
  }

  function init() { bind(); refreshMenu(); }

  window.ArenaCamp = {
    init, refreshMenu, openStart,
    get state() { return G; },
    debug: { select: (i) => { sel = i; renderMap(); renderPanel(); }, endTurn, previewBattle, showArmy, showMercs, begin, pickLeader: (f) => { pick = f; }, setDiff: (d) => { diff = d; }, save, load },
  };
})();
