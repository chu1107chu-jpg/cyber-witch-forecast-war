/* ═══════════════════════════════════════════════════════════════
   POLITICAL ARENA — кошелёк и прогресс игрока (хранится в браузере)
   Без сервера: localStorage (если недоступен — только на время сессии).
   ═══════════════════════════════════════════════════════════════ */
(function (root) {
  'use strict';
  const E = root.ArenaEngine || (typeof require !== 'undefined' ? require('./engine.js') : null);
  const KEY = 'political_arena_v2';

  function pad(n) { return String(n).padStart(2, '0'); }
  function dayStr(d) { return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; }
  const today = () => dayStr(new Date());
  const yesterday = () => { const d = new Date(); d.setDate(d.getDate() - 1); return dayStr(d); };

  function fresh() {
    return {
      v: 1, balance: E.ECON.START_BALANCE,
      wins: 0, losses: 0, streak: 0, bestStreak: 0,
      freeDate: today(), freeUsed: 0,
      dailyDate: '', dailyStreak: 0,
      history: [],
      pendingSpin: 0,          // выплата, на которую можно крутить колесо (0 — нельзя)
    };
  }

  function createStore(storage) {
    let mem = null;
    function load() {
      try {
        const raw = storage && storage.getItem(KEY);
        if (raw) { const s = JSON.parse(raw); if (s && s.v === 1) return Object.assign(fresh(), s); }
      } catch (e) { /* повреждённые данные / нет доступа — начинаем заново */ }
      return fresh();
    }
    let s = load();
    function save() {
      mem = s;
      try { storage && storage.setItem(KEY, JSON.stringify(s)); } catch (e) { /* приватный режим */ }
    }
    function rollDay() {
      if (s.freeDate !== today()) { s.freeDate = today(); s.freeUsed = 0; }
    }

    const api = {
      get() { rollDay(); return s; },
      freeLeft() { rollDay(); return Math.max(0, E.ECON.FREE_FIGHTS_PER_DAY - s.freeUsed); },
      dailyAvailable() { return s.dailyDate !== today(); },
      nextDaily() {
        const st = s.dailyDate === yesterday() ? s.dailyStreak + 1 : 1;
        return { amount: E.ECON.dailyBonus(st), dayStreak: st };
      },

      claimDaily() {
        if (!api.dailyAvailable()) return { ok: false, reason: 'already_claimed' };
        const { amount, dayStreak } = api.nextDaily();
        s.balance += amount; s.dailyDate = today(); s.dailyStreak = dayStreak;
        save();
        return { ok: true, amount, day_streak: dayStreak, balance: s.balance };
      },

      /** Списывает ставку (или бесплатный бой). Возвращает {ok} или {ok:false,error}. */
      placeBet(amount) {
        rollDay();
        amount = Math.floor(Number(amount) || 0);
        if (amount === 0) {
          if (api.freeLeft() <= 0) return { ok: false, error: `Бесплатные бои на сегодня закончились (${E.ECON.FREE_FIGHTS_PER_DAY}/день)` };
          s.freeUsed += 1;
        } else {
          if (amount < E.ECON.MIN_BET) return { ok: false, error: `Минимальная ставка — ${E.ECON.MIN_BET}₲` };
          if (amount > E.ECON.MAX_BET) return { ok: false, error: `Максимальная ставка — ${E.ECON.MAX_BET}₲` };
          if (amount > s.balance) return { ok: false, error: `Не хватает ₲. Баланс: ${s.balance}₲` };
          s.balance -= amount;
        }
        s.pendingSpin = 0;
        save();
        return { ok: true, amount };
      },

      /** Итог боя: считает выплату, серию, историю. */
      settle({ fighterA, fighterB, userSide, winnerId, userWon, bet, mult }) {
        let payout = 0, bailout = false;
        if (userWon) {
          s.streak += 1; s.wins += 1; s.bestStreak = Math.max(s.bestStreak, s.streak);
          if (bet > 0) payout = Math.floor(bet * mult * E.ECON.streakMult(s.streak));
          else payout = E.ECON.FREE_WIN_REWARD;
          s.balance += payout;
          s.pendingSpin = bet > 0 ? payout : 0;
        } else {
          s.streak = 0; s.losses += 1; s.pendingSpin = 0;
        }
        // страховка от тупика: пусто на счёте и бесплатных боёв нет
        if (s.balance < E.ECON.MIN_BET && api.freeLeft() === 0) { s.balance += E.ECON.BAILOUT; bailout = true; }
        s.history.unshift({ t: Date.now(), a: fighterA, b: fighterB, user: userSide, winner: winnerId, bet, payout, won: !!userWon });
        s.history = s.history.slice(0, 20);
        save();
        return { payout, balance: s.balance, streak: s.streak, streakMult: userWon && bet > 0 ? E.ECON.streakMult(s.streak) : 1, bailout };
      },

      /** Колесо удачи: умножает выигрыш. Один раз после победы со ставкой. */
      spin(rng) {
        const base = s.pendingSpin;
        if (!base) return { ok: false, reason: 'no_spin' };
        const r = (rng || Math.random)();
        const segs = E.ECON.SPIN; const total = segs.reduce((a, x) => a + x.weight, 0);
        let acc = 0, idx = 1;
        for (let i = 0; i < segs.length; i++) { acc += segs[i].weight; if (r * total <= acc) { idx = i; break; } }
        const mult = segs[idx].mult;
        const newPayout = Math.floor(base * mult);
        s.balance += newPayout - base;
        s.pendingSpin = 0;
        save();
        return { ok: true, index: idx, mult, base, payout: newPayout, delta: newPayout - base, balance: s.balance };
      },

      grant(amount) { s.balance += Math.max(0, amount | 0); save(); return s.balance; },

      reset() { s = fresh(); save(); },
    };
    return api;
  }

  function safeStorage() {
    try { const t = '__t'; root.localStorage.setItem(t, '1'); root.localStorage.removeItem(t); return root.localStorage; }
    catch (e) { return null; }
  }

  const exported = { createStore, today, yesterday };
  if (typeof module !== 'undefined' && module.exports) module.exports = exported;
  else { exported.store = createStore(safeStorage()); root.ArenaStore = exported; }
})(typeof window !== 'undefined' ? window : globalThis);
