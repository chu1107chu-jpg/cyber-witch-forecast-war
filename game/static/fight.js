/* ═══════════════════════════════════════════════════════
   POLITICAL ARENA — Fight Engine v3 (named specials)
═══════════════════════════════════════════════════════ */
const API = '';
let fighters = [];
let selectedA = null, selectedB = null;
let mode = 'pve';
let gs = null; // gameState
let paused = false;
let gameLoop = null;
let timerInterval = null;
let timeLeft = 45;
let round = 1;

const $ = s => document.querySelector(s);
const $$ = s => document.querySelectorAll(s);

// ── INIT ────────────────────────────────────────────────
async function init() {
  try {
    const res = await fetch(`${API}/api/fighters`);
    const data = await res.json();
    fighters = data.fighters || data;
    renderRoster();
    bindKeys();
  } catch(e) {
    console.error('Init failed:', e);
    fighters = [
      {id:'trump',name:'Трамп',avatar:'/static/avatars/trump.png',hp:220,atk:38,def:18,spd:5},
      {id:'putin',name:'Путин',avatar:'/static/avatars/putin.png',hp:260,atk:30,def:35,spd:6}
    ];
    renderRoster();
    bindKeys();
  }
}

function renderRoster() {
  const grid = $('#roster');
  grid.innerHTML = '';
  fighters.forEach(f => {
    const card = document.createElement('div');
    card.className = 'roster-card';
    card.dataset.id = f.id;
    card.innerHTML = `<img src="${f.avatar||''}" onerror="this.src=''" alt="${f.name}"><div class="card-name">${f.name}</div>`;
    card.onclick = () => selectFighter(f.id);
    grid.appendChild(card);
  });
}

async function selectFighter(id) {
  const f = fighters.find(x => x.id === id);
  if (!f) return;
  // Загрузить полные данные (с moves, taunt) если ещё нет
  let full = f;
  if (!f.moves) {
    try {
      const r = await fetch(`/api/fighters/${id}`);
      if (r.ok) { full = await r.json(); Object.assign(f, full); }
    } catch(e) {}
  }
  const cards = $$('.roster-card');
  if (!selectedA || (selectedA && selectedB)) {
    selectedA = f; selectedB = null;
    cards.forEach(c => { c.classList.remove('sel-a','sel-b'); if(c.dataset.id===id) c.classList.add('sel-a'); });
    setPickSlot('A', f);
    $('#btnFight').disabled = true;
  } else if (!selectedB && id !== selectedA.id) {
    selectedB = f;
    cards.forEach(c => { if(c.dataset.id===id) c.classList.add('sel-b'); });
    setPickSlot('B', f);
    $('#btnFight').disabled = false;
  }
}

function setPickSlot(side, f) {
  const av = $(`#pickAvatar${side}`);
  const nm = $(`#pickName${side}`);
  av.innerHTML = `<img src="${f.avatar||''}" alt="${f.name}" style="width:100%;height:100%;object-fit:cover;border-radius:50%">`;
  nm.textContent = f.name;
  $(`#slot${side}`).classList.add('selected');
}

// ── START FIGHT ─────────────────────────────────────────
async function startFight() {
  if (!selectedA || !selectedB) return;
  // Fetch full fighter data (with moves)
  const [fdA, fdB] = await Promise.all([
    fetchFullFighter(selectedA.id),
    fetchFullFighter(selectedB.id)
  ]);
  gs = {
    A: makeState(fdA),
    B: makeState(fdB),
    winner: null
  };
  round = 1; timeLeft = 45;
  setupHUD();
  showScreen('screenArena');
  startTimer();
  if (mode === 'pve') scheduleAI();
}

async function fetchFullFighter(id) {
  try {
    const r = await fetch(`${API}/api/fighters/${id}`);
    return await r.json();
  } catch { return fighters.find(f => f.id === id) || {}; }
}

function makeState(f) {
  const moves = f.moves || [];
  const ultimate = moves.find(m => m.type === 'ultimate')
    || moves.find(m => m.type === 'special')
    || moves[moves.length - 1]
    || {name: 'СПЕЦУДАР', base_dmg: 55, accuracy: 0.8};
  return {
    id: f.id, name: f.name, avatar: f.avatar || '',
    hp: f.hp || 200, maxHp: f.hp || 200,
    atk: f.atk || 30, def: f.def || 20, spd: f.spd || 5,
    combo: 0, blocking: false, ultimate,
    moves: moves
  };
}

function setupHUD() {
  ['A','B'].forEach(side => {
    const s = gs[side];
    $(`#hudAvatar${side}`).src = s.avatar;
    $(`#hudName${side}`).textContent = s.name;
    $(`#img${side}`).src = s.avatar;
    $(`#hpFill${side}`).style.width = '100%';
    $(`#comboFill${side}`).style.width = '0%';
    const specBtn = $(`#specCtrl${side === 'A' ? 'A' : 'B'}`);
    const key = side === 'A' ? 'F' : 'Enter';
    specBtn.textContent = `${key} — ${s.ultimate.name}`;
    specBtn.classList.remove('ready');
  });
  $('#roundLabel').textContent = `РАУНД ${round}`;
}

// ── TIMER ───────────────────────────────────────────────
function startTimer() {
  clearInterval(timerInterval);
  timerInterval = setInterval(() => {
    if (paused || gs?.winner) return;
    timeLeft--;
    $('#timerLabel').textContent = timeLeft;
    if (timeLeft <= 0) timeoutEnd();
  }, 1000);
}

function timeoutEnd() {
  const winner = gs.A.hp >= gs.B.hp ? 'A' : 'B';
  endFight(winner);
}

// ── ACTIONS ─────────────────────────────────────────────
function playerAction(side, action) {
  if (!gs || gs.winner || paused) return;
  const opponent = side === 'A' ? 'B' : 'A';
  if (action === 'block') {
    gs[side].blocking = true;
    visualBlock(side);
    setTimeout(() => { if(gs) gs[side].blocking = false; }, 600);
    return;
  }
  if (action === 'special') {
    doSpecial(side, opponent);
    return;
  }
  // Normal attacks
  let mult = 1.0, animClass = 'punch-l';
  if (action === 'left')  { mult = 0.9; animClass = side==='A'?'punch-l':'punch-r'; }
  if (action === 'right') { mult = 1.0; animClass = side==='A'?'punch-l':'punch-r'; }
  if (action === 'kick')  { mult = 1.7; animClass = side==='A'?'kick-anim':'kick-anim-r'; }
  doPunch(side, opponent, mult, animClass);
}

function doPunch(atk, def, mult, anim) {
  const a = gs[atk], d = gs[def];
  const imgA = $(`#img${atk}`);
  const imgD = $(`#img${def}`);
  imgA.classList.remove('punch-l','punch-r','kick-anim','kick-anim-r');
  void imgA.offsetWidth;
  imgA.classList.add(anim);
  setTimeout(() => imgA.classList.remove(anim), 300);
  if (d.blocking) {
    showDmgNumber(def, 'БЛОК!', '#4af', 0);
    logMove(`🛡️ ${d.name} заблокировал удар!`);
    return;
  }
  const rand = 0.82 + Math.random() * 0.36;
  const dmg = Math.max(1, Math.round(a.atk * mult * rand - d.def * 0.3));
  d.hp = Math.max(0, d.hp - dmg);
  // Combo
  a.combo = Math.min(a.combo + 1, 3);
  updateComboBar(atk);
  showDmgNumber(def, `-${dmg}`, mult >= 1.5 ? '#ff6b35' : '#fff', dmg);
  imgD.classList.remove('hit-flash','shake-anim','shake-anim-l');
  void imgD.offsetWidth;
  imgD.classList.add('hit-flash', def==='B'?'shake-anim':'shake-anim-l');
  setTimeout(() => imgD.classList.remove('hit-flash','shake-anim','shake-anim-l'), 350);
  updateHpBar(def);
  logMove(`💥 ${a.name}: ${Math.round(dmg)} урона`);
  if (d.hp <= 0) endFight(atk);
}


function showSuperOverlay(atk, moveName, moveDesc) {
  document.querySelectorAll('.super-overlay,.screen-flash').forEach(e => e.remove());
  const flash = document.createElement('div');
  flash.className = 'screen-flash';
  document.body.appendChild(flash);
  setTimeout(() => flash.remove(), 350);
  const ov = document.createElement('div');
  ov.className = 'super-overlay';
  ov.innerHTML = `
    <div class="super-overlay-fighter">${atk.name}</div>
    <div class="super-overlay-name">${moveName}!</div>
    ${moveDesc ? `<div class="super-overlay-desc">${moveDesc}</div>` : ''}
  `;
  document.body.appendChild(ov);
  setTimeout(() => ov.remove(), 950);
  const arena = document.getElementById('arena');
  if (arena) { arena.classList.add('super-shake'); setTimeout(() => arena.classList.remove('super-shake'), 500); }
}

function doSpecial(atk, def) {
  const a = gs[atk];
  if (a.combo < 3) {
    showDmgNumber(atk, 'КОМБО x3!', '#888', 0);
    return;
  }
  a.combo = 0;
  updateComboBar(atk);
  $(`#specCtrl${atk}`).classList.remove('ready');
  const move = a.ultimate;
  showSuperOverlay(a, move.name || 'СУПЕРУДАР', move.desc || '');
  const d = gs[def];
  const rand = 0.9 + Math.random() * 0.2;
  const acc = move.accuracy || 0.85;
  if (Math.random() > acc) {
    showMoveOverlay(`${move.name}... МИМО!`, '#aaa');
    logMove(`🌀 ${a.name}: "${move.name}" — промах!`);
    return;
  }
  const dmg = Math.max(10, Math.round((move.base_dmg || 55) * rand));
  d.hp = Math.max(0, d.hp - dmg);
  showMoveOverlay(move.name + '!', '#ffd700');
  showDmgNumber(def, `-${dmg}`, '#ffd700', dmg);
  const imgA = $(`#img${atk}`);
  imgA.classList.add('golden-glow');
  setTimeout(() => imgA.classList.remove('golden-glow'), 800);
  const imgD = $(`#img${def}`);
  imgD.classList.add('hit-flash');
  setTimeout(() => imgD.classList.remove('hit-flash'), 500);
  updateHpBar(def);
  logMove(`⚡️ ${a.name}: "${move.name}" — ${dmg} урона!`);
  if (d.hp <= 0) endFight(atk);
}

function updateHpBar(side) {
  const s = gs[side];
  const pct = Math.max(0, (s.hp / s.maxHp) * 100);
  $(`#hpFill${side}`).style.width = pct + '%';
}

function updateComboBar(side) {
  const pct = (gs[side].combo / 3) * 100;
  $(`#comboFill${side}`).style.width = pct + '%';
  const specBtn = $(`#specCtrl${side}`);
  if (gs[side].combo >= 3) {
    specBtn.classList.add('ready');
  } else {
    specBtn.classList.remove('ready');
  }
}

function visualBlock(side) {
  showDmgNumber(side, '🛡️', '#4af', 0);
}

// ── VISUAL HELPERS ───────────────────────────────────────
function showDmgNumber(side, text, color, dmg) {
  const layer = $('#damageLayer');
  const el = document.createElement('div');
  el.className = 'dmg-number';
  el.textContent = text;
  el.style.color = color;
  el.style.fontSize = dmg > 50 ? '2rem' : '1.3rem';
  el.style.left = side === 'A' ? '20%' : '65%';
  el.style.top = (30 + Math.random() * 30) + '%';
  layer.appendChild(el);
  setTimeout(() => el.remove(), 900);
}

function showMoveOverlay(text, color) {
  const el = $('#moveNameOverlay');
  el.textContent = text;
  el.style.color = color;
  el.style.textShadow = `0 0 30px ${color}, 0 0 60px ${color}`;
  el.classList.remove('pop');
  void el.offsetWidth;
  el.classList.add('pop');
}

function logMove(text) {
  const log = $('#moveLog');
  const el = document.createElement('span');
  el.className = 'log-entry';
  el.textContent = text;
  log.appendChild(el);
  while (log.children.length > 5) log.removeChild(log.firstChild);
  log.scrollLeft = log.scrollWidth;
}

// ── AI ──────────────────────────────────────────────────
let aiTimeout = null;
function scheduleAI() {
  if (aiTimeout) clearTimeout(aiTimeout);
  const delay = 600 + Math.random() * 800;
  aiTimeout = setTimeout(aiTick, delay);
}

function aiTick() {
  if (!gs || gs.winner || paused) return;
  const actions = ['left','right','kick','block','left','right'];
  const r = Math.random();
  if (gs.B.combo >= 3 && r < 0.5) {
    doSpecial('B', 'A');
  } else {
    const action = actions[Math.floor(Math.random() * actions.length)];
    playerAction('B', action);
  }
  scheduleAI();
}

// ── END FIGHT ────────────────────────────────────────────
function endFight(winner) {
  if (!gs) return;
  clearInterval(timerInterval);
  if (aiTimeout) clearTimeout(aiTimeout);
  if (winner === 'quit') {
    backToRoster(); return;
  }
  gs.winner = winner;
  const w = gs[winner];
  const l = gs[winner === 'A' ? 'B' : 'A'];
  $('#resultTitle').textContent = '🏆 ПОБЕДА!';
  $('#resultAvatar').src = w.avatar;
  $('#resultName').textContent = w.name;
  const tauntEl = $('#resultTaunt');
  if (tauntEl) tauntEl.textContent = w.taunt ? `"${w.taunt}"` : '';
  $('#resultDetails').textContent = `${w.name} победил ${l.name} | HP: ${Math.round(w.hp)} | Раунд ${round}`;
  showScreen('screenResult');
}

function backToRoster() {
  gs = null;
  clearInterval(timerInterval);
  if (aiTimeout) clearTimeout(aiTimeout);
  selectedA = null; selectedB = null;
  $$('.roster-card').forEach(c => c.classList.remove('sel-a','sel-b'));
  ['A','B'].forEach(side => {
    $(`#pickAvatar${side}`).innerHTML = '?';
    $(`#pickName${side}`).textContent = 'Выбери бойца';
    $(`#slot${side}`).classList.remove('selected');
  });
  $('#btnFight').disabled = true;
  showScreen('screenRoster');
}

// ── PAUSE ────────────────────────────────────────────────
function togglePause() {
  paused = !paused;
  $('#pauseOverlay').classList.toggle('hidden', !paused);
}

// ── SCREENS ─────────────────────────────────────────────
function showScreen(id) {
  $$('.screen').forEach(s => s.classList.remove('active'));
  $(id + '').classList.add('active');
  // fix: use direct id
  document.getElementById(id).classList.add('active');
}

// ── KEYS ─────────────────────────────────────────────────
function bindKeys() {
  const map = {
    'a': ()=>playerAction('A','left'),
    'd': ()=>playerAction('A','right'),
    'w': ()=>playerAction('A','kick'),
    's': ()=>playerAction('A','block'),
    'f': ()=>playerAction('A','special'),
    ' ': ()=>playerAction('A','special'),
    'arrowleft':  ()=>playerAction('B','left'),
    'arrowright': ()=>playerAction('B','right'),
    'arrowup':    ()=>playerAction('B','kick'),
    'arrowdown':  ()=>playerAction('B','block'),
    'enter':      ()=>playerAction('B','special'),
    'escape': togglePause,
    'p': togglePause
  };
  document.addEventListener('keydown', e => {
    const fn = map[e.key.toLowerCase()];
    if (fn) { e.preventDefault(); fn(); }
  });
  document.getElementById('btnFight').addEventListener('click', startFight);
}

document.addEventListener('DOMContentLoaded', init);
