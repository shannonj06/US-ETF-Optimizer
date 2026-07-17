// Sidebar.jsx
import { NavLink } from "react-router-dom";

// NavLink (not Link) so the current page gets the "active" class automatically.
function Sidebar() {
  const linkClass = ({ isActive }) => (isActive ? "active" : undefined);
  return (
    <aside className="sidebar">
      <NavLink to="/build" className={linkClass}>Build</NavLink>
      <NavLink to="/inputEtfs" className={linkClass}>Use ETFs</NavLink>
      <NavLink to="/PortfolioOptimizer" className={linkClass}>Optimizer</NavLink>
      <NavLink to="/saved" className={linkClass}>Saved Portfolios</NavLink>
    </aside>
  );
}

export default Sidebar;