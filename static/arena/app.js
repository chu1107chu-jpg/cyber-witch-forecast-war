/* ═══════════════════════════════════════════════════════════════
   POLITICAL ARENA — интерфейс. Вся логика (бой, кошелёк) — в браузере:
   engine.js (бой), store.js (кошелёк/прогресс), fighters.js (данные).
   ═══════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  const E = window.ArenaEngine;
  const S = window.ArenaStore.store;
  const FX = window.ArenaFX;
  const FIGHTERS = window.ARENA_FIGHTERS || [];
  const BY_ID = Object.fromEntries(FIGHTERS.map(f => [f.id, f]));
  const BASE = window.ARENA_BASE || '';           // в iframe Streamlit подставляется абсолютный путь к картинкам

  const $ = (s) => document.querySelector(s);
  const $$ = (s) => Array.from(document.querySelectorAll(s));
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));
  const snd = (name) => { try { if (typeof sfx !== 'undefined' && sfx[name]) sfx[name](); } catch (e) { /* звук не критичен */ } };
  const shortName = (n) => n.split(' ').slice(-1)[0];
  // картинки: встроенные (data:) если страница собрана для Streamlit, иначе файлы рядом
  const avatarUrl = (f) => (f.avatar && f.avatar.startsWith('data:')) ? f.avatar : (window.ARENA_IMG && window.ARENA_IMG[f.id]) || BASE + f.avatar;

  const TYPE_ICON = { light: '⚡', heavy: '🔨', special: '✨', ultimate: '💀' };
  const TYPE_NAME = { light: 'быстрый', heavy: 'тяжёлый', special: 'спец', ultimate: 'УЛЬТА' };

  // ── Состояние ────────────────────────────────────────────────
  let selectedA = null, selectedB = null;
  let betSide = null;            // 'a' | 'b' — за кого играем
  let fight = null, busy = false, ctx = null;
  let currentBet = 0, currentMult = 0, currentAmountUI = 10;
  let query = '', typeFilter = 'all';

  const screens = {
    menu: $('#screenMenu'), select: $('#screenSelect'), bet: $('#screenBet'), fight: $('#screenFight'),
    result: $('#screenResult'), spin: $('#screenSpin'), campStart: $('#screenCampStart'), map: $('#screenMap'),
  };
  function showScreen(name) {
    Object.values(screens).forEach(s => s && s.classList.remove('active'));
    screens[name].classList.add('active');
    $('#btnMenu').style.display = name === 'menu' ? 'none' : '';
    window.scrollTo(0, 0);
  }

  // ── Уведомления (вместо alert: в iframe модальные окна могут быть запрещены) ──
  function toast(msg) {
    const t = document.createElement('div');
    t.className = 'toast'; t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(() => t.classList.add('show'), 10);
    setTimeout(() => { t.classList.remove('show'); setTimeout(() => t.remove(), 300); }, 2800);
  }

  // ── Кошелёк в шапке ─────────────────────────────────────────
  function refreshWallet() {
    const st = S.get();
    $('#balance').textContent = st.balance;
    const free = S.freeLeft();
    $('#freeBadge').textContent = free > 0 ? `${free} беспл.` : '—';
    const bb = $('#betBalance'); if (bb) bb.textContent = `${st.balance}₲`;
    const sb = $('#streakBadge');
    sb.style.display = st.streak >= 2 ? '' : 'none';
    $('#streakCount').textContent = st.streak;
    $('#btnDaily').classList.toggle('has-reward', S.dailyAvailable());
  }

  // ── Сетка бойцов ────────────────────────────────────────────
  function statRow(label, val, max, cls) {
    const w = Math.max(4, Math.min(100, Math.round(val / max * 100)));
    return `<div class="fc-stat-row"><span class="fc-stat-label">${label}</span><div class="fc-stat-bar"><div class="fc-stat-fill ${cls}" style="width:${w}%"></div></div><span class="fc-stat-val">${val}</span></div>`;
  }

  function cardHTML(f) {
    return `
      <div class="fc-tier-bar"></div>
      <div class="fc-portrait">
        <img class="fc-avatar" src="${avatarUrl(f)}" alt="${f.name}" loading="lazy" decoding="async">
        <span class="fc-country">${f.country}</span>
        <span class="fc-tier-badge">${f.tier}</span>
      </div>
      <div class="fc-info">
        <div class="fc-name">${f.name}</div>
        <div class="fc-type">${f.type}</div>
        <div class="fc-stats">
          ${statRow('HP', f.hp, 320, 'hp')}${statRow('ATK', f.atk, 45, 'atk')}${statRow('DEF', f.def, 40, 'def')}${statRow('SPD', f.spd, 10, 'spd')}
        </div>
      </div>
      <div class="fc-traits">
        ${f.strength ? `<div class="fc-trait str">+ ${f.strength}</div>` : ''}
        ${f.weakness ? `<div class="fc-trait weak">− ${f.weakness}</div>` : ''}
      </div>`;
  }

  function attachImgFallback(img, f) {
    if (!img) return;
    img.addEventListener('error', () => {
      const box = img.parentElement;
      if (box && box.classList.contains('fc-portrait')) {          // карточка: эмодзи на цветном фоне
        img.style.display = 'none';
        if (!box.querySelector('.fc-emoji-fallback')) {
          box.style.background = f.gradient || '#222';
          box.insertAdjacentHTML('beforeend', `<div class="fc-emoji-fallback">${f.emoji || '?'}</div>`);
        }
      } else {                                                      // слоты, ставка, бой: круглый значок
        const sp = document.createElement('span');
        sp.className = 'avatar-emoji'; sp.textContent = f.emoji || '?';
        img.replaceWith(sp);
      }
    }, { once: true });
  }

  function matchesFilter(f) {
    if (typeFilter !== 'all' && f.type !== typeFilter) return false;
    if (!query) return true;
    const q = query.toLowerCase();
    return f.name.toLowerCase().includes(q) || (f.country || '').includes(q) || f.type.toLowerCase().includes(q);
  }

  function renderFighters() {
    const grid = $('#fightersGrid');
    grid.innerHTML = '';
    const list = FIGHTERS.filter(matchesFilter);
    if (!list.length) { grid.innerHTML = '<p class="empty-note">Никого не нашли. Попробуй другой запрос.</p>'; return; }
    list.forEach(f => {
      const card = document.createElement('div');
      card.className = `fighter-card tier-${f.tier}`;
      card.dataset.id = f.id;
      card.style.setProperty('--card-gradient', f.gradient);
      if ((selectedA && selectedA.id === f.id) || (selectedB && selectedB.id === f.id)) card.classList.add('selected');
      card.innerHTML = cardHTML(f);
      attachImgFallback(card.querySelector('.fc-avatar'), f);
      card.addEventListener('click', () => selectFighter(f));
      grid.appendChild(card);
    });
  }

  function renderTypeChips() {
    const types = ['all'].concat(Array.from(new Set(FIGHTERS.map(f => f.type))));
    const wrap = $('#typeChips');
    wrap.innerHTML = '';
    types.forEach(t => {
      const b = document.createElement('button');
      b.className = 'type-chip' + (t === typeFilter ? ' active' : '');
      b.textContent = t === 'all' ? 'Все' : t;
      b.addEventListener('click', () => { typeFilter = t; renderTypeChips(); renderFighters(); snd('click'); });
      wrap.appendChild(b);
    });
  }

  // ── Выбор бойцов ────────────────────────────────────────────
  function selectFighter(f) {
    snd('select');
    if (selectedA && selectedA.id === f.id) { selectedA = null; updateSlot('slotA', null); }
    else if (selectedB && selectedB.id === f.id) { selectedB = null; updateSlot('slotB', null); }
    else if (!selectedA) { selectedA = f; updateSlot('slotA', f); }
    else if (!selectedB) { selectedB = f; updateSlot('slotB', f); }
    else { selectedB = f; updateSlot('slotB', f); }       // оба заняты — заменяем второго
    renderFighters();
    $('#btnTobet').disabled = !(selectedA && selectedB);
  }

  function updateSlot(slotId, f) {
    const slot = $('#' + slotId);
    if (!f) {
      slot.classList.remove('filled');
      slot.innerHTML = `<div class="slot-placeholder">?</div><span>Боец ${slotId === 'slotA' ? '1' : '2'}</span>`;
      return;
    }
    slot.classList.add('filled');
    slot.innerHTML = `<button class="slot-remove" aria-label="Убрать">×</button><img class="slot-avatar" src="${avatarUrl(f)}" alt=""><span>${f.name}</span>`;
    slot.querySelector('.slot-remove').addEventListener('click', (ev) => {
      ev.stopPropagation();
      if (slotId === 'slotA') selectedA = null; else selectedB = null;
      updateSlot(slotId, null); renderFighters();
      $('#btnTobet').disabled = !(selectedA && selectedB);
    });
  }

  // ── Экран ставки ────────────────────────────────────────────
  function populateBetCard(side, f, p) {
    const U = side.toUpperCase();
    $(`#betEmoji${U}`).innerHTML = `<img class="bet-avatar" src="${avatarUrl(f)}" alt="">`;
    attachImgFallback($(`#betEmoji${U} img`), f);
    $(`#betName${U}`).textContent = f.name;
    $(`#betType${U}`).textContent = `${f.country} ${f.type}`;
    $(`#betStats${U}`).innerHTML = `<div>HP <strong>${f.hp}</strong></div><div>ATK <strong>${f.atk}</strong></div><div>DEF <strong>${f.def}</strong></div><div>SPD <strong>${f.spd}</strong></div>`;
    $(`#betOdds${U}`).textContent = `шанс ${Math.round(p * 100)}% · ×${E.payoutMult(p).toFixed(2)}`;
  }

  function showBetScreen() {
    betSide = null;
    const pA = E.winProb(selectedA, selectedB);
    populateBetCard('a', selectedA, pA);
    populateBetCard('b', selectedB, 1 - pA);
    $$('.bet-fighter-card').forEach(c => c.classList.remove('selected-bet'));
    $('#matchupFill').style.width = `${Math.round(pA * 100)}%`;
    $('#matchupText').textContent = `${shortName(selectedA.name)} ${Math.round(pA * 100)}%  —  ${Math.round((1 - pA) * 100)}% ${shortName(selectedB.name)}`;
    $('#betAmount').value = Math.min(currentAmountUI, S.get().balance);
    chooseSide('a', true);                       // по умолчанию играем за первого — можно сменить нажатием на карточку
    showScreen('bet');
  }

  function clampBet() {
    let v = parseInt($('#betAmount').value, 10);
    if (!Number.isFinite(v) || v < 0) v = 0;
    return Math.min(v, E.ECON.MAX_BET, S.get().balance);
  }

  function updateBetInfo() {
    const amt = clampBet();
    const bal = S.get().balance;
    const raw = parseInt($('#betAmount').value, 10);
    if (Number.isFinite(raw) && raw !== amt) $('#betAmount').value = amt;
    const note = $('#betNote');
    let canFight = !!betSide;
    let win = '—';
    if (betSide) {
      const me = betSide === 'a' ? selectedA : selectedB, foe = betSide === 'a' ? selectedB : selectedA;
      const mult = E.payoutMult(E.winProb(me, foe));
      win = amt === 0 ? `+${E.ECON.FREE_WIN_REWARD}₲ (тренировка)` : `${Math.floor(amt * mult)}₲ (×${mult.toFixed(2)})`;
    }
    $('#potentialWin').textContent = win;
    $('#betBalance').textContent = `${bal}₲`;
    note.className = 'bet-note';
    if (!betSide) note.textContent = 'Нажми на бойца, за которого играешь.';
    else if (amt === 0) {
      const left = S.freeLeft();
      if (left <= 0) { note.textContent = 'Бесплатные бои на сегодня закончились — поставь хотя бы 1₲ или забери ежедневный бонус.'; note.classList.add('warn'); canFight = false; }
      else note.textContent = `Бесплатных боёв сегодня: ${left}. За победу — +${E.ECON.FREE_WIN_REWARD}₲, за поражение ничего не теряешь.`;
    } else {
      const next = E.ECON.streakMult(S.get().streak + 1);
      note.textContent = next > 1
        ? `Серия побед даёт бонус к выплате: следующая победа ×${next}.`
        : 'Победы подряд увеличивают выплату (×1.2 → ×1.5 → ×2).';
    }
    $('#btnFight').disabled = !canFight;
  }

  function chooseSide(side, silent) {
    betSide = side;
    $$('.bet-fighter-card').forEach(c => c.classList.remove('selected-bet'));
    $(`#betCard${side.toUpperCase()}`).classList.add('selected-bet');
    if (!silent) snd('select');
    updateBetInfo();
  }

  // ── Бой ─────────────────────────────────────────────────────
  const hooks = {
    ult: () => snd('combo'),
    swing: () => snd('click'),
    hit: (res) => snd(res.crit ? 'crit' : 'hit'),
    miss: () => snd('miss'),
    counter: () => snd('counter'),
    combo: () => snd('combo'),
  };

  function stageSetup(fa, fb, side, title) {
    FX.init($('#stage'));
    FX.reset();
    ['A', 'B'].forEach(U => {
      const f = U === 'A' ? fa : fb;
      $(`#fightEmoji${U}`).innerHTML = `<img class="fight-avatar" src="${avatarUrl(f)}" alt="">`;
      attachImgFallback($(`#fightEmoji${U} img`), f);
      $(`#fightName${U}`).textContent = f.name + (side && U.toLowerCase() === side ? ' · ты' : '');
      $(`#status${U}`).innerHTML = '';
      FX.setHp(U.toLowerCase(), f.hp, f.hp, false);
    });
    $('#fighterBoxA').classList.toggle('me', side === 'a');
    $('#fighterBoxB').classList.toggle('me', side === 'b');
    $('#stageEnd').style.display = 'none';
    $('#stageEnd').innerHTML = '';
    $('#fightTitle').textContent = title || '';
    $('#fightLog').innerHTML = '';
    $('#movePicker').style.display = 'none';
    $('#fightRound').textContent = 'РАУНД 1';
    $('#stage').dataset.terrain = (ctx && ctx.terrain) || '';
    updateSpeedBtn();
  }

  function updateSpeedBtn() { $('#speedBtn').textContent = `⏩ ${FX.speed}×`; }

  function cycleSpeed() {
    FX.speed = FX.speed >= 4 ? 1 : FX.speed * 2;
    updateSpeedBtn();
    snd('click');
  }

  async function beginFight(c) {
    ctx = c;
    fight = E.createFight(c.fa, c.fb, c.side);
    stageSetup(c.fa, c.fb, c.side, c.title);
    showScreen('fight');
    snd('fightStart');
    appendLog({ k: 'round', t: `Гонг! ${c.fa.name} против ${c.fb.name}.` });
    busy = true;
    await FX.banner('FIGHT!', 'round', 900);
    busy = false;
    showMovePicker(E.getUserMoves(fight), 1);
  }

  function runFight(o) {
    return beginFight(Object.assign({ mode: 'camp', side: 'a' }, o));
  }

  function startFight() {
    if (busy || !betSide) return;
    const amt = clampBet();
    const placed = S.placeBet(amt);
    if (!placed.ok) { toast(placed.error); snd('error'); refreshWallet(); updateBetInfo(); return; }
    if (amt > 0) currentAmountUI = amt;
    currentBet = amt;
    const me = betSide === 'a' ? selectedA : selectedB, foe = betSide === 'a' ? selectedB : selectedA;
    currentMult = amt > 0 ? E.payoutMult(E.winProb(me, foe)) : 0;
    refreshWallet();
    beginFight({ mode: 'arena', fa: selectedA, fb: selectedB, side: betSide, title: `Арена · ты за ${me.name}` });
  }

  function appendLog(line) {
    const log = $('#fightLog');
    const div = document.createElement('div');
    div.className = 'log-line' + ({ crit: ' crit', miss: ' miss', round: ' round-start', effect: ' effect', combo: ' crit', counter: ' effect' }[line.k] || '');
    div.textContent = line.t;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
  }

  function showMovePicker(info, roundNum) {
    $('#fightRound').textContent = `РАУНД ${roundNum} / ${E.C.ROUNDS}`;
    const hint = $('#aiHint');
    if (info.hint) {
      hint.style.display = '';
      hint.textContent = `Похоже, соперник ударит: ${TYPE_ICON[info.hint]} ${TYPE_NAME[info.hint]} (подсказка верна не всегда)`;
    } else hint.style.display = 'none';

    const grid = $('#movesGrid');
    grid.innerHTML = '';
    info.moves.forEach(m => {
      const btn = document.createElement('button');
      btn.className = 'move-btn type-' + m.type;
      btn.disabled = !m.available;
      btn.innerHTML = `
        <div class="move-name">${m.name}</div>
        <div class="move-info">УРОН ${m.base_dmg} · ТОЧНОСТЬ ${m.accuracy}%${m.available ? '' : ' · ' + m.reason}</div>
        <span class="move-type ${m.type}">${TYPE_ICON[m.type]} ${TYPE_NAME[m.type]}</span>`;
      if (m.available) btn.addEventListener('click', () => playRound(m.index));
      grid.appendChild(btn);
    });
    $('#movePicker').style.display = 'block';
  }

  async function animateRound(r, maxA, maxB) {
    $('#fightRound').textContent = `РАУНД ${r.round} / ${E.C.ROUNDS}`;
    await FX.playRound(r, maxA, maxB, hooks);
    r.lines.forEach(appendLog);
  }

  async function playRound(moveIndex) {
    if (busy || !fight) return;
    busy = true;
    $('#movePicker').style.display = 'none';
    let r;
    try { r = E.playRound(fight, moveIndex); }
    catch (e) { busy = false; toast(e.message || 'Ошибка хода'); snd('error'); $('#movePicker').style.display = 'block'; return; }
    await animateRound(r, fight.a.maxHp, fight.b.maxHp);
    if (r.fight_over) {
      await FX.finish(r.result, r.result.winner_side, ctx.side);
      busy = false;
      finishFight(r.result);
    } else {
      busy = false;
      showMovePicker({ moves: r.moves, hint: r.hint }, r.round_next);
    }
  }

  function stageEnd(result, o) {
    const box = $('#stageEnd');
    box.innerHTML = `
      <div class="end-card ${o.cls || ''}">
        <div class="end-title">${o.title}</div>
        <div class="end-sub">${o.sub || ''}</div>
        <button class="btn-primary" id="btnStageDone">${o.button || 'ДАЛЬШЕ'}</button>
      </div>`;
    box.style.display = 'flex';
    $('#btnStageDone').addEventListener('click', () => { snd('click'); box.style.display = 'none'; o.onClick(); });
  }

  async function playReplay(rep, o) {
    o = o || {};
    ctx = { mode: 'replay', terrain: o.terrain };
    fight = null;
    stageSetup(rep.a, rep.b, o.side || null, o.title || 'Повтор боя');
    $('#movePicker').style.display = 'none';
    showScreen('fight');
    snd('fightStart');
    busy = true;
    const prevSpeed = FX.speed;
    if (o.speed) FX.speed = o.speed;
    updateSpeedBtn();
    await FX.banner('БОЙ!', 'round', 700);
    for (const r of rep.rounds) await animateRound(r, rep.a.hp, rep.b.hp);
    await FX.finish(rep.result, rep.result.winner_side, o.side || null);
    busy = false;
    const w = rep.result.winner_side === 'a' ? rep.a : rep.b;
    FX.speed = prevSpeed;
    stageEnd(rep.result, {
      title: `${w.name} побеждает`,
      sub: rep.result.method === 'KO' ? `Нокаут в ${rep.result.rounds_played}-м раунде` : 'Победа по очкам',
      cls: o.won === false ? 'lose' : o.won ? 'win' : '',
      button: o.button || 'ДАЛЬШЕ',
      onClick: o.onDone || (() => {}),
    });
  }

  // ── Результат ───────────────────────────────────────────────
  function finishFight(result) {
    if (ctx.mode === 'camp') {
      const won = result.user_won;
      snd(won ? 'victory' : 'defeat');
      const done = ctx.onDone;
      stageEnd(result, {
        title: won ? 'ПОБЕДА!' : 'ПОРАЖЕНИЕ',
        sub: ctx.endText ? ctx.endText(won) : '',
        cls: won ? 'win' : 'lose',
        button: 'НА КАРТУ',
        onClick: () => done(result),
      });
      return;
    }
    const won = result.user_won;
    const settle = S.settle({
      fighterA: selectedA.id, fighterB: selectedB.id, userSide: betSide,
      winnerId: result.winner_id, userWon: won, bet: currentBet, mult: currentMult,
    });
    refreshWallet();

    const winner = BY_ID[result.winner_id];
    $('#resultGlow').className = 'result-glow ' + (won ? 'win' : 'lose');
    $('#resultEmoji').textContent = won ? '🏆' : '💀';
    const title = $('#resultTitle');
    title.textContent = won ? 'ПОБЕДА!' : 'ПОРАЖЕНИЕ';
    title.className = 'result-title ' + (won ? 'win' : 'lose');
    $('#resultWinner').textContent = `${winner.emoji} ${winner.name} побеждает!`;
    $('#resultMethod').textContent = result.method === 'KO'
      ? `НОКАУТ в ${result.rounds_played}-м раунде`
      : `ПО ОЧКАМ после ${result.rounds_played} раундов`;

    const bet = $('#resultBet');
    let msg, cls;
    if (currentBet === 0) {
      msg = won ? `+${settle.payout}₲ за тренировку` : 'Бесплатный бой — ничего не потеряно';
      cls = won ? 'win' : '';
    } else if (won) {
      msg = `Выплата ${settle.payout}₲ (чистыми +${settle.payout - currentBet}₲)` + (settle.streakMult > 1 ? ` · серия ×${settle.streakMult}` : '');
      cls = 'win';
    } else { msg = `−${currentBet}₲`; cls = 'lose'; }
    if (settle.bailout) msg += ` · Баланс опустел — держи +${E.ECON.BAILOUT}₲`;
    bet.textContent = msg; bet.className = 'result-bet ' + cls;

    $('#resultNarration').textContent =
      `${selectedA.name}: ${result.hp_a}/${result.max_a} HP  ·  ${selectedB.name}: ${result.hp_b}/${result.max_b} HP`;
    $('#btnSpin').style.display = S.get().pendingSpin > 0 ? '' : 'none';
    showScreen('result');
    snd(won ? 'victory' : 'defeat');
    if (settle.payout > 0) setTimeout(() => snd('coin'), 400);
  }

  // ── Колесо удачи ────────────────────────────────────────────
  const WHEEL_COLORS = ['#e63946', '#6b7280', '#00b4d8', '#06d6a0', '#b44dff', '#f5a623'];
  let wheelBuilt = false, tickTimer = null;

  function buildWheel() {
    const wheel = $('#spinWheel');
    const segs = E.ECON.SPIN, n = segs.length, step = 360 / n;
    wheel.style.background = `conic-gradient(${segs.map((s, i) => `${WHEEL_COLORS[i % WHEEL_COLORS.length]} ${i * step}deg ${(i + 1) * step}deg`).join(',')})`;
    wheel.innerHTML = '';
    segs.forEach((s, i) => {
      const lab = document.createElement('div');
      lab.className = 'wheel-label';
      lab.textContent = `×${s.mult}`;
      lab.style.transform = `translate(-50%, -50%) rotate(${i * step + step / 2}deg) translateY(-92px)`;
      wheel.appendChild(lab);
    });
    wheelBuilt = true;
  }

  function openSpin() {
    if (!wheelBuilt) buildWheel();
    const wheel = $('#spinWheel');
    wheel.style.transition = 'none'; wheel.style.transform = 'rotate(0deg)';
    void wheel.offsetWidth;
    $('#spinResult').style.display = 'none';
    $('#btnDoSpin').style.display = ''; $('#btnDoSpin').disabled = false;
    $('#btnSpinDone').style.display = 'none';
    $('#spinSubtitle').textContent = `Твоя выплата: ${S.get().pendingSpin}₲. Колесо может умножить её — или урезать.`;
    showScreen('spin');
  }

  function doSpin() {
    const res = S.spin();
    if (!res.ok) { toast('Колесо уже использовано'); return; }
    $('#btnDoSpin').disabled = true; $('#btnDoSpin').style.display = 'none';
    const n = E.ECON.SPIN.length, step = 360 / n;
    const jitter = (Math.random() - 0.5) * step * 0.7;
    const target = 360 * 5 + (360 - (res.index * step + step / 2)) + jitter;
    const wheel = $('#spinWheel');
    wheel.style.transition = 'transform 4s cubic-bezier(0.17, 0.67, 0.12, 0.99)';
    wheel.style.transform = `rotate(${target}deg)`;
    let delay = 90;
    const tick = () => { snd('spinTick'); delay = Math.min(delay * 1.06, 320); tickTimer = setTimeout(tick, delay); };
    tick();
    setTimeout(() => {
      clearTimeout(tickTimer);
      refreshWallet();
      $('#spinMult').textContent = `×${res.mult}`;
      const sign = res.delta >= 0 ? '+' : '−';
      $('#spinPayout').textContent = `${res.base}₲ → ${res.payout}₲ (${sign}${Math.abs(res.delta)}₲)`;
      $('#spinResult').style.display = '';
      $('#btnSpinDone').style.display = '';
      snd(res.mult >= 1.5 ? 'spinWin' : 'click');
    }, 4200);
  }

  // ── Модальные окна ──────────────────────────────────────────
  function openModal(id) { $(id).style.display = 'flex'; }
  function closeModal(id) { $(id).style.display = 'none'; }

  function openDaily() {
    const avail = S.dailyAvailable();
    const nxt = S.nextDaily();
    $('#dailyAmount').textContent = avail ? `+${nxt.amount}₲` : '✓';
    $('#dailyStreak').textContent = avail
      ? `День ${nxt.dayStreak} подряд · бонус растёт до ${E.ECON.dailyBonus(99)}₲`
      : 'Сегодняшний бонус уже получен. Возвращайся завтра!';
    $('#btnClaimDaily').disabled = !avail;
    openModal('#modalDaily');
  }

  function claimDaily() {
    const r = S.claimDaily();
    if (r.ok) { snd('daily'); toast(`+${r.amount}₲ — день ${r.day_streak} подряд`); }
    refreshWallet();
    closeModal('#modalDaily');
  }

  function openProfile() {
    const st = S.get();
    $('#pWins').textContent = st.wins; $('#pLosses').textContent = st.losses; $('#pBestStreak').textContent = st.bestStreak;
    const list = $('#historyList');
    list.innerHTML = '';
    if (!st.history.length) list.innerHTML = '<div class="history-empty">Пока нет боёв</div>';
    st.history.slice(0, 8).forEach(h => {
      const a = BY_ID[h.a], b = BY_ID[h.b];
      const row = document.createElement('div');
      row.className = 'history-row ' + (h.won ? 'won' : 'lost');
      const res = h.bet > 0 ? (h.won ? `+${h.payout - h.bet}₲` : `−${h.bet}₲`) : 'бесплатно';
      row.textContent = `${h.won ? '✓' : '✗'} ${a ? shortName(a.name) : '?'} vs ${b ? shortName(b.name) : '?'} · ${res}`;
      list.appendChild(row);
    });
    const rb = $('#btnResetProgress'); rb.textContent = 'Сбросить прогресс'; rb.dataset.armed = '';
    openModal('#modalProfile');
  }

  function resetProgress() {
    const rb = $('#btnResetProgress');
    if (rb.dataset.armed !== '1') {      // двойное нажатие вместо confirm()
      rb.dataset.armed = '1'; rb.textContent = 'Точно сбросить? Нажми ещё раз';
      setTimeout(() => { rb.dataset.armed = ''; rb.textContent = 'Сбросить прогресс'; }, 4000);
      return;
    }
    S.reset(); refreshWallet(); closeModal('#modalProfile'); toast('Прогресс сброшен');
  }

  // ── События ─────────────────────────────────────────────────
  function bindEvents() {
    $('#btnMenu').addEventListener('click', () => { snd('back'); showScreen('menu'); if (window.ArenaCamp) window.ArenaCamp.refreshMenu(); });
    $('#menuArena').addEventListener('click', () => { snd('click'); showScreen('select'); });
    $('#speedBtn').addEventListener('click', cycleSpeed);
    $('#btnTobet').addEventListener('click', () => { snd('click'); showBetScreen(); });
    $('#btnBackSelect').addEventListener('click', () => { snd('back'); showScreen('select'); });
    $('#betCardA').addEventListener('click', () => chooseSide('a'));
    $('#betCardB').addEventListener('click', () => chooseSide('b'));

    $('#betMinus').addEventListener('click', () => { $('#betAmount').value = Math.max(0, clampBet() - 5); updateBetInfo(); });
    $('#betPlus').addEventListener('click', () => { $('#betAmount').value = Math.min(E.ECON.MAX_BET, S.get().balance, clampBet() + 5); updateBetInfo(); });
    $('#betAmount').addEventListener('input', updateBetInfo);
    $$('.bet-quick-btn').forEach(btn => btn.addEventListener('click', () => {
      const v = parseInt(btn.dataset.val, 10);
      $('#betAmount').value = Math.min(v, S.get().balance, E.ECON.MAX_BET);
      updateBetInfo(); snd('click');
    }));

    $('#btnFight').addEventListener('click', startFight);

    $('#btnRematch').addEventListener('click', () => { snd('click'); const keep = betSide; showBetScreen(); if (keep) chooseSide(keep); });
    $('#btnPlayAgain').addEventListener('click', () => {
      snd('back');
      selectedA = selectedB = null; betSide = null;
      updateSlot('slotA', null); updateSlot('slotB', null);
      renderFighters(); $('#btnTobet').disabled = true;
      showScreen('select');
    });

    $('#btnSpin').addEventListener('click', () => { snd('click'); openSpin(); });
    $('#btnDoSpin').addEventListener('click', doSpin);
    $('#btnSpinDone').addEventListener('click', () => { snd('click'); showScreen('result'); $('#btnSpin').style.display = 'none'; });

    $('#btnDaily').addEventListener('click', openDaily);
    $('#btnClaimDaily').addEventListener('click', claimDaily);
    $('#btnCloseDaily').addEventListener('click', () => closeModal('#modalDaily'));
    $('#btnProfile').addEventListener('click', openProfile);
    $('#btnCloseProfile').addEventListener('click', () => closeModal('#modalProfile'));
    $('#btnResetProgress').addEventListener('click', resetProgress);
    ['#modalDaily', '#modalProfile'].forEach(id => $(id).addEventListener('click', (e) => { if (e.target === $(id)) closeModal(id); }));

    $('#soundToggle').addEventListener('click', () => {
      if (typeof sfx === 'undefined') return;
      sfx.enabled = !sfx.enabled;
      $('#soundToggle').classList.toggle('muted', !sfx.enabled);
      $('#soundToggle').textContent = sfx.enabled ? '🔊' : '🔇';
      if (sfx.enabled) snd('click');
    });

    let t = null;
    $('#fighterSearch').addEventListener('input', (e) => {
      clearTimeout(t);
      t = setTimeout(() => { query = e.target.value.trim(); renderFighters(); }, 120);
    });
  }

  function init() {
    renderTypeChips();
    renderFighters();
    refreshWallet();
    bindEvents();
    if (window.ArenaCamp) window.ArenaCamp.init();
    showScreen('menu');
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();

  // для автотестов
  window.__arena = { get fight() { return fight; }, state: () => ({ selectedA, selectedB, betSide, busy }) };
  window.ArenaApp = {
    E, S, BY_ID, FIGHTERS, $, $$, sleep, snd, toast, avatarUrl, attachImgFallback, cardHTML, showScreen, runFight, playReplay,
    openModal, closeModal, refreshWallet, TYPE_ICON, TYPE_NAME, shortName,
  };
})();
