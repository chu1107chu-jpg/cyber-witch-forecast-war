/* ══════════════════════════════════════════════════════
   POLITICAL ARENA — 3D Fight Engine
   Three.js primitives + physics + blood particles
   ══════════════════════════════════════════════════════ */

// ── Helpers ─────────────────────────────────────────────
const $ = id => document.getElementById(id);

function showScreen(id) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  const el = $(id);
  if (el) el.classList.add('active');
}

// ── Game State ───────────────────────────────────────────
let scene, camera, renderer, animFrame;
let fighterA, fighterB;
let gs = null;
let fighters = [];
let selectedA = null, selectedB = null;
let gameMode = 'pve';
let round = 1, maxRounds = 3;
let timeLeft = 45, timerInterval = null;
let paused = false;
let keys = {};
let moveKeys = {};  // held movement keys
let aiTimeout = null;
let clock;

// ── Three.js Init ────────────────────────────────────────
function initThree() {
  const canvas = $('gameCanvas');
  renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x120f18);
  scene.fog = new THREE.FogExp2(0x120f18, 0.018);

  camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 100);
  camera.position.set(0, 2.5, 7);
  camera.lookAt(0, 1.5, 0);

  clock = new THREE.Clock();

  // Lighting
  const ambient = new THREE.AmbientLight(0x8a5a62, 2.4);
  scene.add(ambient);
  const spot = new THREE.SpotLight(0xffaa66, 7.5, 24, Math.PI / 4.5, 0.35);
  spot.position.set(0, 8, 3);
  spot.castShadow = true;
  spot.shadow.mapSize.width = 512;
  spot.shadow.mapSize.height = 512;
  scene.add(spot);
  const fillL = new THREE.PointLight(0x2b7fff, 3.2, 18);
  fillL.position.set(-4, 3, 2);
  scene.add(fillL);
  const fillR = new THREE.PointLight(0xff4477, 3.2, 18);
  fillR.position.set(4, 3, 2);
  scene.add(fillR);
  const front = new THREE.PointLight(0xffffff, 1.6, 14);
  front.position.set(0, 2.8, 5);
  scene.add(front);

  // Floor
  const floorGeo = new THREE.PlaneGeometry(20, 20);
  const floorMat = new THREE.MeshStandardMaterial({ color: 0x1c1824, roughness: 0.88, metalness: 0.12 });
  const floor = new THREE.Mesh(floorGeo, floorMat);
  floor.rotation.x = -Math.PI / 2;
  floor.receiveShadow = true;
  scene.add(floor);

  // Floor grid lines
  const gridHelper = new THREE.GridHelper(20, 20, 0x222233, 0x222233);
  gridHelper.position.y = 0.002;
  scene.add(gridHelper);

  // Background walls
  addArenaWalls();

  window.addEventListener('resize', onResize);
}

function addArenaWalls() {
  // Back wall
  const wallGeo = new THREE.PlaneGeometry(20, 8);
  const wallMat = new THREE.MeshStandardMaterial({ color: 0x0d0d1a, roughness: 1 });
  const backWall = new THREE.Mesh(wallGeo, wallMat);
  backWall.position.set(0, 4, -6);
  scene.add(backWall);

  // Neon strips on walls
  const neonColors = [0xff0044, 0x0044ff, 0xff4400, 0x00aaff];
  neonColors.forEach((c, i) => {
    const stripGeo = new THREE.BoxGeometry(0.05, 5, 0.05);
    const stripMat = new THREE.MeshBasicMaterial({ color: c });
    const strip = new THREE.Mesh(stripGeo, stripMat);
    strip.position.set(-8 + i * 5, 2.5, -5.9);
    scene.add(strip);
    const light = new THREE.PointLight(c, 1.5, 6);
    light.position.copy(strip.position);
    scene.add(light);
  });

  // Torches
  [-4, 4].forEach(x => {
    const torchLight = new THREE.PointLight(0xff5500, 3, 8);
    torchLight.position.set(x, 4, -3);
    scene.add(torchLight);
    // flicker
    torchLight.userData.flicker = true;
    torchLight.userData.baseIntensity = 3;
  });
}

function onResize() {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
}

// ── Fighter 3D Model ─────────────────────────────────────
class Fighter3D {
  constructor(data, side) {
    this.data = data;
    this.side = side;
    this.group = new THREE.Group();
    this.parts = {};
    this.hp = data.hp || 200;
    this.maxHp = data.hp || 200;
    this.atk = data.atk || 50;
    this.def = data.def || 30;
    this.combo = 0;
    this.blocking = false;
    this.ultimate = null;
    this.taunt = data.taunt || '';
    this.animQueue = [];
    this.currentAnim = 'idle';
    this.animTime = 0;
    this.faceTexture = null;
    this.loader = new THREE.TextureLoader();
    this._build();
    this._loadFace();
  }

  _build() {
    const color = this._parseColor(this.data.color || '#ff4444');
    const darkColor = new THREE.Color(color).multiplyScalar(0.4);

    // Materials
    const bodyMat = new THREE.MeshStandardMaterial({ color, roughness: 0.6, metalness: 0.2 });
    const darkMat = new THREE.MeshStandardMaterial({ color: darkColor, roughness: 0.7 });
    const skinMat = new THREE.MeshStandardMaterial({ color: 0xffccaa, roughness: 0.8 });
    const darkSkinMat = new THREE.MeshStandardMaterial({ color: 0xcc8844, roughness: 0.8 });

    // HEAD
    const headGeo = new THREE.SphereGeometry(0.34, 24, 24);
    this.parts.head = new THREE.Mesh(headGeo, skinMat.clone());
    this.parts.head.position.set(0, 1.76, 0);
    this.parts.head.castShadow = true;

    // Face plane on head (for photo)
    const faceGeo = new THREE.PlaneGeometry(0.5, 0.5);
    this.faceMat = new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, side: THREE.DoubleSide });
    this.parts.face = new THREE.Mesh(faceGeo, this.faceMat);
    this.parts.face.position.set(0, 1.76, 0.325);
    this.parts.face.rotation.y = this.side === 'A' ? 0 : Math.PI;

    // NECK
    const neckGeo = new THREE.CylinderGeometry(0.11, 0.13, 0.22, 12);
    this.parts.neck = new THREE.Mesh(neckGeo, skinMat.clone());
    this.parts.neck.position.set(0, 1.48, 0);

    // TORSO
    const torsoGeo = new THREE.BoxGeometry(0.68, 0.78, 0.36);
    this.parts.torso = new THREE.Mesh(torsoGeo, bodyMat.clone());
    this.parts.torso.position.set(0, 1.03, 0);
    this.parts.torso.castShadow = true;

    // HIPS
    const hipsGeo = new THREE.BoxGeometry(0.56, 0.24, 0.32);
    this.parts.hips = new THREE.Mesh(hipsGeo, darkMat.clone());
    this.parts.hips.position.set(0, 0.62, 0);

    // UPPER ARMS
    const upperArmGeo = new THREE.CylinderGeometry(0.1, 0.085, 0.42, 10);
    this.parts.upperArmL = new THREE.Mesh(upperArmGeo, bodyMat.clone());
    this.parts.upperArmL.position.set(-0.46, 1.08, 0);
    this.parts.upperArmL.rotation.z = 0.28;

    this.parts.upperArmR = new THREE.Mesh(upperArmGeo, bodyMat.clone());
    this.parts.upperArmR.position.set(0.46, 1.08, 0);
    this.parts.upperArmR.rotation.z = -0.28;

    // FOREARMS
    const foreArmGeo = new THREE.CylinderGeometry(0.08, 0.065, 0.38, 10);
    this.parts.foreArmL = new THREE.Mesh(foreArmGeo, skinMat.clone());
    this.parts.foreArmL.position.set(-0.5, 0.7, 0);

    this.parts.foreArmR = new THREE.Mesh(foreArmGeo, skinMat.clone());
    this.parts.foreArmR.position.set(0.5, 0.7, 0);

    // FISTS
    const fistGeo = new THREE.BoxGeometry(0.18, 0.15, 0.16);
    this.parts.fistL = new THREE.Mesh(fistGeo, darkSkinMat.clone());
    this.parts.fistL.position.set(-0.54, 0.5, 0.01);

    this.parts.fistR = new THREE.Mesh(fistGeo, darkSkinMat.clone());
    this.parts.fistR.position.set(0.54, 0.5, 0.01);

    // UPPER LEGS
    const upperLegGeo = new THREE.CylinderGeometry(0.13, 0.11, 0.48, 12);
    this.parts.upperLegL = new THREE.Mesh(upperLegGeo, darkMat.clone());
    this.parts.upperLegL.position.set(-0.19, 0.3, 0);

    this.parts.upperLegR = new THREE.Mesh(upperLegGeo, darkMat.clone());
    this.parts.upperLegR.position.set(0.19, 0.3, 0);

    // LOWER LEGS
    const lowerLegGeo = new THREE.CylinderGeometry(0.1, 0.085, 0.44, 12);
    this.parts.lowerLegL = new THREE.Mesh(lowerLegGeo, bodyMat.clone());
    this.parts.lowerLegL.position.set(-0.19, -0.07, 0);

    this.parts.lowerLegR = new THREE.Mesh(lowerLegGeo, bodyMat.clone());
    this.parts.lowerLegR.position.set(0.19, -0.07, 0);

    // FEET
    const footGeo = new THREE.BoxGeometry(0.18, 0.09, 0.28);
    this.parts.footL = new THREE.Mesh(footGeo, darkMat.clone());
    this.parts.footL.position.set(-0.2, -0.3, 0.06);

    this.parts.footR = new THREE.Mesh(footGeo, darkMat.clone());
    this.parts.footR.position.set(0.2, -0.3, 0.06);

    // SHOULDERS
    const shoulderGeo = new THREE.SphereGeometry(0.11, 14, 14);
    this.parts.shoulderL = new THREE.Mesh(shoulderGeo, bodyMat.clone());
    this.parts.shoulderL.position.set(-0.34, 1.2, 0);
    this.parts.shoulderR = new THREE.Mesh(shoulderGeo, bodyMat.clone());
    this.parts.shoulderR.position.set(0.34, 1.2, 0);

    // Add all parts to group
    Object.values(this.parts).forEach(m => {
      m.castShadow = true;
      this.group.add(m);
    });

    // Name badge floating above head
    this.group.position.set(this.side === 'A' ? -2.2 : 2.2, 0, 0);
    this.group.rotation.y = this.side === 'A' ? 0.08 : -0.08;
    if (this.side === 'B') this.group.scale.x = -1;

    scene.add(this.group);
  }

  _parseColor(hex) {
    try { return parseInt(hex.replace('#',''), 16); }
    catch(e) { return 0xff4444; }
  }

  _loadFace() {
    const avatarPath = this.data.avatar;
    if (!avatarPath) return;
    this.loader.load(avatarPath, tex => {
      tex.minFilter = THREE.LinearFilter;
      this.faceMat.map = tex;
      this.faceMat.needsUpdate = true;
    }, undefined, () => {
      // Load failed - use emoji fallback color
    });
  }

  setUltimate(moves) {
    if (!moves || !moves.length) return;
    const ult = moves.find(m => m.type === 'ultimate') || moves[moves.length - 1];
    this.ultimate = ult;
  }

  // ── Animations ──────────────────────────────────────────
  playAnim(name, duration = 400) {
    this.currentAnim = name;
    this.animTime = 0;
    this.animDuration = duration;
    this._animStart = Date.now();
  }

  updateAnim(delta) {
    const t = Math.min((Date.now() - (this._animStart || Date.now())) / (this.animDuration || 400), 1);
    const sin = Math.sin(t * Math.PI);
    const dir = this.side === 'A' ? 1 : -1;

    switch(this.currentAnim) {
      case 'idle':
        // Fighting stance bounce
        const breathe = Math.sin(Date.now() * 0.0036) * 0.045;
        const sway = Math.sin(Date.now() * 0.002) * 0.06;
        this.parts.torso.position.y = 1.03 + breathe;
        this.parts.head.position.y = 1.76 + breathe * 0.85;
        this.parts.neck.position.y = 1.48 + breathe * 0.65;
        this.parts.hips.position.y = 0.62 - breathe * 0.25;

        this.parts.upperArmL.rotation.z = 0.45 + sway;
        this.parts.upperArmR.rotation.z = -0.45 - sway;
        this.parts.foreArmL.rotation.z = 0.18 + sway * 0.6;
        this.parts.foreArmR.rotation.z = -0.18 - sway * 0.6;

        this.parts.upperLegL.rotation.x = -0.08 + breathe * 0.4;
        this.parts.upperLegR.rotation.x = 0.05 - breathe * 0.3;
        this.parts.torso.rotation.y = Math.sin(Date.now() * 0.0016) * 0.12 * dir;
        break;

      case 'punch':
        this.parts.upperArmR.rotation.z = -0.42 - sin * 0.95;
        this.parts.foreArmR.rotation.z = -0.2 - sin * 0.75;
        this.parts.fistR.position.z = sin * 0.62 * dir;
        this.parts.fistR.position.x = 0.54 + sin * 0.16;
        this.parts.fistR.position.y = 0.5 + sin * 0.08;
        this.parts.torso.rotation.y = sin * 0.35 * dir;
        this.parts.head.rotation.y = sin * 0.12 * dir;
        if (t >= 1) this.playAnim('idle');
        break;

      case 'punch2':
        this.parts.upperArmL.rotation.z = 0.42 + sin * 0.95;
        this.parts.foreArmL.rotation.z = 0.2 + sin * 0.75;
        this.parts.fistL.position.z = sin * 0.62 * dir;
        this.parts.fistL.position.x = -0.54 - sin * 0.16;
        this.parts.fistL.position.y = 0.5 + sin * 0.08;
        this.parts.torso.rotation.y = -sin * 0.35 * dir;
        this.parts.head.rotation.y = -sin * 0.12 * dir;
        if (t >= 1) this.playAnim('idle');
        break;

      case 'kick':
        this.parts.upperLegR.rotation.x = -sin * 1.35;
        this.parts.lowerLegR.rotation.x = -sin * 0.9;
        this.parts.footR.position.z = sin * 0.7 * dir;
        this.parts.footR.position.y = -0.3 + sin * 0.5;
        this.parts.torso.rotation.y = sin * 0.18 * dir;
        if (t >= 1) { this._resetLegs(); this.playAnim('idle'); }
        break;

      case 'highkick':
        this.parts.upperLegR.rotation.x = -sin * 1.8;
        this.parts.lowerLegR.rotation.x = -sin * 0.55;
        this.parts.footR.position.y = -0.3 + sin * 1.0;
        this.parts.footR.position.z = sin * 0.42 * dir;
        this.parts.torso.rotation.y = sin * 0.26 * dir;
        if (t >= 1) { this._resetLegs(); this.playAnim('idle'); }
        break;

      case 'block':
        // Arms up in guard
        this.parts.upperArmL.rotation.z = 0.8;
        this.parts.upperArmR.rotation.z = -0.8;
        this.parts.foreArmL.rotation.z = 0.6;
        this.parts.foreArmR.rotation.z = -0.6;
        this.parts.foreArmL.position.y = 1.1;
        this.parts.foreArmR.position.y = 1.1;
        break;

      case 'hit':
        this.parts.torso.position.x = -sin * 0.28 * dir;
        this.parts.head.position.x = -sin * 0.34 * dir;
        this.parts.torso.rotation.z = -sin * 0.12 * dir;
        this.parts.head.rotation.z = -sin * 0.15 * dir;
        if (t >= 1) this.playAnim('idle');
        break;

      case 'special':
        // Big windup + flash
        const s = Math.sin(t * Math.PI * 2);
        this.parts.upperArmR.rotation.z = -0.2 - sin * 1.2;
        this.parts.upperArmL.rotation.z = 0.2 + sin * 0.8;
        this.parts.torso.rotation.y = s * 0.4 * dir;
        this.group.position.y = sin * 0.3;
        if (t >= 1) { this.group.position.y = 0; this.playAnim('idle'); }
        break;

      case 'ko':
        // Fall back
        const fallT = Math.min(t * 1.5, 1);
        this.group.rotation.z = fallT * 1.4 * dir;
        this.group.position.y = -fallT * 0.5;
        break;
    }
  }

  _resetLegs() {
    this.parts.upperLegL.rotation.x = 0; this.parts.upperLegR.rotation.x = 0;
    this.parts.lowerLegL.rotation.x = 0; this.parts.lowerLegR.rotation.x = 0;
    this.parts.footL.position.set(-0.2, -0.3, 0.06); this.parts.footR.position.set(0.2, -0.3, 0.06);
  }

  _resetArms() {
    this.parts.upperArmL.rotation.z = 0.45; this.parts.upperArmR.rotation.z = -0.45;
    this.parts.foreArmL.rotation.z = 0.18; this.parts.foreArmR.rotation.z = -0.18;
    this.parts.foreArmL.position.set(-0.5, 0.7, 0); this.parts.foreArmR.position.set(0.5, 0.7, 0);
    this.parts.fistL.position.set(-0.54, 0.5, 0.01); this.parts.fistR.position.set(0.54, 0.5, 0.01);
    this.parts.torso.rotation.y = 0; this.parts.torso.position.y = 1.03;
    this.parts.head.rotation.y = 0; this.parts.head.rotation.z = 0;
  }

  resetBlockPose() {
    this._resetArms();
    this._resetLegs();
    this.playAnim('idle');
  }

  takeDamage(dmg) {
    this.hp = Math.max(0, this.hp - dmg);
    this.playAnim('hit', 300);
    updateHPBar(this.side);
    if (this.hp <= 0) this.playAnim('ko', 800);
  }

  unblockReset() {
    if (this.currentAnim === 'block') {
      this._resetArms();
      this.playAnim('idle');
    }
  }

  get x() { return this.group.position.x; }
  set x(v) { this.group.position.x = v; }
}

// ── Load Fighters ────────────────────────────────────────
async function loadFighters() {
  try {
    const res = await fetch('/api/fighters');
    const _d = await res.json();
    fighters = Array.isArray(_d) ? _d : (_d.fighters || _d.data || Object.values(_d));
    renderRoster();

    // Warm avatar cache for faster pick-slot updates
    fighters.forEach(f => {
      if (!f.avatar) return;
      const img = new Image();
      img.decoding = 'async';
      img.src = f.avatar;
    });

    // Warm Three.js lazily after roster is shown, not on click
    const warm = () => {
      try { if (!renderer) initThree(); } catch(e) { console.warn('warm init failed', e); }
    };
    if ('requestIdleCallback' in window) requestIdleCallback(warm, { timeout: 1200 });
    else setTimeout(warm, 400);
  } catch(e) {
    console.error('Failed to load fighters', e);
  }
}

function renderRoster() {
  const grid = $('rosterGrid');
  grid.innerHTML = '';
  grid.style.cssText = 'display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:12px;width:100%;max-width:1100px;padding:0 16px;max-height:60vh;overflow-y:auto';

  fighters.forEach(f => {
    const card = document.createElement('div');
    card.className = 'roster-card';
    card.dataset.id = f.id;
    card.style.cssText = 'border:2px solid #333;border-radius:14px;overflow:hidden;cursor:pointer;transition:all .15s;position:relative;background:#161825;min-height:280px';

    const tierColors = {legendary:'#ffd700',epic:'#b44dff',rare:'#00d4ff',uncommon:'#00ff88',common:'#888'};
    const tc = tierColors[f.tier] || '#888';

    card.innerHTML = `
      <div style="position:relative;width:100%;height:200px;overflow:hidden;background:${f.gradient||'#222'}">
        <img src="${f.avatar}" alt="${f.name}" loading="lazy"
             style="width:100%;height:100%;object-fit:cover;display:block"
             onerror="this.style.display='none'">
        <div style="position:absolute;bottom:0;left:0;right:0;height:60%;background:linear-gradient(transparent,rgba(22,24,37,.95))"></div>
        <div style="position:absolute;top:8px;left:8px;font-size:16px">${f.country||''}</div>
        <div style="position:absolute;top:8px;right:8px;background:${tc};color:#000;font-size:9px;font-weight:900;padding:2px 8px;border-radius:4px;text-transform:uppercase;letter-spacing:1px">${f.tier||''}</div>
      </div>
      <div style="padding:10px 12px">
        <div style="font-size:13px;font-weight:700;color:#fff;margin-bottom:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${f.name}</div>
        <div style="font-size:9px;color:${tc};margin-bottom:8px;text-transform:uppercase;letter-spacing:1px">${f.type||''}</div>
        <div style="display:flex;align-items:center;gap:5px;margin-bottom:3px"><span style="font-size:9px;color:#aaa;width:24px;font-weight:700">HP</span><div style="flex:1;height:4px;background:rgba(255,255,255,.06);border-radius:2px;overflow:hidden"><div style="width:${Math.min((f.hp||0)/3,100)}%;height:100%;background:#22c55e;border-radius:2px"></div></div><span style="font-size:9px;color:#888;width:24px;text-align:right">${f.hp}</span></div>
        <div style="display:flex;align-items:center;gap:5px;margin-bottom:3px"><span style="font-size:9px;color:#aaa;width:24px;font-weight:700">ATK</span><div style="flex:1;height:4px;background:rgba(255,255,255,.06);border-radius:2px;overflow:hidden"><div style="width:${Math.min((f.atk||0)*1.6,100)}%;height:100%;background:#e63946;border-radius:2px"></div></div><span style="font-size:9px;color:#888;width:24px;text-align:right">${f.atk}</span></div>
        <div style="display:flex;align-items:center;gap:5px;margin-bottom:3px"><span style="font-size:9px;color:#aaa;width:24px;font-weight:700">DEF</span><div style="flex:1;height:4px;background:rgba(255,255,255,.06);border-radius:2px;overflow:hidden"><div style="width:${Math.min((f.def||0)*2,100)}%;height:100%;background:#3b82f6;border-radius:2px"></div></div><span style="font-size:9px;color:#888;width:24px;text-align:right">${f.def}</span></div>
        <div style="display:flex;align-items:center;gap:5px"><span style="font-size:9px;color:#aaa;width:24px;font-weight:700">SPD</span><div style="flex:1;height:4px;background:rgba(255,255,255,.06);border-radius:2px;overflow:hidden"><div style="width:${Math.min((f.spd||0)*12,100)}%;height:100%;background:#ffd700;border-radius:2px"></div></div><span style="font-size:9px;color:#888;width:24px;text-align:right">${f.spd}</span></div>
      </div>`;
    card.addEventListener('click', () => selectFighter(f.id));
    grid.appendChild(card);
  });
}

function selectFighter(id) {
  console.log('selectFighter called:', id, 'gameMode:', gameMode);
  const f = fighters.find(x => x.id === id);
  if (!f) return;

  if (gameMode === 'pvp') {
    // PvP: first click = A, second = B
    if (!selectedA || selectedB) {
      selectedA = f; selectedB = null;
      updatePickSlot('A', f);
      document.querySelectorAll('.roster-card').forEach(c => {
        c.classList.remove('sel-a','sel-b');
        c.classList.toggle('sel-a', c.dataset.id === String(id));
      });
    } else {
      selectedB = f;
      updatePickSlot('B', f);
      document.querySelectorAll('.roster-card').forEach(c => {
        c.classList.toggle('sel-b', c.dataset.id === String(id));
      });
    }
  } else {
    // PvE: click = set A, auto-pick random B
    selectedA = f;
    updatePickSlot('A', f);
    document.querySelectorAll('.roster-card').forEach(c => {
      c.classList.remove('sel-a','sel-b');
      c.classList.toggle('sel-a', c.dataset.id === String(id));
    });
    // Auto-pick random opponent
    const others = fighters.filter(x => x.id !== f.id);
    if (others.length) {
      selectedB = others[Math.floor(Math.random() * others.length)];
      updatePickSlot('B', selectedB);
      document.querySelectorAll('.roster-card').forEach(c => {
        c.classList.toggle('sel-b', c.dataset.id === String(selectedB.id));
      });
    }
  }
  checkStartReady();
}

function updatePickSlot(side, f) {
  $(`pick${side}Name`).textContent = f.name;
  const emoji = $(`pick${side}Emoji`);
  const img = $(`pick${side}Img`);
  if (f.avatar) {
    img.src = f.avatar; img.style.display = 'block'; emoji.style.display = 'none';
  } else {
    emoji.textContent = f.emoji || '👤'; emoji.style.display = 'block'; img.style.display = 'none';
  }
}

function updateHudAvatars() {
  const a = $('hudAvatarA');
  const b = $('hudAvatarB');
  if (a) a.src = selectedA?.avatar || '';
  if (b) b.src = selectedB?.avatar || '';
}

function checkStartReady() {
  console.log('checkStartReady:', 'A=', selectedA?.name, 'B=', selectedB?.name, 'mode=', gameMode, 'result=', !!(selectedA && (selectedB || gameMode === 'pve')));
  $('btnStart').disabled = !(selectedA && (selectedB || gameMode === 'pve'));
}

function setMode(mode) {
  gameMode = mode;
  $('modePvE').classList.toggle('active', mode === 'pve');
  $('modePvP').classList.toggle('active', mode === 'pvp');
  if (mode === 'pve' && !selectedB) {
    const others = fighters.filter(f => f.id !== selectedA?.id);
    if (others.length) { selectedB = others[Math.floor(Math.random() * others.length)]; updatePickSlot('B', selectedB); }
  }
  checkStartReady();
}

// ── Blood Particles ──────────────────────────────────────
const bloodCanvas = $('bloodCanvas');
const bctx = bloodCanvas.getContext('2d');
let bloodParticles = [];
let bloodPools = [];

function resizeBloodCanvas() {
  bloodCanvas.width = window.innerWidth;
  bloodCanvas.height = window.innerHeight;
}
resizeBloodCanvas();
window.addEventListener('resize', resizeBloodCanvas);

function spawnBlood(screenX, screenY, count, big) {
  for (let i = 0; i < count; i++) {
    const angle = Math.random() * Math.PI * 2;
    const speed = (big ? 4 : 2) + Math.random() * (big ? 8 : 4);
    bloodParticles.push({
      x: screenX, y: screenY,
      vx: Math.cos(angle) * speed,
      vy: Math.sin(angle) * speed - (big ? 5 : 2),
      r: (big ? 4 : 2) + Math.random() * (big ? 6 : 3),
      life: 1, decay: 0.02 + Math.random() * 0.03,
      gravity: 0.25
    });
  }
}

function spawnBloodPool(x, y, size) {
  bloodPools.push({ x, y, r: 0, maxR: size, grow: 0.8, alpha: 0.7 });
}

function updateBlood() {
  bctx.clearRect(0, 0, bloodCanvas.width, bloodCanvas.height);

  // Pools
  bloodPools.forEach(p => {
    if (p.r < p.maxR) p.r += p.grow;
    bctx.beginPath();
    bctx.ellipse(p.x, p.y, p.r, p.r * 0.35, 0, 0, Math.PI * 2);
    bctx.fillStyle = `rgba(120,0,0,${p.alpha})`;
    bctx.fill();
  });
  if (bloodPools.length > 20) bloodPools.shift();

  // Particles
  bloodParticles = bloodParticles.filter(p => p.life > 0);
  bloodParticles.forEach(p => {
    p.x += p.vx; p.y += p.vy;
    p.vy += p.gravity;
    p.vx *= 0.96;
    p.life -= p.decay;
    bctx.beginPath();
    bctx.arc(p.x, p.y, p.r * p.life, 0, Math.PI * 2);
    bctx.fillStyle = `rgba(180,0,0,${p.life})`;
    bctx.fill();
    // Splat when hitting bottom
    if (p.y > window.innerHeight - 80 && p.life > 0.3) {
      spawnBloodPool(p.x, window.innerHeight - 70 + Math.random() * 20, 8 + Math.random() * 12);
      p.life = 0;
    }
  });
}

// Convert 3D world position to screen coords
function worldToScreen(pos3d) {
  const v = pos3d.clone().project(camera);
  return {
    x: (v.x + 1) / 2 * window.innerWidth,
    y: (-v.y + 1) / 2 * window.innerHeight
  };
}

function triggerBlood(fighter, big) {
  if (!fighter) return;
  const hitPos = fighter.parts.torso.getWorldPosition(new THREE.Vector3());
  hitPos.y += 0.4;
  const sc = worldToScreen(hitPos);
  spawnBlood(sc.x, sc.y, big ? 20 : 8, big);
  if (big) spawnBloodPool(sc.x, sc.y + 60, 20 + Math.random() * 20);
  // Red flash on screen
  screenFlash(big ? 'rgba(139,0,0,0.35)' : 'rgba(139,0,0,0.15)', big ? 200 : 100);
}

function screenFlash(color, duration) {
  bctx.fillStyle = color;
  bctx.fillRect(0, 0, bloodCanvas.width, bloodCanvas.height);
  setTimeout(() => bctx.clearRect(0, 0, bloodCanvas.width, bloodCanvas.height), duration);
}

// ── Camera Shake ─────────────────────────────────────────
let shakeMag = 0, shakeDecay = 0;
function cameraShake(mag) {
  shakeMag = Math.max(shakeMag, mag);
  shakeDecay = 0.85;
}

// ── HUD Update ───────────────────────────────────────────
function updateHPBar(side) {
  const f = side === 'A' ? fighterA : fighterB;
  if (!f) return;
  const pct = Math.max(0, (f.hp / f.maxHp) * 100);
  $(`hpFill${side}`).style.width = pct + '%';
  // Color: green>yellow>red
  const fill = $(`hpFill${side}`);
  if (pct > 60) fill.style.background = 'linear-gradient(90deg,#00c851,#00e676)';
  else if (pct > 30) fill.style.background = 'linear-gradient(90deg,#ffbb33,#ffd700)';
  else fill.style.background = 'linear-gradient(90deg,#e63946,#ff2200)';
}

function updateComboBadge(side) {
  const f = side === 'A' ? fighterA : fighterB;
  if (!f) return;
  const badge = $(`comboBadge${side}`);
  if (f.combo >= 3) {
    badge.textContent = '⚡ READY!';
    badge.style.color = '#ff4400';
    $(`tbtnSuper`)?.classList.add('ready');
  } else if (f.combo > 0) {
    badge.textContent = '●'.repeat(f.combo);
    badge.style.color = '#ffd700';
    $(`tbtnSuper`)?.classList.remove('ready');
  } else {
    badge.textContent = '';
    $(`tbtnSuper`)?.classList.remove('ready');
  }
}

function showComboFloat(x, y, text) {
  const el = document.createElement('div');
  el.className = 'combo-float';
  el.style.left = x + 'px'; el.style.top = y + 'px';
  el.style.fontSize = (20 + text.length) + 'px';
  el.textContent = text;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 900);
}

// ── Super Overlay ────────────────────────────────────────
function showSuperOverlay(fighter, moveName, moveDesc) {
  $('superFighterName').textContent = fighter.data.name.toUpperCase();
  $('superMoveName').textContent = moveName;
  $('superMoveDesc').textContent = moveDesc || '';
  const ov = $('superOverlay');
  ov.classList.add('show');
  AudioEngine.special();
  cameraShake(0.4);
  setTimeout(() => ov.classList.remove('show'), 1200);
}

// ── Fight Start ──────────────────────────────────────────
async function startFight3D() {
  console.log('startFight3D called, selectedA:', selectedA?.name, 'selectedB:', selectedB?.name);
  if (!selectedA) return;
  try { if (sfx && !sfx.ctx) sfx.init(); if (sfx?.ctx?.state === 'suspended') sfx.ctx.resume(); } catch(e) {}
  try { AudioEngine.uiClick(); } catch(e) {}

  // Auto-pick B for PvE
  if (gameMode === 'pve' && !selectedB) {
    const others = fighters.filter(f => f.id !== selectedA.id);
    selectedB = others[Math.floor(Math.random() * others.length)];
  }

  showScreen('');
  $('hud').style.display = 'block';
  $('touchControls').style.display = 'flex';
  $('pauseBtn').style.display = 'flex';

  // Init Three.js if needed
  if (!renderer) initThree();
  if (renderer && scene && camera) {
    renderer.setSize(window.innerWidth, window.innerHeight);
  }

  // Clear previous fighters
  if (fighterA) { scene.remove(fighterA.group); fighterA = null; }
  if (fighterB) { scene.remove(fighterB.group); fighterB = null; }
  bloodParticles = []; bloodPools = [];

  // Use already loaded roster data for instant start
  selectedA = fighters.find(f => f.id === selectedA.id) || selectedA;
  selectedB = fighters.find(f => f.id === selectedB.id) || selectedB;

  fighterA = new Fighter3D(selectedA, 'A');
  fighterB = new Fighter3D(selectedB, 'B');
  fighterA.setUltimate(selectedA.moves);
  fighterB.setUltimate(selectedB.moves);

  $('hudNameA').textContent = selectedA.name;
  $('hudNameB').textContent = selectedB.name;
  updateHudAvatars();

  gs = { winner: null, round };

  round = 1;
  $('roundLabel').textContent = `РАУНД ${round}`;
  showRoundBreak('РАУНД ' + round, 'НАЧАЛО!', () => {
    console.log('Round break done, starting fight loop...');
    startTimer();
    try { AudioEngine.startBg(); } catch(e) {}
    if (gameMode === 'pve') scheduleAI();
    if (!animFrame) gameLoop();
    console.log('gameLoop started, fighterA:', !!fighterA, 'fighterB:', !!fighterB);
  });
}

function showRoundBreak(title, sub, cb) {
  const el = $('roundBreak');
  $('roundBreakTitle').textContent = title;
  el.classList.add('show');
  try { AudioEngine.countdownGo(); } catch(e) {}
  setTimeout(() => { el.classList.remove('show'); if (cb) cb(); }, 1500);
}

// ── Timer ────────────────────────────────────────────────
function startTimer() {
  clearInterval(timerInterval);
  timeLeft = 45;
  $('timerBox').textContent = timeLeft;
  $('timerBox').classList.remove('urgent');
  timerInterval = setInterval(() => {
    if (paused || gs?.winner) return;
    timeLeft--;
    $('timerBox').textContent = timeLeft;
    if (timeLeft <= 10) $('timerBox').classList.add('urgent');
    if (timeLeft <= 5 && timeLeft > 0) AudioEngine.countdown();
    if (timeLeft <= 0) { clearInterval(timerInterval); timeoutEnd(); }
  }, 1000);
}

function timeoutEnd() {
  if (!fighterA || !fighterB) return;
  const winner = fighterA.hp >= fighterB.hp ? 'A' : 'B';
  endFight(winner);
}

// ── Combat ───────────────────────────────────────────────
function doAction(side, action) {
  if (!gs || gs.winner || paused) return;
  const atk = side === 'A' ? fighterA : fighterB;
  const def = side === 'A' ? fighterB : fighterA;
  if (!atk || !def) return;

  if (action === 'block') {
    atk.blocking = true; atk.playAnim('block', 600);
    AudioEngine.block(); return;
  }
  if (action === 'unblock') {
    atk.blocking = false; atk.unblockReset(); return;
  }
  if (action === 'special') {
    if (atk.combo < 3) return;
    doSpecial(atk, def); return;
  }

  let mult = 1.0, animName = 'punch';
  if (action === 'punch')  { mult = 0.9 + Math.random() * 0.2; animName = Math.random() > 0.5 ? 'punch' : 'punch2'; AudioEngine.punch(); }
  if (action === 'kick')   { mult = 1.5 + Math.random() * 0.3; animName = Math.random() > 0.5 ? 'kick' : 'highkick'; AudioEngine.kick(); }

  atk.playAnim(animName, 300);

  setTimeout(() => {
    if (!def || !atk || gs?.winner) return;
    if (def.blocking) {
      AudioEngine.block();
      triggerBlood(def, false);
      showComboFloatOnFighter(def, '🛡 БЛОК!');
      return;
    }
    const rand = 0.8 + Math.random() * 0.4;
    const dmg = Math.max(1, Math.round(atk.atk * mult * rand - def.def * 0.25));
    def.takeDamage(dmg);
    atk.combo = Math.min(atk.combo + 1, 3);
    updateComboBadge(side);
    triggerBlood(def, dmg > 40);
    cameraShake(dmg > 40 ? 0.25 : 0.1);
    showDmgFloat(def, dmg, mult >= 1.5);
    if (def.hp <= 0) { setTimeout(() => endFight(side), 300); }
  }, 180);
}

function doSpecial(atk, def) {
  const move = atk.ultimate;
  const moveName = move ? move.name : 'СУПЕРУДАР';
  const moveDesc = move ? (move.desc || '') : '';

  atk.combo = 0; updateComboBadge(atk.side);
  atk.playAnim('special', 600);
  showSuperOverlay(atk, moveName, moveDesc);
  cameraShake(0.5);

  setTimeout(() => {
    if (!def || gs?.winner) return;
    if (def.blocking) def.blocking = false;
    const dmg = Math.round(atk.atk * (1.8 + Math.random() * 0.5));
    def.takeDamage(dmg);
    triggerBlood(def, true);
    showDmgFloat(def, dmg, true);
    if (def.hp <= 0) setTimeout(() => endFight(atk.side), 400);
  }, 500);
}

function showDmgFloat(def, dmg, big) {
  const pos = def.parts.head.getWorldPosition(new THREE.Vector3());
  pos.y += 0.6;
  const sc = worldToScreen(pos);
  const el = document.createElement('div');
  el.className = 'combo-float';
  el.style.left = sc.x + 'px'; el.style.top = (sc.y - 30) + 'px';
  el.style.fontSize = big ? '32px' : '22px';
  el.style.color = big ? '#ff4400' : '#fff';
  el.textContent = `-${dmg}`;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 900);
}

function showComboFloatOnFighter(f, text) {
  const pos = f.parts.head.getWorldPosition(new THREE.Vector3());
  const sc = worldToScreen(pos);
  showComboFloat(sc.x - 30, sc.y - 60, text);
}

// ── End Fight ────────────────────────────────────────────
function endFight(winSide) {
  if (gs?.winner) return;
  gs.winner = winSide;
  clearInterval(timerInterval);
  if (aiTimeout) clearTimeout(aiTimeout);
  AudioEngine.stopBg();
  AudioEngine.win();

  const winner = winSide === 'A' ? fighterA : fighterB;
  const loser  = winSide === 'A' ? fighterB : fighterA;
  if (loser) loser.playAnim('ko', 1000);
  cameraShake(0.3);

  setTimeout(() => {
    $('hud').style.display = 'none';
    $('touchControls').style.display = 'none';
    $('pauseBtn').style.display = 'none';
    cancelAnimationFrame(animFrame); animFrame = null;

    $('resultTitle').textContent = '🏆 ПОБЕДА!';
    $('resultName').textContent = winner.data.name;
    $('resultTaunt').textContent = winner.taunt ? `"${winner.taunt}"` : '';
    const av = $('resultAvatar');
    if (winner.data.avatar) { av.src = winner.data.avatar; av.style.display = 'block'; }
    else { av.style.display = 'none'; }
    showScreen('screenResult');
  }, 1200);
}

function revengePlay() {
  [selectedA, selectedB] = [selectedB, selectedA];
  startFight3D();
}

function quitFight() {
  clearInterval(timerInterval);
  if (aiTimeout) clearTimeout(aiTimeout);
  AudioEngine.stopBg();
  if (animFrame) { cancelAnimationFrame(animFrame); animFrame = null; }
  $('hud').style.display = 'none';
  $('touchControls').style.display = 'none';
  $('pauseBtn').style.display = 'none';
  $('pauseOverlay').classList.remove('show');
  paused = false;
  showScreen('screenRoster');
}

// ── AI ───────────────────────────────────────────────────
function scheduleAI() {
  if (aiTimeout) clearTimeout(aiTimeout);
  const delay = 500 + Math.random() * 900;
  aiTimeout = setTimeout(aiTick, delay);
}

function aiTick() {
  if (!gs || gs.winner || paused || gameMode !== 'pve') return;
  if (fighterB.combo >= 3 && Math.random() < 0.5) {
    doAction('B', 'special');
  } else {
    const rolls = ['punch','punch','kick','block','punch'];
    doAction('B', rolls[Math.floor(Math.random() * rolls.length)]);
  }
  scheduleAI();
}

// ── Pause ────────────────────────────────────────────────
function togglePause() {
  paused = !paused;
  $('pauseOverlay').classList.toggle('show', paused);
  $('pauseBtn').textContent = paused ? '▶' : '⏸';
  if (paused) AudioEngine.stopBg(); else AudioEngine.startBg();
}

// ── Keyboard Controls ────────────────────────────────────
function touchAction(side, action, down) {
  if (down) {
    if (action === 'block') doAction(side, 'block');
    else if (action === 'left' || action === 'right') {
      moveKeys[side + action] = down;
    }
  } else {
    moveKeys[side + action] = false;
    if (action === 'block') doAction(side, 'unblock');
  }
}

function triggerAction(side, action) {
  AudioEngine.uiClick();
  doAction(side, action);
}

window.addEventListener('keydown', e => {
  if (keys[e.code]) return;
  keys[e.code] = true;

  if (e.code === 'Escape') { togglePause(); return; }
  if (!gs || gs.winner || paused) return;

  // P1: A/D move, J punch, K kick, L block, J+K = special (F key also)
  if (e.code === 'KeyA') { moveKeys['Aleft'] = true; }
  if (e.code === 'KeyD') { moveKeys['Aright'] = true; }
  if (e.code === 'KeyJ') { if (keys['KeyK']) doAction('A','special'); else doAction('A','punch'); }
  if (e.code === 'KeyK') { if (keys['KeyJ']) doAction('A','special'); else doAction('A','kick'); }
  if (e.code === 'KeyL') { doAction('A','block'); }
  if (e.code === 'KeyF') { doAction('A','special'); }

  // P2 (PvP): arrows + numpad
  if (gameMode === 'pvp') {
    if (e.code === 'ArrowLeft')  { moveKeys['Bleft'] = true; }
    if (e.code === 'ArrowRight') { moveKeys['Bright'] = true; }
    if (e.code === 'Numpad1') { doAction('B','punch'); }
    if (e.code === 'Numpad2') { doAction('B','kick'); }
    if (e.code === 'Numpad3') { doAction('B','block'); }
    if (e.code === 'Numpad0') { doAction('B','special'); }
  }
});

window.addEventListener('keyup', e => {
  keys[e.code] = false;
  if (e.code === 'KeyA') { moveKeys['Aleft'] = false; }
  if (e.code === 'KeyD') { moveKeys['Aright'] = false; }
  if (e.code === 'KeyL') { doAction('A','unblock'); }
  if (gameMode === 'pvp') {
    if (e.code === 'ArrowLeft')  { moveKeys['Bleft'] = false; }
    if (e.code === 'ArrowRight') { moveKeys['Bright'] = false; }
    if (e.code === 'Numpad3') { doAction('B','unblock'); }
  }
});

// ── Movement Update ──────────────────────────────────────
const MOVE_SPEED = 0.04;
const BOUNDS = { min: -3.5, max: 3.5 };

function updateMovement() {
  if (!fighterA || !fighterB || !gs || gs.winner) return;
  const minDist = 0.9;

  if (moveKeys['Aleft'])  fighterA.x = Math.max(BOUNDS.min, fighterA.x - MOVE_SPEED);
  if (moveKeys['Aright']) fighterA.x = Math.min(BOUNDS.max, fighterA.x + MOVE_SPEED);
  if (gameMode === 'pvp') {
    if (moveKeys['Bleft'])  fighterB.x = Math.max(BOUNDS.min, fighterB.x - MOVE_SPEED);
    if (moveKeys['Bright']) fighterB.x = Math.min(BOUNDS.max, fighterB.x + MOVE_SPEED);
  }

  // Keep fighters facing each other
  const dirA = fighterB.x > fighterA.x ? 1 : -1;
  fighterA.group.scale.x = dirA;
  fighterB.group.scale.x = -dirA;
  // Don't let them overlap
  const dist = Math.abs(fighterB.x - fighterA.x);
  if (dist < minDist) {
    const mid = (fighterA.x + fighterB.x) / 2;
    fighterA.x = mid - minDist / 2 * dirA;
    fighterB.x = mid + minDist / 2 * dirA;
  }
}

// ── Game Loop ─────────────────────────────────────────────
function gameLoop() {
  animFrame = requestAnimationFrame(gameLoop);
  const delta = clock.getDelta();
  if (!gameLoop._logged) { console.log('gameLoop running, scene children:', scene.children.length, 'renderer:', !!renderer); gameLoop._logged = true; }

  if (!paused) {
    updateMovement();
    if (fighterA) fighterA.updateAnim(delta);
    if (fighterB) fighterB.updateAnim(delta);

    // Camera shake
    if (shakeMag > 0.005) {
      camera.position.x = (Math.random() - 0.5) * shakeMag;
      camera.position.y = 2.5 + (Math.random() - 0.5) * shakeMag;
      shakeMag *= shakeDecay;
    } else {
      camera.position.x = 0; camera.position.y = 2.5; shakeMag = 0;
    }

    // Flicker torch lights
    scene.children.forEach(obj => {
      if (obj.isPointLight && obj.userData.flicker) {
        obj.intensity = obj.userData.baseIntensity + (Math.random() - 0.5) * 1.5;
      }
    });
  }

  updateBlood();
  renderer.render(scene, camera);
}

// ── Init ─────────────────────────────────────────────────
// initThree deferred to startFight3D
loadFighters();
