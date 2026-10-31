(function (root) {
  'use strict';

  const C = {
    ROUNDS: 5,
    ULT_FROM_ROUND: 3,
    CRIT_BASE: 0.12,
    CRIT_LUCK: 0.015,
    CRIT_MULT: 1.6,
    DMG_SCALE: 1.25,
    HINT_TRUTH: 0.6,
    CONFUSE_ACC_PENALTY: 0.20,
    HEAL: 20,
  };

  const BEATS = { light: 'special', special: 'heavy', heavy: 'light' };
  const COUNTERED_BY = { special: 'light', heavy: 'special', light: 'heavy' };

  function createRng(seed) {
    let a = (seed >>> 0) || 1;
    function random() {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    }
    return {
      random,
      uniform: (lo, hi) => lo + (hi - lo) * random(),
      int: (lo, hi) => lo + Math.floor(random() * (hi - lo + 1)),
      pick: (arr) => arr[Math.floor(random() * arr.length)],
      weighted(items, weights) {
        const total = weights.reduce((s, w) => s + w, 0);
        let r = random() * total;
        for (let i = 0; i < items.length; i++) { r -= weights[i]; if (r <= 0) return items[i]; }
        return items[items.length - 1];
      },
    };
  }

  function makeCombatant(f) {
    return {
      id: f.id, name: f.name, moves: f.moves, luck: f.luck || 5,
      maxHp: f.hp, hp: f.hp,
      atk: f.atk, def: f.def, spd: f.spd,
      confused: false,
      ultUsed: false,
      history: [],
      dealt: 0,
    };
  }

  function movesFor(c, round) {
    return c.moves.map((m, index) => {
      let available = true, reason = '';
      if (m.type === 'ultimate') {
        if (round < C.ULT_FROM_ROUND) { available = false; reason = `с ${C.ULT_FROM_ROUND}-го раунда`; }
        else if (c.ultUsed) { available = false; reason = 'уже использована'; }
      }
      return { index, name: m.name, type: m.type, base_dmg: m.base_dmg, accuracy: m.accuracy, effect: m.effect || '', available, reason };
    });
  }

  function aiPick(state, ai, foe) {
    const rng = state.rng;
    const avail = movesFor(ai, state.round).filter(m => m.available);
    const hpRatio = ai.hp / ai.maxHp;
    const lastFoe = foe.history[foe.history.length - 1];
    const weights = avail.map(m => {
      let w = 1;
      if (m.type === 'light') w = hpRatio > 0.5 ? 2.0 : 1.0;
      else if (m.type === 'heavy') w = hpRatio < 0.4 ? 1.6 : 1.0;
      else if (m.type === 'special') w = state.round === 2 ? 1.8 : 1.2;
      else if (m.type === 'ultimate') w = hpRatio < 0.5 ? 4.0 : 2.5;
      if (lastFoe && m.type === COUNTERED_BY[lastFoe]) w *= 1.6;
      return w;
    });
    return rng.weighted(avail, weights);
  }

  function strike(att, def, move, foeType, comboCount, rng) {
    let acc = move.accuracy / 100;
    if (att.confused) acc -= C.CONFUSE_ACC_PENALTY;
    const dodge = (def.spd - att.spd) * 0.02;
    const hitChance = Math.max(0.2, Math.min(0.98, acc - dodge));
    if (rng.random() > hitChance) return { dmg: 0, miss: true, crit: false, counter: false, weak: false };

    let raw = move.base_dmg + att.atk * 0.5 - def.def * 0.35;
    raw *= rng.uniform(0.85, 1.15);

    let crit = false;
    if (rng.random() < C.CRIT_BASE + att.luck * C.CRIT_LUCK) { raw *= C.CRIT_MULT; crit = true; }

    let counter = false, weak = false;
    if (BEATS[move.type] && BEATS[move.type] === foeType) { raw *= 1.3; counter = true; }
    else if (foeType && BEATS[foeType] === move.type) { raw *= 0.8; weak = true; }

    if (comboCount >= 3) raw *= 1.6; else if (comboCount === 2) raw *= 1.3;

    return { dmg: Math.max(1, Math.floor(raw * C.DMG_SCALE)), miss: false, crit, counter, weak };
  }

  function comboOf(history) {
    let n = 1;
    for (let i = history.length - 1; i > 0 && history[i] === history[i - 1]; i--) n++;
    return history.length ? n : 0;
  }

  // эффект применяется только если удар попал
  function applyEffect(effect, att, def) {
    switch (effect) {
      case 'def_down': def.def = Math.max(0, def.def - 5); return `${def.name}: защита −5`;
      case 'atk_down': def.atk = Math.max(0, def.atk - 5); return `${def.name}: атака −5`;
      case 'spd_down': def.spd = Math.max(0, def.spd - 2); return `${def.name}: скорость −2`;
      case 'confuse':  def.confused = true;               return `${def.name} в замешательстве (точность −20%)`;
      case 'atk_up':   att.atk += 5;                      return `${att.name}: атака +5`;
      case 'def_up':   att.def += 5;                      return `${att.name}: защита +5`;
      case 'spd_up':   att.spd += 2;                      return `${att.name}: скорость +2`;
      case 'hp_regen': {
        const before = att.hp; att.hp = Math.min(att.maxHp, att.hp + C.HEAL);
        return `${att.name} восстановил ${att.hp - before} HP`;
      }
      default: return '';
    }
  }

  function createFight(fa, fb, userSide, seed) {
    if (!fa || !fb) throw new Error('Боец не найден');
    if (fa.id === fb.id) throw new Error('Нельзя выставить бойца против самого себя');
    const state = {
      a: makeCombatant(fa), b: makeCombatant(fb),
      userSide: userSide === 'b' ? 'b' : 'a',
      round: 1, finished: false, winner: null, method: null,
      rng: createRng(seed == null ? (Date.now() ^ (Math.random() * 1e9)) : seed),
      rounds: [], nextAi: null, hint: null,
    };
    prepareAi(state);
    return state;
  }

  const userOf = (s) => (s.userSide === 'a' ? s.a : s.b);
  const aiOf = (s) => (s.userSide === 'a' ? s.b : s.a);

  /** Соперник выбирает ход ЗАРАНЕЕ; подсказка правдива с вероятностью HINT_TRUTH. */
  function prepareAi(state) {
    const u = userOf(state), ai = aiOf(state);
    state.nextAi = aiPick(state, ai, u);
    const types = ['light', 'heavy', 'special'].concat(state.round >= C.ULT_FROM_ROUND && !ai.ultUsed ? ['ultimate'] : []);
    const real = state.nextAi.type;
    state.hint = state.rng.random() < C.HINT_TRUTH ? real : state.rng.pick(types.filter(t => t !== real));
  }

  function getUserMoves(state) {
    return { moves: movesFor(userOf(state), state.round), hint: state.hint };
  }

  const P = (n, x) => ({ n, x });
  function narrate(state, r) {
    const lines = [{ k: 'round', t: `Раунд ${r.round}` }];
    const side = (name, mv, res, hit) => {
      if (res.miss) lines.push({ k: 'miss', t: `${name} промахивается: «${mv.name}»` });
      else if (res.crit) lines.push({ k: 'crit', t: `КРИТ! ${name}: «${mv.name}» — ${res.dmg} урона` });
      else lines.push({ k: 'hit', t: `${name}: «${mv.name}» — ${res.dmg} урона` });
      if (res.counter) lines.push({ k: 'counter', t: `Контрудар! ${name} прочитал соперника (×1.3)` });
    };
    side(state.a.name, r.move_a, r.res_a);
    side(state.b.name, r.move_b, r.res_b);
    if (r.combo_a >= 2) lines.push({ k: 'combo', t: `COMBO ×${r.combo_a}: ${state.a.name}` });
    if (r.combo_b >= 2) lines.push({ k: 'combo', t: `COMBO ×${r.combo_b}: ${state.b.name}` });
    [r.effect_a, r.effect_b].forEach(e => e && lines.push({ k: 'effect', t: `↳ ${e}` }));
    return lines;
  }

  function playRound(state, moveIndex) {
    if (state.finished) throw new Error('Бой уже окончен');
    const u = userOf(state), ai = aiOf(state);
    const mv = u.moves[moveIndex];
    if (!mv) throw new Error('Неверный ход');
    const info = movesFor(u, state.round)[moveIndex];
    if (!info.available) throw new Error(`Ход недоступен (${info.reason})`);

    const aiMove = state.nextAi;
    const mA = state.userSide === 'a' ? mv : aiMove;
    const mB = state.userSide === 'a' ? aiMove : mv;

    state.a.history.push(mA.type); state.b.history.push(mB.type);
    if (mA.type === 'ultimate') state.a.ultUsed = true;
    if (mB.type === 'ultimate') state.b.ultUsed = true;
    const comboA = comboOf(state.a.history), comboB = comboOf(state.b.history);

    // оба бьют одновременно, по статам на начало раунда
    const resA = strike(state.a, state.b, mA, mB.type, comboA, state.rng);
    const resB = strike(state.b, state.a, mB, mA.type, comboB, state.rng);
    state.a.confused = false; state.b.confused = false;   // замешательство живёт один раунд

    state.b.hp = Math.max(0, state.b.hp - resA.dmg);
    state.a.hp = Math.max(0, state.a.hp - resB.dmg);
    state.a.dealt += resA.dmg; state.b.dealt += resB.dmg;

    const effA = !resA.miss && mA.effect ? applyEffect(mA.effect, state.a, state.b) : '';
    const effB = !resB.miss && mB.effect ? applyEffect(mB.effect, state.b, state.a) : '';

    const r = {
      round: state.round,
      move_a: mA, move_b: mB, res_a: resA, res_b: resB,
      damage_to_a: resB.dmg, damage_to_b: resA.dmg,
      hp_a: state.a.hp, hp_b: state.b.hp,
      combo_a: comboA >= 2 ? comboA : 0, combo_b: comboB >= 2 ? comboB : 0,
      effect_a: effA, effect_b: effB,
    };
    r.lines = narrate(state, r);
    state.rounds.push(r);

    const ko = state.a.hp <= 0 || state.b.hp <= 0;
    const last = state.round >= C.ROUNDS;
    if (ko || last) {
      finish(state, ko, resA.dmg, resB.dmg);
      r.fight_over = true;
      r.result = resultOf(state);
    } else {
      state.round += 1;
      prepareAi(state);
      r.fight_over = false;
      Object.assign(r, getUserMoves(state), { round_next: state.round });
    }
    return r;
  }

  function finish(state, ko, lastDmgA, lastDmgB) {
    const A = state.a, B = state.b;
    state.finished = true;
    if (A.hp <= 0 && B.hp <= 0) {                       // двойной нокаут: решает последний обмен
      state.winner = lastDmgA > lastDmgB ? 'a' : lastDmgB > lastDmgA ? 'b' : (state.rng.random() < 0.5 ? 'a' : 'b');
      state.method = 'KO';
    } else if (B.hp <= 0) { state.winner = 'a'; state.method = 'KO'; }
    else if (A.hp <= 0) { state.winner = 'b'; state.method = 'KO'; }
    else {
      const ra = A.hp / A.maxHp, rb = B.hp / B.maxHp;
      if (Math.abs(ra - rb) >= 0.01) state.winner = ra > rb ? 'a' : 'b';
      else if (A.dealt !== B.dealt) state.winner = A.dealt > B.dealt ? 'a' : 'b';
      else state.winner = state.rng.random() < 0.5 ? 'a' : 'b';
      state.method = 'DECISION';
    }
    const w = state.winner === 'a' ? A : B;
    if (w.hp <= 0) w.hp = 1;
  }

  function resultOf(state) {
    const w = state.winner === 'a' ? state.a : state.b;
    return {
      winner_side: state.winner, winner_id: w.id, winner_name: w.name, method: state.method,
      user_won: state.winner === state.userSide,
      hp_a: state.a.hp, hp_b: state.b.hp, max_a: state.a.maxHp, max_b: state.b.maxHp,
      rounds_played: state.rounds.length,
    };
  }

  const ECON = {
    START_BALANCE: 100, MIN_BET: 1, MAX_BET: 100,
    FREE_FIGHTS_PER_DAY: 3, FREE_WIN_REWARD: 10,
    streakMult: (n) => (n >= 5 ? 2.0 : n >= 3 ? 1.5 : n >= 2 ? 1.2 : 1.0),
    dailyBonus: (dayStreak) => Math.min(50 + (dayStreak - 1) * 10, 200),
    BAILOUT: 50,
    SPIN: [
      { mult: 0.5, weight: 25 }, { mult: 1.0, weight: 35 }, { mult: 1.5, weight: 20 },
      { mult: 2.0, weight: 12 }, { mult: 3.0, weight: 5 }, { mult: 5.0, weight: 3 },
    ],
  };

  // Модель подобрана симуляцией 60 000 боёв (см. tests/arena_engine.test.js):
  const power = (f) => f.hp * 0.3 + f.atk * 2.5 + f.def * 1.5 + f.spd * 1.2 + (f.luck || 5) * 0.8;
  const clamp = (x, lo, hi) => Math.max(lo, Math.min(hi, x));
  function winProb(f, foe) {
    const pf = power(f), po = power(foe);
    return clamp(1 / (1 + Math.exp(-12.3 * (pf - po) / (pf + po))), 0.12, 0.88);
  }
  const payoutMult = (p) => Math.round(clamp(0.92 / p, 1.1, 4.0) * 100) / 100;

  const api = { C, ECON, power, winProb, payoutMult, BEATS, createRng, createFight, getUserMoves, playRound, aiPick, movesFor, resultOf };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.ArenaEngine = api;
})(typeof window !== 'undefined' ? window : globalThis);
