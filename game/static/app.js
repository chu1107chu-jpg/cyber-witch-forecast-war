/* ═══════════════════════════════════════════════════════
   POLITICAL ARENA — Frontend Logic
   ═══════════════════════════════════════════════════════ */

const API = '';  // same origin

// ── State ───────────────────────────────────────────────
let fighters = [];
let selectedA = null;
let selectedB = null;
let betFighter = null;
let balance = 100;
let freeRemaining = 3;

// ── DOM refs ────────────────────────────────────────────
const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

const screens = {
  select: $('#screenSelect'),
  bet: $('#screenBet'),
  fight: $('#screenFight'),
  result: $('#screenResult'),
};

function showScreen(name) {
  Object.values(screens).forEach(s => s.classList.remove('active'));
  screens[name].classList.add('active');
  window.scrollTo(0, 0);
}

// ── Init ────────────────────────────────────────────────
async function init() {
  try {
    const [fRes, wRes] = await Promise.all([
      fetch(`${API}/api/fighters`).then(r => r.json()),
      fetch(`${API}/api/wallet`).then(r => r.json()),
    ]);
    fighters = fRes.fighters;
    balance = wRes.balance;
    freeRemaining = wRes.free_remaining;
    updateWallet();
    renderFighters();
    bindEvents();
  } catch (e) {
    console.error('Init failed:', e);
  }
}

// ── Wallet ──────────────────────────────────────────────
function updateWallet() {
  $('#balance').textContent = balance;
  $('#freeBadge').textContent = freeRemaining > 0 ? `${freeRemaining} free` : '—';
  const betBal = $('#betBalance');
  if (betBal) betBal.textContent = `${balance}₲`;
}

// ── Render Fighters Grid ────────────────────────────────
function renderFighters(typeFilter = 'all') {
  const grid = $('#fightersGrid');
  grid.innerHTML = '';

  const list = typeFilter === 'all' ? fighters : fighters.filter(f => f.type === typeFilter);

  list.forEach(f => {
    const card = document.createElement('div');
    card.className = 'fighter-card';
    card.dataset.id = f.id;
    card.style.setProperty('--card-gradient', f.gradient);

    const isSelected = (selectedA && selectedA.id === f.id) || (selectedB && selectedB.id === f.id);
    if (isSelected) card.classList.add('selected');

    card.innerHTML = `
      <span class="kawaii-sparkle">✨</span>
      <div class="fc-emoji">${f.emoji}</div>
      <div class="fc-name">${f.name}</div>
      <div class="fc-country">${f.country}</div>
      <div class="fc-type">${f.type}</div>
      <div class="fc-stats">
        <div>HP <span class="stat-val">${f.hp}</span></div>
        <div>ATK <span class="stat-val">${f.atk}</span></div>
        <div>DEF <span class="stat-val">${f.def}</span></div>
        <div>SPD <span class="stat-val">${f.spd}</span></div>
      </div>
    `;

    card.addEventListener('click', () => selectFighter(f));
    grid.appendChild(card);
  });
}

// ── Select Fighter ──────────────────────────────────────
function selectFighter(f) {
  if (selectedA && selectedA.id === f.id) {
    selectedA = null;
    updateSlot('slotA', null);
  } else if (selectedB && selectedB.id === f.id) {
    selectedB = null;
    updateSlot('slotB', null);
  } else if (!selectedA) {
    selectedA = f;
    updateSlot('slotA', f);
  } else if (!selectedB) {
    if (f.id === selectedA.id) return;
    selectedB = f;
    updateSlot('slotB', f);
  } else {
    // Both full — replace B
    selectedB = f;
    updateSlot('slotB', f);
  }

  renderFighters(getCurrentFilter());
  updateFightButton();
}

function updateSlot(slotId, f) {
  const slot = $(`#${slotId}`);
  if (!f) {
    slot.classList.remove('filled');
    slot.innerHTML = `<div class="slot-placeholder">?</div><span>Боец ${slotId === 'slotA' ? '1' : '2'}</span>`;
    return;
  }
  slot.classList.add('filled');
  slot.innerHTML = `
    <button class="slot-remove" onclick="event.stopPropagation(); removeSlot('${slotId}')">×</button>
    <div class="slot-emoji">${f.emoji}</div>
    <span>${f.name}</span>
  `;
}

// Make removeSlot global
window.removeSlot = function(slotId) {
  if (slotId === 'slotA') { selectedA = null; }
  else { selectedB = null; }
  updateSlot(slotId, null);
  renderFighters(getCurrentFilter());
  updateFightButton();
};

function updateFightButton() {
  $('#btnTobet').disabled = !(selectedA && selectedB);
}

function getCurrentFilter() {
  const active = document.querySelector('.filter-btn.active');
  return active ? active.dataset.type : 'all';
}

// ── Bet Screen ──────────────────────────────────────────
function showBetScreen() {
  betFighter = null;
  populateBetCard('A', selectedA);
  populateBetCard('B', selectedB);
  $$('.bet-fighter-card').forEach(c => c.classList.remove('selected-bet'));
  $('#betAmount').value = Math.min(10, balance);
  updateBetInfo();
  showScreen('bet');
}

function populateBetCard(side, f) {
  $(`#betEmoji${side}`).textContent = f.emoji;
  $(`#betName${side}`).textContent = f.name;
  $(`#betType${side}`).textContent = `${f.type} · ${f.country}`;
  $(`#betStats${side}`).innerHTML = `
    <div>HP <strong>${f.hp}</strong></div>
    <div>ATK <strong>${f.atk}</strong></div>
    <div>DEF <strong>${f.def}</strong></div>
    <div>SPD <strong>${f.spd}</strong></div>
  `;
}

function selectBetFighter(side) {
  betFighter = side === 'a' ? selectedA : selectedB;
  $$('.bet-fighter-card').forEach(c => c.classList.remove('selected-bet'));
  $(`#betCard${side.toUpperCase()}`).classList.add('selected-bet');
  updateBetInfo();
}

function updateBetInfo() {
  const amt = parseInt($('#betAmount').value) || 0;
  const winText = amt === 0 ? 'FREE' : `+${Math.floor(amt * 2)}₲`;
  $('#potentialWin').textContent = winText;
  $('#betBalance').textContent = `${balance}₲`;
  $('#btnFight').disabled = !betFighter;
}

// ── Fight! ──────────────────────────────────────────────
async function startFight() {
  const betAmt = parseInt($('#betAmount').value) || 0;

  if (betAmt > balance) {
    alert('Недостаточно средств!');
    return;
  }

  showScreen('fight');

  // Setup fight display
  $('#fightEmojiA').textContent = selectedA.emoji;
  $('#fightNameA').textContent = selectedA.name;
  $('#fightEmojiB').textContent = selectedB.emoji;
  $('#fightNameB').textContent = selectedB.name;
  $('#hpBarA').style.width = '100%';
  $('#hpBarB').style.width = '100%';
  $('#hpTextA').textContent = `${selectedA.hp}/${selectedA.hp}`;
  $('#hpTextB').textContent = `${selectedB.hp}/${selectedB.hp}`;
  $('#fightRound').textContent = 'РАУНД 1';
  $('#fightLog').innerHTML = '';

  // API call
  let data;
  try {
    const res = await fetch(`${API}/api/fight`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        fighter_a: selectedA.id,
        fighter_b: selectedB.id,
        bet_fighter: betFighter.id,
        bet_amount: betAmt,
        client_seed: Math.random().toString(36).slice(2, 10),
      }),
    });
    data = await res.json();
    if (!res.ok) {
      alert(data.detail || 'Ошибка');
      showScreen('bet');
      return;
    }
  } catch (e) {
    alert('Ошибка соединения');
    showScreen('bet');
    return;
  }

  // Animate rounds
  await animateRounds(data);

  // Update wallet
  balance = data.wallet.balance;
  freeRemaining = data.wallet.free_remaining;
  updateWallet();

  // Show result
  showResult(data);
}

async function animateRounds(data) {
  const log = $('#fightLog');
  const maxHpA = selectedA.hp;
  const maxHpB = selectedB.hp;

  for (let i = 0; i < data.rounds.length; i++) {
    const r = data.rounds[i];

    $('#fightRound').textContent = `РАУНД ${r.round}`;

    // Parse narration lines
    const lines = r.narration.split('\n');
    for (const line of lines) {
      await sleep(600);
      const div = document.createElement('div');
      div.className = 'log-line';
      if (line.includes('КРИТ') || line.includes('КРИТИЧЕСКИЙ')) div.className += ' crit';
      else if (line.includes('промах') || line.includes('мимо')) div.className += ' miss';
      else if (line.startsWith('Раунд') || line.startsWith('Гонг')) div.className += ' round-start';
      else if (line.includes('↳')) div.className += ' effect';
      div.textContent = line;
      log.appendChild(div);
      log.scrollTop = log.scrollHeight;
    }

    // Update HP bars
    const hpAPct = Math.max(0, (r.hp_a / maxHpA) * 100);
    const hpBPct = Math.max(0, (r.hp_b / maxHpB) * 100);

    const barA = $('#hpBarA');
    const barB = $('#hpBarB');
    barA.style.width = `${hpAPct}%`;
    barB.style.width = `${hpBPct}%`;

    barA.className = 'hp-fill' + (hpAPct < 20 ? ' critical' : hpAPct < 40 ? ' low' : '');
    barB.className = 'hp-fill' + (hpBPct < 20 ? ' critical' : hpBPct < 40 ? ' low' : '');

    $('#hpTextA').textContent = `${r.hp_a}/${maxHpA}`;
    $('#hpTextB').textContent = `${r.hp_b}/${maxHpB}`;

    await sleep(800);
  }
}

// ── Result ──────────────────────────────────────────────
function showResult(data) {
  const won = data.bet.won;
  const winnerFighter = data.winner_id === selectedA.id ? selectedA : selectedB;

  const glow = $('#resultGlow');
  glow.className = 'result-glow ' + (won ? 'win' : 'lose');

  $('#resultEmoji').textContent = won ? '🏆' : '💀';
  const title = $('#resultTitle');
  title.textContent = won ? 'ПОБЕДА!' : 'ПОРАЖЕНИЕ';
  title.className = 'result-title ' + (won ? 'win' : 'lose');

  $('#resultWinner').textContent = `${winnerFighter.emoji} ${winnerFighter.name} побеждает!`;

  const betDiv = $('#resultBet');
  if (data.bet.amount === 0) {
    betDiv.textContent = 'Бесплатный бой';
    betDiv.className = 'result-bet';
  } else if (won) {
    betDiv.textContent = `+${data.bet.payout}₲`;
    betDiv.className = 'result-bet win';
  } else {
    betDiv.textContent = `-${data.bet.amount}₲`;
    betDiv.className = 'result-bet lose';
  }

  $('#resultNarration').textContent = data.narration;

  showScreen('result');
}

// ── Utility ─────────────────────────────────────────────
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// ── Event Bindings ──────────────────────────────────────
function bindEvents() {
  // Filters
  $$('.filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      $$('.filter-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      renderFighters(btn.dataset.type);
    });
  });

  // To bet screen
  $('#btnTobet').addEventListener('click', showBetScreen);

  // Back to select
  $('#btnBackSelect').addEventListener('click', () => showScreen('select'));

  // Bet fighter selection
  $('#betCardA').addEventListener('click', () => selectBetFighter('a'));
  $('#betCardB').addEventListener('click', () => selectBetFighter('b'));

  // Bet amount controls
  $('#betMinus').addEventListener('click', () => {
    const inp = $('#betAmount');
    inp.value = Math.max(0, (parseInt(inp.value) || 0) - 5);
    updateBetInfo();
  });
  $('#betPlus').addEventListener('click', () => {
    const inp = $('#betAmount');
    inp.value = Math.min(100, Math.min(balance, (parseInt(inp.value) || 0) + 5));
    updateBetInfo();
  });
  $('#betAmount').addEventListener('input', updateBetInfo);

  // Quick bet buttons
  $$('.bet-quick-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const val = parseInt(btn.dataset.val);
      $('#betAmount').value = Math.min(val, balance);
      updateBetInfo();
    });
  });

  // Fight!
  $('#btnFight').addEventListener('click', startFight);

  // Play again
  $('#btnPlayAgain').addEventListener('click', () => {
    selectedA = null;
    selectedB = null;
    betFighter = null;
    updateSlot('slotA', null);
    updateSlot('slotB', null);
    renderFighters();
    updateFightButton();
    showScreen('select');
  });
}

// ── Start ───────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', init);
