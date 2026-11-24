"use strict";

/* Music Composer UI: settings -> /api/compose -> piano roll, chord sheet and
   in-browser preview playback (Web Audio). Download MIDI -> /api/midi. */

const $ = (id) => document.getElementById(id);
const STORE_KEY = "music-composer-settings-v1";
const NOTE_NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"];
const SECTION_COLOR = {
  intro: "--sec-intro", verse: "--sec-verse", verse2: "--sec-verse",
  chorus: "--sec-chorus", chorus2: "--sec-chorus", ending: "--sec-ending",
};
const STYLE_HINTS = {
  "chords": "Held root-position chords, nothing else. Ready for Logic's Arpeggiator (MIDI FX slot on the Chords track) and for the Chord track.",
  "block": "Held chords plus a low root note in the left hand. Logic's Arpeggiator would include that low note, so use Chords only for arpeggios.",
  "arpeggio": "One fixed eighth-note pattern written into the MIDI. For Logic's own arpeggio styles, use Chords only instead.",
};
const EPS = 1e-6;

let OPTS = null;
let params = null;
let song = null;
let composeSeq = 0;

const cssVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
// "Bb" -> "B♭", "C#dim7" -> "C♯dim7", "bVImaj7" -> "♭VImaj7", "m7b5" -> "m7♭5"; "dim"/"sus" are left alone.
const pretty = (s) => s.replace(/#/g, "♯").replace(/b(?=[0-9IViv]|$)|(?<=[A-G])b/g, "♭");

/* ------------------------------------------------------------ settings */

function loadSettings() {
  try { return JSON.parse(localStorage.getItem(STORE_KEY)) || {}; } catch (e) { return {}; }
}
function saveSettings() {
  try { localStorage.setItem(STORE_KEY, JSON.stringify(params)); } catch (e) { /* private mode */ }
}

/* Settings can come in the link, e.g. /?key=D&scale=minor&tempo=92&time=6/8&seed=7
   (also level, style, form=intro,verse,chorus). They override the saved settings. */
function linkParams() {
  const q = new URLSearchParams(location.search);
  const out = {};
  for (const [name, field] of [["key", "key"], ["scale", "scale"], ["time", "time"], ["level", "level"], ["style", "chord_style"]]) {
    if (q.has(name)) out[field] = q.get(name);
  }
  for (const name of ["tempo", "seed"]) {
    if (q.has(name)) out[name] = parseInt(q.get(name), 10);
  }
  if (q.has("form")) out.form = q.get("form").split(",").map((x) => x.trim());
  if (out.chord_style) out.v = 2;
  return out;
}

function initialParams(stored) {
  const ok = (v, list) => list.includes(v);
  // Settings saved before "Chords only" existed had "block" as the default: move them to the new default once.
  if (!stored.v) stored.chord_style = OPTS.default_chord_style;
  const levels = OPTS.levels.filter((l) => l.available).map((l) => l.id);
  const styles = OPTS.chord_styles.map((s) => s.id);
  const sections = OPTS.sections.map((s) => s.id);
  const form = Array.isArray(stored.form) ? stored.form.filter((k) => sections.includes(k)) : [];
  return {
    key: ok(stored.key, OPTS.keys) ? stored.key : "C",
    scale: ok(stored.scale, OPTS.scales) ? stored.scale : "major",
    tempo: Number.isInteger(stored.tempo) ? clamp(stored.tempo, OPTS.tempo.min, OPTS.tempo.max) : OPTS.tempo.default,
    time: ok(stored.time, OPTS.times) ? stored.time : "4/4",
    level: ok(stored.level, levels) ? stored.level : "basic",
    chord_style: ok(stored.chord_style, styles) ? stored.chord_style : (OPTS.default_chord_style || styles[0]),
    form: form.length ? form : OPTS.default_form.slice(),
    seed: Number.isInteger(stored.seed) ? stored.seed : null,
    v: 2,
  };
}

/* ------------------------------------------------------------ server */

async function post(path, body) {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    let msg = `Something went wrong (${r.status})`;
    try { msg = (await r.json()).error || msg; } catch (e) { /* not JSON */ }
    throw new Error(msg);
  }
  return r;
}

function showError(msg) { const el = $("error"); el.textContent = msg; el.hidden = false; }
function hideError() { $("error").hidden = true; }

async function compose() {
  const seq = ++composeSeq;
  $("stage").classList.add("busy");
  try {
    const data = await (await post("/api/compose", params)).json();
    if (seq !== composeSeq) return;
    song = data;
    params.seed = data.seed;
    $("seed").value = data.seed;
    saveSettings();
    hideError();
    renderMeta();
    drawRollStatic();
    renderSheet();
    player.songChanged();
  } catch (e) {
    if (seq === composeSeq) showError(e.message);
  } finally {
    if (seq === composeSeq) $("stage").classList.remove("busy");
  }
}

async function downloadMidi() {
  try {
    const r = await post("/api/midi", params);
    const disp = r.headers.get("Content-Disposition") || "";
    const m = disp.match(/filename="([^"]+)"/);
    const blob = await r.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = m ? m[1] : (song && song.filename) || "song.mid";
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 4000);
  } catch (e) {
    showError(e.message);
  }
}

/* ------------------------------------------------------------ controls */

function segmented(el, items, current, onPick) {
  el.innerHTML = "";
  for (const it of items) {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = it.label;
    b.setAttribute("aria-pressed", String(it.id === current));
    if (it.disabled) { b.disabled = true; b.title = it.title || ""; }
    b.addEventListener("click", () => {
      for (const o of el.children) o.setAttribute("aria-pressed", String(o === b));
      onPick(it.id);
    });
    el.appendChild(b);
  }
}

function buildControls() {
  const keySel = $("key");
  keySel.innerHTML = OPTS.keys.map((k) => `<option value="${k}">${k.replace("b", "♭").replace("#", "♯")}</option>`).join("");
  keySel.value = params.key;
  keySel.addEventListener("change", () => { params.key = keySel.value; compose(); });

  segmented($("scale"), OPTS.scales.map((s) => ({ id: s, label: s[0].toUpperCase() + s.slice(1) })),
    params.scale, (v) => { params.scale = v; compose(); });

  const tempo = $("tempo");
  tempo.min = OPTS.tempo.min; tempo.max = OPTS.tempo.max; tempo.value = params.tempo;
  $("tempoOut").textContent = `${params.tempo} BPM`;
  tempo.addEventListener("input", () => {
    params.tempo = Number(tempo.value);
    $("tempoOut").textContent = `${params.tempo} BPM`;
    player.tempoChanged();
    renderMeta();
    saveSettings();
  });

  segmented($("time"), OPTS.times.map((t) => ({ id: t, label: t })), params.time,
    (v) => { params.time = v; compose(); });

  segmented($("level"), OPTS.levels.map((l) => ({
    id: l.id, label: l.label, disabled: !l.available, title: "Coming soon",
  })), params.level, (v) => { params.level = v; showLevelHint(); compose(); });
  showLevelHint();

  segmented($("style"), OPTS.chord_styles, params.chord_style, (v) => {
    params.chord_style = v; $("styleHint").textContent = STYLE_HINTS[v]; compose();
  });
  $("styleHint").textContent = STYLE_HINTS[params.chord_style];

  buildFormChips();

  const seed = $("seed");
  seed.addEventListener("change", () => {
    const v = parseInt(seed.value, 10);
    params.seed = Number.isFinite(v) && v >= 0 ? v : null;
    compose();
  });
  $("newSong").addEventListener("click", () => { params.seed = null; compose(); });
}

function showLevelHint() {
  const lvl = OPTS.levels.find((l) => l.id === params.level);
  $("levelHint").textContent = lvl ? lvl.hint : "";
}

function buildFormChips() {
  const el = $("form");
  el.innerHTML = "";
  for (const sec of OPTS.sections) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "chip";
    b.textContent = sec.label;
    b.style.setProperty("--chip-color", `var(${SECTION_COLOR[sec.id]})`);
    b.setAttribute("aria-pressed", String(params.form.includes(sec.id)));
    b.addEventListener("click", () => {
      const on = params.form.includes(sec.id);
      if (on && params.form.length === 1) return; // keep at least one section
      const chosen = new Set(params.form);
      on ? chosen.delete(sec.id) : chosen.add(sec.id);
      params.form = OPTS.sections.map((s) => s.id).filter((id) => chosen.has(id));
      b.setAttribute("aria-pressed", String(!on));
      compose();
    });
    el.appendChild(b);
  }
}

function renderMeta() {
  if (!song) return;
  $("songMeta").innerHTML =
    `<strong>${song.key}</strong> · ${song.time} · ${params.tempo} BPM · ` +
    `${song.sections.length} sections · seed <strong>${song.seed}</strong>`;
}

/* ------------------------------------------------------------ audio */

function makeImpulse(ctx, seconds) {
  const rate = ctx.sampleRate, len = Math.floor(rate * seconds);
  const buf = ctx.createBuffer(2, len, rate);
  for (let ch = 0; ch < 2; ch++) {
    const d = buf.getChannelData(ch);
    for (let i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / len, 3);
  }
  return buf;
}

function trackOn(name) {
  return name === "Melody" ? $("trackMelody").checked : $("trackChords").checked;
}

class Player {
  constructor() {
    this.ctx = null;
    this.playing = false;
    this.pos = 0;            // playhead (quarters) while stopped
    this.voices = new Set();
    this.timer = null;
  }

  init() {
    if (this.ctx) return;
    const Ctx = window.AudioContext || window.webkitAudioContext;
    const ctx = (this.ctx = new Ctx());
    this.master = ctx.createGain();
    this.master.gain.value = 0.9;
    const comp = ctx.createDynamicsCompressor();
    comp.threshold.value = -16;
    comp.ratio.value = 3;
    this.master.connect(comp).connect(ctx.destination);
    const reverb = ctx.createConvolver();
    reverb.buffer = makeImpulse(ctx, 2.4);
    const wet = ctx.createGain();
    wet.gain.value = 0.22;
    reverb.connect(wet).connect(this.master);
    this.bus = {};
    for (const name of ["Melody", "Chords"]) {
      const g = ctx.createGain();
      g.connect(this.master);
      g.connect(reverb);
      this.bus[name] = g;
    }
    this.applyTracks();
  }

  applyTracks() {
    if (!this.ctx) return;
    for (const [name, g] of Object.entries(this.bus)) {
      g.gain.setTargetAtTime(trackOn(name) ? 1 : 0, this.ctx.currentTime, 0.02);
    }
  }

  now() {
    if (!this.playing) return this.pos;
    return this.beat0 + Math.max(0, this.ctx.currentTime - this.t0) / this.spq;
  }

  play(from = this.pos, keepTails = false) {
    if (!song) return;
    this.init();
    this.ctx.resume();
    if (!keepTails) this.silence();
    if (from >= song.total_quarters - EPS) from = 0;
    this.range = this.loopRange(from);
    this.spq = 60 / params.tempo;
    this.beat0 = from;
    this.t0 = this.ctx.currentTime + 0.06;
    this.queue = this.buildQueue(from, this.range[1]);
    this.qi = 0;
    this.playing = true;
    clearInterval(this.timer);
    this.timer = setInterval(() => this.pump(), 25);
    this.pump();
    updatePlayButton();
    requestAnimationFrame(frame);
  }

  pause() {
    if (!this.playing) return;
    this.pos = this.now();
    this.playing = false;
    clearInterval(this.timer);
    this.silence();
    updatePlayButton();
    drawPlayhead();
  }

  toggle() {
    if (this.playing) return this.pause();
    this.startPos = this.pos;
    this.play();
  }

  /* Like Logic: Stop returns to where you pressed Play; pressed again, to bar 1. */
  stop() {
    if (!song) return;
    const target = this.playing ? (this.startPos || 0) : 0;
    if (this.playing) {
      this.playing = false;
      clearInterval(this.timer);
      this.silence();
      updatePlayButton();
    }
    this.pos = target;
    drawPlayhead();
    updatePosition();
  }

  seek(beat) {
    if (!song) return;
    beat = clamp(beat, 0, song.total_quarters);
    this.startPos = beat;
    if (this.playing) this.play(beat);
    else { this.pos = beat; drawPlayhead(); updatePosition(); }
  }

  tempoChanged() { if (this.playing) this.play(this.now()); }

  songChanged() {
    if (!song) return;
    if (this.playing) this.play(Math.min(this.now(), song.total_quarters - EPS));
    else { this.pos = Math.min(this.pos, song.total_quarters); drawPlayhead(); updatePosition(); }
  }

  loopRange(from) {
    if ($("loop").checked) {
      const sec = sectionAt(from);
      if (sec) return [sec.start, sec.start + sec.bars * song.bar_quarters];
    }
    return [0, song.total_quarters];
  }

  buildQueue(from, to) {
    const q = [];
    for (const track of song.tracks) {
      for (const [start, dur, pitch, vel] of track.notes) {
        const end = start + dur;
        if (end <= from + EPS || start >= to - EPS) continue;
        const s = Math.max(start, from);           // notes already sounding restart at the playhead
        q.push({ track: track.name, start: s, dur: Math.min(end, to) - s, pitch, vel });
      }
    }
    return q.sort((a, b) => a.start - b.start);
  }

  pump() {
    const ctx = this.ctx, horizon = ctx.currentTime + 0.25;
    while (this.qi < this.queue.length) {
      const n = this.queue[this.qi];
      const t = this.t0 + (n.start - this.beat0) * this.spq;
      if (t > horizon) break;
      this.voice(n, Math.max(t, ctx.currentTime), n.dur * this.spq);
      this.qi++;
    }
    if (this.now() >= this.range[1] - EPS) {
      if ($("loop").checked) {
        this.play(this.range[0], true);
      } else {
        this.playing = false;
        this.pos = 0;
        clearInterval(this.timer);
        updatePlayButton();
        drawPlayhead();
        updatePosition();
      }
    }
  }

  voice(n, t, dur) {
    const ctx = this.ctx;
    dur = Math.max(dur, 0.04);
    const f = 440 * Math.pow(2, (n.pitch - 69) / 12);
    const v = Math.pow(n.vel / 127, 1.5);
    const out = ctx.createGain();
    const filt = ctx.createBiquadFilter();
    filt.type = "lowpass";
    const oscs = [];
    const osc = (type, freq, gain) => {
      const o = ctx.createOscillator();
      o.type = type;
      o.frequency.value = freq;
      if (gain === 1) o.connect(filt);
      else { const g = ctx.createGain(); g.gain.value = gain; o.connect(g).connect(filt); }
      oscs.push(o);
    };
    let stopAt;
    const env = out.gain;
    env.setValueAtTime(0, t);
    if (n.track === "Melody") {
      filt.frequency.value = 3400;
      osc("triangle", f, 1);
      osc("sine", f * 2, 0.16);
      const peak = 0.30 * v;
      env.linearRampToValueAtTime(peak, t + 0.012);
      env.setTargetAtTime(peak * 0.65, t + 0.012, 0.18);
      env.setTargetAtTime(0, t + dur, 0.07);
      stopAt = t + dur + 0.5;
    } else {
      filt.frequency.value = 1500 + 1500 * v;
      osc("sine", f, 1);
      osc("triangle", f, 0.35);
      const peak = 0.13 * v;
      env.linearRampToValueAtTime(peak, t + 0.006);
      env.setTargetAtTime(peak * 0.3, t + 0.006, 0.5);
      env.setTargetAtTime(0, t + dur, 0.18);
      stopAt = t + dur + 1.2;
    }
    filt.connect(out).connect(this.bus[n.track]);
    const rec = { out, oscs };
    for (const o of oscs) { o.start(t); o.stop(stopAt); }
    oscs[0].onended = () => { out.disconnect(); this.voices.delete(rec); };
    this.voices.add(rec);
  }

  silence() {
    if (!this.ctx) return;
    const now = this.ctx.currentTime;
    for (const rec of this.voices) {
      const g = rec.out.gain;
      if (g.cancelAndHoldAtTime) g.cancelAndHoldAtTime(now); else g.cancelScheduledValues(now);
      g.setTargetAtTime(0, now, 0.02);
      for (const o of rec.oscs) { try { o.stop(now + 0.12); } catch (e) { /* already stopped */ } }
    }
    this.voices.clear();
  }
}

const player = new Player();

function updatePlayButton() {
  $("playLabel").textContent = player.playing ? "Pause" : "Play";
  $("playIcon").innerHTML = player.playing
    ? '<path d="M7 4h4v16H7zM14 4h4v16h-4z" fill="currentColor"/>'
    : '<path d="M7 4l13 8-13 8z" fill="currentColor"/>';
}

function sectionAt(beat) {
  if (!song) return null;
  for (const sec of song.sections) {
    if (beat >= sec.start - EPS && beat < sec.start + sec.bars * song.bar_quarters - EPS) return sec;
  }
  return song.sections[song.sections.length - 1];
}

function updatePosition() {
  if (!song) return;
  const b = player.now();
  const bar = Math.floor(b / song.bar_quarters + EPS) + 1;
  const beat = Math.floor((b % song.bar_quarters) / song.group_quarters + EPS) + 1;
  const sec = sectionAt(b);
  $("pos").innerHTML = `<strong>Bar ${bar}</strong> · beat ${beat} · ${sec ? sec.label : ""}`;
  highlightBar(bar - 1);
}

function frame() {
  drawPlayhead();
  updatePosition();
  if (player.playing) requestAnimationFrame(frame);
}

/* ------------------------------------------------------------ piano roll */

const roll = { canvas: $("roll"), layer: document.createElement("canvas"), geo: null };

function roundRect(g, x, y, w, h, r) {
  r = Math.min(r, w / 2, h / 2);
  g.beginPath();
  g.moveTo(x + r, y);
  g.arcTo(x + w, y, x + w, y + h, r);
  g.arcTo(x + w, y + h, x, y + h, r);
  g.arcTo(x, y + h, x, y, r);
  g.arcTo(x, y, x + w, y, r);
  g.closePath();
}

function drawRollStatic() {
  const c = roll.canvas, dpr = window.devicePixelRatio || 1;
  const W = c.clientWidth, H = c.clientHeight;
  c.width = Math.round(W * dpr); c.height = Math.round(H * dpr);
  const L = roll.layer;
  L.width = c.width; L.height = c.height;
  const g = L.getContext("2d");
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.clearRect(0, 0, W, H);
  if (!song) return;

  const padL = 38, padR = 10, secH = 26, chordH = 24, top = secH + chordH + 6, bottom = H - 10;
  const total = song.total_quarters, bq = song.bar_quarters;
  const x = (b) => padL + (b / total) * (W - padL - padR);
  const all = song.tracks.flatMap((t) => t.notes.map((n) => n[2]));
  const minP = Math.min(...all) - 2, maxP = Math.max(...all) + 2;
  const rowH = (bottom - top) / (maxP - minP + 1);
  const y = (p) => top + (maxP - p) * rowH;
  const text = cssVar("--text"), muted = cssVar("--muted"), line = cssVar("--line");
  const font = '-apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", system-ui, sans-serif';

  // section bands
  song.sections.forEach((sec, i) => {
    const x0 = x(sec.start), x1 = x(sec.start + sec.bars * bq);
    const col = cssVar(SECTION_COLOR[sec.kind]);
    g.fillStyle = col;
    g.globalAlpha = i % 2 ? 0.05 : 0.09;
    g.fillRect(x0, secH, x1 - x0, H - secH);
    g.globalAlpha = 0.9;
    roundRect(g, x0 + 1.5, 3, x1 - x0 - 3, secH - 6, 6);
    g.fill();
    g.globalAlpha = 1;
    g.fillStyle = "#fff";
    g.font = `600 12px ${font}`;
    g.save();
    g.beginPath(); g.rect(x0 + 2, 0, x1 - x0 - 4, secH); g.clip();
    g.fillText(sec.label, x0 + 9, secH / 2 + 4.5);
    g.restore();
  });

  // pitch grid with C labels
  g.font = `11px ${font}`;
  for (let p = minP; p <= maxP; p++) {
    if (p % 12 !== 0) continue;
    const yy = y(p) + rowH;
    g.strokeStyle = line; g.lineWidth = 1;
    g.beginPath(); g.moveTo(padL, yy); g.lineTo(W - padR, yy); g.stroke();
    g.fillStyle = muted;
    g.fillText(`C${p / 12 - 1}`, 6, yy - 2);
  }

  // bar lines
  for (let b = 0, i = 0; b <= total + EPS; b += bq, i++) {
    const isSection = song.sections.some((s) => Math.abs(s.start - b) < EPS) || Math.abs(b - total) < EPS;
    g.strokeStyle = line;
    g.globalAlpha = isSection ? 1 : 0.55;
    g.lineWidth = isSection ? 1.5 : 1;
    g.beginPath(); g.moveTo(x(b) + 0.5, secH); g.lineTo(x(b) + 0.5, bottom); g.stroke();
  }
  g.globalAlpha = 1;

  // chord symbols
  g.font = `600 12px ${font}`;
  g.fillStyle = text;
  for (const sec of song.sections) {
    for (const ch of sec.chords) {
      const x0 = x(ch.start), w = x(ch.start + ch.length) - x0;
      // full symbol if it fits, else just the root letter(s), else nothing
      const root = ch.symbol.match(/^[A-G][#b]?/)[0];
      const label = [pretty(ch.symbol), pretty(root)].find((s) => g.measureText(s).width + 6 < w);
      if (label) g.fillText(label, x0 + 4, secH + chordH / 2 + 5);
    }
  }

  // notes
  const drawTrack = (name, color, alpha, radius) => {
    const track = song.tracks.find((t) => t.name === name);
    if (!track) return;
    g.fillStyle = color;
    g.globalAlpha = trackOn(name) ? alpha : alpha * 0.25;
    for (const [s, d, p] of track.notes) {
      const x0 = x(s), w = Math.max(2, x(s + d) - x0 - 0.75);
      roundRect(g, x0, y(p) + 0.5, w, Math.max(2.5, rowH - 1), radius);
      g.fill();
    }
    g.globalAlpha = 1;
  };
  drawTrack("Chords", cssVar("--chords"), 0.55, 2);
  drawTrack("Melody", cssVar("--melody"), 1, 3);

  roll.geo = { padL, padR, W, H, total, x, secH };
  drawPlayhead();
}

function drawPlayhead() {
  const c = roll.canvas, g = c.getContext("2d");
  g.setTransform(1, 0, 0, 1, 0, 0);
  g.clearRect(0, 0, c.width, c.height);
  g.drawImage(roll.layer, 0, 0);
  if (!song || !roll.geo) return;
  const dpr = window.devicePixelRatio || 1;
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  const xx = roll.geo.x(player.now());
  g.strokeStyle = cssVar("--playhead");
  g.lineWidth = 2;
  g.beginPath(); g.moveTo(xx, roll.geo.secH); g.lineTo(xx, roll.geo.H); g.stroke();
  g.fillStyle = cssVar("--playhead");
  g.beginPath(); g.moveTo(xx - 6, roll.geo.secH); g.lineTo(xx + 6, roll.geo.secH); g.lineTo(xx, roll.geo.secH + 8); g.fill();
}

roll.canvas.addEventListener("click", (e) => {
  if (!song || !roll.geo) return;
  const r = roll.canvas.getBoundingClientRect();
  const { padL, padR, W, total } = roll.geo;
  const beat = ((e.clientX - r.left - padL) / (W - padL - padR)) * total;
  player.seek(Math.floor(clamp(beat, 0, total - EPS) / song.bar_quarters) * song.bar_quarters);
});

let resizeQueued = false;
window.addEventListener("resize", () => {
  if (resizeQueued) return;
  resizeQueued = true;
  requestAnimationFrame(() => { resizeQueued = false; drawRollStatic(); });
});
if (window.matchMedia) {
  const mq = window.matchMedia("(prefers-color-scheme: dark)");
  (mq.addEventListener ? mq.addEventListener.bind(mq, "change") : mq.addListener.bind(mq))(() => drawRollStatic());
}

/* ------------------------------------------------------------ chord sheet */

let barCells = [];
let currentBar = -1;

function renderSheet() {
  const root = $("sheet");
  root.innerHTML = "";
  barCells = [];
  currentBar = -1;
  const bq = song.bar_quarters;
  for (const sec of song.sections) {
    const firstBar = Math.round(sec.start / bq) + 1;
    const nbars = Math.ceil(sec.bars - EPS);
    const card = document.createElement("div");
    card.className = "sec-card";
    card.style.setProperty("--sec", `var(${SECTION_COLOR[sec.kind]})`);
    const h = document.createElement("h3");
    h.textContent = sec.label;
    const sub = document.createElement("span");
    sub.textContent = `bars ${firstBar}–${firstBar + nbars - 1}`;
    h.appendChild(sub);
    card.appendChild(h);
    const grid = document.createElement("div");
    grid.className = "bars";
    for (let b = 0; b < nbars; b++) {
      const bs = sec.start + b * bq;
      const cell = document.createElement("button");
      cell.type = "button";
      cell.className = "bar";
      cell.setAttribute("aria-label", `Play from bar ${firstBar + b}`);
      const chords = sec.chords.filter((c) => c.start >= bs - EPS && c.start < bs + bq - EPS);
      if (chords.length) {
        for (const c of chords) {
          const d = document.createElement("span");
          d.className = "chord";
          d.innerHTML = `<span class="sym"></span><span class="rn"></span>`;
          d.firstChild.textContent = pretty(c.symbol);
          d.lastChild.textContent = pretty(c.roman);
          cell.appendChild(d);
        }
      } else {
        const held = document.createElement("span");
        held.className = "held";
        held.textContent = "—";
        held.title = "Chord continues";
        cell.appendChild(held);
      }
      const num = document.createElement("span");
      num.className = "num";
      num.textContent = firstBar + b;
      cell.appendChild(num);
      cell.addEventListener("click", () => player.seek(bs));
      grid.appendChild(cell);
      barCells[firstBar + b - 1] = cell;
    }
    card.appendChild(grid);
    root.appendChild(card);
  }
  updatePosition();
}

function highlightBar(index) {
  if (index === currentBar) return;
  if (barCells[currentBar]) barCells[currentBar].classList.remove("now");
  currentBar = index;
  if (barCells[index]) barCells[index].classList.add("now");
}

/* ------------------------------------------------------------ wiring */

function wireTransport() {
  $("play").addEventListener("click", () => player.toggle());
  $("rewind").addEventListener("click", () => player.seek(0));
  $("stop").addEventListener("click", () => player.stop());
  $("download").addEventListener("click", downloadMidi);
  for (const id of ["trackMelody", "trackChords"]) {
    $(id).addEventListener("change", () => { player.applyTracks(); drawRollStatic(); });
  }
  $("loop").addEventListener("change", () => { if (player.playing) player.play(player.now()); });
  document.addEventListener("keydown", (e) => {
    const tag = e.target.tagName;
    if (["INPUT", "SELECT", "TEXTAREA"].includes(tag)) return;
    if (e.code === "Escape") { e.preventDefault(); player.stop(); return; }
    if (tag === "BUTTON") return; // Space would also click the focused button
    if (e.code === "Space") { e.preventDefault(); player.toggle(); }
    if (e.code === "Home") { e.preventDefault(); player.seek(0); }
  });
}

async function init() {
  try {
    const r = await fetch("/api/options");
    OPTS = await r.json();
  } catch (e) {
    showError("Can't reach the composer server. Is `python3 -m music_composer.ui` still running?");
    return;
  }
  params = initialParams(Object.assign(loadSettings(), linkParams()));
  if (location.search) history.replaceState(null, "", location.pathname); // applied; a reload keeps your later changes
  buildControls();
  wireTransport();
  updatePlayButton();
  await compose();
}

init();
