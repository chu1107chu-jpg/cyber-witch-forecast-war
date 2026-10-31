const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const ARENA = path.join(__dirname, '..', 'static', 'arena');

global.window = {};
require(path.join(ARENA, 'fighters.js'));
const E = require(path.join(ARENA, 'engine.js'));
global.ArenaEngine = E;
const Store = require(path.join(ARENA, 'store.js'));
const F = window.ARENA_FIGHTERS;

const playAuto = (state, pick) => {
  let last;
  while (!state.finished) {
    const { moves, hint } = E.getUserMoves(state);
    last = E.playRound(state, pick(moves, hint, state));
  }
  return last;
};
const firstAvail = (moves) => moves.find(m => m.available).index;
const memStorage = () => { const m = {}; return { getItem: k => (k in m ? m[k] : null), setItem: (k, v) => { m[k] = String(v); }, removeItem: k => { delete m[k]; } }; };

test('данные: 42 бойца, у каждого 4 типа ударов и валидный аватар', () => {
  assert.equal(F.length, 42);
  for (const f of F) {
    assert.deepEqual(f.moves.map(m => m.type).sort(), ['heavy', 'light', 'special', 'ultimate']);
    assert.match(f.avatar, /^img\/.+\.(jpg|svg)$/);
    assert.ok(require('node:fs').existsSync(path.join(ARENA, f.avatar)), 'нет файла ' + f.avatar);
  }
});

test('бой детерминирован по seed', () => {
  const run = () => { const s = E.createFight(F[0], F[1], 'a', 42); playAuto(s, firstAvail); return [s.winner, s.method, s.a.hp, s.b.hp, s.rounds.length]; };
  assert.deepEqual(run(), run());
});

test('победитель определяется ходом боя: нокаут или больше HP% (никакого 70/30 по хэшу)', () => {
  const rng = E.createRng(1);
  for (let i = 0; i < 1500; i++) {
    const a = F[Math.floor(rng.random() * F.length)]; let b;
    do { b = F[Math.floor(rng.random() * F.length)]; } while (b.id === a.id);
    const s = E.createFight(a, b, rng.random() < 0.5 ? 'a' : 'b', 500 + i);
    playAuto(s, (moves) => { const av = moves.filter(m => m.available); return av[Math.floor(rng.random() * av.length)].index; });
    const last = s.rounds[s.rounds.length - 1];
    if (s.method === 'KO') {
      const loser = s.winner === 'a' ? last.hp_b : last.hp_a;
      assert.equal(loser, 0, 'при нокауте проигравший на 0 HP');
    } else {
      assert.equal(s.rounds.length, E.C.ROUNDS);
      const ra = last.hp_a / s.a.maxHp, rb = last.hp_b / s.b.maxHp;
      if (Math.abs(ra - rb) >= 0.01) assert.equal(s.winner, ra > rb ? 'a' : 'b', 'по очкам побеждает тот, у кого больше HP%');
    }
    assert.ok(s.rounds.length <= E.C.ROUNDS);
  }
});

test('регресс: баффы действуют на атакующего и не подменяют соперника', () => {
  const buffer = { id: 'buff', name: 'Баффер', hp: 200, atk: 20, def: 10, spd: 5, luck: 5,
    moves: ['light', 'heavy', 'special', 'ultimate'].map(t => ({ name: t, type: t, base_dmg: 10, accuracy: 100, effect: 'atk_up' })) };
  const dummy = { id: 'dummy', name: 'Манекен', hp: 300, atk: 1, def: 1, spd: 1, luck: 1,
    moves: ['light', 'heavy', 'special', 'ultimate'].map(t => ({ name: t, type: t, base_dmg: 1, accuracy: 100 })) };
  const s = E.createFight(buffer, dummy, 'a', 7);
  playAuto(s, firstAvail);
  assert.equal(s.b.id, 'dummy'); assert.equal(s.b.name, 'Манекен');
  assert.equal(s.b.atk, 1, 'у соперника атака не растёт');
  assert.ok(s.a.atk > 20, 'у атакующего атака выросла');
});

test('регресс: hp_regen лечит атакующего, а не соперника', () => {
  const healer = { id: 'h', name: 'Лекарь', hp: 200, atk: 5, def: 5, spd: 5, luck: 1,
    moves: ['light', 'heavy', 'special', 'ultimate'].map(t => ({ name: t, type: t, base_dmg: 1, accuracy: 100, effect: 'hp_regen' })) };
  const hitter = { id: 'x', name: 'Бьющий', hp: 200, atk: 60, def: 5, spd: 5, luck: 1,
    moves: ['light', 'heavy', 'special', 'ultimate'].map(t => ({ name: t, type: t, base_dmg: 40, accuracy: 100 })) };
  const s = E.createFight(healer, hitter, 'a', 3);
  const r = E.playRound(s, 0);
  assert.ok(r.effect_a.includes('восстановил') || s.a.hp === s.a.maxHp, 'лечение описано');
  assert.ok(s.b.hp <= s.b.maxHp);
});

test('ульта: не раньше 3-го раунда и только один раз', () => {
  const s = E.createFight(F[2], F[3], 'a', 11);
  assert.equal(E.getUserMoves(s).moves[3].available, false);
  assert.throws(() => E.playRound(s, 3), /недоступен/);
  E.playRound(s, 0); E.playRound(s, 0);
  if (!s.finished) {
    assert.equal(E.getUserMoves(s).moves[3].available, true);
    E.playRound(s, 3);
    if (!s.finished) assert.equal(E.getUserMoves(s).moves[3].available, false, 'вторая ульта запрещена');
  }
});

test('подсказка про ход соперника верна примерно в 60% случаев и привязана к реальному ходу', () => {
  let n = 0, truth = 0;
  for (let i = 0; i < 400; i++) {
    const s = E.createFight(F[i % F.length], F[(i + 7) % F.length], 'a', 9000 + i);
    for (let r = 0; r < 3 && !s.finished; r++) {
      const hint = E.getUserMoves(s).hint, real = s.nextAi.type;
      n++; if (hint === real) truth++;
      E.playRound(s, E.getUserMoves(s).moves.find(m => m.available).index);
    }
  }
  const p = truth / n;
  assert.ok(p > 0.5 && p < 0.7, 'доля верных подсказок ' + p.toFixed(2));
});

test('баланс: бой честный по сторонам, нокауты бывают, фаворит выигрывает чаще', () => {
  const rng = E.createRng(2024); let aWins = 0, ko = 0, favWins = 0, favN = 0; const N = 3000;
  for (let i = 0; i < N; i++) {
    const a = F[Math.floor(rng.random() * F.length)]; let b;
    do { b = F[Math.floor(rng.random() * F.length)]; } while (b.id === a.id);
    const s = E.createFight(a, b, 'a', 70000 + i);
    playAuto(s, (moves, hint, st) => { const u = st.a, o = st.b; return E.aiPick(st, u, o).index; });
    if (s.winner === 'a') aWins++; if (s.method === 'KO') ko++;
    const pa = E.winProb(a, b);
    if (Math.abs(pa - 0.5) > 0.15) { favN++; if ((pa > 0.5) === (s.winner === 'a')) favWins++; }
  }
  assert.ok(aWins / N > 0.46 && aWins / N < 0.54, 'сторона A выигрывает ' + (aWins / N).toFixed(3));
  assert.ok(ko / N > 0.2 && ko / N < 0.6, 'доля нокаутов ' + (ko / N).toFixed(2));
  assert.ok(favWins / favN > 0.6, 'фавориты выигрывают ' + (favWins / favN).toFixed(2));
});

test('коэффициенты: фаворит платит меньше андердога, границы соблюдены', () => {
  const strong = F.reduce((x, y) => (E.power(x) > E.power(y) ? x : y)), weak = F.reduce((x, y) => (E.power(x) < E.power(y) ? x : y));
  const p = E.winProb(strong, weak);
  assert.ok(p > 0.5 && p <= 0.88);
  assert.ok(E.payoutMult(p) < E.payoutMult(1 - p));
  assert.ok(E.payoutMult(0.5) > 1.1 && E.payoutMult(0.01) <= 4.0 && E.payoutMult(0.99) >= 1.1);
});

test('кошелёк: ставка, победа, серия, колесо, бонус, страховка', () => {
  const st = Store.createStore(memStorage());
  assert.equal(st.get().balance, 100);
  assert.deepEqual(st.placeBet(10), { ok: true, amount: 10 }); assert.equal(st.get().balance, 90);
  assert.equal(st.placeBet(1000).ok, false); assert.equal(st.placeBet(-5).ok, false);
  const w = st.settle({ fighterA: 'a', fighterB: 'b', userSide: 'a', winnerId: 'a', userWon: true, bet: 10, mult: 2 });
  assert.equal(w.payout, 20); assert.equal(w.balance, 110); assert.equal(st.get().pendingSpin, 20);
  const sp = st.spin(() => 0.0);
  assert.equal(sp.mult, 0.5); assert.equal(sp.payout, 10); assert.equal(st.get().balance, 100);
  assert.equal(st.spin().ok, false, 'колесо только один раз');
  st.placeBet(10); const w2 = st.settle({ fighterA: 'a', fighterB: 'b', userSide: 'a', winnerId: 'a', userWon: true, bet: 10, mult: 2 });
  assert.equal(w2.streakMult, 1.2); assert.equal(w2.payout, 24);
  assert.equal(st.claimDaily().ok, true); assert.equal(st.claimDaily().ok, false);
  for (let i = 0; i < 3; i++) assert.equal(st.placeBet(0).ok, true);
  assert.equal(st.placeBet(0).ok, false);
});

test('кошелёк: страховка от тупика и устойчивость к битым данным', () => {
  const m = memStorage(); m.setItem('political_arena_v2', '{не json');
  const st = Store.createStore(m); assert.equal(st.get().balance, 100);
  const s = st.get(); s.balance = 1; s.freeUsed = 3;
  st.placeBet(1);
  const r = st.settle({ fighterA: 'a', fighterB: 'b', userSide: 'a', winnerId: 'b', userWon: false, bet: 1, mult: 2 });
  assert.equal(r.bailout, true); assert.equal(st.get().balance, 50);
});
