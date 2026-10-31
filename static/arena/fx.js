(function (root) {
  'use strict';

  const reduced = !!(root.matchMedia && root.matchMedia('(prefers-reduced-motion: reduce)').matches);
  const FX = { speed: reduced ? 3 : 1, stage: null, layer: null, enabled: true };

  const sleep = (ms) => new Promise(r => setTimeout(r, ms));
  const wait = (ms) => sleep(ms / FX.speed);
  const TYPE_COLOR = { light: '#00d4ff', heavy: '#ff7a2d', special: '#b44dff', ultimate: '#ffd700' };
  const TYPE_ICON = { light: '⚡', heavy: '🔨', special: '✨', ultimate: '💀' };

  function anim(el, frames, opts) {
    const o = Object.assign({ fill: 'forwards' }, opts);
    o.duration = (o.duration || 300) / FX.speed;
    if (o.delay) o.delay /= FX.speed;
    if (!el || typeof el.animate !== 'function') return wait(opts && opts.duration || 300);
    const commit = o.commit; delete o.commit;
    try {
      const a = el.animate(frames, o);
      return new Promise(res => {
        a.onfinish = () => {
          if (commit && a.commitStyles) { try { a.commitStyles(); a.cancel(); } catch (e) { } }
          res(a);
        };
        a.oncancel = () => res(a);
      });
    } catch (e) { return Promise.resolve(); }
  }

  const cur = (side) => FX.sprites[side].style.transform || 'none';

  function make(cls, text, parent) {
    const el = document.createElement('div');
    el.className = cls;
    if (text != null) el.textContent = text;
    (parent || FX.layer).appendChild(el);
    return el;
  }

  function rectIn(el) {
    const s = FX.stage.getBoundingClientRect(), r = el.getBoundingClientRect();
    return { x: r.left - s.left + r.width / 2, y: r.top - s.top + r.height / 2, w: r.width, h: r.height, sw: s.width, sh: s.height };
  }

  function init(stage) {
    FX.stage = stage;
    FX.layer = stage.querySelector('.stage-fx');
    FX.bannerEl = stage.querySelector('.stage-banner');
    FX.sprites = { a: stage.querySelector('#spriteA'), b: stage.querySelector('#spriteB') };
    FX.inner = { a: FX.sprites.a.querySelector('.sprite-inner'), b: FX.sprites.b.querySelector('.sprite-inner') };
  }

  function reset() {
    if (!FX.stage) return;
    FX.layer.innerHTML = '';
    FX.bannerEl.className = 'stage-banner';
    FX.bannerEl.textContent = '';
    ['a', 'b'].forEach(s => {
      FX.sprites[s].getAnimations && FX.sprites[s].getAnimations().forEach(a => a.cancel());
      FX.inner[s].getAnimations && FX.inner[s].getAnimations().forEach(a => a.cancel());
      FX.sprites[s].style.cssText = '';
      FX.inner[s].style.cssText = '';
      FX.sprites[s].className = 'sprite sprite-' + s;
    });
    FX.stage.classList.remove('dim', 'ko');
  }

  function banner(text, cls, ms) {
    const b = FX.bannerEl;
    b.className = 'stage-banner ' + (cls || '');
    b.textContent = text;
    void b.offsetWidth;
    b.classList.add('show');
    return anim(b, [
      { opacity: 0, transform: 'translate(-50%,-50%) scale(2.2)' },
      { opacity: 1, transform: 'translate(-50%,-50%) scale(1)', offset: 0.25 },
      { opacity: 1, transform: 'translate(-50%,-50%) scale(1)', offset: 0.8 },
      { opacity: 0, transform: 'translate(-50%,-50%) scale(0.9)' },
    ], { duration: ms || 900, fill: 'both' });
  }

  function floatNum(side, text, cls) {
    if (!FX.stage) return;
    const c = rectIn(FX.sprites[side]);
    const el = make('dmg-num ' + cls, text);
    el.style.left = (c.x + (Math.random() - 0.5) * 30) + 'px';
    el.style.top = (c.y - 40) + 'px';
    anim(el, [
      { transform: 'translate(-50%,0) scale(0.4)', opacity: 0 },
      { transform: 'translate(-50%,-14px) scale(1.25)', opacity: 1, offset: 0.2 },
      { transform: 'translate(-50%,-70px) scale(0.9)', opacity: 0 },
    ], { duration: cls === 'crit' ? 1300 : 950 }).then(() => el.remove());
  }

  function moveTag(side, move) {
    const c = rectIn(FX.sprites[side]);
    const el = make('move-tag ' + move.type, `${TYPE_ICON[move.type]} ${move.name}`);
    el.style.left = c.x + 'px';
    el.style.top = Math.max(8, c.y - c.h / 2 - 26) + 'px';
    anim(el, [
      { opacity: 0, transform: 'translate(-50%,8px) scale(0.7)' },
      { opacity: 1, transform: 'translate(-50%,0) scale(1)', offset: 0.2 },
      { opacity: 1, transform: 'translate(-50%,0) scale(1)', offset: 0.8 },
      { opacity: 0, transform: 'translate(-50%,-6px) scale(1)' },
    ], { duration: 1000, fill: 'both' }).then(() => el.remove());
  }

  function particles(x, y, color, n, spread) {
    if (reduced) return;
    for (let i = 0; i < n; i++) {
      const p = make('particle', null);
      const sz = 3 + Math.random() * 5;
      p.style.cssText = `left:${x}px;top:${y}px;width:${sz}px;height:${sz}px;background:${color};box-shadow:0 0 8px ${color}`;
      const ang = Math.random() * Math.PI * 2, d = (spread || 60) * (0.4 + Math.random());
      anim(p, [
        { transform: 'translate(-50%,-50%) scale(1)', opacity: 1 },
        { transform: `translate(${Math.cos(ang) * d - sz / 2}px,${Math.sin(ang) * d + 20 - sz / 2}px) scale(0.2)`, opacity: 0 },
      ], { duration: 450 + Math.random() * 350, easing: 'cubic-bezier(.1,.7,.3,1)' }).then(() => p.remove());
    }
  }

  function ring(x, y, color, size, ms) {
    const r = make('ring', null);
    r.style.cssText = `left:${x}px;top:${y}px;border-color:${color};box-shadow:0 0 18px ${color}`;
    anim(r, [
      { transform: 'translate(-50%,-50%) scale(0.1)', opacity: 0.95 },
      { transform: `translate(-50%,-50%) scale(${size || 3})`, opacity: 0 },
    ], { duration: ms || 520, easing: 'ease-out' }).then(() => r.remove());
  }

  function slashes(x, y, color) {
    for (let i = 0; i < 3; i++) {
      const s = make('slash', null);
      s.style.cssText = `left:${x}px;top:${y}px;background:linear-gradient(90deg,transparent,${color},#fff,transparent)`;
      const rot = -35 + i * 28 + (Math.random() - 0.5) * 10;
      anim(s, [
        { transform: `translate(-50%,-50%) rotate(${rot}deg) scaleX(0)`, opacity: 1 },
        { transform: `translate(-50%,-50%) rotate(${rot}deg) scaleX(1)`, opacity: 1, offset: 0.4 },
        { transform: `translate(-50%,-50%) rotate(${rot}deg) scaleX(1)`, opacity: 0 },
      ], { duration: 320, delay: i * 70 }).then(() => s.remove());
    }
  }

  function orb(from, to, color) {
    const o = make('orb', null);
    o.style.cssText = `left:${from.x}px;top:${from.y}px;background:radial-gradient(circle,#fff,${color} 60%,transparent 70%);box-shadow:0 0 22px ${color}`;
    return anim(o, [
      { transform: 'translate(-50%,-50%) scale(0.4)', opacity: 1 },
      { transform: `translate(${to.x - from.x - 14}px,${to.y - from.y - 14}px) scale(1.3)`, opacity: 1 },
    ], { duration: 240, easing: 'ease-in' }).then(() => o.remove());
  }

  function flash(color, ms, peak) {
    const f = make('flash', null);
    f.style.background = color;
    anim(f, [{ opacity: 0 }, { opacity: peak || 0.55, offset: 0.2 }, { opacity: 0 }], { duration: ms || 300 }).then(() => f.remove());
  }

  function shake(power) {
    const k = Math.min(14, 3 + power / 5);
    anim(FX.stage, [
      { transform: 'translate(0,0)' },
      { transform: `translate(${-k}px,${k / 3}px)` },
      { transform: `translate(${k}px,${-k / 3}px)` },
      { transform: `translate(${-k / 2}px,0)` },
      { transform: 'translate(0,0)' },
    ], { duration: 320, fill: 'none' });
  }

  function dash(side, dx) {
    const sign = side === 'a' ? 1 : -1;
    return anim(FX.sprites[side], [
      { transform: 'translateX(0) scale(1)' },
      { transform: `translateX(${-sign * 14}px) scale(0.96)`, offset: 0.35 },
      { transform: `translateX(${sign * dx}px) scale(1.12)` },
    ], { duration: 260, easing: 'cubic-bezier(.5,0,.8,.4)', commit: true });
  }

  function back(side) {
    return anim(FX.sprites[side], [{ transform: cur(side) }, { transform: 'translateX(0) scale(1)' }], { duration: 260, easing: 'ease-out', commit: true });
  }

  function recoil(side, strong) {
    const sign = side === 'a' ? -1 : 1;
    const inner = FX.inner[side];
    inner.classList.add('hit-flash');
    setTimeout(() => inner.classList.remove('hit-flash'), 280 / FX.speed);
    return anim(FX.sprites[side], [
      { transform: cur(side) },
      { transform: `translateX(${sign * (strong ? 46 : 26)}px) rotate(${sign * (strong ? 10 : 5)}deg) scale(0.94)`, offset: 0.4 },
      { transform: 'translateX(0) rotate(0) scale(1)' },
    ], { duration: strong ? 480 : 360, easing: 'ease-out', commit: true });
  }

  function dodge(side) {
    const sign = side === 'a' ? -1 : 1;
    return anim(FX.sprites[side], [
      { transform: cur(side), opacity: 1 },
      { transform: `translate(${sign * 40}px,-26px) rotate(${sign * 8}deg)`, opacity: 0.55, offset: 0.45 },
      { transform: 'translate(0,0) rotate(0)', opacity: 1 },
    ], { duration: 460, easing: 'ease-in-out', commit: true });
  }

  function status(side, text) {
    const row = document.getElementById('status' + side.toUpperCase());
    if (!row) return;
    const chip = document.createElement('span');
    chip.className = 'status-chip';
    chip.textContent = text;
    row.appendChild(chip);
    while (row.children.length > 4) row.removeChild(row.firstChild);
  }

  function setHp(side, hp, max, animate) {
    const pct = Math.max(0, Math.min(100, hp / max * 100));
    const U = side.toUpperCase();
    const bar = document.getElementById('hpBar' + U), ghost = document.getElementById('hpGhost' + U);
    bar.style.width = pct + '%';
    bar.className = 'hp-fill' + (pct < 20 ? ' critical' : pct < 40 ? ' low' : '');
    if (ghost) {
      if (animate) setTimeout(() => { ghost.style.width = pct + '%'; }, 450 / FX.speed);
      else ghost.style.width = pct + '%';
    }
    document.getElementById('hpText' + U).textContent = `${Math.max(0, Math.round(hp))}/${max}`;
  }

  function impactPoint(side) {
    const c = rectIn(FX.sprites[side]);
    return { x: c.x, y: c.y };
  }

  function dashDistance() {
    const a = rectIn(FX.sprites.a), b = rectIn(FX.sprites.b);
    const gap = b.x - a.x;
    return gap > 40 ? gap * 0.36 : 70;
  }

  async function playRound(r, maxA, maxB, hooks) {
    hooks = hooks || {};
    const dx = dashDistance();
    const ulting = r.move_a.type === 'ultimate' || r.move_b.type === 'ultimate';
    FX.stage.classList.toggle('dim', ulting);
    moveTag('a', r.move_a);
    moveTag('b', r.move_b);
    if (ulting) {
      const who = r.move_a.type === 'ultimate' ? 'a' : 'b';
      FX.sprites[who].classList.add('aura');
      if (hooks.ult) hooks.ult();
      banner(r.move_a.type === 'ultimate' && r.move_b.type === 'ultimate' ? 'ДВЕ УЛЬТЫ!' : 'УЛЬТА!', 'ult', 950);
      await wait(650);
    } else {
      await wait(380);
    }

    const sideData = [['a', 'b', r.move_a, r.res_a, r.combo_a, r.effect_a], ['b', 'a', r.move_b, r.res_b, r.combo_b, r.effect_b]];
    const orbs = sideData.filter(([, , m, res]) => (m.type === 'special' || m.type === 'ultimate') && !res.miss)
      .map(([att, def, m]) => orb(impactPoint(att), impactPoint(def), TYPE_COLOR[m.type]));
    await Promise.all([dash('a', dx), dash('b', dx)].concat(orbs));
    if (hooks.swing) hooks.swing();

    const crit = r.res_a.crit || r.res_b.crit;
    const biggest = Math.max(r.res_a.dmg, r.res_b.dmg);
    const bigHit = ulting || biggest >= 35 || crit;
    const anims = [];
    const clash = !r.res_a.miss && !r.res_b.miss;
    if (clash) {
      const m = (a, b) => ({ x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 });
      const p = m(impactPoint('a'), impactPoint('b'));
      ring(p.x, p.y, '#fff', 2.2, 380);
    }
    sideData.forEach(([att, def, move, res]) => {
      const pt = impactPoint(def);
      const color = TYPE_COLOR[move.type];
      if (res.miss) {
        anims.push(dodge(def));
        floatNum(def, 'ПРОМАХ', 'miss');
        if (hooks.miss) hooks.miss();
        return;
      }
      if (move.type === 'light') slashes(pt.x, pt.y, color);
      if (move.type === 'heavy') { ring(pt.x, pt.y, color, 3.2, 560); particles(pt.x, pt.y, color, 10, 80); }
      if (move.type === 'special') { ring(pt.x, pt.y, color, 2.6, 520); particles(pt.x, pt.y, color, 14, 90); }
      if (move.type === 'ultimate') { ring(pt.x, pt.y, color, 4.5, 700); ring(pt.x, pt.y, '#fff', 3, 520); particles(pt.x, pt.y, color, 26, 130); }
      particles(pt.x, pt.y, res.crit ? '#ffd700' : '#ff2d7b', res.crit ? 16 : 8, 60);
      anims.push(recoil(def, res.dmg >= 30 || res.crit));
      floatNum(def, `−${res.dmg}`, res.crit ? 'crit' : res.counter ? 'counter' : 'hit');
      if (hooks.hit) hooks.hit(res);
    });
    setHp('a', r.hp_a, maxA, true);
    setHp('b', r.hp_b, maxB, true);
    if (bigHit) shake(biggest);
    if (crit) { flash('#ffd700', 380, 0.5); banner('КРИТ!', 'crit', 700); }
    else if (ulting) flash('#fff', 320, 0.7);
    if (r.res_a.counter || r.res_b.counter) { if (hooks.counter) hooks.counter(); }
    if (r.combo_a >= 2 || r.combo_b >= 2) { if (hooks.combo) hooks.combo(); }
    if (r.res_a.counter || r.res_b.counter) setTimeout(() => banner('КОНТРУДАР!', 'counter', 800), crit ? 700 / FX.speed : 80);
    if (r.combo_a >= 2) status('a', `COMBO ×${r.combo_a}`);
    if (r.combo_b >= 2) status('b', `COMBO ×${r.combo_b}`);
    if (r.effect_a) status('a', r.effect_a.replace(/^[^:]+:\s*/, ''));
    if (r.effect_b) status('b', r.effect_b.replace(/^[^:]+:\s*/, ''));
    await Promise.all(anims);
    sideData.forEach(([att]) => FX.sprites[att].classList.remove('aura'));
    FX.stage.classList.remove('dim');
    await Promise.all([back('a'), back('b')]);
    await wait(crit ? 500 : 280);
  }

  function confetti(n) {
    if (reduced) return;
    const colors = ['#ffd700', '#ff2d7b', '#00d4ff', '#b44dff', '#00ff88'];
    const w = FX.stage.clientWidth || 600;
    for (let i = 0; i < (n || 40); i++) {
      const c = make('confetti', null);
      c.style.cssText = `left:${Math.random() * w}px;top:-10px;background:${colors[i % colors.length]}`;
      anim(c, [
        { transform: 'translateY(0) rotate(0)', opacity: 1 },
        { transform: `translateY(${260 + Math.random() * 80}px) translateX(${(Math.random() - 0.5) * 120}px) rotate(${Math.random() * 720}deg)`, opacity: 0.9 },
      ], { duration: 1400 + Math.random() * 1200, delay: Math.random() * 500, easing: 'ease-in' }).then(() => c.remove());
    }
  }

  async function finish(result, winnerSide, userSide) {
    const loser = winnerSide === 'a' ? 'b' : 'a';
    const ko = result.method === 'KO';
    FX.stage.classList.add('ko');
    if (ko) {
      flash('#fff', 500, 0.8);
      banner('K.O.!', 'ko', 1300);
      FX.sprites[loser].classList.add('fallen');
      anim(FX.sprites[loser], [
        { transform: 'translate(0,0) rotate(0)', opacity: 1 },
        { transform: `translate(${loser === 'a' ? -30 : 30}px,34px) rotate(${loser === 'a' ? -78 : 78}deg)`, opacity: 0.55 },
      ], { duration: 700, easing: 'ease-in' });
    } else {
      banner('ПО ОЧКАМ', 'decision', 1100);
      FX.sprites[loser].classList.add('fallen');
    }
    await wait(500);
    anim(FX.sprites[winnerSide], [
      { transform: 'translateY(0) scale(1)' },
      { transform: 'translateY(-34px) scale(1.18)', offset: 0.45 },
      { transform: 'translateY(0) scale(1.1)' },
    ], { duration: 700, easing: 'ease-out' });
    FX.sprites[winnerSide].classList.add('winner');
    if (userSide == null || winnerSide === userSide) confetti(46);
    await wait(900);
  }

  root.ArenaFX = Object.assign(FX, { init, reset, wait, anim, banner, floatNum, setHp, playRound, finish, confetti, status, particles, ring, flash, sleep });
})(typeof window !== 'undefined' ? window : globalThis);
