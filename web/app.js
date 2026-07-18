/**
 * Virtual Steering — Web App (app.js)
 * Hand gesture detection via MediaPipe Tasks Vision JS.
 * Dispatches KeyboardEvents on document → controls game.js.
 */

'use strict';

import { FilesetResolver, HandLandmarker }
  from 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.3/vision_bundle.mjs';

// ──────────────────────────────────────────────────────────────
// Constants
// ──────────────────────────────────────────────────────────────
const MEDIAPIPE_WASM = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.3/wasm';
const MODEL_URL      = 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task';

const HAND_CONNECTIONS = [
  [0,1],[1,2],[2,3],[3,4],
  [0,5],[5,6],[6,7],[7,8],
  [5,9],[9,10],[10,11],[11,12],
  [9,13],[13,14],[14,15],[15,16],
  [13,17],[0,17],[17,18],[18,19],[19,20],
];

// ──────────────────────────────────────────────────────────────
// State
// ──────────────────────────────────────────────────────────────
let handLandmarker = null;
let lastVideoTime  = -1;

const state = {
  smoothedAngle : 0,
  gesture       : 'neutral',
  hands         : [],
  activeKeys    : new Set(),
};

let prevKeys = new Set();    // for change detection → keyboard dispatch

let cfg = {
  steerThreshold : 15,
  smoothing      : 0.25,
};

// FPS
let fpsFrames = 0, fpsTimer = performance.now();

// Key → ArrowKey map
const KEY_MAP = {
  left  : 'ArrowLeft',
  right : 'ArrowRight',
  gas   : 'ArrowUp',
  brake : 'ArrowDown',
};

// ──────────────────────────────────────────────────────────────
// DOM
// ──────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const loader       = $('loader');
const loaderStatus = $('loader-status');
const loaderFill   = $('loader-fill');
const appEl        = $('app');
const video        = $('webcam');
const canvas       = $('hud');
const ctx          = canvas.getContext('2d');

const keyEls = { left:$('key-left'), right:$('key-right'), gas:$('key-gas'), brake:$('key-brake') };
const gestureBadge = $('gesture-badge');
const fpsBadge     = $('fps-badge');
const telemAngle   = $('telem-angle');

// ──────────────────────────────────────────────────────────────
// Init
// ──────────────────────────────────────────────────────────────
async function init() {
  try {
    progress(10, 'Requesting camera…');
    await startCamera();

    progress(35, 'Loading MediaPipe AI model…');
    const vision = await FilesetResolver.forVisionTasks(MEDIAPIPE_WASM);

    progress(65, 'Initializing hand tracker…');
    handLandmarker = await HandLandmarker.createFromOptions(vision, {
      baseOptions: { modelAssetPath: MODEL_URL, delegate: 'GPU' },
      runningMode                 : 'VIDEO',
      numHands                    : 2,
      minHandDetectionConfidence  : 0.7,
      minHandPresenceConfidence   : 0.5,
      minTrackingConfidence       : 0.5,
    });

    progress(100, 'Ready!');
    await sleep(350);
    showApp();
    setupSettings();
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);
    tick();

  } catch (err) {
    loaderStatus.textContent = '✕ ' + err.message;
    loaderStatus.style.color = '#ff3344';
    console.error(err);
  }
}

function progress(pct, msg) {
  loaderFill.style.width = pct + '%';
  loaderStatus.textContent = msg;
}

function showApp() {
  loader.style.opacity = '0';
  setTimeout(() => loader.style.display = 'none', 600);
  appEl.classList.remove('hidden');
}

// ──────────────────────────────────────────────────────────────
// Camera
// ──────────────────────────────────────────────────────────────
async function startCamera(deviceId = null) {
  const stream = await navigator.mediaDevices.getUserMedia({
    video: {
      width: {ideal:1280}, height: {ideal:720}, facingMode:'user',
      ...(deviceId ? {deviceId:{exact:deviceId}} : {}),
    }
  });
  video.srcObject = stream;
  return new Promise(r => { video.onloadedmetadata = () => r(); });
}

function resizeCanvas() {
  canvas.width  = canvas.offsetWidth;
  canvas.height = canvas.offsetHeight;
}

// ──────────────────────────────────────────────────────────────
// Main Loop
// ──────────────────────────────────────────────────────────────
function tick() {
  requestAnimationFrame(tick);
  if (video.readyState < 2) return;

  const now = performance.now();
  if (video.currentTime !== lastVideoTime) {
    lastVideoTime = video.currentTime;
    const results = handLandmarker.detectForVideo(video, now);
    processResults(results);
    dispatchKeyChanges();   // ← send keyboard events to game
  }

  drawHUD();
  updateDOM();

  // FPS
  fpsFrames++;
  if (now - fpsTimer >= 500) {
    const fps = Math.round(fpsFrames / ((now - fpsTimer) / 1000));
    fpsFrames = 0; fpsTimer = now;
    if (fpsBadge) fpsBadge.textContent = fps;
  }
}

// ──────────────────────────────────────────────────────────────
// Keyboard Dispatch — sends events to game.js
// ──────────────────────────────────────────────────────────────
function dispatchKeyChanges() {
  const cur  = state.activeKeys;
  const prev = prevKeys;

  for (const k of cur) {
    if (!prev.has(k)) {
      // Key just pressed
      document.dispatchEvent(new KeyboardEvent('keydown', {
        key: KEY_MAP[k], code: KEY_MAP[k], bubbles: true, cancelable: true,
      }));
    }
  }

  for (const k of prev) {
    if (!cur.has(k)) {
      // Key just released
      document.dispatchEvent(new KeyboardEvent('keyup', {
        key: KEY_MAP[k], code: KEY_MAP[k], bubbles: true, cancelable: true,
      }));
    }
  }

  prevKeys = new Set(cur);
}

// ──────────────────────────────────────────────────────────────
// Hand Processing
// ──────────────────────────────────────────────────────────────
function processResults(results) {
  state.hands = [];

  if (!results?.landmarks?.length) {
    state.gesture = 'neutral';
    state.smoothedAngle *= 0.88;
    state.activeKeys.clear();
    return;
  }

  for (let i = 0; i < results.landmarks.length; i++) {
    const lms = results.landmarks[i];
    state.hands.push({ lms, gesture: classifyGesture(lms) });
  }

  // Steering angle (with mirror correction)
  if (state.hands.length >= 2) {
    const angle = steeringAngle(state.hands);
    state.smoothedAngle = cfg.smoothing * state.smoothedAngle + (1 - cfg.smoothing) * angle;
  } else {
    state.smoothedAngle *= 0.90;
  }

  state.gesture = dominantGesture(state.hands);

  // Active keys
  state.activeKeys.clear();
  const a = state.smoothedAngle;
  const t = cfg.steerThreshold;
  if (a < -t) state.activeKeys.add('left');
  if (a >  t) state.activeKeys.add('right');
  if (state.gesture === 'fist') state.activeKeys.add('gas');
  if (state.gesture === 'open') state.activeKeys.add('brake');
}

// Curl-based gesture: avg tip→MCP distance normalised by hand size
function classifyGesture(lms) {
  const TIPS = [8,12,16,20], MCPS = [5,9,13,17];
  const sz = d2(lms[0], lms[9]);
  if (sz < 1e-5) return 'neutral';
  let s = 0;
  for (let i = 0; i < 4; i++) s += d2(lms[TIPS[i]], lms[MCPS[i]]) / sz;
  const avg = s / 4;
  if (avg < 0.65) return 'fist';
  if (avg > 0.85) return 'open';
  return 'neutral';
}

function d2(a, b) { return Math.hypot(a.x - b.x, a.y - b.y); }

function steeringAngle(hands) {
  // Video is CSS-mirrored → flip x before computing to get correct direction
  const sorted = [...hands].sort((a, b) => (1 - a.lms[0].x) - (1 - b.lms[0].x));
  const [lh, rh] = sorted;
  const dx = (1 - rh.lms[0].x) - (1 - lh.lms[0].x);
  const dy = rh.lms[0].y - lh.lms[0].y;
  if (Math.abs(dx) < 0.02) return 0;
  return Math.max(-90, Math.min(90, Math.atan2(dy, dx) * (180 / Math.PI)));
}

function dominantGesture(hands) {
  if (!hands.length) return 'neutral';
  const g = hands.map(h => h.gesture);
  if (g.includes('open')) return 'open';
  if (g.includes('fist')) return 'fist';
  return 'neutral';
}

// ──────────────────────────────────────────────────────────────
// HUD Canvas Drawing
// ──────────────────────────────────────────────────────────────
function drawHUD() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  drawSkeleton();
  if (state.hands.length >= 2) {
    drawWristLine();
    drawSteeringWheel();
  }
}

function drawSkeleton() {
  const W = canvas.width, H = canvas.height;
  const px = lm => (1 - lm.x) * W;   // mirror x to match CSS scaleX(-1)
  const py = lm => lm.y * H;

  for (const hand of state.hands) {
    const lms = hand.lms;
    const col = hand.gesture === 'fist' ? 'rgba(0,232,120,0.85)'
              : hand.gesture === 'open' ? 'rgba(255,51,68,0.85)'
              : 'rgba(0,200,255,0.75)';
    const dot = hand.gesture === 'fist' ? '#00e878'
              : hand.gesture === 'open' ? '#ff3344'
              : '#00e8ff';

    ctx.strokeStyle = col; ctx.lineWidth = 2;
    for (const [a, b] of HAND_CONNECTIONS) {
      ctx.beginPath();
      ctx.moveTo(px(lms[a]), py(lms[a]));
      ctx.lineTo(px(lms[b]), py(lms[b]));
      ctx.stroke();
    }

    for (const lm of lms) {
      ctx.beginPath(); ctx.arc(px(lm), py(lm), 4, 0, Math.PI*2);
      ctx.fillStyle = dot; ctx.fill();
    }

    ctx.beginPath(); ctx.arc(px(lms[0]), py(lms[0]), 9, 0, Math.PI*2);
    ctx.strokeStyle = dot; ctx.lineWidth = 2; ctx.stroke();
  }
}

function drawWristLine() {
  const W = canvas.width, H = canvas.height;
  const [h0, h1] = [state.hands[0].lms[0], state.hands[1].lms[0]];
  ctx.beginPath();
  ctx.moveTo((1-h0.x)*W, h0.y*H);
  ctx.lineTo((1-h1.x)*W, h1.y*H);
  ctx.strokeStyle = 'rgba(0,200,255,0.5)';
  ctx.lineWidth = 2; ctx.setLineDash([7,6]); ctx.stroke(); ctx.setLineDash([]);
}

function drawSteeringWheel() {
  const cx = canvas.width  * 0.5;
  const cy = canvas.height * 0.74;
  const R  = Math.min(canvas.width, canvas.height) * 0.11;
  const Hr = R * 0.17;
  const a  = (state.smoothedAngle * Math.PI) / 180;

  ctx.shadowColor = '#00c8ff'; ctx.shadowBlur = 18;

  // Outer rim
  ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI*2);
  ctx.strokeStyle='#00c8ff'; ctx.lineWidth=4; ctx.stroke();
  ctx.shadowBlur = 0;

  // Inner fill
  ctx.beginPath(); ctx.arc(cx, cy, R-7, 0, Math.PI*2);
  ctx.fillStyle='rgba(7,6,15,0.55)'; ctx.fill();

  // 3 Spokes
  for (let i=0; i<3; i++) {
    const ang = a + i * Math.PI * 2/3;
    ctx.beginPath();
    ctx.moveTo(cx + Hr*1.4*Math.cos(ang), cy + Hr*1.4*Math.sin(ang));
    ctx.lineTo(cx + (R-10)*Math.cos(ang), cy + (R-10)*Math.sin(ang));
    ctx.strokeStyle='#00c8ff'; ctx.lineWidth=4; ctx.stroke();
  }

  // Hub
  ctx.beginPath(); ctx.arc(cx, cy, Hr, 0, Math.PI*2);
  ctx.fillStyle='#12102a'; ctx.fill();
  ctx.strokeStyle='#00c8ff'; ctx.lineWidth=2; ctx.stroke();

  // 12-o-clock dot
  const mdx = cx + R*Math.cos(a - Math.PI/2);
  const mdy = cy + R*Math.sin(a - Math.PI/2);
  ctx.beginPath(); ctx.arc(mdx, mdy, 5, 0, Math.PI*2);
  ctx.fillStyle='#ffd600'; ctx.fill();
}

// ──────────────────────────────────────────────────────────────
// DOM Updates
// ──────────────────────────────────────────────────────────────
function updateDOM() {
  const a = state.smoothedAngle;
  if (telemAngle) telemAngle.textContent = (a>=0?'+':'') + a.toFixed(1) + '°';

  const keys = state.activeKeys;
  setKey(keyEls.left,  keys.has('left'),  'active');
  setKey(keyEls.right, keys.has('right'), 'active');
  setKey(keyEls.gas,   keys.has('gas'),   'active-green');
  setKey(keyEls.brake, keys.has('brake'), 'active-red');

  if (!gestureBadge) return;
  gestureBadge.className = 'gesture-badge';
  if (!state.hands.length) {
    gestureBadge.textContent = '✋ SHOW BOTH HANDS';
  } else if (state.gesture === 'fist') {
    gestureBadge.classList.add('fist');
    gestureBadge.textContent = '✊ FIST — GAS';
  } else if (state.gesture === 'open') {
    gestureBadge.classList.add('open');
    gestureBadge.textContent = '🖐 OPEN — BRAKE';
  } else if (keys.has('left')) {
    gestureBadge.classList.add('steer');
    gestureBadge.textContent = '◄ STEERING LEFT';
  } else if (keys.has('right')) {
    gestureBadge.classList.add('steer');
    gestureBadge.textContent = 'STEERING RIGHT ►';
  } else if (state.hands.length === 1) {
    gestureBadge.textContent = '🖐 SHOW SECOND HAND';
  } else {
    gestureBadge.textContent = '● HOLD STEADY';
  }
}

function setKey(el, on, cls) {
  if (!el) return;
  el.classList.remove('active','active-green','active-red');
  if (on) el.classList.add(cls);
}

// ──────────────────────────────────────────────────────────────
// Settings
// ──────────────────────────────────────────────────────────────
function setupSettings() {
  const panel = $('settings-panel');
  $('btn-settings')?.addEventListener('click', () => panel.classList.toggle('hidden'));
  $('btn-close-settings')?.addEventListener('click', () => panel.classList.add('hidden'));

  const ts = $('thresh-slider'), tv = $('thresh-val');
  ts?.addEventListener('input', () => { cfg.steerThreshold = +ts.value; if(tv) tv.textContent = ts.value; });

  const ss = $('smooth-slider'), sv = $('smooth-val');
  ss?.addEventListener('input', () => { cfg.smoothing = +ss.value/100; if(sv) sv.textContent = cfg.smoothing.toFixed(2); });

  navigator.mediaDevices.enumerateDevices().then(devs => {
    const sel = $('camera-select');
    if (!sel) return;
    devs.filter(d => d.kind==='videoinput').forEach((d,i) => {
      const o = document.createElement('option');
      o.value = d.deviceId; o.textContent = d.label || `Camera ${i+1}`;
      sel.appendChild(o);
    });
    sel.addEventListener('change', () => startCamera(sel.value));
  });
}

// ──────────────────────────────────────────────────────────────
// Boot
// ──────────────────────────────────────────────────────────────
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
window.addEventListener('load', init);
