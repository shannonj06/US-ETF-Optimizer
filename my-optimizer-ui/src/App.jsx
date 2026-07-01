import './App.css';
//import {useState, useEffect} from "react";
import {Routes, Route} from "react-router-dom";
import HomePage from "./pages/Home.jsx";
// import LoginPage from "./pages/Login.jsx";
// import GuestPage from "./pages/Guest.jsx";

//path is just the url ending you want the page to appear on
function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />}/>
      {/* <Route path ="/Login" element={<LoginPage />}/> */}
      {/* <Route path ="/Guest" element={<GuestPage />} /> */}
    </Routes>
    
  )
}

export default App