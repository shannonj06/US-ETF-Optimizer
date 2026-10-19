import { Link, useNavigate } from "react-router-dom";
import { GuestLimitsList } from "../components/guestNotice.jsx";
import { GUEST_MAX_HISTORY_YEARS } from "../config/guestPolicy.js";

// The guest landing page states the allowance up front. Someone who knows the
// preview is one optimization spends it on a portfolio they actually want,
// rather than discovering the limit after a throwaway run.
function GuestPage(){
    const navigate = useNavigate();
    return(
    <div className='guestPage'>
        <h1>Continue as Guest</h1>
        <p>
            Try the optimizer without an account. The preview runs the full
            pipeline on real market data — it is just metered.
        </p>

        <h2>What you get</h2>
        <GuestLimitsList />

        <h2>What needs an account</h2>
        <ul className="guest-limits guest-limits-locked">
            <li>Tuning the screening thresholds, scoring and optimizer weights</li>
            <li>The Canadian ETF universe</li>
            <li>Saving portfolios and exporting them</li>
            <li>History beyond {GUEST_MAX_HISTORY_YEARS} years</li>
        </ul>

        <p className="guest-fineprint">
            The guest allowance is counted per network, so opening a private
            window does not reset it. Creating an account is free.
        </p>

        <div className="guest-upgrade-actions">
            <button onClick={() => navigate("/build")}>Get Started</button>
            <Link className="guest-cta" to="/CreateAccount">Create a free account</Link>
        </div>
    </div>
    );
}

export default GuestPage;
