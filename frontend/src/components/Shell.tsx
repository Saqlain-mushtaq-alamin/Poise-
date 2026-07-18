import { AnimatePresence, motion } from "framer-motion";
import { type ReactNode } from "react";
import { useLocation } from "react-router-dom";

import type { SidecarStatus } from "../lib/types";
import { Sidebar } from "./Sidebar";
import { StatusBar } from "./StatusBar";

interface ShellProps {
  children: ReactNode;
  sidecarStatus: SidecarStatus | null;
}

/** Top-level layout every page renders inside. Owns the sidebar, the
 * page-transition animation, the status bar, and a reserved slot below the
 * content area for Phase 5's webcam overlay. */
export function Shell({ children, sidecarStatus }: ShellProps) {
  const location = useLocation();

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

        {/* Phase 5 (Webcam Analysis) mounts its always-on confidence overlay
            here so it can render above any page without each page needing
            to know about it. Empty until then. */}
        <div id="webcam-overlay-slot" className="shell__webcam-slot" />

        <StatusBar sidecarStatus={sidecarStatus} />
      </div>
    </div>
  );
}
