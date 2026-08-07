// Sidebar.jsx — primary navigation.
// NavLink (not Link) so the active route is highlighted; routing behavior is
// unchanged. Icons are inline stroke SVGs (Lucide-style) for crisp, dependency-
// free iconography.
import { NavLink } from "react-router-dom";

const NAV = [
  { to: "/build", label: "Build", icon: IconLayers },
  { to: "/inputEtfs", label: "Use ETFs", icon: IconList },
  { to: "/PortfolioOptimizer", label: "Optimizer", icon: IconSliders },
  { to: "/cash-analysis", label: "Cash Analysis", icon: IconTrend },
  { to: "/saved", label: "Saved Portfolios", icon: IconBookmark },
];

function Sidebar() {
  return (
    <aside className="sidebar">
      <span className="sidebar-eyebrow">Workspace</span>
      <nav className="sidebar-nav">
        {NAV.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) => `nav-item${isActive ? " active" : ""}`}
          >
            <span className="nav-icon">
              <Icon />
            </span>
            <span className="nav-label">{label}</span>
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}

/* ---- icons (24×24, 1.6 stroke, inherit currentColor) ---- */
function svgProps() {
  return {
    width: 20,
    height: 20,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.7,
    strokeLinecap: "round",
    strokeLinejoin: "round",
  };
}
function IconLayers() {
  return (
    <svg {...svgProps()}>
      <path d="M12 3 3 8l9 5 9-5-9-5Z" />
      <path d="m3 13 9 5 9-5" />
      <path d="m3 18 9 5 9-5" opacity="0.55" />
    </svg>
  );
}
function IconList() {
  return (
    <svg {...svgProps()}>
      <path d="M8 6h13M8 12h13M8 18h13" />
      <circle cx="3.5" cy="6" r="1.2" />
      <circle cx="3.5" cy="12" r="1.2" />
      <circle cx="3.5" cy="18" r="1.2" />
    </svg>
  );
}
function IconSliders() {
  return (
    <svg {...svgProps()}>
      <path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3" />
      <path d="M1 14h6M9 8h6M17 16h6" />
    </svg>
  );
}
function IconTrend() {
  return (
    <svg {...svgProps()}>
      <path d="m3 17 6-6 4 4 8-8" />
      <path d="M17 7h4v4" />
    </svg>
  );
}
function IconBookmark() {
  return (
    <svg {...svgProps()}>
      <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2Z" />
    </svg>
  );
}

export default Sidebar;
