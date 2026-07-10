import './App.css';
import {Routes, Route, Outlet} from "react-router-dom";
import Header from "./components/header.jsx";
import Sidebar from "./components/sidebar.jsx";
import HomePage from "./pages/Home.jsx";
import LoginPanel from "./pages/Login.jsx";
import GuestPage from "./pages/Guest.jsx";
import CreateAccountPanel from "./pages/CreateAccount.jsx";
import BuildPage from "./pages/build.jsx";
import InputEtfsPage from "./pages/inputEtfs.jsx";
import PortfolioOptimizerPage from "./pages/PortfolioOptimizer.jsx";
import ResultsPage from "./pages/results.jsx";
import GraphsPage from "./pages/graphs.jsx";
import SavedPortfoliosPage from "./pages/savedPortfolios.jsx";

// Layout renders the Header once, then the active page in its place (<Outlet />).
function Layout(){
  return (
    <>
      <Header />
      <Outlet />
    </>
  );
}

// AppLayout adds the Sidebar alongside the page. Nest the "app" pages (build,
// optimizer, results, …) inside it; auth pages stay on the header-only Layout.
function AppLayout(){
  return (
    <div className="app-shell">
      <Sidebar />
      <div className="app-content">
        <Outlet />
      </div>
    </div>
  );
}

//path is just the url ending you want the page to appear on
function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route element={<Layout />}>
        {/* Auth pages: header only, no sidebar */}
        <Route path="/Login" element={<LoginPanel />} />
        <Route path="/Guest" element={<GuestPage />} />
        <Route path="/CreateAccount" element={<CreateAccountPanel />} />

        {/* App pages: header + sidebar */}
        <Route element={<AppLayout />}>
          <Route path="/build" element={<BuildPage />} />
          <Route path="/inputEtfs" element={<InputEtfsPage />} />
          <Route path="/PortfolioOptimizer" element={<PortfolioOptimizerPage />} />
          <Route path="/results" element={<ResultsPage />} />
          <Route path="/graphs" element={<GraphsPage />} />
          <Route path="/saved" element={<SavedPortfoliosPage />} />
        </Route>
      </Route>
    </Routes>
  )
}

export default App
