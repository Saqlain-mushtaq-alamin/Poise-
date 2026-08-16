import { AnimatePresence, motion } from "framer-motion";
import { type ReactNode, useState } from "react";
import { useLocation } from "react-router-dom";

import { useConfidenceTracking } from "../hooks/useConfidenceTracking";
import type { PoiseAPI } from "../lib/api";
import type { SidecarStatus } from "../lib/types";
import { CoachingToast } from "./vision/CoachingToast";
import { ConfidenceOverlay } from "./vision/ConfidenceOverlay";
import { Sidebar } from "./Sidebar";
import { StatusBar } from "./StatusBar";

interface ShellProps {
  children: ReactNode;
  sidecarStatus: SidecarStatus | null;
  api: PoiseAPI | null;
}

/** Top-level layout every page renders inside. Owns the sidebar, the
 * page-transition animation, the status bar, and the Phase 5 webcam
 * confidence overlay — mounted here (rather than per-page) so it can
 * render above any page without each page needing to know about it. Off
 * by default: starting it requests camera access, which shouldn't happen
 * without the person explicitly asking for it. */
export function Shell({ children, sidecarStatus, api }: ShellProps) {
  const location = useLocation();
  const [webcamEnabled, setWebcamEnabled] = useState(false);
  const [overlayVisible, setOverlayVisible] = useState(true);

  const confidence = useConfidenceTracking({
    api,
    sessionId: null, // wired up to the active interview session once Phase 4 + 5 are integrated
    coachingEnabled: true,
  });

  function handleToggleWebcam() {
    if (webcamEnabled) {
      confidence.stop();
      setWebcamEnabled(false);
    } else {
      setWebcamEnabled(true);
      void confidence.start();
    }
  }

  return (
    <div className="shell">
      <Sidebar />

      <div className="shell__main">
        <div className="shell__content">
          <AnimatePresence mode="wait">
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.2, ease: [0.4, 0, 0.2, 1] }}
              className="shell__page"
            >
              {children}
            </motion.div>
          </AnimatePresence>
        </div>

        <div id="webcam-overlay-slot" className="shell__webcam-slot">
          <button type="button" className="shell__webcam-toggle" onClick={handleToggleWebcam}>
            {webcamEnabled ? "Turn off confidence tracking" : "Turn on confidence tracking"}
          </button>

          {webcamEnabled && confidence.latestResult && (
            <ConfidenceOverlay
              score={confidence.latestResult.compositeScore}
              eyeContactRatio={confidence.latestResult.eyeContact.contact_ratio_30s}
              expression={confidence.latestResult.expression}
              gestureAssessment={confidence.latestResult.gesture?.assessment}
              visible={overlayVisible}
              onToggleVisible={() => setOverlayVisible((v) => !v)}
            />
          )}

          {webcamEnabled && (
            <CoachingToast tip={confidence.coachingTip} onDismiss={confidence.dismissTip} />
          )}
        </div>

        <StatusBar sidecarStatus={sidecarStatus} api={api} />
      </div>
    </div>
  );
}
