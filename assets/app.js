const elements = {
  cameraStatus: document.querySelector('#cameraStatus'),
  bridgeStatus: document.querySelector('#bridgeStatus'),
  calibrationStatus: document.querySelector('#calibrationStatus'),
  candidate: document.querySelector('#candidate'),
  instruction: document.querySelector('#instruction'),
  zones: document.querySelector('#zones'),
  confirmLabel: document.querySelector('#confirmLabel'),
  calibrateLabel: document.querySelector('#calibrateLabel'),
  confirmState: document.querySelector('#confirmState'),
  calibrateState: document.querySelector('#calibrateState'),
  confirmButton: document.querySelector('#confirmButton'),
  calibrateButton: document.querySelector('#calibrateButton'),
  soundButton: document.querySelector('#soundButton'),
  fullscreenButton: document.querySelector('#fullscreenButton'),
  videoWrap: document.querySelector('.video-wrap'),
  lastEvent: document.querySelector('#lastEvent'),
  eventLog: document.querySelector('#eventLog'),
};

const noteFrequencies = {
  C4: 261.63,
  D4: 293.66,
  E4: 329.63,
  F4: 349.23,
  G4: 392.00,
  A4: 440.00,
};

let audioContext = null;
let masterGain = null;
let lastAudioSequence = null;

function setPill(element, text, ready) {
  element.textContent = text;
  element.className = `pill ${ready ? 'ready' : 'waiting'}`;
}

async function enableAudio() {
  if (!audioContext) {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    audioContext = new AudioContext();
    masterGain = audioContext.createGain();
    masterGain.gain.value = 0.72;
    masterGain.connect(audioContext.destination);
  }
  if (audioContext.state !== 'running') await audioContext.resume();
  elements.soundButton.textContent = '♫ Sound on';
  elements.soundButton.classList.add('enabled');
}

function piano(note) {
  if (!audioContext || audioContext.state !== 'running') return;
  const now = audioContext.currentTime;
  const gain = audioContext.createGain();
  const body = audioContext.createBiquadFilter();
  body.type = 'lowpass';
  body.frequency.setValueAtTime(2600, now);
  gain.gain.setValueAtTime(0.0001, now);
  gain.gain.exponentialRampToValueAtTime(0.44, now + 0.012);
  gain.gain.exponentialRampToValueAtTime(0.12, now + 0.22);
  gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.9);
  gain.connect(body).connect(masterGain);

  [1, 2].forEach((harmonic) => {
    const oscillator = audioContext.createOscillator();
    oscillator.type = harmonic === 1 ? 'triangle' : 'sine';
    oscillator.frequency.value = noteFrequencies[note] * harmonic;
    oscillator.detune.value = harmonic === 1 ? -3 : 4;
    const level = audioContext.createGain();
    level.gain.value = harmonic === 1 ? 0.8 : 0.16;
    oscillator.connect(level).connect(gain);
    oscillator.start(now);
    oscillator.stop(now + 0.95);
  });
}

function noise(duration, filterType, frequency, level, start = audioContext.currentTime) {
  const sampleCount = Math.ceil(audioContext.sampleRate * duration);
  const buffer = audioContext.createBuffer(1, sampleCount, audioContext.sampleRate);
  const data = buffer.getChannelData(0);
  for (let i = 0; i < sampleCount; i += 1) data[i] = Math.random() * 2 - 1;
  const source = audioContext.createBufferSource();
  const filter = audioContext.createBiquadFilter();
  const gain = audioContext.createGain();
  source.buffer = buffer;
  filter.type = filterType;
  filter.frequency.value = frequency;
  gain.gain.setValueAtTime(level, start);
  gain.gain.exponentialRampToValueAtTime(0.0001, start + duration);
  source.connect(filter).connect(gain).connect(masterGain);
  source.start(start);
  source.stop(start + duration);
}

function drum(kind) {
  if (!audioContext || audioContext.state !== 'running') return;
  const now = audioContext.currentTime;
  if (kind === 'snare') {
    noise(0.19, 'highpass', 1200, 0.55, now);
    const tone = audioContext.createOscillator();
    const gain = audioContext.createGain();
    tone.type = 'triangle';
    tone.frequency.value = 185;
    gain.gain.setValueAtTime(0.22, now);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.12);
    tone.connect(gain).connect(masterGain);
    tone.start(now);
    tone.stop(now + 0.13);
    return;
  }
  if (kind === 'hat') {
    noise(0.075, 'highpass', 6800, 0.28, now);
    return;
  }

  const oscillator = audioContext.createOscillator();
  const gain = audioContext.createGain();
  oscillator.type = 'sine';
  const isKick = kind === 'kick';
  oscillator.frequency.setValueAtTime(isKick ? 155 : 220, now);
  oscillator.frequency.exponentialRampToValueAtTime(isKick ? 43 : 82, now + (isKick ? 0.2 : 0.28));
  gain.gain.setValueAtTime(isKick ? 0.9 : 0.55, now);
  gain.gain.exponentialRampToValueAtTime(0.0001, now + (isKick ? 0.38 : 0.45));
  oscillator.connect(gain).connect(masterGain);
  oscillator.start(now);
  oscillator.stop(now + 0.46);
}

function playSound(group, sound) {
  if (group === 'piano') piano(sound);
  if (group === 'drum') drum(sound);
}

function playEvent(event) {
  if (event.kind !== 'control.activate') return;
  const group = event.metadata?.group || (event.control_id?.startsWith('piano_') ? 'piano' : 'drum');
  const sound = event.metadata?.sound || event.control_id?.replace('piano_', '').replace('drum_', '');
  playSound(group, sound?.toUpperCase() in noteFrequencies ? sound.toUpperCase() : sound);
}

function consumeAudioEvents(events) {
  const sequences = events.map((event) => event.sequence).filter(Number.isFinite);
  if (lastAudioSequence === null) {
    lastAudioSequence = sequences.length ? Math.max(...sequences) : 0;
    return;
  }
  events
    .filter((event) => event.sequence > lastAudioSequence)
    .sort((a, b) => a.sequence - b.sequence)
    .forEach(playEvent);
  if (sequences.length) lastAudioSequence = Math.max(lastAudioSequence, ...sequences);
}

function renderZones(zones) {
  elements.zones.replaceChildren();
  zones.forEach((zone) => {
    const card = document.createElement('button');
    const [x0, y0, x1, y1] = zone.rect;
    card.type = 'button';
    card.className = `zone-card ${zone.group}${zone.occupied ? ' active' : ''}`;
    card.style.left = `${x0 * 100}%`;
    card.style.top = `${y0 * 100}%`;
    card.style.width = `${(x1 - x0) * 100}%`;
    card.style.height = `${(y1 - y0) * 100}%`;
    card.title = `${zone.label} · camera occupancy ${Math.round((zone.occupancy || 0) * 100)}%`;

    const label = document.createElement('strong');
    label.textContent = zone.label;
    const occupancy = document.createElement('span');
    occupancy.textContent = `${Math.round((zone.occupancy || 0) * 100)}%`;
    card.append(label, occupancy);
    card.addEventListener('pointerdown', async () => {
      await enableAudio();
      card.classList.add('preview');
      playSound(zone.group, zone.sound);
    });
    card.addEventListener('pointerup', () => card.classList.remove('preview'));
    card.addEventListener('pointerleave', () => card.classList.remove('preview'));
    elements.zones.append(card);
  });
}

function renderEvent(event) {
  if (!event) {
    elements.lastEvent.textContent = 'Waiting for an activation…';
    return;
  }
  const accepted = event.kind === 'control.activate';
  elements.lastEvent.className = `last-event ${accepted ? 'accepted' : 'rejected'}`;
  elements.lastEvent.textContent = accepted
    ? `${event.metadata?.action || event.control_id} · ${event.source}`
    : `Ignored: ${event.metadata?.reason || 'no valid selection'}`;
}

function renderLog(events) {
  elements.eventLog.replaceChildren();
  events.slice(0, 8).forEach((event) => {
    const item = document.createElement('li');
    const kind = document.createElement('b');
    kind.textContent = event.kind === 'control.activate' ? 'PLAY' : 'REJECT';
    const control = document.createElement('span');
    control.textContent = event.metadata?.sound || event.control_id || 'none';
    const source = document.createElement('small');
    source.textContent = event.source;
    item.append(kind, control, source);
    elements.eventLog.append(item);
  });
}

function render(state) {
  const directMode = state.input_mode === 'direct_buttons';
  const cameraReady = ['connected', 'streaming'].includes(state.camera.status);
  const activeZones = (state.zones || []).filter((zone) => zone.occupied);
  setPill(elements.cameraStatus, `camera · ${state.camera.status}`, cameraReady);
  setPill(elements.bridgeStatus, `bridge · ${state.bridge.status}`, state.bridge.status === 'ready');
  setPill(
    elements.calibrationStatus,
    directMode ? 'mode · direct buttons' : state.detector.calibrated ? 'surface · live' : 'surface · uncalibrated',
    directMode || state.detector.calibrated,
  );

  elements.candidate.textContent = activeZones.length
    ? `PLAYING · ${activeZones.map((zone) => zone.label).join(' + ')}`
    : 'READY TO PLAY';
  elements.candidate.classList.toggle('active', activeZones.length > 0);
  elements.candidate.classList.remove('error');

  if (directMode) {
    elements.instruction.textContent = 'Camera offline: D2 tests C4, D3 tests kick.';
  } else if (!state.detector.calibrated) {
    elements.instruction.textContent = 'Clear the instrument surface, then calibrate.';
  } else {
    elements.instruction.textContent = 'Play the projected piano and drum zones with your hands.';
  }

  renderZones(state.zones || []);
  elements.confirmLabel.textContent = directMode ? 'D2 · C4' : 'D2 · TEST C4';
  elements.calibrateLabel.textContent = directMode ? 'D3 · KICK' : 'D3 · CALIBRATE';
  elements.confirmButton.textContent = 'Test C4';
  elements.calibrateButton.textContent = directMode ? 'Test kick' : 'Capture background';
  elements.confirmState.textContent = state.buttons.confirm ? 'DOWN' : 'UP';
  elements.calibrateState.textContent = state.buttons.calibrate ? 'DOWN' : 'UP';
  renderEvent(state.last_event);
  renderLog(state.events || []);
  consumeAudioEvents(state.events || []);
}

async function command(path) {
  const response = await fetch(path, { method: 'POST' });
  if (!response.ok) throw new Error(`${path} returned ${response.status}`);
}

elements.soundButton.addEventListener('click', enableAudio);
elements.confirmButton.addEventListener('click', async () => {
  await enableAudio();
  await command('/confirm');
});
elements.calibrateButton.addEventListener('click', () => command('/calibrate'));
elements.fullscreenButton.addEventListener('click', async () => {
  if (document.fullscreenElement) await document.exitFullscreen();
  else await elements.videoWrap.requestFullscreen();
});
document.addEventListener('fullscreenchange', () => {
  elements.fullscreenButton.textContent = document.fullscreenElement ? '× Exit full screen' : '⛶ Full screen';
});

async function poll() {
  try {
    const response = await fetch('/state', { cache: 'no-store' });
    if (!response.ok) throw new Error(`state returned ${response.status}`);
    render(await response.json());
  } catch (error) {
    setPill(elements.cameraStatus, 'board · disconnected', false);
    console.error(error);
  } finally {
    window.setTimeout(poll, 80);
  }
}

poll();
