import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { PORTFOLIO_PROFILES, OPTIMIZER_CONFIG } from "../config/profiles.js";
import SavePortfolioButton from "../components/save_button.jsx";
import {
  ApiErrorMessage,
  GuestAllowanceBanner,
  GuestUpgradePrompt,
} from "../components/guestNotice.jsx";
import { api } from "../config/api.js";
import { useGuestAccess } from "../config/useGuestAccess.js";
import { GUEST_ALLOWED_MARKETS } from "../config/guestPolicy.js";

// Selectable ETF universes. Mirrors the backend's /markets endpoint; both share
// the same schema, so only the ticker universe changes.
const MARKETS = [
    { code: "US", label: "United States" },
    { code: "CA", label: "Canada" },
];

function PortfolioOptimizerPage(){
    // Selected style/market are owned here; the form is remounted (key) whenever
    // either changes, so inputs re-seed and stale results are cleared.
    const [style, setStyle] = useState("conservative");
    const [market, setMarket] = useState("US");
    const guest = useGuestAccess();

    return(
    <div className='portfolioOptimizerPage'>
        <h1>Develop a Portfolio</h1>

        <GuestAllowanceBanner
            isGuest={guest.isGuest}
            left={guest.left}
            action="optimize"
        />

        <MarketDropDown market={market} setMarket={setMarket} isGuest={guest.isGuest} />
        <PortfolioStyleDropDown style={style} setStyle={setStyle} className="portfolio_drop_box"/>
        <OptimizerForm
            key={`${market}-${style}`}
            style={style}
            market={market}
            guest={guest}
        />
    </div>
    );
}

// Chooses which ETF universe the optimizer screens. Same shape as the style
// dropdown below so the two controls read as a pair.
function MarketDropDown({ market, setMarket, isGuest }){
    return (
        <div>
            <label>Select ETF Universe</label>
            <p>Which market's ETFs to screen and optimize</p>
            <select value={market} onChange={(e) => setMarket(e.target.value)}>
                {MARKETS.map((m) => {
                    // The guest preview covers the US universe only; the option
                    // stays visible so the feature is discoverable.
                    const locked = isGuest && !GUEST_ALLOWED_MARKETS.includes(m.code);
                    return (
                        <option key={m.code} value={m.code} disabled={locked}>
                            {m.label}{locked ? " — account required" : ""}
                        </option>
                    );
                })}
            </select>
        </div>
    );
}

function PortfolioStyleDropDown({ style, setStyle }){
    return (
        <div>
            <label>Select Portfolio Style</label>
            <p>Sets the overall risk/return posture</p>
            <select value={style} onChange={(e) => setStyle(e.target.value)}>
                <option value="conservative">Conservative</option>
                <option value="enhanced">Enhanced</option>
                <option value="strategic">Strategic</option>
            </select>
        </div>
    );
}

// Holds every editable value for the selected style, plus the API call and results.
function OptimizerForm({ style, market = "US", guest }){
    const navigate = useNavigate();
    const profile = PORTFOLIO_PROFILES[style];
    const cfg = OPTIMIZER_CONFIG[style];

    // Form state, seeded from the profile / optimizer config.
    const [screening, setScreening] = useState({
        aum_min:      profile.aum_min,
        max_expense:  profile.max_expense,
        max_duration: profile.max_duration,
    });
    const [scoreWeights, setScoreWeights] = useState(profile.score_weights);
    const [slsqpWeights, setSlsqpWeights] = useState(cfg.slsqp_weights);

    // Request state.
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [result, setResult] = useState(null);

    const marketLabel = MARKETS.find((m) => m.code === market)?.label ?? market;

    // Guests run a style at its recommended settings. The server substitutes the
    // profile defaults for whatever is sent, so the inputs are shown read-only
    // rather than pretending an edit would take effect.
    const inputsLocked = guest.isGuest;
    const outOfRuns = guest.isGuest && !guest.canUse("optimize");

    // The values that produced the result — saved with the portfolio and passed forward.
    const inputs = { profile: style, market, screening, score_weights: scoreWeights, optimizer_weights: slsqpWeights };

    async function runOptimization(){
        setLoading(true);
        setError(null);
        setResult(null);
        try {
            setResult(await api.optimize({
                profile: style,
                market,                           // "US" | "CA" — which ETF universe
                screening,                        // { aum_min, max_expense, max_duration }
                score_weights: scoreWeights,      // selection weights
                optimizer_weights: slsqpWeights,  // SLSQP objective weights
                include_charts: true,
            }));
        } catch (e) {
            setError(e);
        } finally {
            setLoading(false);
            // A run consumes a guest's allowance, and a refused one may have
            // changed nothing — re-read rather than assuming either way.
            guest.refresh();
        }
    }

    return (
        <div className="optimizer-form">
            <SelectScreeningValues
                values={screening}
                setValues={setScreening}
                locked={inputsLocked}
            />
            <SelectScoreWeights
                weights={scoreWeights}
                setWeights={setScoreWeights}
                locked={inputsLocked}
            />
            <SelectOptimizerConfig
                weights={slsqpWeights}
                setWeights={setSlsqpWeights}
                locked={inputsLocked}
            />

            <button onClick={runOptimization} disabled={loading || outOfRuns}>
                {loading
                    ? `Running ${marketLabel} optimization…`
                    : `Run ${marketLabel} Optimization`}
            </button>

            <ApiErrorMessage error={error} />
            <GuestUpgradePrompt
                isGuest={guest.isGuest}
                left={guest.left}
                action="optimize"
            />

            {/* Appears once the run finishes; carries result + inputs to the results page. */}
            {result && (
                <>
                    {/* Echoed by the backend, so it reflects the universe that actually ran. */}
                    <p className="run-summary">
                        Optimized the{" "}
                        <strong>
                            {MARKETS.find((m) => m.code === (result.market ?? market))?.label ?? market}
                        </strong>{" "}
                        ETF universe.
                    </p>
                    <button
                        className="see-results"
                        onClick={() => navigate("/results", { state: { result, inputs } })}
                    >
                        See Results
                    </button>
                    <SavePortfolioButton type="optimize" inputs={inputs} results={result} />
                </>
            )}
        </div>
    );
}

// Explains why a section is read-only, once per section.
function LockedNote(){
    return (
        <p className="locked-note">
            Guest preview: these use the selected style&rsquo;s recommended values.
            Create a free account to tune them.
        </p>
    );
}

function SelectScreeningValues({ values, setValues, locked }){
    const update = (key, value) =>
        setValues((prev) => ({ ...prev, [key]: Number(value) }));
    return(
        <details className="screening-values">
            <summary>Screening Values{locked ? " (locked)" : ""}</summary>
            {locked && <LockedNote />}
            <label>Minimum AUM ($)
                <input type="number" value={values.aum_min} disabled={locked}
                    onChange={(e) => update("aum_min", e.target.value)} />
            </label>
            <label>Max Expense Ratio
                <input type="number" step="0.0001" value={values.max_expense} disabled={locked}
                    onChange={(e) => update("max_expense", e.target.value)} />
            </label>
            <label>Max Duration (years)
                <input type="number" step="0.1" value={values.max_duration} disabled={locked}
                    onChange={(e) => update("max_duration", e.target.value)} />
            </label>
        </details>
    );
}

function SelectScoreWeights({ weights, setWeights, locked }){
    const update = (key, value) =>
        setWeights((prev) => ({ ...prev, [key]: Number(value) }));
    return(
        <details className="score-weights">
            <summary>Scoring Weights{locked ? " (locked)" : ""}</summary>
            {locked && <LockedNote />}
            {Object.entries(weights).map(([key, value]) => (
                <label key={key}>{key}
                    <input type="number" step="0.01" value={value} disabled={locked}
                        onChange={(e) => update(key, e.target.value)} />
                </label>
            ))}
        </details>
    );
}

function SelectOptimizerConfig({ weights, setWeights, locked }){
    const update = (key, value) =>
        setWeights((prev) => ({ ...prev, [key]: Number(value) }));
    return(
        <details className="optimizer-config">
            <summary>Optimizer Weights{locked ? " (locked)" : ""}</summary>
            {locked && <LockedNote />}
            {Object.entries(weights).map(([key, value]) => (
                <label key={key}>{key}
                    <input type="number" step="0.01" value={value} disabled={locked}
                        onChange={(e) => update(key, e.target.value)} />
                </label>
            ))}
        </details>
    );
}

export default PortfolioOptimizerPage;
