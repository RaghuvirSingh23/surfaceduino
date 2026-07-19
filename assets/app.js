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
  lastEvent: document.querySelector('#lastEvent'),
  eventLog: document.querySelector('#eventLog'),
};

function setPill(element, text, ready) {
  element.textContent = text;
  element.className = `pill ${ready ? 'ready' : 'waiting'}`;
}

function percent(value) {
  return `${Math.round((value || 0) * 100)}%`;
}

function renderZones(zones, candidate) {
  elements.zones.replaceChildren();
  zones.forEach((zone, index) => {
    const card = document.createElement('article');
    card.className = `zone-card zone-${index + 1}${candidate === zone.id ? ' selected' : ''}`;

    const top = document.createElement('div');
    const label = document.createElement('strong');
    label.textContent = zone.label;
    const value = document.createElement('span');
    value.textContent = percent(zone.occupancy);
    top.append(label, value);

    const meter = document.createElement('div');
    meter.className = 'meter';
    const fill = document.createElement('i');
    fill.style.width = percent(zone.occupancy);
    meter.append(fill);

    const state = document.createElement('small');
    state.textContent = zone.occupied ? 'OCCUPIED' : 'CLEAR';
    card.append(top, meter, state);
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
    ? `${event.control_id} activated via ${event.source}`
    : `Ignored: ${event.metadata?.reason || 'no valid selection'}`;
}

function renderLog(events) {
  elements.eventLog.replaceChildren();
  events.slice(0, 8).forEach((event) => {
    const item = document.createElement('li');
    const kind = document.createElement('b');
    kind.textContent = event.kind === 'control.activate' ? 'ACTIVATE' : 'REJECT';
    const control = document.createElement('span');
    control.textContent = event.control_id || 'none';
    const source = document.createElement('small');
    source.textContent = event.source;
    item.append(kind, control, source);
    elements.eventLog.append(item);
  });
}

function render(state) {
  const directMode = state.input_mode === 'direct_buttons';
  const cameraReady = ['connected', 'streaming'].includes(state.camera.status);
  setPill(elements.cameraStatus, `camera · ${state.camera.status}`, cameraReady);
  setPill(elements.bridgeStatus, `bridge · ${state.bridge.status}`, state.bridge.status === 'ready');
  setPill(
    elements.calibrationStatus,
    directMode
      ? 'mode · direct buttons'
      : state.detector.calibrated ? 'surface · calibrated' : 'surface · uncalibrated',
    directMode || state.detector.calibrated,
  );

  elements.candidate.textContent = state.detector.ambiguous
    ? 'AMBIGUOUS'
    : state.candidate || 'NO SELECTION';
  elements.candidate.classList.toggle('active', Boolean(state.candidate));
  elements.candidate.classList.toggle('error', Boolean(state.detector.ambiguous));

  if (directMode) {
    elements.instruction.textContent = 'Camera offline: D2 runs ONE, D3 runs TWO.';
  } else if (!state.detector.calibrated) {
    elements.instruction.textContent = 'Clear the surface, then calibrate.';
  } else if (state.detector.ambiguous) {
    elements.instruction.textContent = 'Keep only one zone occupied.';
  } else if (state.candidate) {
    elements.instruction.textContent = 'Selection ready. Press D2 to commit.';
  } else {
    elements.instruction.textContent = 'Place a hand or object inside one zone.';
  }

  renderZones(state.zones || [], state.candidate);
  elements.confirmLabel.textContent = directMode ? 'D2 · ONE' : 'D2 · CONFIRM';
  elements.calibrateLabel.textContent = directMode ? 'D3 · TWO' : 'D3 · CALIBRATE';
  elements.confirmButton.textContent = directMode ? 'Simulate ONE' : 'Simulate confirm';
  elements.calibrateButton.textContent = directMode ? 'Simulate TWO' : 'Capture background';
  elements.confirmState.textContent = state.buttons.confirm ? 'DOWN' : 'UP';
  elements.calibrateState.textContent = state.buttons.calibrate ? 'DOWN' : 'UP';
  renderEvent(state.last_event);
  renderLog(state.events || []);
}

async function command(path) {
  const response = await fetch(path, { method: 'POST' });
  if (!response.ok) throw new Error(`${path} returned ${response.status}`);
}

elements.confirmButton.addEventListener('click', () => command('/confirm'));
elements.calibrateButton.addEventListener('click', () => command('/calibrate'));

async function poll() {
  try {
    const response = await fetch('/state', { cache: 'no-store' });
    if (!response.ok) throw new Error(`state returned ${response.status}`);
    render(await response.json());
  } catch (error) {
    setPill(elements.cameraStatus, 'board · disconnected', false);
    console.error(error);
  } finally {
    window.setTimeout(poll, 250);
  }
}

poll();
