const SILENCE = Object.freeze({ rawAmp: 0, bass: 0, mid: 0, treble: 0 });

export class AudioInput {
  constructor(options = {}) {
    this.mediaDevices = options.mediaDevices || globalThis.navigator?.mediaDevices;
    this.AudioContextImpl = options.AudioContextImpl || globalThis.AudioContext || globalThis.webkitAudioContext;
    this.generation = 0;
    this.stream = null;
    this.context = null;
    this.analyser = null;
    this.data = null;
    this.levels = { ...SILENCE };
    this.outputLevels = { ...SILENCE };
  }

  async setListening(listening) {
    if (!listening) return this.stop();
    if (this.stream || this.analyser) return;
    const generation = ++this.generation;
    try {
      const stream = await this.mediaDevices?.getUserMedia({ audio: true, video: false });
      if (!stream || generation !== this.generation) {
        stream?.getTracks?.().forEach((track) => track.stop());
        return;
      }
      const context = new this.AudioContextImpl();
      const analyser = context.createAnalyser();
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = 0.65;
      context.createMediaStreamSource(stream).connect(analyser);
      this.stream = stream;
      this.context = context;
      this.analyser = analyser;
      this.data = new Uint8Array(analyser.frequencyBinCount);
    } catch (error) {
      if (generation === this.generation) console.warn("[PresenceApp] Microphone unavailable:", error);
    }
  }

  setOutputLevels(levels) {
    for (const band of Object.keys(SILENCE)) this.outputLevels[band] = Number(levels?.[band]) || 0;
  }

  sample(useOutput = false) {
    if (useOutput) return this._decay(this.outputLevels, 0.9);
    if (!this.analyser || !this.data) return this._decay(this.levels, 0.76);
    this.analyser.getByteFrequencyData(this.data);
    let sum = 0, bass = 0, mid = 0, treble = 0;
    for (let i = 0; i < this.data.length; i += 1) {
      const value = this.data[i];
      sum += value;
      if (i >= 1 && i <= 10) bass += value;
      else if (i <= 45) mid += value;
      else if (i <= 90) treble += value;
    }
    const average = sum / this.data.length;
    this.levels = average < 3 ? { ...SILENCE } : {
      rawAmp: Math.min(1, Math.pow(average / 42, 0.85)),
      bass: Math.min(1, Math.pow((bass / 10) / 45, 0.8)),
      mid: Math.min(1, Math.pow((mid / 35) / 38, 0.85)),
      treble: Math.min(1, Math.pow((treble / 45) / 30, 0.9)),
    };
    return this.levels;
  }

  _decay(levels, factor) {
    for (const band of Object.keys(SILENCE)) levels[band] = levels[band] * factor < 0.002 ? 0 : levels[band] * factor;
    return { ...levels };
  }

  stop() {
    this.generation += 1;
    this.stream?.getTracks?.().forEach((track) => track.stop());
    this.stream = null;
    this.analyser = null;
    this.data = null;
    const context = this.context;
    this.context = null;
    context?.close?.().catch?.(() => {});
  }

  dispose() {
    this.stop();
    this.outputLevels = { ...SILENCE };
    this.levels = { ...SILENCE };
  }
}
