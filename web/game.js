/**
 * Virtual Steering — Embedded Racing Game (game.js)
 * A neon top-down racing game that listens to document keyboard events.
 * Controlled by the gesture system in app.js via dispatched KeyboardEvents.
 */

'use strict';

const gc  = document.getElementById('game');
const gx  = gc.getContext('2d');

// ── Constants ──
const ROAD_L   = 0.12;   // road left edge (fraction of width)
const ROAD_R   = 0.88;
const LANES    = 3;
const BASE_SPD = 220;
const MAX_SPD  = 820;
const ACCEL    = 120;
const BRAKE    = 300;
const DRIFT_SPD = 320;   // lateral speed of player car

// ── State ──
let gw, gh, roadLeft, roadRight, roadW;
let gameState = 'PLAYING';
let score = 0, lives = 3, gameTime = 0;
let scrollSpeed = BASE_SPD;
let dashY = 0;

// ── Player ──
const player = { x:0, y:0, w:38, h:68, wobble:0 };

// ── Collections ──
let enemies   = [];
let pickups   = [];
let particles = [];
let stars     = [];   // background stars

// ── Timers ──
let spawnT  = 0;
let pickupT = 0;

// ── Keys ──
const keys = {};
document.addEventListener('keydown', e => { keys[e.key] = true;  e.preventDefault(); }, { passive:false });
document.addEventListener('keyup',   e => { keys[e.key] = false; });

// ── DOM refs ──
const elScore = document.getElementById('game-score');
const elSpd   = document.getElementById('game-speed-display');
const elLives = document.getElementById('game-lives');

// ──────────────────────────────────────────────────────────────
// Resize
// ──────────────────────────────────────────────────────────────
function resize() {
  gw = gc.width  = gc.offsetWidth;
  gh = gc.height = gc.offsetHeight;
  roadLeft  = gw * ROAD_L;
  roadRight = gw * ROAD_R;
  roadW     = roadRight - roadLeft;
  player.x  = gw * 0.5;
  player.y  = gh * 0.77;
  // scatter background stars
  stars = Array.from({length:30}, () => ({
    x: roadLeft + Math.random() * roadW,
    y: Math.random() * gh,
    r: Math.random() * 1.5,
  }));
}

window.addEventListener('resize', resize);

// ──────────────────────────────────────────────────────────────
// Main Loop
// ──────────────────────────────────────────────────────────────
let lastT = performance.now();

function loop() {
  requestAnimationFrame(loop);
  const now = performance.now();
  const dt  = Math.min((now - lastT) / 1000, 0.05);
  lastT = now;

  if (gameState === 'PLAYING') update(dt);
  render();
  updateDOM();
}

// ──────────────────────────────────────────────────────────────
// Update
// ──────────────────────────────────────────────────────────────
function update(dt) {
  gameTime += dt;
  score    += dt * (scrollSpeed / 80);

  // ── Speed control ──
  if (keys['ArrowUp']) {
    scrollSpeed = Math.min(MAX_SPD, scrollSpeed + ACCEL * 4 * dt);
  } else if (keys['ArrowDown']) {
    scrollSpeed = Math.max(BASE_SPD * 0.4, scrollSpeed - BRAKE * dt);
  } else {
    // Natural slow drift to natural speed
    const tgt = Math.min(BASE_SPD + gameTime * 6, MAX_SPD * 0.7);
    scrollSpeed += (tgt - scrollSpeed) * dt * 0.8;
  }

  // ── Steering ──
  const moveSpd = DRIFT_SPD * (0.7 + scrollSpeed / MAX_SPD * 0.8);
  if (keys['ArrowLeft'])  player.x = Math.max(roadLeft  + player.w/2, player.x - moveSpd * dt);
  if (keys['ArrowRight']) player.x = Math.min(roadRight - player.w/2, player.x + moveSpd * dt);

  // Wobble effect when steering
  if (keys['ArrowLeft'])  player.wobble = Math.max(-0.12, player.wobble - dt * 4);
  else if (keys['ArrowRight']) player.wobble = Math.min(0.12, player.wobble + dt * 4);
  else player.wobble *= 0.85;

  // ── Road scroll ──
  dashY = (dashY + scrollSpeed * dt) % 80;

  // ── Enemy spawn ──
  spawnT -= dt;
  if (spawnT <= 0) {
    spawnEnemy();
    spawnT = Math.max(0.4, 1.8 - gameTime * 0.02) * (BASE_SPD / scrollSpeed);
  }

  // ── Pickup spawn ──
  pickupT -= dt;
  if (pickupT <= 0) {
    spawnPickup();
    pickupT = 3.5 + Math.random() * 3;
  }

  // ── Move enemies ──
  for (let i = enemies.length - 1; i >= 0; i--) {
    const e = enemies[i];
    e.y += (scrollSpeed + e.relSpd) * dt;
    e.x += e.drift * dt;

    // Clamp to road
    e.x = Math.max(roadLeft + e.w/2, Math.min(roadRight - e.w/2, e.x));

    if (e.y > gh + 120) { enemies.splice(i, 1); continue; }

    // Collision
    if (!e.hit &&
        Math.abs(e.x - player.x) < (e.w + player.w)/2 - 6 &&
        Math.abs(e.y - player.y) < (e.h + player.h)/2 - 6) {
      e.hit = true;
      lives--;
      burst(player.x, player.y, '#ff3344', 16);
      burst(e.x, e.y, e.color, 10);
      if (lives <= 0) { gameState = 'GAMEOVER'; }
    }
  }

  // ── Move pickups ──
  for (let i = pickups.length - 1; i >= 0; i--) {
    const p = pickups[i];
    p.y   += scrollSpeed * dt;
    p.ang += dt * 2.5;
    if (p.y > gh + 50) { pickups.splice(i, 1); continue; }

    if (Math.abs(p.x - player.x) < 36 && Math.abs(p.y - player.y) < 36) {
      pickups.splice(i, 1);
      score += 200;
      scrollSpeed = Math.min(MAX_SPD, scrollSpeed + 60);
      burst(p.x, p.y, '#ffd600', 12);
    }
  }

  // ── Particles ──
  for (let i = particles.length - 1; i >= 0; i--) {
    const p = particles[i];
    p.x += p.vx * dt; p.y += p.vy * dt;
    p.vy += 60 * dt;  // gravity
    p.life -= dt;
    if (p.life <= 0) particles.splice(i, 1);
  }

  // Exhaust
  if (keys['ArrowUp'] && Math.random() < 0.5) exhaust();
}

// ──────────────────────────────────────────────────────────────
// Spawn helpers
// ──────────────────────────────────────────────────────────────
function randLaneX() {
  const lw = roadW / LANES;
  const l  = Math.floor(Math.random() * LANES);
  return roadLeft + lw * l + lw * (0.25 + Math.random() * 0.5);
}

function spawnEnemy() {
  const colors = ['#ff3344','#ff5500','#cc2200','#ff7700'];
  const w = 32 + Math.random() * 12;
  const h = 58 + Math.random() * 18;
  enemies.push({
    x: randLaneX(), y: -h - 20, w, h,
    relSpd: -60 + Math.random() * 40,
    drift: (Math.random() - 0.5) * 20,
    color: colors[Math.floor(Math.random() * colors.length)],
    hit: false,
  });
}

function spawnPickup() {
  pickups.push({ x:randLaneX(), y:-20, ang:0 });
}

function burst(x, y, color, n) {
  for (let i = 0; i < n; i++) {
    const a = Math.random() * Math.PI * 2;
    const s = 80 + Math.random() * 140;
    particles.push({ x, y, vx:Math.cos(a)*s, vy:Math.sin(a)*s, color,
                     life:0.35 + Math.random()*.3, r:2+Math.random()*4 });
  }
}

function exhaust() {
  particles.push({
    x: player.x + (Math.random()-0.5)*8,
    y: player.y + player.h/2,
    vx: (Math.random()-.5)*20, vy: 40+Math.random()*60,
    color: '#00c8ff', life:0.25, r:2+Math.random()*3,
  });
}

// ──────────────────────────────────────────────────────────────
// Render
// ──────────────────────────────────────────────────────────────
function render() {
  gx.clearRect(0, 0, gw, gh);
  drawBg();
  drawRoad();
  drawPickups();
  drawEnemies();
  drawPlayer();
  drawParticles();
  drawSpeedLines();
  if (gameState === 'GAMEOVER') drawGameOver();
}

function drawBg() {
  // Sky gradient
  const grad = gx.createLinearGradient(0, 0, 0, gh * 0.5);
  grad.addColorStop(0, '#0a0618'); grad.addColorStop(1, '#07060f');
  gx.fillStyle = grad; gx.fillRect(0, 0, gw, gh);

  // Grassy shoulders
  gx.fillStyle = '#080f08';
  gx.fillRect(0, 0, roadLeft, gh);
  gx.fillRect(roadRight, 0, gw - roadRight, gh);

  // Tiny road stars (twinkling road surface texture)
  for (const s of stars) {
    s.y = (s.y + scrollSpeed * 0.002) % gh;
    gx.globalAlpha = 0.15;
    gx.fillStyle = '#ffffff';
    gx.beginPath(); gx.arc(s.x, s.y, s.r, 0, Math.PI*2); gx.fill();
  }
  gx.globalAlpha = 1;
}

function drawRoad() {
  // Road surface
  const rg = gx.createLinearGradient(roadLeft, 0, roadRight, 0);
  rg.addColorStop(0,   '#111125'); rg.addColorStop(0.5, '#141428');
  rg.addColorStop(1,   '#111125');
  gx.fillStyle = rg; gx.fillRect(roadLeft, 0, roadW, gh);

  // Neon edge glow lines
  ['#00c8ff','#00c8ff'].forEach((col, i) => {
    const lx = i === 0 ? roadLeft : roadRight;
    gx.shadowColor = col; gx.shadowBlur = 10;
    gx.strokeStyle = col; gx.lineWidth = 2.5;
    gx.beginPath(); gx.moveTo(lx, 0); gx.lineTo(lx, gh); gx.stroke();
  });
  gx.shadowBlur = 0;

  // Lane dividers
  const lw = roadW / LANES;
  gx.strokeStyle = 'rgba(255,255,255,0.18)'; gx.lineWidth = 2;
  gx.setLineDash([40, 40]); gx.lineDashOffset = -dashY;
  for (let l = 1; l < LANES; l++) {
    const lx = roadLeft + lw * l;
    gx.beginPath(); gx.moveTo(lx, 0); gx.lineTo(lx, gh); gx.stroke();
  }
  gx.setLineDash([]); gx.lineDashOffset = 0;
}

function drawPlayer() {
  const {x, y, w, h, wobble} = player;

  gx.save();
  gx.translate(x, y);
  gx.rotate(wobble);

  // Glow
  gx.shadowColor = '#00c8ff'; gx.shadowBlur = 22;

  // Body
  rr(gx, -w/2, -h/2, w, h, 8); gx.fillStyle = '#0a3d6e'; gx.fill();

  // Top highlight
  rr(gx, -w/2+4, -h/2+5, w-8, h*0.42, 5); gx.fillStyle = '#1565a8'; gx.fill();

  // Windshield
  rr(gx, -w/2+5, -h/2+10, w-10, h*0.27, 4);
  gx.fillStyle = 'rgba(140,220,255,0.45)'; gx.fill();

  // Rear window
  rr(gx, -w/2+5, h*0.2, w-10, h*0.17, 3);
  gx.fillStyle = 'rgba(140,220,255,0.22)'; gx.fill();

  // Outline
  rr(gx, -w/2, -h/2, w, h, 8); gx.strokeStyle = '#00c8ff'; gx.lineWidth = 2; gx.stroke();

  // Headlights
  gx.shadowColor='#fff'; gx.shadowBlur=12; gx.fillStyle='#fff';
  gx.fillRect(-w/2+3, -h/2,   8, 4);
  gx.fillRect(w/2-11, -h/2,   8, 4);

  // Tail lights
  gx.shadowColor='#ff3344'; gx.shadowBlur=14; gx.fillStyle='#ff3344';
  gx.fillRect(-w/2+3, h/2-4, 8, 4);
  gx.fillRect(w/2-11, h/2-4, 8, 4);

  gx.shadowBlur = 0;
  gx.restore();
}

function drawEnemies() {
  for (const e of enemies) {
    gx.shadowColor = e.color; gx.shadowBlur = 14;
    gx.fillStyle = e.color;
    rr(gx, e.x-e.w/2, e.y-e.h/2, e.w, e.h, 6); gx.fill();

    // Windshield
    gx.fillStyle = 'rgba(0,0,0,0.45)';
    rr(gx, e.x-e.w/2+5, e.y-e.h*0.12, e.w-10, e.h*0.23, 3); gx.fill();

    // Outline
    gx.strokeStyle = 'rgba(255,255,255,0.25)'; gx.lineWidth = 1.5;
    rr(gx, e.x-e.w/2, e.y-e.h/2, e.w, e.h, 6); gx.stroke();
    gx.shadowBlur = 0;
  }
}

function drawPickups() {
  for (const p of pickups) {
    gx.save();
    gx.translate(p.x, p.y); gx.rotate(p.ang);
    gx.shadowColor='#ffd600'; gx.shadowBlur=22;
    gx.beginPath();
    gx.moveTo(0,-16); gx.lineTo(12,0); gx.lineTo(0,16); gx.lineTo(-12,0); gx.closePath();
    gx.fillStyle='#ffd600'; gx.fill();
    gx.strokeStyle='rgba(255,255,255,0.6)'; gx.lineWidth=1.5; gx.stroke();

    // Inner gem
    gx.beginPath();
    gx.moveTo(0,-7); gx.lineTo(5,0); gx.lineTo(0,7); gx.lineTo(-5,0); gx.closePath();
    gx.fillStyle='#fff8'; gx.fill();

    gx.shadowBlur=0; gx.restore();
  }
}

function drawParticles() {
  for (const p of particles) {
    const a = Math.max(0, p.life / 0.65);
    gx.globalAlpha = a;
    gx.fillStyle = p.color; gx.shadowColor = p.color; gx.shadowBlur = 8;
    gx.beginPath(); gx.arc(p.x, p.y, p.r, 0, Math.PI*2); gx.fill();
  }
  gx.globalAlpha = 1; gx.shadowBlur = 0;
}

function drawSpeedLines() {
  const extra = (scrollSpeed - BASE_SPD - 100) / (MAX_SPD - BASE_SPD);
  if (extra <= 0) return;
  gx.globalAlpha = Math.min(extra * 0.45, 0.4);
  gx.strokeStyle = 'rgba(200,240,255,0.6)'; gx.lineWidth = 1;
  for (let i = 0; i < 12; i++) {
    const lx = roadLeft + Math.random() * roadW;
    const ly = Math.random() * gh;
    const ln = 25 + Math.random() * 70;
    gx.beginPath(); gx.moveTo(lx, ly); gx.lineTo(lx, ly+ln); gx.stroke();
  }
  gx.globalAlpha = 1;
}

function drawGameOver() {
  gx.fillStyle = 'rgba(7,6,15,0.88)'; gx.fillRect(0,0,gw,gh);

  gx.textAlign='center'; gx.font=`900 ${Math.min(gw*.1, 42)}px Orbitron,monospace`;
  gx.fillStyle='#ff3344'; gx.shadowColor='#ff3344'; gx.shadowBlur=24;
  gx.fillText('GAME OVER', gw/2, gh/2 - 40);

  gx.shadowBlur=0; gx.font=`700 ${Math.min(gw*.055, 22)}px Orbitron,monospace`;
  gx.fillStyle='#e8e8f0';
  gx.fillText(`SCORE: ${Math.floor(score)}`, gw/2, gh/2 + 10);

  gx.font=`600 ${Math.min(gw*.04, 15)}px Rajdhani,sans-serif`;
  gx.fillStyle='#5a5a72';
  gx.fillText('Press  SPACE  or  make a FIST  to restart', gw/2, gh/2 + 50);
  gx.textAlign='left';
}

// ──────────────────────────────────────────────────────────────
// DOM Overlay Update
// ──────────────────────────────────────────────────────────────
function updateDOM() {
  if (!elScore) return;
  elScore.textContent  = `SCORE: ${Math.floor(score)}`;
  elSpd.textContent    = `${Math.round(scrollSpeed)} km/h`;
  elLives.textContent  = '♥ '.repeat(Math.max(0, lives)).trim() || '—';
}

// ──────────────────────────────────────────────────────────────
// Restart
// ──────────────────────────────────────────────────────────────
function restart() {
  score=0; lives=3; gameTime=0; scrollSpeed=BASE_SPD;
  enemies=[]; pickups=[]; particles=[];
  player.x=gw*0.5; player.y=gh*0.77; player.wobble=0;
  gameState='PLAYING';
}

document.addEventListener('keydown', e => {
  if (e.key === ' ' && gameState === 'GAMEOVER') restart();
});

// Also allow restarting via fist gesture (dispatched from app.js)
// app.js dispatches custom event 'vs-restart'
document.addEventListener('vs-restart', restart);

// ──────────────────────────────────────────────────────────────
// Utility: Rounded Rect Path
// ──────────────────────────────────────────────────────────────
function rr(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x+r, y);
  ctx.lineTo(x+w-r, y);    ctx.arcTo(x+w, y,   x+w, y+r,   r);
  ctx.lineTo(x+w, y+h-r);  ctx.arcTo(x+w, y+h, x+w-r, y+h, r);
  ctx.lineTo(x+r, y+h);    ctx.arcTo(x,   y+h, x,   y+h-r, r);
  ctx.lineTo(x,   y+r);    ctx.arcTo(x,   y,   x+r, y,     r);
  ctx.closePath();
}

// ──────────────────────────────────────────────────────────────
// Boot
// ──────────────────────────────────────────────────────────────
window.addEventListener('load', () => {
  resize();
  loop();
});
