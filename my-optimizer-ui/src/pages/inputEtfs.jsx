import { useState } from "react";
import SavePortfolioButton from "../components/save_button.jsx";

const API_URL = "http://localhost:8000";

function InputEtfsPage() {
  // Each holding is { ticker, weight }. weight is a string so "" means "not entered".
  const [etfs, setEtfs] = useState([{ ticker: "", weight: "" }]);
  const [period, setPeriod] = useState("5y");
  const [rf, setRf] = useState(0.04);

  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function addTicker() {
    setEtfs([...etfs, { ticker: "", weight: "" }]);
  }

  function updateTicker(index, value) {
    const copy = [...etfs];
    copy[index] = { ...copy[index], ticker: value.toUpperCase() };
    setEtfs(copy);
  }

  function updateWeight(index, value) {
    const copy = [...etfs];
    copy[index] = { ...copy[index], weight: value };
    setEtfs(copy);
  }

  // Turn the rows into a { TICKER: weight } map summing to 1, or return an error string.
  function buildWeights() {
    const rows = etfs.filter((r) => r.ticker.trim() !== "");
    if (rows.length === 0) return { error: "Add at least one ticker." };

    // Reject the same ticker entered on more than one row.
    const seen = new Set();
    for (const r of rows) {
      const t = r.ticker.trim().toUpperCase();
      if (seen.has(t)) return { error: `Duplicate ticker "${t}". Enter each ETF once.` };
      seen.add(t);
    }

    let sumEntered = 0;
    let blanks = 0;
    for (const r of rows) {
      if (r.weight.trim() === "") {
        blanks++;
      } else {
        const w = Number(r.weight);
        if (Number.isNaN(w) || w < 0) {
          return { error: `Invalid weight "${r.weight}" for ${r.ticker}.` };
        }
        sumEntered += w;
      }
    }

    const weights = {};
    if (blanks > 0) {
      // Auto-generate: blank rows share whatever weight is left over, evenly.
      const remaining = 1 - sumEntered;
      if (remaining <= 0) {
        return {
          error:
            "Entered weights already total 1 or more, so blank tickers can't be " +
            "auto-filled. Lower them or enter a weight for every ticker.",
        };
      }
      const auto = remaining / blanks;
      for (const r of rows) {
        const t = r.ticker.trim().toUpperCase();
        weights[t] = r.weight.trim() === "" ? auto : Number(r.weight);
      }
    } else {
      // Every row has a weight — it must sum to 1.
      if (Math.abs(sumEntered - 1) > 0.001) {
        return {
          error: `Weights must sum to 1 (currently ${sumEntered.toFixed(3)}).`,
        };
      }
      for (const r of rows) {
        weights[r.ticker.trim().toUpperCase()] = Number(r.weight);
      }
    }
    return { weights };
  }

  async function evaluate() {
    setError("");
    setResult(null);

    const { weights, error: weightError } = buildWeights();
    if (weightError) {
      setError(weightError);
      return;
    }

    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/evaluate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          weights: weights,
          period: period,
          rf: rf,
        }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Request failed (${res.status})`);
      }

      const data = await res.json();
      setResult(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="input-your-portfolio">
      <h1>Use Existing ETFs</h1>

      <AddHoldings
        etfs={etfs}
        addTicker={addTicker}
        updateTicker={updateTicker}
        updateWeight={updateWeight}
      />

      <Settings
        period={period}
        setPeriod={setPeriod}
        rf={rf}
        setRf={setRf}
      />

      <button onClick={evaluate} disabled={loading}>
        {loading ? "Evaluating..." : "Evaluate Portfolio"}
      </button>

      {error && <p className="error">{error}</p>}
      {result && (
        <>
          <PortfolioResults result={result} />
          <SavePortfolioButton
            type="evaluate"
            inputs={{ etfs, period, rf }}
            results={result}
          />
        </>
      )}

    </div>
  );
}

function AddHoldings({ etfs, addTicker, updateTicker, updateWeight }) {
  return (
    <div>
      <p>
        <span className="step-number">1. </span>
        Add your Holdings
      </p>

      <p className="text-blurb">
        Enter a ticker and its weight for each ETF you hold. Weights must sum to 1;
        leave a weight blank to have it filled in evenly from the remainder.
      </p>

      {etfs.map((row, index) => (
        <div key={index} className="holding-row">
          <input
            value={row.ticker}
            onChange={(e) => updateTicker(index, e.target.value)}
            placeholder="VOO"
          />
          <input
            type="number"
            step="0.01"
            min="0"
            value={row.weight}
            onChange={(e) => updateWeight(index, e.target.value)}
            placeholder="auto"
          />
        </div>
      ))}

      <button className="add-ticker-button" onClick={addTicker}>
        Add Ticker
      </button>
    </div>
  );
}

function Settings({ period, setPeriod, rf, setRf }) {
  return (
    <div>
      <p>
        <span className="step-number">2. </span>
        Settings <span className="option">optional</span>
      </p>

      <div className="history-window">
        <p>History Window</p>

        <select value={period} onChange={(e) => setPeriod(e.target.value)}>
          <option value="1y">1y</option>
          <option value="2y">2y</option>
          <option value="3y">3y</option>
          <option value="4y">4y</option>
          <option value="5y">5y</option>
        </select>
      </div>

      <div className="risk-free-rate">
        <p>Risk Free Rate</p>

        <input
          type="number"
          step="0.01"
          value={rf}
          onChange={(e) => setRf(Number(e.target.value))}
        />
      </div>
    </div>
  );
}

function PortfolioResults({result}){
    return(
    <div>
        <WeightsTable result={result} />
        <PortfolioMetrics result={result} />
        <Charts result={result} />
    </div>
    );
}

function WeightsTable({result}){
    const weights = result.weights;
    return(
        <div>
            <h2>ETF Weights</h2>
        <table>
            <thead>
            <tr>
                <th>ETF</th>
                <th>Weight</th>
            </tr>
            </thead>
            <tbody>
                {weights.map((row) => (
                    <tr key={row.ETF}>
                        <td>{row.ETF}</td>
                        <td>{row.Weight}</td>
                    </tr>
                ))}
            </tbody>
        </table>
        </div>
    );
}

function PortfolioMetrics({result}){
    const metrics = result.metrics;
    return(
        <div>
            <h2>Portfolio Metrics</h2>
            <table>
                <thead>
                    <tr>
                        <th>Metric</th>
                        <th>Value</th>
                    </tr>
                </thead>
                <tbody>
                    {metrics.map((row) => (
                        <tr key={row.index}>
                        <td>{row.index}</td>
                        <td>{row.Value}</td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>)
}

function Charts({result}){
    const [activeTab, setActiveTab] = useState("Monte Carlo");
    return(
        <div>
            <div className="tabs">
                <button className={activeTab == "Monte Carlo" ? "tab active-tab" : "tab"}
                onClick={() =>setActiveTab('Monte Carlo')}>
                    Monte Carlo
                </button>

                <button className={activeTab == "Monte Carlo Distribution" ? "tab active-tab" : "tab"}
                onClick={() =>setActiveTab('Monte Carlo Distribution')}>
                    Monte Carlo Distribution
                </button>

                <button className={activeTab == "Backtest" ? "tab active-tab" : "tab"}
                onClick={() =>setActiveTab('Backtest')}>
                    Backtest
                </button>

                <button className={activeTab == "Stress Test" ? "tab active-tab" : "tab"}
                onClick={() =>setActiveTab('Stress Test')}>
                    Stress Test
                </button>
            </div>
            {activeTab == "Monte Carlo" && <MonteCarlo result={result} />}
            {activeTab == "Monte Carlo Distribution" && <MonteCarloDist result={result} />}
            {activeTab == "Backtest" && <Backtest result={result} />}
            {activeTab == "Stress Test" && <StressTest result={result} />}
        </div>
    )
}

function MonteCarlo({ result }){
    const chart = result.charts.monte_carlo;
    if (!chart) return <p>No chart.</p>;
    return (
        <figure className="charts">
            <img alt="Monte Carlo" src={`data:image/png;base64,${chart}`}
                style={{ maxWidth: "100%" }} />
        </figure>
    );
}

function MonteCarloDist({ result }){
    const chart = result.charts.monte_carlo_dist;
    if (!chart) return <p>No chart.</p>;
    return (
        <figure className="charts">
            <img alt="Monte Carlo Distribution" src={`data:image/png;base64,${chart}`}
                style={{ maxWidth: "100%" }} />
        </figure>
    );
}

function Backtest({ result }){
    const chart = result.charts.backtest;
    if (!chart) return <p>No chart.</p>;
    return (
        <figure className="charts">
            <img alt="Backtest" src={`data:image/png;base64,${chart}`}
                style={{ maxWidth: "100%" }} />
        </figure>
    );
}

function StressTest({ result }){
    const chart = result.charts.rate_hike;
    if (!chart) return <p>No chart.</p>;
    return (
        <figure className="charts">
            <img alt="Stress Test" src={`data:image/png;base64,${chart}`}
                style={{ maxWidth: "100%" }} />
        </figure>
    );
}

export default InputEtfsPage;
