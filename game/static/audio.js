/* ═══════════════════════════════════════════════════════
   POLITICAL ARENA — Procedural Sound Engine (Web Audio API)
   No external files needed. All sounds generated in real-time.
   ═══════════════════════════════════════════════════════ */

class SoundEngine {
  constructor() {
    this.ctx = null;
    this.enabled = true;
    this.volume = 0.4;
  }

  init() {
    this.ctx = new (window.AudioContext || window.webkitAudioContext)();
  }

  ensure() {
    if (!this.ctx) this.init();
    if (this.ctx.state === 'suspended') this.ctx.resume();
  }

  // ── Primitives ──────────────────────────────────────

  tone(freq, dur, type = 'sine', vol) {
    if (!this.enabled) return;
    this.ensure();
    const v = (vol ?? 0.3) * this.volume;
    const t = this.ctx.currentTime;
    const osc = this.ctx.createOscillator();
    const g = this.ctx.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(freq, t);
    g.gain.setValueAtTime(v, t);
    g.gain.exponentialRampToValueAtTime(0.001, t + dur);
    osc.connect(g).connect(this.ctx.destination);
    osc.start(t);
    osc.stop(t + dur);
  }

  sweep(f1, f2, dur, type = 'sine', vol) {
    if (!this.enabled) return;
    this.ensure();
    const v = (vol ?? 0.2) * this.volume;
    const t = this.ctx.currentTime;
    const osc = this.ctx.createOscillator();
    const g = this.ctx.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(f1, t);
    osc.frequency.exponentialRampToValueAtTime(f2, t + dur);
    g.gain.setValueAtTime(v, t);
    g.gain.exponentialRampToValueAtTime(0.001, t + dur);
    osc.connect(g).connect(this.ctx.destination);
    osc.start(t);
    osc.stop(t + dur);
  }

  noise(dur, vol) {
    if (!this.enabled) return;
    this.ensure();
    const v = (vol ?? 0.2) * this.volume;
    const len = this.ctx.sampleRate * dur;
    const buf = this.ctx.createBuffer(1, len, this.ctx.sampleRate);
    const d = buf.getChannelData(0);
    for (let i = 0; i < len; i++) d[i] = Math.random() * 2 - 1;
    const src = this.ctx.createBufferSource();
    src.buffer = buf;
    const g = this.ctx.createGain();
    const t = this.ctx.currentTime;
    g.gain.setValueAtTime(v, t);
    g.gain.exponentialRampToValueAtTime(0.001, t + dur);
    src.connect(g).connect(this.ctx.destination);
    src.start(t);
  }

  // ── Game Sounds ─────────────────────────────────────

  // UI
  click() { this.tone(1200, 0.04, 'square', 0.15); }

  hover() { this.tone(800, 0.02, 'sine', 0.05); }

  select() {
    this.tone(600, 0.06, 'triangle', 0.2);
    setTimeout(() => this.tone(900, 0.08, 'triangle', 0.15), 40);
  }

  back() { this.tone(400, 0.08, 'triangle', 0.15); }

  error() {
    this.tone(200, 0.15, 'square', 0.2);
    setTimeout(() => this.tone(150, 0.2, 'square', 0.15), 100);
  }

  // Fight
  fightStart() {
    this.sweep(100, 400, 0.3, 'sawtooth', 0.3);
    setTimeout(() => this.noise(0.2, 0.3), 200);
    setTimeout(() => this.tone(600, 0.15, 'square', 0.25), 350);
  }

  hit() {
    this.noise(0.12, 0.35);
    this.sweep(300, 80, 0.15, 'sawtooth', 0.25);
  }

  crit() {
    this.noise(0.25, 0.5);
    this.sweep(400, 60, 0.3, 'sawtooth', 0.35);
    setTimeout(() => this.tone(200, 0.2, 'square', 0.2), 50);
  }

  miss() { this.sweep(600, 200, 0.15, 'sine', 0.08); }

  block() {
    this.tone(800, 0.05, 'square', 0.2);
    this.tone(600, 0.08, 'square', 0.15);
  }

  heal() {
    this.tone(500, 0.1, 'sine', 0.15);
    setTimeout(() => this.tone(700, 0.15, 'sine', 0.12), 80);
    setTimeout(() => this.tone(900, 0.2, 'sine', 0.1), 160);
  }

  combo() {
    [500, 650, 800, 1000].forEach((f, i) => {
      setTimeout(() => this.tone(f, 0.1, 'triangle', 0.2), i * 55);
    });
  }

  counter() {
    this.sweep(1000, 300, 0.15, 'sawtooth', 0.25);
    setTimeout(() => this.noise(0.1, 0.2), 80);
  }

  // Results
  victory() {
    const notes = [523, 659, 784, 1047];
    notes.forEach((f, i) => {
      setTimeout(() => this.tone(f, 0.4, 'triangle', 0.2), i * 150);
    });
    setTimeout(() => this.noise(0.15, 0.15), 600);
  }

  defeat() {
    this.sweep(300, 100, 0.6, 'sawtooth', 0.15);
    setTimeout(() => this.tone(80, 0.8, 'sine', 0.12), 200);
  }

  // Economy
  coin() {
    this.tone(1400, 0.08, 'square', 0.12);
    setTimeout(() => this.tone(1800, 0.12, 'square', 0.1), 60);
  }

  daily() {
    [700, 900, 1100, 1400].forEach((f, i) => {
      setTimeout(() => this.tone(f, 0.12, 'sine', 0.15), i * 90);
    });
  }

  referral() {
    [600, 800, 1000, 800, 1200].forEach((f, i) => {
      setTimeout(() => this.tone(f, 0.1, 'triangle', 0.15), i * 70);
    });
  }

  // Spin Wheel
  spinTick() { this.tone(600 + Math.random() * 600, 0.03, 'triangle', 0.12); }

  spinWin() {
    setTimeout(() => this.coin(), 0);
    setTimeout(() => this.coin(), 150);
    setTimeout(() => this.victory(), 300);
  }

  // Round transition
  roundStart() {
    this.tone(400, 0.08, 'square', 0.2);
    setTimeout(() => this.tone(600, 0.1, 'square', 0.25), 80);
  }

  // Countdown beep
  countdown() { this.tone(800, 0.06, 'sine', 0.15); }
  countdownGo() { this.tone(1200, 0.15, 'sine', 0.25); }
}

// Global singleton
const sfx = new SoundEngine();
// AudioEngine compatibility layer for fight3d.js
const AudioEngine = {
  _s(fn) { try { sfx.ensure(); fn(); } catch(e) {} },
  uiClick()     { this._s(() => sfx.click()); },
  punch()       { this._s(() => sfx.hit()); },
  heavyPunch()  { this._s(() => sfx.crit()); },
  kick()        { this._s(() => sfx.hit()); },
  block()       { this._s(() => sfx.block()); },
  special()     { this._s(() => sfx.combo()); },
  crit()        { this._s(() => sfx.crit()); },
  win()         { this._s(() => sfx.victory()); },
  lose()        { this._s(() => sfx.defeat()); },
  countdown()   { this._s(() => sfx.countdown()); },
  countdownGo() { this._s(() => sfx.countdownGo()); },
  startBg()     { },
  stopBg()      { },
  toggle()      { sfx.enabled = !sfx.enabled; }
};
