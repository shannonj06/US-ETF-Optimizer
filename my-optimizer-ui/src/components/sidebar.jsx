// Sidebar.jsx
import { Link } from "react-router-dom";

function Sidebar() {
  return (
    <aside className="sidebar">
      <Link to="/build">Build</Link>
      <Link to="/inputEtfs">Use ETFs</Link>
      <Link to="/PortfolioOptimizer">Optimizer</Link>
      <Link to="/saved">Saved Portfolios</Link>
    </aside>
  );
}

export default Sidebar;