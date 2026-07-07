import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { PORTFOLIO_PROFILES, OPTIMIZER_CONFIG } from "../config/profiles.js";

// FastAPI backend (uvicorn defaults to port 8000). Override with VITE_API_URL in .env.
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

function PortfolioOptimizerPage(){
    // Selected style is owned here; the form is remounted (key={style}) whenever it
    // changes, so all its inputs re-seed from that profile's defaults.
    const [style, setStyle] = useState("conservative");
    return(
    <div className='portfolioOptimizerPage'>
        <h1>Develop a Portfolio</h1>
        <PortfolioStyleDropDown style={style} setStyle={setStyle} className="portfolio_drop_box"/>
        <OptimizerForm key={style} style={style} />
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
function OptimizerForm({ style }){
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
                {loading ? "Running…" : "Run Optimization"}
            </button>

            {error && <p className="error-message">{error}</p>}

            {/* Appears once the run finishes; carries the result to the results page. */}
            {result && (
                <button
                    className="see-results"
                    onClick={() => navigate("/results", { state: { result } })}
                >
                    See Results
                </button>
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
