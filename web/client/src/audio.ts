/**
 * Original court soundtrack and turn chime, synthesized in the browser.
 * No third-party recording — this music is original and royalty-free.
 */

const STORAGE_KEY = "cc_music_muted";

const MELODY = [
  293.66, 220, 349.23, 392, 440, 392, 349.23, 293.66,
  261.63, 293.66, 220, 0, 196, 220, 261.63, 293.66,
];
const BASS = [73.42, 110, 73.42, 65.41];
const BEAT = 0.72;

let ctx: AudioContext | null = null;
let timer: number | null = null;
let step = 0;
let musicOn = false;
const listeners = new Set<() => void>();

function readMuted(): boolean {
  return localStorage.getItem(STORAGE_KEY) === "1";
}

function context(): AudioContext {
  if (!ctx) ctx = new AudioContext();
  if (ctx.state === "suspended") void ctx.resume();
  return ctx;
}

function tone(
  audio: AudioContext,
  freq: number,
  when: number,
  duration: number,
  type: OscillatorType,
  peak: number,
) {
  const osc = audio.createOscillator();
  const filter = audio.createBiquadFilter();
  const gain = audio.createGain();
  filter.type = "lowpass";
  filter.frequency.setValueAtTime(1400, when);
  osc.type = type;
  osc.frequency.setValueAtTime(freq, when);
  gain.gain.setValueAtTime(0.0001, when);
  gain.gain.exponentialRampToValueAtTime(peak, when + 0.03);
  gain.gain.exponentialRampToValueAtTime(0.0001, when + duration);
  osc.connect(filter);
  filter.connect(gain);
  gain.connect(audio.destination);
  osc.start(when);
  osc.stop(when + duration + 0.05);
}

function scheduleBeat() {
  if (!ctx || readMuted()) return;
  const now = ctx.currentTime + 0.05;
  const note = MELODY[step % MELODY.length];
  if (note) tone(ctx, note, now, 0.62, "triangle", 0.04);
  if (step % 4 === 0) tone(ctx, BASS[(step / 4) % BASS.length], now, 1.6, "sine", 0.028);
  step += 1;
}

function startLoop() {
  if (musicOn || readMuted()) return;
  context();
  musicOn = true;
  scheduleBeat();
  timer = window.setInterval(scheduleBeat, BEAT * 1000);
}

function stopLoop() {
  if (timer != null) window.clearInterval(timer);
  timer = null;
  musicOn = false;
}

export function isMusicMuted(): boolean {
  return readMuted();
}

export function subscribeMusic(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function notify() {
  listeners.forEach((fn) => fn());
}

/** Call from a click or key press so the browser allows sound. */
export function unlockAudio() {
  context();
  if (!readMuted()) startLoop();
}

export function setMusicMuted(muted: boolean) {
  localStorage.setItem(STORAGE_KEY, muted ? "1" : "0");
  if (muted) stopLoop();
  else startLoop();
  notify();
}

export function playTurnBuzz() {
  const audio = context();
  const now = audio.currentTime + 0.02;
  tone(audio, 784, now, 0.09, "sine", 0.12);
  tone(audio, 1046, now + 0.12, 0.16, "sine", 0.1);
}
