/* ═══════════════════════════════════════════════════════
   FIGHT AUDIO ENGINE — Web Audio API (no files needed)
   ═══════════════════════════════════════════════════════ */
const SFX = (() => {
  let ctx, master;
  let muted = false;

  function getCtx() {
    if (!ctx) {
      ctx = new (window.AudioContext || window.webkitAudioContext)();
      master = ctx.createGain();
      master.gain.value = 0.5;
      master.connect(ctx.destination);
    }
    if (ctx.state === 'suspended') ctx.resume();
    return ctx;
  }

  function noiseBuf(dur, vol) {
    const c = getCtx();
    const len = c.sampleRate * dur;
    const buf = c.createBuffer(1, len, c.sampleRate);
    const d = buf.getChannelData(0);
    for (let i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * vol;
    return buf;
  }

  function osc(freq, type, dur, vol, ramp) {
    const c = getCtx();
    const o = c.createOscillator();
    o.type = type;
    o.frequency.setValueAtTime(freq, c.currentTime);
    if (ramp) o.frequency.exponentialRampToValueAtTime(ramp, c.currentTime + dur);
    const g = c.createGain();
    g.gain.setValueAtTime(vol, c.currentTime);
    g.gain.exponentialRampToValueAtTime(0.001, c.currentTime + dur);
    o.connect(g).connect(master);
    o.start(); o.stop(c.currentTime + dur);
  }

  function noiseHit(dur, vol, freq) {
    const c = getCtx();
    const src = c.createBufferSource();
    src.buffer = noiseBuf(dur, 1);
    const flt = c.createBiquadFilter();
    flt.type = 'bandpass'; flt.frequency.value = freq || 600; flt.Q.value = 1;
    const g = c.createGain();
    g.gain.setValueAtTime(vol, c.currentTime);
    g.gain.exponentialRampToValueAtTime(0.001, c.currentTime + dur);
    src.connect(flt).connect(g).connect(master);
    src.start();
  }

  return {
    toggle() { muted = !muted; if (master) master.gain.value = muted ? 0 : 0.5; return muted; },
    isMuted() { return muted; },

    punch() {
      if (muted) return;
      noiseHit(0.08, 0.6, 800);
      osc(150, 'sine', 0.1, 0.35, 40);
    },
    punchHeavy() {
      if (muted) return;
      noiseHit(0.12, 0.8, 500);
      osc(100, 'sine', 0.18, 0.5, 30);
      osc(200, 'square', 0.06, 0.15, 80);
    },
    block() {
      if (muted) return;
      osc(1200, 'sine', 0.15, 0.25, 800);
      osc(2400, 'sine', 0.08, 0.1, 1800);
      noiseHit(0.04, 0.2, 3000);
    },
    special() {
      if (muted) return;
      osc(200, 'sawtooth', 0.5, 0.3, 1200);
      setTimeout(() => {
        noiseHit(0.2, 0.9, 400);
        osc(80, 'sine', 0.3, 0.5, 20);
        osc(600, 'square', 0.15, 0.2, 100);
      }, 200);
    },
    ko() {
      if (muted) return;
      osc(60, 'sine', 0.8, 0.6, 15);
      noiseHit(0.4, 0.7, 300);
      osc(120, 'sawtooth', 0.5, 0.3, 30);
      setTimeout(() => osc(40, 'sine', 1.0, 0.4, 10), 300);
    },
    bell() {
      if (muted) return;
      osc(800, 'sine', 0.6, 0.3, 400);
      osc(1200, 'sine', 0.4, 0.15, 600);
    },
    countdown() {
      if (muted) return;
      osc(600, 'square', 0.1, 0.2, 400);
    },
    countdownGo() {
      if (muted) return;
      osc(800, 'square', 0.15, 0.3, 1200);
      osc(1200, 'sine', 0.2, 0.2, 600);
    },
    combo() {
      if (muted) return;
      osc(523, 'sine', 0.08, 0.2, 523);
      setTimeout(() => osc(659, 'sine', 0.08, 0.2, 659), 60);
      setTimeout(() => osc(784, 'sine', 0.12, 0.25, 784), 120);
    },
    tick() {
      if (muted) return;
      osc(1000, 'sine', 0.03, 0.08, 800);
    },
    win() {
      if (muted) return;
      const notes = [523, 659, 784, 1047];
      notes.forEach((n, i) => setTimeout(() => osc(n, 'sine', 0.3, 0.2, n * 0.8), i * 150));
    },
    lose() {
      if (muted) return;
      osc(300, 'sawtooth', 0.6, 0.2, 80);
      setTimeout(() => osc(200, 'sawtooth', 0.8, 0.25, 50), 400);
    }
  };
})();
