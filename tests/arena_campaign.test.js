// Тесты кампании «Political Arena».  Запуск:  node --test tests/
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const ARENA = path.join(__dirname, '..', 'static', 'arena');

global.window = {};
require(path.join(ARENA, 'fighters.js'));
const E = require(path.join(ARENA, 'engine.js'));
global.ArenaEngine = E;
const C = require(path.join(ARENA, 'campaign.js'));
const F = window.ARENA_FIGHTERS;
const P = C.PLAYER;

const fresh = (seed = 1, leader = F[0].id, diff = 'normal') => C.newCampaign(leader, seed, diff);

/** Инварианты состояния — проверяются после каждого хода в симуляциях. */
function checkInvariants(G, where = '') {
  const seen = new Set();
  G.regions.forEach(r => {
    if (r.garrison) {
      assert.ok(r.owner, `${where}: гарнизон в ничьём регионе ${r.id}`);
      const ref = C.refOf(G, r.owner, r.garrison);
      assert.ok(ref, `${where}: гарнизон ${r.garrison} не числится в армии ${r.owner}`);
      assert.ok(!seen.has(r.garrison), `${where}: боец ${r.garrison} стоит в двух регионах`);
      seen.add(r.garrison);
    }
    if (r.owner === null) assert.equal(r.building, null, `${where}: постройка в ничьём регионе`);
  });
  const all = new Set();
  Object.values(G.factions).forEach(f => {
    assert.ok(Number.isFinite(f.gold), `${where}: золото не число у ${f.id}`);
    assert.ok(f.gold >= 0, `${where}: отрицательное золото у ${f.id}: ${f.gold}`);
    assert.ok(f.fighters.length <= C.ARMY_MAX, `${where}: армия больше лимита у ${f.id}`);
    if (f.eliminated) assert.equal(C.regionsOf(G, f.id).length, 0, `${where}: уничтоженная фракция владеет землёй`);
    f.fighters.forEach(x => {
      assert.ok(!all.has(x.id), `${where}: боец ${x.id} служит двум фракциям`);
      all.add(x.id);
      assert.ok(x.lvl >= 0 && x.lvl <= C.MAX_LVL);
      assert.ok(x.wounded >= 0 && x.wounded <= C.WOUND_TURNS);
    });
  });
}

test('карта: 30 регионов, уникальные имена, симметричные соседи, связность', () => {
  const G = fresh();
  assert.equal(G.regions.length, C.N);
  assert.equal(new Set(G.regions.map(r => r.name)).size, C.N);
  for (let i = 0; i < C.N; i++) C.neighbors(i).forEach(n => assert.ok(C.neighbors(n).includes(i)));
  const seen = new Set([0]), q = [0];
  while (q.length) C.neighbors(q.pop()).forEach(n => { if (!seen.has(n)) { seen.add(n); q.push(n); } });
  assert.equal(seen.size, C.N);
});

test('старт: 4 фракции по углам, у каждой столица и командир, остальное ничейное с ополчением', () => {
  const G = fresh(7, 'trump');
  assert.deepEqual(Object.keys(G.factions), ['p', 'a', 'b', 'c']);
  assert.equal(G.factions.p.leaderId, 'trump');
  assert.equal(new Set(Object.values(G.factions).map(f => f.leaderId)).size, 4);
  Object.values(G.factions).forEach(f => {
    const cap = G.regions[f.capital];
    assert.equal(cap.owner, f.id); assert.equal(cap.garrison, f.leaderId); assert.equal(cap.terrain, 'city');
    assert.equal(f.fighters.length, 1); assert.ok(f.fighters[0].commander);
  });
  assert.equal(C.regionsOf(G, null).length, C.N - 4);
  C.regionsOf(G, null).forEach(r => { const m = C.militia(r); assert.ok(m.hp > 0 && m.moves.length === 4); });
  assert.equal(G.factions.p.gold, C.START_GOLD);
  checkInvariants(G, 'старт');
});

test('кампания детерминирована по seed и переживает JSON-сохранение', () => {
  const run = (G0) => {
    const G = G0 || fresh(42);
    for (let i = 0; i < 12; i++) C.endTurn(G);
    return G;
  };
  const a = run(), b = run();
  assert.deepEqual(a, b);
  const c = JSON.parse(JSON.stringify(fresh(42)));
  for (let i = 0; i < 12; i++) C.endTurn(c);
  assert.deepEqual(a, c);
});

test('роспись: у каждого бойца допустимая редкость, цена и содержание', () => {
  F.forEach(f => assert.ok(C.RECRUIT[f.tier || 'common'], `неизвестная редкость у ${f.id}: ${f.tier}`));
  const G = fresh();
  const mercs = C.availableMercs(G);
  assert.equal(mercs.length, F.length - 4);
  assert.ok(!mercs.some(m => Object.values(G.factions).some(f => f.leaderId === m.id)));
});

test('экономика: доход по местности и рынкам, содержание наёмников, лидер бесплатный', () => {
  const G = fresh(3);
  const cap = G.regions[G.factions.p.capital];
  assert.equal(C.income(G, P), C.TERRAIN.city.income);
  assert.equal(C.upkeep(G, P), 0);
  cap.building = 'market';
  assert.equal(C.income(G, P), C.TERRAIN.city.income + 12);
  G.factions.p.gold = 500;
  const merc = C.availableMercs(G)[0];
  assert.ok(C.recruit(G, P, merc.id).ok);
  assert.equal(G.factions.p.gold, 500 - C.priceOf(merc));
  assert.equal(C.upkeep(G, P), C.upkeepOf(merc));
  assert.equal(C.netIncome(G, P), C.income(G, P) - C.upkeepOf(merc));
  // уровень сложности меняет только доход ИИ
  const H = fresh(3, F[0].id, 'hard'), Ez = fresh(3, F[0].id, 'easy');
  assert.equal(C.income(H, P), C.income(Ez, P));
  assert.ok(C.income(H, 'a') > C.income(Ez, 'a'));
});

test('найм: нет денег / уже нанят / лимит армии / чужой боец', () => {
  const G = fresh(5);
  const list = C.availableMercs(G);
  G.factions.p.gold = 0;
  assert.equal(C.recruit(G, P, list[0].id).ok, false);
  G.factions.p.gold = 10000;
  assert.ok(C.recruit(G, P, list[0].id).ok);
  assert.equal(C.recruit(G, P, list[0].id).ok, false, 'второй раз нанять нельзя');
  assert.equal(C.recruit(G, P, G.factions.a.leaderId).ok, false, 'лидера ИИ нанять нельзя');
  assert.equal(C.recruit(G, P, 'no_such').ok, false);
  for (let i = 1; i < 12; i++) { const m = C.availableMercs(G)[0]; if (m) C.recruit(G, P, m.id); }
  assert.equal(G.factions.p.fighters.length, C.ARMY_MAX);
  checkInvariants(G);
});

test('резерв атакует приграничный регион, гарнизон — только соседей своего региона', () => {
  const G = fresh(11);
  G.factions.p.gold = 1000;
  const merc = C.availableMercs(G)[0];
  C.recruit(G, P, merc.id);
  const cap = G.factions.p.capital;
  const near = C.neighbors(cap)[0];
  const far = G.regions.find(r => !C.neighbors(cap).includes(r.id) && r.id !== cap && r.owner === null &&
    !C.neighbors(r.id).some(n => G.regions[n].owner === P));
  assert.equal(C.attackCheck(G, P, merc.id, near), '');                   // резерв → сосед столицы
  assert.notEqual(C.attackCheck(G, P, merc.id, far.id), '');              // далёкий регион недоступен
  assert.equal(C.attackCheck(G, P, G.factions.p.leaderId, near), '');     // командир в столице: соседи — можно
  assert.notEqual(C.attackCheck(G, P, G.factions.p.leaderId, cap), '');   // свой регион — нельзя
  const ref = C.refOf(G, P, merc.id);
  ref.acted = true; assert.match(C.attackCheck(G, P, merc.id, near), /действовал/);
  ref.acted = false; ref.wounded = 1; assert.match(C.attackCheck(G, P, merc.id, near), /ранен/);
});

test('победа: регион переходит атакующему, у победителя опустел исходный регион', () => {
  const G = fresh(13);
  const cap = G.regions[G.factions.p.capital];
  const target = G.regions[C.neighbors(cap.id)[0]];
  const lead = G.factions.p.leaderId;
  const goldBefore = G.factions.p.gold;
  const rep = C.resolveBattle(G, P, lead, target.id, true);
  assert.ok(rep.captured);
  assert.equal(target.owner, P); assert.equal(target.garrison, lead);
  assert.equal(cap.garrison, null, 'командир ушёл из столицы');
  assert.ok(G.factions.p.gold > goldBefore);
  assert.ok(C.refOf(G, P, lead).acted);
  checkInvariants(G);
});

test('поражение: боец ранен и остаётся на месте, регион не меняется', () => {
  const G = fresh(14);
  const cap = G.regions[G.factions.p.capital];
  const target = G.regions[C.neighbors(cap.id)[0]];
  const lead = G.factions.p.leaderId;
  const rep = C.resolveBattle(G, P, lead, target.id, false);
  assert.equal(rep.captured, false);
  assert.equal(target.owner, null);
  assert.equal(cap.garrison, lead);
  assert.equal(C.refOf(G, P, lead).wounded, C.WOUND_TURNS);
});

test('пустой чужой регион берётся без боя', () => {
  const G = fresh(15);
  const r = G.regions[C.neighbors(G.factions.p.capital)[0]];
  r.owner = 'a'; r.garrison = null;               // чужой, без гарнизона
  const pb = C.prepareBattle(G, P, G.factions.p.leaderId, r.id);
  assert.ok(pb.undefended);
  const rep = C.autoBattle(G, P, G.factions.p.leaderId, r.id, E.createRng(1));
  assert.ok(rep.captured && rep.undefended);
});

test('падение столицы уничтожает фракцию: земли ничьи, бойцы свободны', () => {
  const G = fresh(16);
  const A = G.factions.a;
  const extra = G.regions[C.neighbors(A.capital)[0]];
  extra.owner = 'a'; extra.garrison = null; extra.building = 'fort';
  A.gold = 300;
  const mercId = C.availableMercs(G)[0].id;
  C.recruit(G, 'a', mercId);
  const pRegion = G.regions[C.neighbors(A.capital)[1]];
  pRegion.owner = P; pRegion.garrison = G.factions.p.leaderId; G.regions[G.factions.p.capital].garrison = null;
  const rep = C.resolveBattle(G, P, G.factions.p.leaderId, A.capital, true);
  assert.ok(rep.capital);
  assert.ok(A.eliminated);
  assert.equal(C.regionsOf(G, 'a').length, 0);
  assert.equal(extra.owner, null); assert.equal(extra.building, null);
  assert.ok(C.availableMercs(G).some(m => m.id === mercId), 'нанятые побеждённого вернулись на рынок');
  assert.ok(C.availableMercs(G).some(m => m.id === A.leaderId), 'лидер побеждённого снова доступен для найма');
  checkInvariants(G);
});

test('защитник получает бонусы: столица, форт; уровень и ранение меняют характеристики', () => {
  const G = fresh(17);
  const A = G.factions.a, cap = G.regions[A.capital];
  const raw = C.fighterData(G, A.leaderId);
  const asAtt = C.combatant(G, C.refOf(G, 'a', A.leaderId), null, false).fighter;
  assert.equal(asAtt.hp, Math.round(raw.hp * 1.15), 'командир: +15% HP');
  const asDef = C.combatant(G, C.refOf(G, 'a', A.leaderId), cap, true);
  assert.ok(asDef.fighter.hp > asAtt.hp, 'город + столица добавляют HP');
  cap.building = 'fort';
  const withFort = C.combatant(G, C.refOf(G, 'a', A.leaderId), cap, true);
  assert.ok(withFort.fighter.hp > asDef.fighter.hp);
  assert.ok(withFort.notes.some(n => /столица/.test(n)) && withFort.notes.some(n => /форт/.test(n)));
});

test('тренировка: цена растёт, максимум 5 уровней, бонусы к HP/ATK/DEF', () => {
  const G = fresh(18);
  G.factions.p.gold = 1000;
  const lead = G.factions.p.leaderId;
  const before = C.combatant(G, C.refOf(G, P, lead), null, false).fighter;
  for (let i = 0; i < C.MAX_LVL; i++) assert.ok(C.train(G, P, lead).ok);
  assert.equal(C.train(G, P, lead).ok, false, 'после максимума тренировать нельзя');
  const after = C.combatant(G, C.refOf(G, P, lead), null, false).fighter;
  assert.ok(after.hp > before.hp * 1.25 && after.atk === before.atk + C.MAX_LVL && after.def === before.def + C.MAX_LVL);
  C.refOf(G, P, lead).wounded = 1;
  const hurt = C.combatant(G, C.refOf(G, P, lead), null, false).fighter;
  assert.ok(hurt.hp < after.hp * 0.7, 'ранение −35% HP');
  G.factions.p.gold = 1;
  C.refOf(G, P, lead).lvl = 0;
  assert.equal(C.train(G, P, lead).ok, false, 'нет денег');
});

test('постройки: цена, один регион — одна постройка, только свои земли', () => {
  const G = fresh(19);
  const cap = G.factions.p.capital;
  G.factions.p.gold = 1000;
  assert.ok(C.build(G, P, cap, 'fort').ok);
  assert.equal(C.build(G, P, cap, 'market').ok, false);
  assert.equal(C.build(G, P, C.neighbors(cap)[0], 'market').ok, false, 'не свой регион');
  assert.equal(C.build(G, P, cap, 'wat').ok, false);
  assert.equal(G.factions.p.gold, 1000 - C.BUILDINGS.fort.cost);
});

test('выкуп ничейного региона: только соседний, цена списывается', () => {
  const G = fresh(20);
  const cap = G.factions.p.capital;
  const near = C.neighbors(cap).find(n => G.regions[n].owner === null);
  G.factions.p.gold = 5000;
  const far = G.regions.find(r => r.owner === null && !C.neighbors(r.id).some(n => G.regions[n].owner === P));
  assert.equal(C.buyRegion(G, P, far.id).ok, false);
  const g0 = G.factions.p.gold;
  assert.ok(C.buyRegion(G, P, near).ok);
  assert.equal(G.factions.p.gold, g0 - C.buyPrice(G, near));
  assert.equal(G.regions[near].owner, P);
  assert.equal(C.buyRegion(G, P, near).ok, false, 'уже куплен');
});

test('назначение гарнизона: из резерва бесплатно, переброска тратит действие', () => {
  const G = fresh(21);
  G.factions.p.gold = 1000;
  const m = C.availableMercs(G)[0]; C.recruit(G, P, m.id);
  const cap = G.factions.p.capital;
  const near = C.neighbors(cap)[0];
  G.regions[near].owner = P;
  assert.ok(C.assign(G, P, m.id, near).ok);
  assert.equal(C.refOf(G, P, m.id).acted, false, 'из резерва — бесплатно');
  assert.equal(C.assign(G, P, m.id, near).ok, false);
  const other = C.neighbors(near).find(n => n !== cap);
  G.regions[other].owner = P;
  assert.ok(C.assign(G, P, m.id, other).ok);
  assert.equal(C.refOf(G, P, m.id).acted, true, 'переброска тратит действие');
  assert.equal(C.assign(G, P, m.id, near).ok, false, 'второй раз за ход нельзя');
  assert.equal(C.assign(G, P, m.id, G.regions.find(r => r.owner === null).id).ok, false, 'в чужой/ничей нельзя');
  checkInvariants(G);
});

test('начало хода: доход, лечение (база лечит сразу), банкротство увольняет наёмников', () => {
  const G = fresh(22);
  const f = G.factions.p;
  f.gold = 500;
  const m = C.availableMercs(G)[0]; C.recruit(G, P, m.id);
  const lead = C.refOf(G, P, f.leaderId), merc = C.refOf(G, P, m.id);
  lead.wounded = 2; merc.wounded = 2; lead.acted = merc.acted = true;
  G.regions[f.capital].building = 'base';
  const g0 = f.gold;
  C.startOfTurn(G, P, []);
  assert.equal(lead.wounded, 0, 'на базе лечатся сразу');
  assert.equal(merc.wounded, 1, 'в резерве — по 1 за ход');
  assert.ok(!lead.acted && !merc.acted);
  assert.equal(f.gold, g0 + C.income(G, P) - C.upkeep(G, P));

  // банкротство: много наёмников, доход мал, денег нет
  const H = fresh(23);
  const hf = H.factions.p; hf.gold = 3000;
  for (let i = 0; i < 6; i++) C.recruit(H, P, C.availableMercs(H).slice(-1)[0].id);
  assert.ok(C.upkeep(H, P) > C.income(H, P));
  hf.gold = 0;
  const log = [];
  C.startOfTurn(H, P, log);
  assert.ok(hf.gold >= 0);
  assert.ok(log.length > 0 && /уходит/.test(log[0]));
  checkInvariants(H);
});

test('условия конца игры: поражение, победа по регионам, по уничтожению, по таймеру', () => {
  let G = fresh(30);
  G.regions.forEach(r => { if (r.owner === P) { r.owner = null; r.garrison = null; } });
  assert.deepEqual(C.checkEnd(G), { winner: null, reason: 'defeat' });

  G = fresh(31);
  for (let i = 0; i < C.WIN_REGIONS; i++) { const r = G.regions.find(r => r.owner === null); r.owner = P; }
  assert.deepEqual(C.checkEnd(G), { winner: P, reason: 'regions' });

  G = fresh(32);
  ['a', 'b', 'c'].forEach(k => C.eliminate(G, k));
  assert.deepEqual(C.checkEnd(G), { winner: P, reason: 'eliminated' });

  G = fresh(33); G.turn = C.MAX_TURNS + 1;
  assert.equal(C.checkEnd(G).reason, 'time');
  G = fresh(34); G.turn = C.MAX_TURNS + 1;
  G.regions.find(r => r.owner === null).owner = P;
  assert.equal(C.checkEnd(G).winner, P, 'больше всех регионов к концу — победа');
});

test('симуляция: 24 партии — инварианты держатся, каждая партия заканчивается', () => {
  let finished = 0;
  for (let g = 0; g < 24; g++) {
    const G = fresh(500 + g, F[(g * 5) % F.length].id, ['easy', 'normal', 'hard'][g % 3]);
    const rng = E.createRng(900 + g);
    for (let t = 0; t < 90 && !G.over; t++) {
      if (g % 2) C.aiAct(G, P, rng, [], { skill: g % 4 === 1 });    // половина партий — бот-игрок, остальные — пассивный
      checkInvariants(G, `партия ${g}, ход ${G.turn}, до endTurn`);
      C.checkEnd(G);
      if (G.over) break;
      C.endTurn(G);
      checkInvariants(G, `партия ${g}, ход ${G.turn}, после endTurn`);
    }
    if (G.over) finished++;
  }
  assert.equal(finished, 24, 'каждая партия должна закончиться не позже таймера');
});

test('баланс: «лёгкая» заметно проще «сложной»; пассивный игрок не побеждает', () => {
  const win = (diff, passive) => {
    let w = 0; const n = 30;
    for (let g = 0; g < n; g++) {
      const G = fresh(1000 + g, F[(g * 7) % F.length].id, diff);
      const rng = E.createRng(5000 + g);
      for (let t = 0; t < 90 && !G.over; t++) {
        if (!passive) C.aiAct(G, P, rng, [], { skill: true, minOdds: 0.5 });
        C.checkEnd(G); if (G.over) break; C.endTurn(G);
      }
      if (G.over && G.over.winner === P) w++;
    }
    return w / n;
  };
  const easy = win('easy'), hard = win('hard'), idle = win('normal', true);
  assert.ok(easy > hard + 0.1, `лёгкая ${easy} должна быть заметно проще сложной ${hard}`);
  assert.ok(easy >= 0.35 && easy <= 0.9, `лёгкая: ${easy}`);
  assert.ok(hard >= 0.05 && hard <= 0.5, `сложная: ${hard}`);
  assert.ok(idle <= 0.1, `пассивный игрок не должен побеждать: ${idle}`);
});
