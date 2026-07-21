import { describe, expect, it } from "vitest";

import { float32ToPCM16Bytes } from "./audio-encoding";

describe("float32ToPCM16Bytes", () => {
  it("converts 0.0 to 0", () => {
    const buffer = float32ToPCM16Bytes(new Float32Array([0]));
    expect(new DataView(buffer).getInt16(0, true)).toBe(0);
  });

  it("converts 1.0 to the max positive int16", () => {
    const buffer = float32ToPCM16Bytes(new Float32Array([1.0]));
    expect(new DataView(buffer).getInt16(0, true)).toBe(32767);
  });

  it("converts -1.0 to the max negative int16", () => {
    const buffer = float32ToPCM16Bytes(new Float32Array([-1.0]));
    expect(new DataView(buffer).getInt16(0, true)).toBe(-32768);
  });

  it("clamps values outside [-1, 1]", () => {
    const buffer = float32ToPCM16Bytes(new Float32Array([2.5, -3.0]));
    const view = new DataView(buffer);
    expect(view.getInt16(0, true)).toBe(32767);
    expect(view.getInt16(2, true)).toBe(-32768);
  });

  it("produces exactly 2 bytes per sample", () => {
    const buffer = float32ToPCM16Bytes(new Float32Array([0.1, 0.2, 0.3, 0.4]));
    expect(buffer.byteLength).toBe(8);
  });

  it("handles an empty array", () => {
    const buffer = float32ToPCM16Bytes(new Float32Array([]));
    expect(buffer.byteLength).toBe(0);
  });

  it("round-trips a mid-range value within 1 LSB of precision", () => {
    const buffer = float32ToPCM16Bytes(new Float32Array([0.5]));
    const decoded = new DataView(buffer).getInt16(0, true) / 32767;
    expect(Math.abs(decoded - 0.5)).toBeLessThan(0.001);
  });

  it("writes samples little-endian", () => {
    const buffer = float32ToPCM16Bytes(new Float32Array([1.0]));
    const bytes = new Uint8Array(buffer);
    // 32767 = 0x7FFF -> low byte 0xFF, high byte 0x7F
    expect(bytes[0]).toBe(0xff);
    expect(bytes[1]).toBe(0x7f);
  });
});
