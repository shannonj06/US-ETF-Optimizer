import './App.css';
import {Routes, Route, Outlet} from "react-router-dom";
import Header from "./components/header.jsx";
import HomePage from "./pages/Home.jsx";
import LoginPanel from "./pages/Login.jsx";
import GuestPage from "./pages/Guest.jsx";
import CreateAccountPanel from "./pages/CreateAccount.jsx";
import BuildPage from "./pages/build.jsx";
import InputEtfsPage from "./pages/inputEtfs.jsx";
import PortfolioOptimizerPage from "./pages/PortfolioOptimizer.jsx";
import ResultsPage from "./pages/results.jsx";

// Layout renders the Header once, then the active page in its place (<Outlet />).
function Layout(){
  return (
    <>
      <Header />
      <Outlet />
    </>
  );
}

//path is just the url ending you want the page to appear on
function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route element={<Layout />}>
        <Route path="/Login" element={<LoginPanel />} />
        <Route path="/Guest" element={<GuestPage />} />
        <Route path="/CreateAccount" element={<CreateAccountPanel />} />
        <Route path="/build" element={<BuildPage />} />
        <Route path="/inputEtfs" element={<InputEtfsPage />} />
        <Route path="/PortfolioOptimizer" element={<PortfolioOptimizerPage />} />
        <Route path="/results" element={<ResultsPage />} />
      </Route>
    </Routes>
  )
}

export default App
