/**
 * AudioWorkletProcessor for real-time mic capture — runs on the browser's
 * dedicated audio rendering thread, so this file is plain JS (no bundler,
 * no TypeScript, no imports) and can't be unit-tested the way the rest of
 * the codebase is: jsdom doesn't implement AudioWorkletGlobalScope, and no
 * real browser runs in this project's test suite. The RMS/zero-crossing
 * math here intentionally mirrors backend/app/services/vad.py's EnergyVAD
 * so the "fast, rough, browser-side" stage and the "accurate, sidecar-side"
 * stage (Phase 3 spec §3.2) agree on what counts as speech.
 *
 * Emits three message types over `this.port`:
 *   - {type: 'audio-chunk', samples: Float32Array}   every 480 samples (30ms @ 16kHz)
 *   - {type: 'volume-level', level: number}          every render quantum, for the UI meter
 *   - {type: 'vad-frame', isSpeech: boolean, timestampMs: number}  every 30ms chunk
 */

const CHUNK_SIZE = 480; // 30ms @ 16kHz, matching backend/app/services/vad.py
const ENERGY_THRESHOLD = 0.02;
const ZCR_MAX = 0.35;

class MicProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.buffer = new Float32Array(CHUNK_SIZE);
    this.bufferIndex = 0;
    this.elapsedMs = 0;
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || input.length === 0) return true;
    const channel = input[0];

    for (let i = 0; i < channel.length; i++) {
      this.buffer[this.bufferIndex++] = channel[i];

      if (this.bufferIndex === CHUNK_SIZE) {
        this.flushChunk();
        this.bufferIndex = 0;
      }
    }

    return true; // keep the processor alive
  }

  flushChunk() {
    const chunk = this.buffer.slice(0, CHUNK_SIZE);

    let sumSquares = 0;
    let crossings = 0;
    for (let i = 0; i < chunk.length; i++) {
      sumSquares += chunk[i] * chunk[i];
      if (i > 0 && Math.sign(chunk[i]) !== Math.sign(chunk[i - 1]) && chunk[i - 1] !== 0) {
        crossings++;
      }
    }
    const rms = Math.sqrt(sumSquares / chunk.length);
    const zcr = crossings / (chunk.length - 1);
    const isSpeech = rms > ENERGY_THRESHOLD && zcr < ZCR_MAX;

    this.port.postMessage({ type: "audio-chunk", samples: chunk });
    this.port.postMessage({ type: "volume-level", level: rms });
    this.port.postMessage({ type: "vad-frame", isSpeech, timestampMs: this.elapsedMs });

    this.elapsedMs += 30;
  }
}

registerProcessor("mic-processor", MicProcessor);
