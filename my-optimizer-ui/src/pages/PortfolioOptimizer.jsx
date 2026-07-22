import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { PORTFOLIO_PROFILES, OPTIMIZER_CONFIG } from "../config/profiles.js";
import SavePortfolioButton from "../components/save_button.jsx";

// FastAPI backend (uvicorn defaults to port 8000). Override with VITE_API_URL in .env.
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

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
    return(
    <div className='portfolioOptimizerPage'>
        <h1>Develop a Portfolio</h1>
        <MarketDropDown market={market} setMarket={setMarket} />
        <PortfolioStyleDropDown style={style} setStyle={setStyle} className="portfolio_drop_box"/>
        <OptimizerForm key={`${market}-${style}`} style={style} market={market} />
    </div>
    );
}

// Chooses which ETF universe the optimizer screens. Same shape as the style
// dropdown below so the two controls read as a pair.
function MarketDropDown({ market, setMarket }){
    return (
        <div>
            <label>Select ETF Universe</label>
            <p>Which market's ETFs to screen and optimize</p>
            <select value={market} onChange={(e) => setMarket(e.target.value)}>
                {MARKETS.map((m) => (
                    <option key={m.code} value={m.code}>{m.label}</option>
                ))}
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
function OptimizerForm({ style, market = "US" }){
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
    const [error, setError] = useState("");
    const [result, setResult] = useState(null);

    const marketLabel = MARKETS.find((m) => m.code === market)?.label ?? market;

    // The values that produced the result — saved with the portfolio and passed forward.
    const inputs = { profile: style, market, screening, score_weights: scoreWeights, optimizer_weights: slsqpWeights };

    async function runOptimization(){
        setLoading(true);
        setError("");
        setResult(null);
        try {
            const res = await fetch(`${API_URL}/optimize`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    profile: style,
                    market,                           // "US" | "CA" — which ETF universe
                    screening,                        // { aum_min, max_expense, max_duration }
                    score_weights: scoreWeights,      // selection weights
                    optimizer_weights: slsqpWeights,  // SLSQP objective weights
                    include_charts: true,
                }),
            });
            if (!res.ok) {
                // FastAPI returns errors as { detail: ... }
                const body = await res.json().catch(() => ({}));
                throw new Error(body.detail || `Request failed (${res.status})`);
            }
            setResult(await res.json());
        } catch (e) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    }

    return (
        <div className="optimizer-form">
            <SelectScreeningValues values={screening} setValues={setScreening} />
            <SelectScoreWeights weights={scoreWeights} setWeights={setScoreWeights} />
            <SelectOptimizerConfig weights={slsqpWeights} setWeights={setSlsqpWeights} />

            <button onClick={runOptimization} disabled={loading}>
                {loading
                    ? `Running ${marketLabel} optimization…`
                    : `Run ${marketLabel} Optimization`}
            </button>

            {error && <p className="error-message">{error}</p>}

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

function SelectScreeningValues({ values, setValues }){
    const update = (key, value) =>
        setValues((prev) => ({ ...prev, [key]: Number(value) }));
    return(
        <details className="screening-values">
            <summary>Screening Values</summary>
            <label>Minimum AUM ($)
                <input type="number" value={values.aum_min}
                    onChange={(e) => update("aum_min", e.target.value)} />
            </label>
            <label>Max Expense Ratio
                <input type="number" step="0.0001" value={values.max_expense}
                    onChange={(e) => update("max_expense", e.target.value)} />
            </label>
            <label>Max Duration (years)
                <input type="number" step="0.1" value={values.max_duration}
                    onChange={(e) => update("max_duration", e.target.value)} />
            </label>
        </details>
    );
}

function SelectScoreWeights({ weights, setWeights }){
    const update = (key, value) =>
        setWeights((prev) => ({ ...prev, [key]: Number(value) }));
    return(
        <details className="score-weights">
            <summary>Scoring Weights</summary>
            {Object.entries(weights).map(([key, value]) => (
                <label key={key}>{key}
                    <input type="number" step="0.01" value={value}
                        onChange={(e) => update(key, e.target.value)} />
                </label>
            ))}
        </details>
    );
}

function SelectOptimizerConfig({ weights, setWeights }){
    const update = (key, value) =>
        setWeights((prev) => ({ ...prev, [key]: Number(value) }));
    return(
        <details className="optimizer-config">
            <summary>Optimizer Weights</summary>
            {Object.entries(weights).map(([key, value]) => (
                <label key={key}>{key}
                    <input type="number" step="0.01" value={value}
                        onChange={(e) => update(key, e.target.value)} />
                </label>
            ))}
        </details>
    );
}

export default PortfolioOptimizerPage;
