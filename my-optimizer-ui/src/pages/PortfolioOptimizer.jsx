import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { PORTFOLIO_PROFILES, OPTIMIZER_CONFIG } from "../config/profiles.js";
import { SCREENING_LABELS, SCORE_WEIGHT_LABELS, OPTIMIZER_WEIGHT_LABELS } from "../config/labels.js";
import { formatCurrency } from "../config/format.js";
import SavePortfolioButton from "../components/save_button.jsx";

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
    const [elapsed, setElapsed] = useState(0);
    const [error, setError] = useState("");
    const [result, setResult] = useState(null);

    // The values that produced the result — saved with the portfolio and passed forward.
    const inputs = { profile: style, screening, score_weights: scoreWeights, optimizer_weights: slsqpWeights };

    async function runOptimization(){
        setLoading(true);
        setError("");
        setResult(null);
        setElapsed(0);
        // The backend pulls live price history per ETF one at a time, so a full run
        // routinely takes a couple of minutes — this ticks so it doesn't look hung.
        const timer = setInterval(() => setElapsed((s) => s + 1), 1000);
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
            clearInterval(timer);
            setLoading(false);
        }
    }

    return (
        <div className="optimizer-form">
            <SelectScreeningValues values={screening} setValues={setScreening} />
            <SelectScoreWeights weights={scoreWeights} setWeights={setScoreWeights} />
            <SelectOptimizerConfig weights={slsqpWeights} setWeights={setSlsqpWeights} />

            <button onClick={runOptimization} disabled={loading}>
                {loading ? `Running… (${elapsed}s)` : "Run Optimization"}
            </button>
            {loading && (
                <p className="section-hint">
                    Pulling live price history for every screened ETF and running all three optimizers —
                    this typically takes 2–4 minutes. Please keep this tab open.
                </p>
            )}

            {error && <p className="error-message">{error}</p>}

            {/* Appears once the run finishes; carries result + inputs to the results page. */}
            {result && (
                <>
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

// Renders one config field per its unit: percent fields are edited/displayed as
// whole percentages (state stays a 0-1 fraction underneath), currency fields keep
// a raw dollar input with a formatted "$200M"-style preview, everything else is a
// plain number. Shared by the three config sections below.
function ConfigField({ fieldKey, value, meta, onChange }){
    if (meta.unit === "percent") {
        const display = Number((value * 100).toFixed(4));
        return (
            <label title={meta.hint}>
                {meta.label}
                <div className="unit-input">
                    <input type="number" step="0.01" value={display}
                        onChange={(e) => onChange(fieldKey, Number(e.target.value) / 100)} />
                    <span className="unit-suffix">%</span>
                </div>
                <span className="field-hint">{meta.hint}</span>
            </label>
        );
    }
    if (meta.unit === "currency") {
        return (
            <label title={meta.hint}>
                {meta.label}
                <div className="unit-input">
                    <input type="number" step="1000000" value={value}
                        onChange={(e) => onChange(fieldKey, Number(e.target.value))} />
                    <span className="unit-suffix">{formatCurrency(value)}</span>
                </div>
                <span className="field-hint">{meta.hint}</span>
            </label>
        );
    }
    return (
        <label title={meta.hint}>
            {meta.label}
            <div className="unit-input">
                <input type="number" step="0.1" value={value}
                    onChange={(e) => onChange(fieldKey, Number(e.target.value))} />
                {meta.unit === "years" && <span className="unit-suffix">yrs</span>}
            </div>
            <span className="field-hint">{meta.hint}</span>
        </label>
    );
}

function SelectScreeningValues({ values, setValues }){
    const update = (key, value) => setValues((prev) => ({ ...prev, [key]: value }));
    return(
        <details className="screening-values">
            <summary>Screening Values</summary>
            <p className="section-hint">Filters applied before any ETF is scored — funds outside these limits are excluded entirely.</p>
            {Object.entries(values).map(([key, value]) => (
                <ConfigField key={key} fieldKey={key} value={value}
                    meta={SCREENING_LABELS[key] ?? { label: key, hint: "" }} onChange={update} />
            ))}
        </details>
    );
}

function SelectScoreWeights({ weights, setWeights }){
    const update = (key, value) => setWeights((prev) => ({ ...prev, [key]: value }));
    return(
        <details className="score-weights">
            <summary>Scoring Weights</summary>
            <p className="section-hint">Controls which ETFs get picked in the first place — higher weight means that factor matters more when ranking candidates.</p>
            {Object.entries(weights).map(([key, value]) => (
                <ConfigField key={key} fieldKey={key} value={value}
                    meta={SCORE_WEIGHT_LABELS[key] ?? { label: key, hint: "" }} onChange={update} />
            ))}
        </details>
    );
}

function SelectOptimizerConfig({ weights, setWeights }){
    const update = (key, value) => setWeights((prev) => ({ ...prev, [key]: value }));
    return(
        <details className="optimizer-config">
            <summary>Optimizer Weights</summary>
            <p className="section-hint">Controls how the final portfolio allocation is built from the selected ETFs.</p>
            {Object.entries(weights).map(([key, value]) => (
                <ConfigField key={key} fieldKey={key} value={value}
                    meta={OPTIMIZER_WEIGHT_LABELS[key] ?? { label: key, hint: "" }} onChange={update} />
            ))}
        </details>
    );
}

export default PortfolioOptimizerPage;
