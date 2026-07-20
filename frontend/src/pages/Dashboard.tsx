import { motion } from "framer-motion";
import { Link } from "react-router-dom";

export function Dashboard() {
  return (
    <div className="page dashboard">
      <motion.div
        className="dashboard__welcome"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.3 }}
      >
        <h1>Poise</h1>
        <p className="dashboard__tagline">Practice until you don't have to think about it.</p>
      </motion.div>

      <div className="dashboard__cta-grid">
        <Link to="/interview" className="dashboard__cta-card dashboard__cta-card--interview">
          <h2>Start Interview</h2>
          <p>Run a voice-driven mock interview, scored as you go.</p>
        </Link>
        <Link to="/ielts" className="dashboard__cta-card dashboard__cta-card--ielts">
          <h2>Practice IELTS Speaking</h2>
          <p>Part 1, 2, and 3 drills with band-score feedback.</p>
        </Link>
      </div>

      <section className="dashboard__recent">
        <h3>Recent sessions</h3>
        <div className="dashboard__empty-state">
          <p>No sessions yet. Your first one will show up here.</p>
        </div>
      </section>
    </div>
  );
}
