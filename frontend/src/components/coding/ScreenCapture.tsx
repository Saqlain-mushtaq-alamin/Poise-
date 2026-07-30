/**
 * ScreenCapture — Phase 6.
 *
 * Mount point: frontend/src/components/coding/ScreenCapture.tsx
 *
 * User-initiated screenshot capture for whiteboard/screen-share
 * evaluation. Uses the browser's getDisplayMedia API (works inside
 * the Tauri webview). No background/automatic capture — the button
 * click is the only trigger, per the privacy note in the plan.
 */
import { useState } from 'react';

export class ScreenCaptureController {
  /** Prompts the OS picker, grabs a single frame, and immediately stops
   * the media stream — we only ever want one still image, not a live feed. */
  async captureWindow(): Promise<Blob> {
    const stream = await navigator.mediaDevices.getDisplayMedia({
      video: { displaySurface: 'window' } as MediaTrackConstraints,
      audio: false,
    });

    try {
      const video = document.createElement("video");
      video.srcObject = stream;
      await new Promise<void>((resolve) => {
        video.onloadedmetadata = () => {
          video.play().then(resolve).catch(resolve);
        };
      });

      const canvas = document.createElement("canvas");
      canvas.width = video.videoWidth || 1280;
      canvas.height = video.videoHeight || 720;
      const ctx = canvas.getContext("2d");
      if (!ctx) throw new Error("Canvas context unavailable");
      ctx.drawImage(video, 0, 0);

      return await new Promise<Blob>((resolve, reject) => {
        canvas.toBlob((blob) => {
          if (blob) resolve(blob);
          else reject(new Error('Failed to encode screenshot'));
        }, 'image/png');
      });
    } finally {
      stream.getTracks().forEach((t) => t.stop());
    }
  }
}

export interface ScreenCaptureButtonProps {
  onCapture: (blob: Blob) => void | Promise<void>;
  disabled?: boolean;
}

export function ScreenCaptureButton({ onCapture, disabled }: ScreenCaptureButtonProps) {
  const [capturing, setCapturing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const controller = new ScreenCaptureController();

  const handleClick = async () => {
    setError(null);
    setCapturing(true);
    try {
      const blob = await controller.captureWindow();
      await onCapture(blob);
    } catch (e) {
      if ((e as DOMException)?.name !== 'NotAllowedError') {
        setError('Could not capture screen. Please try again.');
      }
    } finally {
      setCapturing(false);
    }
  };

  return (
    <div className="poise-screen-capture">
      <button
        className="poise-btn poise-btn--secondary"
        onClick={handleClick}
        disabled={disabled || capturing}
      >
        {capturing ? 'Capturing…' : '📷 Capture Screen / Whiteboard'}
      </button>
      {error && <span className="poise-screen-capture__error">{error}</span>}
    </div>
  );
}
