import { motion } from "framer-motion";
import { useState } from "react";
import { NavLink } from "react-router-dom";

interface NavItem {
  to: string;
  label: string;
  icon: string;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Dashboard", icon: "\u2302" }, // house
  { to: "/interview", label: "Interview Mode", icon: "\u{1F399}" }, // mic
  { to: "/ielts", label: "IELTS Speaking", icon: "\u{1F5E3}" }, // speech balloon
  { to: "/history", label: "Session History", icon: "\u{1F4CA}" }, // chart
  { to: "/settings", label: "Settings", icon: "\u2699" }, // gear
];

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <motion.nav
      className="sidebar"
      animate={{ width: collapsed ? "var(--sidebar-width-collapsed)" : "var(--sidebar-width)" }}
      transition={{ duration: 0.2, ease: [0.4, 0, 0.2, 1] }}
      aria-label="Primary"
    >
      <div className="sidebar__brand">
        <span className="sidebar__brand-mark">P</span>
        {!collapsed && <span className="sidebar__brand-name">Poise</span>}
      </div>

      <ul className="sidebar__list">
        {NAV_ITEMS.map((item) => (
          <li key={item.to}>
            <NavLink
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                `sidebar__link${isActive ? " sidebar__link--active" : ""}`
              }
            >
              <span className="sidebar__icon" aria-hidden="true">
                {item.icon}
              </span>
              {!collapsed && <span>{item.label}</span>}
            </NavLink>
          </li>
        ))}
      </ul>

      <button
        type="button"
        className="sidebar__collapse-toggle"
        onClick={() => setCollapsed((c) => !c)}
        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        {collapsed ? "\u00BB" : "\u00AB"}
      </button>
    </motion.nav>
  );
}
