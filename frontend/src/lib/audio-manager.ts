/**
 * Global audio singleton & unlocker for flawless autoplay in Tauri / WebView2.
 *
 * Browsers and Chromium WebView2 require a user interaction token before
 * audio can play. By capturing the first user gesture (e.g. clicking 'Start Interview'
 * or clicking anywhere on screen) and priming a persistent AudioContext + HTML5
 * Audio element, subsequent AI question audio can play automatically without
 * any user gesture restrictions.
 */

let sharedAudioContext: AudioContext | null = null;
let isAudioPrimed = false;

export function getSharedAudioContext(): AudioContext {
  if (typeof window === "undefined") {
    return {} as AudioContext;
  }
  const AudioCtxClass =
    window.AudioContext ||
    (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;

  if (!AudioCtxClass) {
    return {} as AudioContext;
  }

  if (!sharedAudioContext || sharedAudioContext.state === "closed") {
    try {
      sharedAudioContext = new AudioCtxClass();
    } catch {
      // Fallback
    }
  }
  return sharedAudioContext!;
}

/**
 * Prime and unlock audio subsystems during a user gesture.
 * Safe to call multiple times.
 */
export function unlockGlobalAudio(): void {
  if (typeof window === "undefined") return;

  try {
    const ctx = getSharedAudioContext();
    if (ctx && typeof ctx.resume === "function") {
      if (ctx.state === "suspended") {
        ctx.resume().catch(() => {});
      }
      // Play a 1-sample silent sound through Web Audio directly to destination
      try {
        const buffer = ctx.createBuffer(1, 1, 22050);
        const source = ctx.createBufferSource();
        source.buffer = buffer;
        source.connect(ctx.destination);
        source.start(0);
      } catch {
        // ok
      }
    }

    // Prime HTML5 AudioElement subsystem with a silent 0.05s WAV
    if (!isAudioPrimed) {
      try {
        const silentAudio = new Audio(
          "data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAAEA"
        );
        silentAudio.volume = 0.01;
        silentAudio.play().then(() => {
          isAudioPrimed = true;
        }).catch(() => {});
      } catch {
        // ok
      }
    }

    // Unpause Web Speech API if stuck
    if (window.speechSynthesis && window.speechSynthesis.paused) {
      try {
        window.speechSynthesis.resume();
      } catch {
        // ok
      }
    }
  } catch {
    // Ignore in non-standard test runners
  }
}

/**
 * Strips markdown, bullet points, headers, and code delimiters so the speech
 * synthesizer reads natural conversational dialogue without awkward symbols.
 */
export function cleanSpeechText(raw: string): string {
  if (!raw) return "";
  return raw
    .replace(/```[\s\S]*?```/g, "Code block omitted.") // Code blocks
    .replace(/\*\*(.*?)\*\*/g, "$1") // Bold **text**
    .replace(/\*(.*?)\*/g, "$1")     // Italic *text*
    .replace(/__(.*?)__/g, "$1")     // Bold __text__
    .replace(/_(.*?)_/g, "$1")       // Italic _text_
    .replace(/#+/g, "")              // Remove all header hashes
    .replace(/`([^`]+)`/g, "$1")     // Inline code `foo`
    .replace(/^\s*[-*+]\s+/gm, "")   // Bullet points
    .replace(/^\s*\d+\.\s+/gm, "")   // Numbered lists
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1") // Links [text](url)
    .replace(/\n{2,}/g, ". ")        // Paragraph breaks to pause
    .replace(/\n/g, " ")             // Line breaks to space
    .replace(/\s{2,}/g, " ")         // Collapse spaces
    .trim();
}

// Auto-register unlock listeners so any first click/key anywhere unlocks audio
if (typeof window !== "undefined") {
  const events = ["pointerdown", "click", "keydown", "touchstart"];
  const handleUserGesture = () => {
    unlockGlobalAudio();
  };
  events.forEach((ev) => {
    try {
      window.addEventListener(ev, handleUserGesture, { capture: true, passive: true });
    } catch {
      // ok
    }
  });
}
