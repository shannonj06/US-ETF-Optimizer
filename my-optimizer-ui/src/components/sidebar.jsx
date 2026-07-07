// Sidebar.jsx
import { Link } from "react-router-dom";

function Sidebar() {
  return (
    <aside className="sidebar">
      <h2>InvestMint</h2>
      <Link to="/build">Build</Link>
      <Link to="/input-etfs">Use ETFs</Link>
      <Link to="/portfolio-optimizer">Optimizer</Link>
    </aside>
  );
}

export default Sidebar;