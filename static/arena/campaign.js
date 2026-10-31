(function (root) {
  'use strict';
  const E = root.ArenaEngine || (typeof require !== 'undefined' ? require('./engine.js') : null);
  const roster = () => root.ARENA_FIGHTERS || [];
  const byId = (id) => roster().find(f => f.id === id);

  const W = 6, H = 5, N = W * H;
  const MAX_TURNS = 60;
  const WIN_REGIONS = N / 2;
  const START_GOLD = 100;
  const WOUND_TURNS = 2;
  const MAX_ATTACKS_AI = 3;
  const ARMY_MAX = 10;
  const MAX_LVL = 5;
  const CAPITAL_DEF = 0.15;
  const DIFFS = {
    easy:   { name: 'Лёгкая',   aiGold: 80,  aiIncome: 0.85, aiMinOdds: 0.64 },
    normal: { name: 'Обычная',  aiGold: 100, aiIncome: 1.0,  aiMinOdds: 0.56 },
    hard:   { name: 'Сложная',  aiGold: 140, aiIncome: 1.2,  aiMinOdds: 0.50 },
  };
  const PLAYER = 'p';
  const FACTION_COLORS = { p: '#00d4ff', a: '#ff2d7b', b: '#f5a623', c: '#b44dff' };
  const CAPITALS = { p: [0, H - 1], a: [W - 1, 0], b: [0, 0], c: [W - 1, H - 1] };

  const REGION_NAMES = [
    'Северная Гавань', 'Серебряный Холм', 'Янтарная Равнина', 'Тихий Берег', 'Каменный Перевал', 'Зелёный Предел',
    'Красная Скала', 'Вороний Лес', 'Золотая Долина', 'Ветреный Мыс', 'Лунный Брод', 'Железный Город',
    'Туманная Топь', 'Белая Крепость', 'Медный Склон', 'Солнечный Порт', 'Горький Ручей', 'Старая Застава',
    'Тёмный Бор', 'Хрустальное Озеро', 'Соляная Пустошь', 'Багровый Закат', 'Орлиное Гнездо', 'Весенний Луг',
    'Чёрный Утёс', 'Новый Рубеж', 'Дальний Остров', 'Тихая Бухта', 'Звёздный Холм', 'Последний Оплот',
  ];

  const TERRAIN = {
    plain:    { name: 'Равнина',    income: 8,  def: 0,    icon: '🌾' },
    forest:   { name: 'Лес',        income: 6,  def: 0.10, icon: '🌲' },
    mountain: { name: 'Горы',       income: 5,  def: 0.25, icon: '⛰️' },
    coast:    { name: 'Побережье',  income: 10, def: 0.05, icon: '⚓' },
    city:     { name: 'Город',      income: 18, def: 0.15, icon: '🏙️' },
  };
  const BUILDINGS = {
    fort:   { name: 'Форт',  cost: 60,  icon: '🏰', desc: 'защитник получает +25% HP' },
    market: { name: 'Рынок', cost: 80,  icon: '🏪', desc: '+12 монет в ход' },
    base:   { name: 'База',  cost: 100, icon: '⚔️', desc: 'гарнизон +10% HP, атака из региона +3 ATK, раненые лечатся за ход' },
  };
  const MARKET_BONUS = 12;
  const RECRUIT = { common: [35, 3], uncommon: [50, 4], rare: [70, 5], epic: [100, 7], legendary: [140, 9] };

  const idx = (x, y) => y * W + x;
  const xy = (i) => [i % W, Math.floor(i / W)];
  function neighbors(i) {
    const [x, y] = xy(i), out = [];
    if (x > 0) out.push(idx(x - 1, y));
    if (x < W - 1) out.push(idx(x + 1, y));
    if (y > 0) out.push(idx(x, y - 1));
    if (y < H - 1) out.push(idx(x, y + 1));
    return out;
  }
  const dist = (a, b) => { const [ax, ay] = xy(a), [bx, by] = xy(b); return Math.abs(ax - bx) + Math.abs(ay - by); };

  const SHIELD = 'data:image/svg+xml;utf8,' + encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect width="100" height="100" fill="#2a2f45"/>' +
    '<text x="50" y="68" font-size="56" text-anchor="middle">🛡️</text></svg>');
  const MILITIA_MOVES = [
    { name: 'Выпад', type: 'light', base_dmg: 13, accuracy: 90 },
    { name: 'Тяжёлый удар', type: 'heavy', base_dmg: 32, accuracy: 60 },
    { name: 'Манёвр', type: 'special', base_dmg: 20, accuracy: 78, effect: 'def_down' },
    { name: 'Последний натиск', type: 'ultimate', base_dmg: 48, accuracy: 66 },
  ];
  function militia(region) {
    const m = region.power;
    const title = m < 1.0 ? 'Ополчение' : m < 1.3 ? 'Стража' : 'Гвардия';
    return {
      id: 'militia_' + region.id, name: `${title}: ${region.name}`, country: '🛡️', type: 'Гарнизон', emoji: '🛡️',
      avatar: SHIELD, tier: 'common', neutral: true,
      hp: Math.round(160 * m), atk: Math.round(22 * m), def: Math.round(16 * m), spd: 4, luck: 5,
      moves: MILITIA_MOVES, gradient: 'linear-gradient(135deg,#2a2f45,#3a3f55)',
    };
  }
  function fighterData(G, id) {
    if (id && id.startsWith('militia_')) return militia(G.regions[parseInt(id.slice(8), 10)]);
    return byId(id);
  }

  function newCampaign(leaderId, seed, diff) {
    diff = DIFFS[diff] ? diff : 'normal';
    seed = seed == null ? (Date.now() & 0x7fffffff) : seed;
    const rng = E.createRng(seed);
    const capIdx = {}; Object.keys(CAPITALS).forEach(k => { capIdx[k] = idx(CAPITALS[k][0], CAPITALS[k][1]); });
    const capList = Object.values(capIdx);

    const regions = [];
    const names = REGION_NAMES.slice();
    for (let i = N - 1; i > 0; i--) { const j = Math.floor(rng.random() * (i + 1)); [names[i], names[j]] = [names[j], names[i]]; }
    for (let i = 0; i < N; i++) {
      const [x, y] = xy(i);
      const edge = x === 0 || x === W - 1 || y === 0 || y === H - 1;
      let terrain;
      if (capList.includes(i)) terrain = 'city';
      else terrain = rng.weighted(['plain', 'forest', 'mountain', 'coast', 'city'], [34, 22, 16, edge ? 30 : 6, 9]);
      const d = Math.min(...capList.map(c => dist(i, c)));
      let power = 0.85 + 0.09 * d + (terrain === 'city' ? 0.1 : 0);
      power = Math.min(1.6, Math.round(power * 100) / 100);
      regions.push({ id: i, name: names[i], x, y, terrain, owner: null, garrison: null, building: null, power });
    }

    const leaders = [leaderId];
    const pool = roster().filter(f => f.id !== leaderId);
    const rivalKeys = ['a', 'b', 'c'];
    rivalKeys.forEach(() => { const k = Math.floor(rng.random() * pool.length); leaders.push(pool.splice(k, 1)[0].id); });

    const factions = {};
    ['p', 'a', 'b', 'c'].forEach((key, n) => {
      const lf = byId(leaders[n]);
      factions[key] = {
        id: key, name: lf.name, leaderId: lf.id, color: FACTION_COLORS[key], isPlayer: key === PLAYER,
        gold: key === PLAYER ? START_GOLD : DIFFS[diff].aiGold, eliminated: false, capital: capIdx[key],
        fighters: [{ id: lf.id, wounded: 0, acted: false, commander: true, lvl: 0 }],
      };
      regions[capIdx[key]].owner = key;
      regions[capIdx[key]].garrison = lf.id;
    });

    return { v: 2, seed, diff, turn: 1, regions, factions, log: [], over: null };
  }

  const player = (G) => G.factions[PLAYER];
  const regionsOf = (G, fid) => G.regions.filter(r => r.owner === fid);
  const refOf = (G, fid, id) => G.factions[fid].fighters.find(f => f.id === id) || null;
  function locationOf(G, fid, id) { const r = G.regions.find(r => r.owner === fid && r.garrison === id); return r ? r.id : -1; }

  function regionIncome(r) { return TERRAIN[r.terrain].income + (r.building === 'market' ? MARKET_BONUS : 0); }
  const incomeMult = (G, fid) => (fid === PLAYER ? 1 : DIFFS[G.diff || 'normal'].aiIncome);
  const income = (G, fid) => Math.round(regionsOf(G, fid).reduce((s, r) => s + regionIncome(r), 0) * incomeMult(G, fid));
  const priceOf = (f) => RECRUIT[f.tier || 'common'][0];
  const upkeepOf = (f) => RECRUIT[f.tier || 'common'][1];
  const upkeep = (G, fid) => G.factions[fid].fighters.filter(r => !r.commander).reduce((s, r) => s + upkeepOf(byId(r.id)), 0);
  const netIncome = (G, fid) => income(G, fid) - upkeep(G, fid);

  function availableMercs(G) {
    const taken = new Set(Object.values(G.factions).flatMap(f => f.fighters.map(r => r.id)));
    return roster().filter(f => !taken.has(f.id)).sort((a, b) => priceOf(a) - priceOf(b) || a.name.localeCompare(b.name));
  }

  function combatant(G, ref, region, asDefender) {
    const base = fighterData(G, ref.id);
    const notes = [];
    let hpMult = 1, atkAdd = 0, defAdd = 0;
    if (ref.commander) { hpMult *= 1.15; atkAdd += 3; notes.push('командир: +15% HP, +3 ATK'); }
    if (ref.lvl > 0) { hpMult *= 1 + 0.06 * ref.lvl; atkAdd += ref.lvl; defAdd += ref.lvl; notes.push(`уровень ${ref.lvl}: +${6 * ref.lvl}% HP, +${ref.lvl} ATK/DEF`); }
    if (ref.wounded > 0) { hpMult *= 0.65; notes.push('ранен: −35% HP'); }
    if (region) {
      if (asDefender) {
        const T = TERRAIN[region.terrain];
        let b = T.def; if (region.building === 'fort') b += 0.25; if (region.building === 'base') b += 0.10;
        if (region.owner && G.factions[region.owner].capital === region.id) b += CAPITAL_DEF;
        if (b > 0) {
          const parts = [T.name.toLowerCase()];
          if (region.owner && G.factions[region.owner].capital === region.id) parts.push('столица');
          if (region.building) parts.push(BUILDINGS[region.building].name.toLowerCase());
          hpMult *= 1 + b; notes.push(`${parts.join(' + ')}: +${Math.round(b * 100)}% HP защитнику`);
        }
      } else if (region.building === 'base') { atkAdd += 3; notes.push('база: +3 ATK'); }
    }
    return { fighter: Object.assign({}, base, { hp: Math.round(base.hp * hpMult), atk: base.atk + atkAdd, def: base.def + defAdd }), notes };
  }

  function defenderOf(G, to) {
    if (to.garrison) return { ref: refOf(G, to.owner, to.garrison), faction: to.owner };
    if (to.owner === null) return { ref: { id: 'militia_' + to.id, wounded: 0, acted: false, commander: false }, faction: null, neutral: true };
    return null;
  }

  /** Откуда идёт удар: сосед цели, которым владеет фракция (база в приоритете, затем собственный регион бойца). */
  function stagingFor(G, fid, fighterId, toIdx) {
    const own = neighbors(toIdx).filter(n => G.regions[n].owner === fid);
    if (!own.length) return -1;
    const loc = locationOf(G, fid, fighterId);
    if (loc >= 0) return own.includes(loc) ? loc : -1;          // гарнизон бьёт только соседей своего региона
    return own.find(n => G.regions[n].building === 'base') ?? own[0];
  }

  function attackCheck(G, fid, fighterId, toIdx) {
    const to = G.regions[toIdx], ref = refOf(G, fid, fighterId);
    if (!to) return 'Нет такого региона';
    if (!ref) return 'Боец не из твоей армии';
    if (to.owner === fid) return 'Нельзя атаковать свой регион';
    if (ref.acted) return 'Этот боец уже действовал в этом ходу';
    if (ref.wounded > 0) return 'Боец ранен и не может атаковать';
    if (stagingFor(G, fid, fighterId, toIdx) < 0) {
      return locationOf(G, fid, fighterId) >= 0 ? 'Гарнизон бьёт только соседние регионы. Резерв может бить любой приграничный' : 'Атаковать можно только регионы рядом с твоими землями';
    }
    return '';
  }

  function prepareBattle(G, fid, fighterId, toIdx) {
    const err = attackCheck(G, fid, fighterId, toIdx);
    if (err) return { error: err };
    const to = G.regions[toIdx], fromIdx = stagingFor(G, fid, fighterId, toIdx), from = G.regions[fromIdx];
    const att = combatant(G, refOf(G, fid, fighterId), from, false);
    const d = defenderOf(G, to);
    if (!d) return { undefended: true, attacker: att.fighter, notesAttacker: att.notes, odds: 1, to, from, fromIdx, fid, fighterId };
    const def = combatant(G, d.ref, to, true);
    return {
      attacker: att.fighter, defender: def.fighter, notesAttacker: att.notes, notesDefender: def.notes,
      odds: E.winProb(att.fighter, def.fighter), neutral: !!d.neutral, to, from, fromIdx, fid, fighterId,
    };
  }

  function addLog(G, text) { G.log.unshift(text); G.log = G.log.slice(0, 60); }

  function resolveBattle(G, fid, fighterId, toIdx, attackerWon) {
    const to = G.regions[toIdx];
    const defFid = to.owner;
    const attRef = refOf(G, fid, fighterId);
    const fromIdx = stagingFor(G, fid, fighterId, toIdx);
    const attName = fighterData(G, attRef.id).name;
    const rep = { attacker: fid, defender: defFid, from: fromIdx, to: toIdx, fighterId, captured: false, loot: 0, text: '' };
    attRef.acted = true;

    const d = defenderOf(G, to);
    if (attackerWon) {
      const loot = regionIncome(to) * 2 + (defFid ? 10 : 0);
      if (d && d.ref && !d.neutral) { d.ref.wounded = WOUND_TURNS; d.ref.acted = true; }
      const wasCapital = defFid && G.factions[defFid].capital === to.id;
      const loc = locationOf(G, fid, fighterId);
      if (loc >= 0) G.regions[loc].garrison = null;
      to.owner = fid; to.garrison = fighterId;
      if (to.building === 'base') to.building = null;
      G.factions[fid].gold += loot;
      rep.captured = true; rep.loot = loot;
      rep.text = `${attName} захватывает «${to.name}»${defFid ? ` у ${G.factions[defFid].name}` : ''} (+${loot}₲)`;
      if (wasCapital) { rep.capital = true; rep.text += ' — СТОЛИЦА ПАЛА'; eliminate(G, defFid, fid); }
      else if (defFid) checkElimination(G, defFid);
    } else {
      attRef.wounded = WOUND_TURNS;
      rep.text = `${attName} терпит поражение у «${to.name}»`;
    }
    addLog(G, `Ход ${G.turn}: ${rep.text}`);
    return rep;
  }

  /** Падение столицы = конец фракции: земли становятся ничейными, бойцы уходят «на рынок». */
  function eliminate(G, fid) {
    const f = G.factions[fid];
    G.regions.forEach(r => { if (r.owner === fid) { r.owner = null; r.garrison = null; r.building = null; } });
    f.eliminated = true; f.fighters = []; f.gold = 0;
    addLog(G, `Ход ${G.turn}: фракция ${f.name} разгромлена — её земли стали ничейными`);
  }

  function checkElimination(G, fid) {
    const f = G.factions[fid];
    if (!f.eliminated && regionsOf(G, fid).length === 0) {
      f.eliminated = true; f.fighters = [];
      addLog(G, `Ход ${G.turn}: фракция ${f.name} уничтожена`);
    }
  }

  function autoBattle(G, fid, fighterId, toIdx, rng, skillful) {
    const pb = prepareBattle(G, fid, fighterId, toIdx);
    if (pb.error) return null;
    if (pb.undefended) return Object.assign(resolveBattle(G, fid, fighterId, toIdx, true), { auto: true, undefended: true });
    const s = E.createFight(pb.attacker, pb.defender, 'a', rng.int(1, 2147483646));
    while (!s.finished) E.playRound(s, skillful ? skillPick(s) : E.aiPick(s, s.a, s.b).index);
    const replay = { a: pb.attacker, b: pb.defender, rounds: s.rounds, result: E.resultOf(s) };
    return Object.assign(resolveBattle(G, fid, fighterId, toIdx, s.winner === 'a'), { auto: true, rounds: s.rounds.length, replay });
  }
  function skillPick(s) {
    const { moves, hint } = E.getUserMoves(s);
    const av = moves.filter(m => m.available);
    const beat = av.filter(m => E.BEATS[m.type] === hint);
    if (beat.length) return beat.sort((a, b) => b.base_dmg - a.base_dmg)[0].index;
    const ult = av.find(m => m.type === 'ultimate'); if (ult && s.rng.random() < 0.6) return ult.index;
    return av.sort((a, b) => b.base_dmg * b.accuracy - a.base_dmg * a.accuracy)[0].index;
  }

  function recruit(G, fid, fighterId) {
    const f = G.factions[fid], data = byId(fighterId);
    if (!data) return { ok: false, error: 'Боец не найден' };
    if (!availableMercs(G).some(m => m.id === fighterId)) return { ok: false, error: 'Этого бойца уже нанял кто-то другой' };
    if (f.fighters.length >= ARMY_MAX) return { ok: false, error: `Не больше ${ARMY_MAX} бойцов в армии` };
    const price = priceOf(data);
    if (f.gold < price) return { ok: false, error: `Не хватает монет (нужно ${price}₲)` };
    f.gold -= price;
    f.fighters.push({ id: fighterId, wounded: 0, acted: false, commander: false, lvl: 0 });
    return { ok: true, price };
  }

  const trainCost = (ref) => 40 + 35 * (ref.lvl || 0);
  function train(G, fid, fighterId) {
    const f = G.factions[fid], ref = refOf(G, fid, fighterId);
    if (!ref) return { ok: false, error: 'Боец не из твоей армии' };
    if ((ref.lvl || 0) >= MAX_LVL) return { ok: false, error: 'Максимальный уровень' };
    const cost = trainCost(ref);
    if (f.gold < cost) return { ok: false, error: `Не хватает монет (нужно ${cost}₲)` };
    f.gold -= cost; ref.lvl = (ref.lvl || 0) + 1;
    return { ok: true, cost, lvl: ref.lvl };
  }

  function dismiss(G, fid, fighterId) {
    const f = G.factions[fid], ref = refOf(G, fid, fighterId);
    if (!ref || ref.commander) return { ok: false, error: 'Командира нельзя распустить' };
    G.regions.forEach(r => { if (r.owner === fid && r.garrison === fighterId) r.garrison = null; });
    f.fighters = f.fighters.filter(x => x.id !== fighterId);
    return { ok: true };
  }

  function assign(G, fid, fighterId, regionIdx) {
    const ref = refOf(G, fid, fighterId), r = G.regions[regionIdx];
    if (!ref) return { ok: false, error: 'Боец не из твоей армии' };
    if (!r || r.owner !== fid) return { ok: false, error: 'Назначать можно только в свои регионы' };
    if (r.garrison === fighterId) return { ok: false, error: 'Боец уже здесь' };
    if (r.garrison) return { ok: false, error: 'В регионе уже есть гарнизон — сначала освободи его' };
    const loc = locationOf(G, fid, fighterId);
    if (loc >= 0) {
      if (ref.acted) return { ok: false, error: 'Этот боец уже действовал в этом ходу' };
      G.regions[loc].garrison = null; ref.acted = true;
    }
    r.garrison = fighterId;
    return { ok: true };
  }

  function unassign(G, fid, regionIdx) {
    const r = G.regions[regionIdx];
    if (!r || r.owner !== fid || !r.garrison) return { ok: false, error: 'Тут нет гарнизона' };
    const ref = refOf(G, fid, r.garrison);
    if (ref.acted) return { ok: false, error: 'Этот боец уже действовал в этом ходу' };
    r.garrison = null;
    return { ok: true };
  }

  function build(G, fid, regionIdx, kind) {
    const f = G.factions[fid], r = G.regions[regionIdx], b = BUILDINGS[kind];
    if (!b) return { ok: false, error: 'Неизвестная постройка' };
    if (!r || r.owner !== fid) return { ok: false, error: 'Строить можно только в своих регионах' };
    if (r.building) return { ok: false, error: 'Здесь уже есть постройка' };
    if (f.gold < b.cost) return { ok: false, error: `Не хватает монет (нужно ${b.cost}₲)` };
    f.gold -= b.cost; r.building = kind;
    return { ok: true, cost: b.cost };
  }

  function buyPrice(G, regionIdx) { const r = G.regions[regionIdx]; return Math.round(40 + 55 * r.power + regionIncome(r) * 3); }
  function buyRegion(G, fid, regionIdx) {
    const f = G.factions[fid], r = G.regions[regionIdx];
    if (!r || r.owner !== null) return { ok: false, error: 'Купить можно только ничейный регион' };
    if (!neighbors(regionIdx).some(n => G.regions[n].owner === fid)) return { ok: false, error: 'Регион должен граничить с твоими землями' };
    const price = buyPrice(G, regionIdx);
    if (f.gold < price) return { ok: false, error: `Не хватает монет (нужно ${price}₲)` };
    f.gold -= price; r.owner = fid;
    addLog(G, `Ход ${G.turn}: ${f.name} выкупает «${r.name}» (−${price}₲)`);
    return { ok: true, price };
  }

  function startOfTurn(G, fid, rep) {
    const f = G.factions[fid];
    if (f.eliminated) return;
    const inc = income(G, fid), up = upkeep(G, fid);
    f.gold += inc - up;
    while (f.gold < 0) {
      const mercs = f.fighters.filter(r => !r.commander).sort((a, b) => upkeepOf(byId(a.id)) - upkeepOf(byId(b.id)));
      if (!mercs.length) { f.gold = 0; break; }
      dismiss(G, fid, mercs[0].id);
      f.gold += priceOf(byId(mercs[0].id)) * 0.3 | 0;
      if (rep) rep.push(`${f.name}: не хватило денег на содержание — ${byId(mercs[0].id).name} уходит`);
    }
    f.fighters.forEach(r => {
      const loc = locationOf(G, fid, r.id);
      const healFast = loc >= 0 && G.regions[loc].building === 'base';
      if (r.wounded > 0) r.wounded = healFast ? 0 : r.wounded - 1;
      r.acted = false;
    });
    return { income: inc, upkeep: up };
  }

  function aiTurn(G, fid, rng, rep) {
    if (G.factions[fid].eliminated) return;
    startOfTurn(G, fid, rep);
    aiAct(G, fid, rng, rep);
  }
  function aiAct(G, fid, rng, rep, opts) {
    opts = opts || {};
    const f = G.factions[fid];
    if (f.eliminated) return;
    const minOdds = opts.minOdds != null ? opts.minOdds : DIFFS[G.diff || 'normal'].aiMinOdds;

    const regs0 = regionsOf(G, fid);
    const want = Math.min(regs0.length + 1, 8);
    if (f.gold >= 80 && f.fighters.length < want) {
      const affordable = availableMercs(G).filter(m => priceOf(m) <= f.gold - 20);
      if (affordable.length) {
        const best = affordable.slice(-Math.max(1, Math.ceil(affordable.length / 3)));
        recruit(G, fid, best[Math.floor(rng.random() * best.length)].id);
      }
    }
    for (let k = 0; k < 3 && f.gold >= 160; k++) {
      const cand = f.fighters.filter(r => (r.lvl || 0) < MAX_LVL).sort((a, b) => (a.lvl || 0) - (b.lvl || 0));
      if (!cand.length || f.gold < trainCost(cand[0]) + 60) break;
      train(G, fid, cand[0].id);
    }
    const bench = f.fighters.filter(r => locationOf(G, fid, r.id) < 0 && r.wounded === 0)
      .sort((a, b) => (b.commander ? 1 : 0) - (a.commander ? 1 : 0));
    const empty = regionsOf(G, fid).filter(r => !r.garrison)
      .sort((a, b) => (b.id === f.capital ? 99 : borderScore(G, b)) - (a.id === f.capital ? 99 : borderScore(G, a)));
    bench.forEach(r => { const t = empty.shift(); if (t) t.garrison = r.id; });

    const mine = regionsOf(G, fid);
    if (f.gold >= 150) {
      const free = mine.filter(r => !r.building);
      if (free.length) {
        const rich = free.slice().sort((a, b) => regionIncome(b) - regionIncome(a))[0];
        const border = free.slice().sort((a, b) => borderScore(G, b) - borderScore(G, a))[0];
        build(G, fid, (rng.random() < 0.5 ? rich : border).id, rng.random() < 0.5 ? 'market' : 'fort');
      }
    }

    let attacks = 0;
    const ready = f.fighters.filter(r => !r.acted && r.wounded === 0 && locationOf(G, fid, r.id) !== f.capital)
      .sort((a, b) => ((locationOf(G, fid, a.id) < 0) ? 0 : 1) - ((locationOf(G, fid, b.id) < 0) ? 0 : 1) || rng.random() - 0.5);
    for (const ref of ready) {
      if (attacks >= MAX_ATTACKS_AI) break;
      if (ref.acted || ref.wounded > 0) continue;
      let best = null;
      const cand = new Set();
      regionsOf(G, fid).forEach(r => neighbors(r.id).forEach(n => { if (G.regions[n].owner !== fid) cand.add(n); }));
      cand.forEach(n => {
        const pb = prepareBattle(G, fid, ref.id, n);
        if (pb.error) return;
        const target = G.regions[n];
        const isCap = target.owner && G.factions[target.owner].capital === n;
        const bonus = (target.owner === PLAYER ? 0.04 : 0) + regionIncome(target) / 200 + (pb.undefended ? 0.3 : 0) + (isCap ? 0.1 : 0);
        const score = pb.odds + bonus;
        const need = pb.undefended ? 0 : minOdds;
        if (pb.odds >= need && (!best || score > best.score)) best = { n, score, odds: pb.odds };
      });
      if (best) {
        const wasPlayer = G.regions[best.n].owner === PLAYER;
        const r = autoBattle(G, fid, ref.id, best.n, rng, opts.skill);
        if (r) {
          attacks++;
          rep.push({ text: r.text, ai: true, vsPlayer: wasPlayer, captured: r.captured, capital: !!r.capital, region: best.n, from: r.from, fighterId: ref.id,
            attacker: fid, defender: r.defender, replay: r.replay, undefended: !!r.undefended });
        }
      }
    }

    if (f.gold >= 180) {
      const options = [];
      regionsOf(G, fid).forEach(r => neighbors(r.id).forEach(n => { if (G.regions[n].owner === null) options.push(n); }));
      if (options.length) {
        const n = options.sort((a, b) => buyPrice(G, a) - buyPrice(G, b))[0];
        if (f.gold >= buyPrice(G, n) + 60) { const r = buyRegion(G, fid, n); if (r.ok) rep.push({ text: `${f.name} выкупает «${G.regions[n].name}»`, ai: true, region: n, bought: true, attacker: fid }); }
      }
    }
  }

  function borderScore(G, r) {
    return neighbors(r.id).filter(n => G.regions[n].owner !== r.owner).length;
  }

  function status(G) {
    const mine = regionsOf(G, PLAYER).length;
    return { regions: mine, target: WIN_REGIONS, turn: G.turn, maxTurns: MAX_TURNS, gold: player(G).gold,
      income: income(G, PLAYER), upkeep: upkeep(G, PLAYER) };
  }

  function checkEnd(G) {
    if (G.over) return G.over;
    const mine = regionsOf(G, PLAYER).length;
    const rivals = ['a', 'b', 'c'].map(k => G.factions[k]);
    if (G.factions[PLAYER].eliminated || mine === 0) G.over = { winner: null, reason: 'defeat' };
    else if (rivals.every(r => r.eliminated)) G.over = { winner: PLAYER, reason: 'eliminated' };
    else if (mine >= WIN_REGIONS) G.over = { winner: PLAYER, reason: 'regions' };
    else if (G.turn > MAX_TURNS) {
      const best = Math.max(...rivals.map(r => regionsOf(G, r.id).length));
      G.over = mine >= best ? { winner: PLAYER, reason: 'time' } : { winner: null, reason: 'time' };
    }
    return G.over;
  }

  function endTurn(G) {
    if (G.over) return { events: [], income: null };
    const rng = E.createRng((G.seed + G.turn * 7919) >>> 0);
    const events = [];
    ['a', 'b', 'c'].forEach(k => {
      aiTurn(G, k, rng, events);
      checkEnd(G);
    });
    G.turn += 1;
    const inc = startOfTurn(G, PLAYER, events);
    checkEnd(G);
    return { events, income: inc };
  }

  const api = {
    W, H, N, MAX_TURNS, WIN_REGIONS, START_GOLD, PLAYER, FACTION_COLORS, TERRAIN, BUILDINGS, RECRUIT, WOUND_TURNS, DIFFS, ARMY_MAX, MAX_LVL, CAPITAL_DEF,
    train, trainCost, eliminate, skillPick,
    newCampaign, neighbors, dist, player, regionsOf, refOf, locationOf, regionIncome, income, upkeep, netIncome,
    priceOf, upkeepOf, availableMercs, combatant, defenderOf, attackCheck, prepareBattle, resolveBattle, autoBattle, stagingFor,
    recruit, dismiss, assign, unassign, build, buyPrice, buyRegion, endTurn, status, checkEnd, militia, fighterData, aiAct, startOfTurn, addLog,
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.ArenaCampaign = api;
})(typeof window !== 'undefined' ? window : globalThis);
