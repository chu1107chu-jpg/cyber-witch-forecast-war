"""Страница: Snake — лови предсказания, зарабатывай кредиты."""
import os
import json
import uuid
import requests
import streamlit as st
import streamlit.components.v1 as components

API   = os.environ.get("BASE_URL", "http://localhost:8000") + "/api/v1"
token = st.session_state.get("token", "")
headers = {"Authorization": f"Bearer {token}"}

st.title("🐍 Utility Snake")
st.caption("Управляй корзиной, лови золотые шары-предсказания. RTP ≈ 43.5%.")

stake = st.slider("Ставка за сессию (кредиты)", 10, 500, 50, step=10)

# --- встроенный JS-клиент ---
SNAKE_HTML = """
<!DOCTYPE html>
<html>
<head>
<style>
  body { margin:0; background:#0e1117; display:flex; flex-direction:column;
         align-items:center; font-family:sans-serif; color:#eee; }
  canvas { border:2px solid #555; margin-top:10px; }
  #info  { margin:6px; font-size:14px; }
  button { margin:4px; padding:8px 20px; cursor:pointer;
           background:#2196f3; color:#fff; border:none; border-radius:6px; }
</style>
</head>
<body>
<canvas id="c" width="480" height="320"></canvas>
<div id="info">Нажми «Старт» для начала игры</div>
<button onclick="startGame()">Старт</button>
<button onclick="finishGame()">Финиш</button>
<script>
const cv = document.getElementById('c');
const cx = cv.getContext('2d');
const API_BASE = "{API_BASE}";
const TOKEN    = "{TOKEN}";

let sessionId = null, balls = [], basket = {x:200, w:80, y:290, h:16};
let score = 0, frame = 0, raf = null, ballSeq = [];

function rand(seed) {
  // LCG для воспроизводимости (seed уже задан сервером через HMAC)
  let x = seed; return () => { x = (x*1664525+1013904223)>>>0; return x/4294967296; };
}

async function startGame() {
  const resp = await fetch(API_BASE + '/snake/session/start', {
    method:'POST', headers:{'Content-Type':'application/json',
    'Authorization':'Bearer '+TOKEN},
    body: JSON.stringify({stake: """ + str(50) + """, client_nonce: crypto.randomUUID()})
  });
  const d = await resp.json();
  sessionId  = d.session_id;
  ballSeq    = d.ball_sequence || [];   // цвета : "gold"|"blue"|"red"|"green"
  score = 0; frame = 0; balls = [];
  document.getElementById('info').textContent = 'ID: '+sessionId+' | Очки: 0';
  cancelAnimationFrame(raf);
  loop();
}

async function finishGame() {
  if (!sessionId) return;
  cancelAnimationFrame(raf);
  // имитируем серию позиций корзины каждые 3 кадра
  const resp = await fetch(API_BASE + '/snake/session/finish', {
    method:'POST', headers:{'Content-Type':'application/json',
    'Authorization':'Bearer '+TOKEN},
    body: JSON.stringify({session_id: sessionId,
      basket_x_history: Array.from({length:120}, (_,i)=>basket.x + Math.sin(i*0.1)*20)
    })
  });
  const d = await resp.json();
  document.getElementById('info').textContent =
    'Пойманó: '+d.catches+' | Выплата: '+d.payout+' cr | Баланс: '+d.balance+' cr';
  sessionId = null;
}

function loop() {
  cx.fillStyle='#0e1117'; cx.fillRect(0,0,480,320);
  // корзина
  cx.fillStyle='#2196f3';
  cx.fillRect(basket.x, basket.y, basket.w, basket.h);

  // спавн шара каждые 60 кадров
  if (frame % 60 === 0 && ballSeq.length > 0) {
    const color = ballSeq[frame/60 | 0] || 'blue';
    const colorMap = {gold:'#FFD700', blue:'#4fc3f7', red:'#ef5350', green:'#66bb6a'};
    balls.push({x: Math.random()*440+20, y:0, vy:2.5,
                color: colorMap[color]||'#fff', name:color});
  }
  // движение мышки/касания
  balls.forEach(b => {
    b.y += b.vy;
    cx.beginPath(); cx.arc(b.x,b.y,10,0,Math.PI*2);
    cx.fillStyle=b.color; cx.fill();
  });
  balls = balls.filter(b => b.y < 330);

  frame++;
  document.getElementById('info').textContent = 'Кадр: '+frame+' | Сессия: '+(sessionId||'—');
  raf = requestAnimationFrame(loop);
}

// управление мышью
cv.addEventListener('mousemove', e => {
  const rect = cv.getBoundingClientRect();
  basket.x = Math.min(Math.max(e.clientX - rect.left - basket.w/2, 0), 480-basket.w);
});
</script>
</body>
</html>
""".replace("{API_BASE}", API).replace("{TOKEN}", token)

components.html(SNAKE_HTML, height=420, scrolling=False)

st.markdown("---")
with st.expander("Последние сессии"):
    try:
        hist = requests.get(f"{API}/snake/history",
                            headers=headers, timeout=5).json()
        import pandas as pd
        st.dataframe(pd.DataFrame(hist.get("items", [])), use_container_width=True)
    except Exception:
        st.info("Нет данных")
