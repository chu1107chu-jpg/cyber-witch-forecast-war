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
function renderFighters() {
  const grid = $('#fightersGrid');
  grid.innerHTML = '';

  const list = fighters;

  list.forEach(f => {
    const card = document.createElement('div');
    card.className = 'fighter-card';
    card.dataset.id = f.id;
    card.style.setProperty('--card-gradient', f.gradient);

    const isSelected = (selectedA && selectedA.id === f.id) || (selectedB && selectedB.id === f.id);
    if (isSelected) card.classList.add('selected');

    card.innerHTML = `
      <div class="fc-portrait">
        <img class="fc-avatar" src="${f.avatar}" alt="${f.name}" loading="lazy">
        <div class="fc-avatar-overlay"></div>
        <div class="fc-avatar-scanlines"></div>
        <span class="fc-country-badge">${f.country}</span>
      </div>
      <div class="fc-info">
        <div class="fc-name">${f.name}</div>
        <div class="fc-type-badge">${f.type || ''}</div>
        <div class="fc-stats">
          <div class="stat-bar-row"><span class="stat-bar-label">HP</span><div class="stat-bar-track"><div class="stat-bar-fill" style="width:${Math.min(100,Math.round(f.hp/3.2))}%;background:${f.color||'#e74c3c'}"></div></div><span class="stat-val-num">${f.hp}</span></div>
          <div class="stat-bar-row"><span class="stat-bar-label">ATK</span><div class="stat-bar-track"><div class="stat-bar-fill" style="width:${Math.min(100,f.atk*2)}%;background:${f.color||'#e74c3c'}"></div></div><span class="stat-val-num">${f.atk}</span></div>
          <div class="stat-bar-row"><span class="stat-bar-label">DEF</span><div class="stat-bar-track"><div class="stat-bar-fill" style="width:${Math.min(100,f.def*2)}%;background:${f.color||'#e74c3c'}"></div></div><span class="stat-val-num">${f.def}</span></div>
          <div class="stat-bar-row"><span class="stat-bar-label">SPD</span><div class="stat-bar-track"><div class="stat-bar-fill" style="width:${Math.min(100,f.spd*10)}%;background:${f.color||'#e74c3c'}"></div></div><span class="stat-val-num">${f.spd}</span></div>
        </div>
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

  renderFighters();
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
    <img class="slot-avatar" src="${f.avatar}" alt="">
    <span>${f.name}</span>
  `;
}

// Make removeSlot global
window.removeSlot = function(slotId) {
  if (slotId === 'slotA') { selectedA = null; }
  else { selectedB = null; }
  updateSlot(slotId, null);
  renderFighters();
  updateFightButton();
};

function updateFightButton() {
  $('#btnTobet').disabled = !(selectedA && selectedB);
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
  $(`#betEmoji${side}`).innerHTML = `<img class="bet-avatar" src="${f.avatar}" alt="">`;
  $(`#betName${side}`).textContent = f.name;
  $(`#betType${side}`).textContent = f.country;
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
let currentFightId = null;
let currentFightData = null;

async function startFight() {
  const betAmt = parseInt($('#betAmount').value) || 0;

  if (betAmt > balance) {
    alert('Недостаточно средств!');
    return;
  }

  showScreen('fight');

  // Setup fight display
  $('#fightEmojiA').innerHTML = `<img class="fight-avatar" src="${selectedA.avatar}" alt="">`;
  $('#fightNameA').textContent = selectedA.name;
  $('#fightEmojiB').innerHTML = `<img class="fight-avatar" src="${selectedB.avatar}" alt="">`;
  $('#fightNameB').textContent = selectedB.name;
  $('#hpBarA').style.width = '100%';
  $('#hpBarB').style.width = '100%';
  $('#hpTextA').textContent = `${selectedA.hp}/${selectedA.hp}`;
  $('#hpTextB').textContent = `${selectedB.hp}/${selectedB.hp}`;
  $('#fightRound').textContent = 'РАУНД 1';
  $('#fightLog').innerHTML = '';
  $('#movePicker').style.display = 'none';

  // Start fight via API
  let data;
  try {
    const res = await fetch(`${API}/api/fight/start`, {
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

  currentFightId = data.fight_id;
  currentFightData = data;

  // Show move picker for round 1
  showMovePicker(data.moves, data.round);
}

function showMovePicker(moves, roundNum) {
  $('#fightRound').textContent = `РАУНД ${roundNum}`;
  const grid = $('#movesGrid');
  grid.innerHTML = '';

  moves.forEach(m => {
    const btn = document.createElement('button');
    btn.className = 'move-btn';
    btn.disabled = !m.available;
    const typeClass = m.type === 'ultimate' ? 'ultimate' : '';
    btn.innerHTML = `
      <div class="move-name">${m.name}</div>
      <div class="move-info">DMG: ${m.base_dmg} · ACC: ${m.accuracy}%</div>
      <span class="move-type ${typeClass}">${m.type}</span>
    `;
    if (m.available) {
      btn.addEventListener('click', () => playRound(m.index));
    }
    grid.appendChild(btn);
  });

  $('#movePicker').style.display = 'block';
}

async function playRound(moveIndex) {
  // Hide picker while processing
  $('#movePicker').style.display = 'none';

  let data;
  try {
    const res = await fetch(`${API}/api/fight/round`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        fight_id: currentFightId,
        move_index: moveIndex,
      }),
    });
    data = await res.json();
    if (!res.ok) {
      alert(data.detail || 'Ошибка');
      return;
    }
  } catch (e) {
    alert('Ошибка соединения');
    return;
  }

  // Animate this round
  await animateOneRound(data);

  if (data.fight_over) {
    // Update wallet
    balance = data.wallet.balance;
    freeRemaining = data.wallet.free_remaining;
    updateWallet();
    // Show result
    showResult(data.result);
  } else {
    // Show move picker for next round
    showMovePicker(data.next_moves, data.round + 1);
  }
}

async function animateOneRound(r) {
  const log = $('#fightLog');
  const maxHpA = selectedA.hp;
  const maxHpB = selectedB.hp;

  const lines = r.narration.split('\n');
  for (const line of lines) {
    await sleep(500);
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

  await sleep(600);
}

// ── Result ──────────────────────────────────────────────
function showResult(data) {
  const won = data.bet.won;
  const winnerId = data.winner_id;
  const winnerFighter = winnerId === selectedA.id ? selectedA : selectedB;

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
