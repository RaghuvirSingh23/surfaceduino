const NOTE_FREQUENCIES: Record<string, number> = {
  C4: 261.63,
  D4: 293.66,
  E4: 329.63,
  F4: 349.23,
  G4: 392.0,
  A4: 440.0,
  B4: 493.88,
};

class AudioEngine {
  private context: AudioContext | null = null;
  private master: GainNode | null = null;

  get enabled(): boolean {
    return this.context?.state === "running";
  }

  async enable(): Promise<void> {
    if (!this.context) {
      const Ctor =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext })
          .webkitAudioContext;
      this.context = new Ctor();
      this.master = this.context.createGain();
      this.master.gain.value = 0.72;
      this.master.connect(this.context.destination);
    }
    if (this.context.state !== "running") await this.context.resume();
  }

  play(group: string, sound: string): void {
    if (!this.context || !this.master || this.context.state !== "running") return;
    if (group === "piano") this.piano(sound.toUpperCase());
    else if (group === "drum") this.drum(sound.toLowerCase());
  }

  private piano(note: string): void {
    const ctx = this.context!;
    const master = this.master!;
    const frequency = NOTE_FREQUENCIES[note] ?? NOTE_FREQUENCIES.C4;
    const now = ctx.currentTime;
    const gain = ctx.createGain();
    const body = ctx.createBiquadFilter();
    body.type = "lowpass";
    body.frequency.setValueAtTime(2600, now);
    gain.gain.setValueAtTime(0.0001, now);
    gain.gain.exponentialRampToValueAtTime(0.44, now + 0.012);
    gain.gain.exponentialRampToValueAtTime(0.12, now + 0.22);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.9);
    gain.connect(body).connect(master);

    [1, 2].forEach((harmonic) => {
      const oscillator = ctx.createOscillator();
      oscillator.type = harmonic === 1 ? "triangle" : "sine";
      oscillator.frequency.value = frequency * harmonic;
      oscillator.detune.value = harmonic === 1 ? -3 : 4;
      const level = ctx.createGain();
      level.gain.value = harmonic === 1 ? 0.8 : 0.16;
      oscillator.connect(level).connect(gain);
      oscillator.start(now);
      oscillator.stop(now + 0.95);
    });
  }

  private noise(
    duration: number,
    filterType: BiquadFilterType,
    frequency: number,
    level: number,
    start: number
  ): void {
    const ctx = this.context!;
    const master = this.master!;
    const sampleCount = Math.ceil(ctx.sampleRate * duration);
    const buffer = ctx.createBuffer(1, sampleCount, ctx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < sampleCount; i += 1) data[i] = Math.random() * 2 - 1;
    const source = ctx.createBufferSource();
    const filter = ctx.createBiquadFilter();
    const gain = ctx.createGain();
    source.buffer = buffer;
    filter.type = filterType;
    filter.frequency.value = frequency;
    gain.gain.setValueAtTime(level, start);
    gain.gain.exponentialRampToValueAtTime(0.0001, start + duration);
    source.connect(filter).connect(gain).connect(master);
    source.start(start);
    source.stop(start + duration);
  }

  private drum(kind: string): void {
    const ctx = this.context!;
    const master = this.master!;
    const now = ctx.currentTime;
    if (kind === "snare") {
      this.noise(0.19, "highpass", 1200, 0.55, now);
      const tone = ctx.createOscillator();
      const gain = ctx.createGain();
      tone.type = "triangle";
      tone.frequency.value = 185;
      gain.gain.setValueAtTime(0.22, now);
      gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.12);
      tone.connect(gain).connect(master);
      tone.start(now);
      tone.stop(now + 0.13);
      return;
    }
    if (kind === "hat") {
      this.noise(0.075, "highpass", 6800, 0.28, now);
      return;
    }

    const oscillator = ctx.createOscillator();
    const gain = ctx.createGain();
    oscillator.type = "sine";
    const isKick = kind === "kick";
    oscillator.frequency.setValueAtTime(isKick ? 155 : 220, now);
    oscillator.frequency.exponentialRampToValueAtTime(
      isKick ? 43 : 82,
      now + (isKick ? 0.2 : 0.28)
    );
    gain.gain.setValueAtTime(isKick ? 0.9 : 0.55, now);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + (isKick ? 0.38 : 0.45));
    oscillator.connect(gain).connect(master);
    oscillator.start(now);
    oscillator.stop(now + 0.46);
  }
}

export const audioEngine = new AudioEngine();
