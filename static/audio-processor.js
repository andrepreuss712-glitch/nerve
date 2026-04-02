// AudioWorklet processor: converts Float32 samples to Int16 PCM
// and posts the buffer to the main thread for Socket.IO streaming.
class AudioProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._buffer = [];
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || !input[0]) return true;
    const samples = input[0];
    for (let i = 0; i < samples.length; i++) {
      // Clamp to [-1, 1] and convert Float32 -> Int16
      const s = Math.max(-1, Math.min(1, samples[i]));
      this._buffer.push(s < 0 ? s * 0x8000 : s * 0x7FFF);
    }
    // Flush at ~100ms worth of samples (1600 samples at 16kHz = 3200 bytes)
    if (this._buffer.length >= 1600) {
      const int16 = new Int16Array(this._buffer.splice(0, 1600));
      this.port.postMessage(int16.buffer, [int16.buffer]);
    }
    return true;
  }
}

registerProcessor('audio-processor', AudioProcessor);
