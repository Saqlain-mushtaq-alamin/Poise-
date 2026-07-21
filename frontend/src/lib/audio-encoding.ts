/**
 * Converts Web Audio's native Float32 PCM (range [-1, 1]) to 16-bit PCM
 * bytes — the format backend/app/routers/voice.py's WebSocket endpoints
 * expect (see `_pcm16_bytes_to_float32` there, which does the inverse).
 * Pure math, no browser APIs, fully unit-testable.
 */
export function float32ToPCM16Bytes(samples: Float32Array): ArrayBuffer {
  const buffer = new ArrayBuffer(samples.length * 2);
  const view = new DataView(buffer);

  for (let i = 0; i < samples.length; i++) {
    const clamped = Math.max(-1, Math.min(1, samples[i]));
    const intSample = clamped < 0 ? clamped * 32768 : clamped * 32767;
    view.setInt16(i * 2, Math.round(intSample), true /* little-endian */);
  }

  return buffer;
}
