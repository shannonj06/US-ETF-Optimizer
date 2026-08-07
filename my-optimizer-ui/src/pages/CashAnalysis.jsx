import { useEffect, useMemo, useState } from "react";
import { useLocation } from "react-router-dom";
import { listPortfolios } from "../config/portfolios";
import { isSupabaseConfigured } from "../config/supabaseClient";
import {
  getCurrentInputPortfolio,
  getLatestOptimizedPortfolio,
  holdingsFromSavedPortfolio,
  loadAnalysisState,
  saveAnalysisState,
} from "../config/cashAnalysisState";
import { BarChart, ChartLegend, LineChart } from "../components/charts.jsx";
import {
  fmtCurrency,
  fmtPct,
  fmtSignedCurrency,
  seriesColor,
} from "../components/chartUtils.js";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const SOURCES = [
  { id: "input", label: "Current Input Portfolio" },
  { id: "optimized", label: "Latest Optimized Portfolio" },
  { id: "saved", label: "Saved Portfolio" },
  { id: "manual", label: "Manual Portfolio" },
];

// today's date as YYYY-MM-DD for date-input max attributes
const TODAY = new Date().toISOString().slice(0, 10);

const emptyRow = () => ({ ticker: "", weight: "" });

const DEFAULT_STATE = {
  source: "manual",
  rows: [emptyRow()],
  initialCash: "10000",
  startDate: "2022-01-03",
  endDate: "",
  allowFractional: true,
  dividendTreatment: "cash",
  frequency: "monthly",
};

// Initial form state: a hand-off from another page wins, then persisted session
// state, then defaults. Computed once (lazy useState init) so there's no
// state-sync effect on mount.
function computeInitialState(navState) {
  const handoff = navState?.holdings; // canonical percent holdings
  const persisted = loadAnalysisState();
  if (handoff && handoff.length) {
    return {
      ...DEFAULT_STATE,
      ...(persisted || {}),
      source: navState.source || "manual",
      rows: handoff.map((h) => ({ ticker: h.ticker, weight: String(h.weight) })),
    };
  }
  if (persisted) {
    return {
      ...DEFAULT_STATE,
      ...persisted,
      rows: persisted.rows?.length ? persisted.rows : [emptyRow()],
    };
  }
  return DEFAULT_STATE;
}

// ── tiny helpers ─────────────────────────────────────────────────────────────
function Info({ text }) {
  return (
    <span className="ca-info" tabIndex={0} title={text} aria-label={text}>
      ⓘ
    </span>
  );
}

function signClass(v) {
  if (v > 0) return "ca-pos";
  if (v < 0) return "ca-neg";
  return "ca-zero";
}

// value with sign + arrow + color (never color alone)
function Delta({ value, pct = false }) {
  const cls = signClass(value);
  const arrow = value > 0 ? "▲" : value < 0 ? "▼" : "—";
  return (
    <span className={cls}>
      <span aria-hidden="true" className="ca-arrow">
        {arrow}
      </span>{" "}
      {pct ? fmtPct(value) : fmtSignedCurrency(value)}
    </span>
  );
}

export default function CashAnalysisPage() {
  const location = useLocation();

  // ── form state (seeded once from hand-off / persisted session state) ────────
  const [initial] = useState(() => computeInitialState(location.state));
  const [source, setSource] = useState(initial.source);
  const [rows, setRows] = useState(initial.rows);
  const [initialCash, setInitialCash] = useState(initial.initialCash);
  const [startDate, setStartDate] = useState(initial.startDate);
  const [endDate, setEndDate] = useState(initial.endDate); // blank => latest available
  const [allowFractional, setAllowFractional] = useState(initial.allowFractional);
  const [dividendTreatment, setDividendTreatment] = useState(initial.dividendTreatment);
  const [frequency, setFrequency] = useState(initial.frequency);

  const [savedList, setSavedList] = useState(null);
  const [savedError, setSavedError] = useState("");
  const [selectedSavedId, setSelectedSavedId] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  // ── persist form state (not the heavy result) across navigation ─────────────
  useEffect(() => {
    saveAnalysisState({
      source,
      rows,
      initialCash,
      startDate,
      endDate,
      allowFractional,
      dividendTreatment,
      frequency,
    });
  }, [source, rows, initialCash, startDate, endDate, allowFractional, dividendTreatment, frequency]);

  // ── source selection populates the editor ───────────────────────────────────
  function applySource(id) {
    setSource(id);
    setError("");
    if (id === "input") {
      const h = getCurrentInputPortfolio();
      if (!h || !h.length) {
        setError("No portfolio found from the Use ETFs page. Enter one there first, or switch to Manual.");
        return;
      }
      setRows(h.map((x) => ({ ticker: x.ticker, weight: String(x.weight) })));
    } else if (id === "optimized") {
      const rec = getLatestOptimizedPortfolio();
      if (!rec || !rec.holdings?.length) {
        setError("No optimized portfolio yet. Run the optimizer, open its results, then return here.");
        return;
      }
      setRows(rec.holdings.map((x) => ({ ticker: x.ticker, weight: String(x.weight) })));
    } else if (id === "saved") {
      loadSaved();
    }
    // manual: leave rows as-is
  }

  async function loadSaved() {
    if (!isSupabaseConfigured) {
      setSavedError("Saved portfolios require Supabase to be configured.");
      return;
    }
    setSavedError("");
    try {
      const data = await listPortfolios();
      setSavedList(data || []);
    } catch (e) {
      setSavedError(e.message || "Could not load saved portfolios.");
    }
  }

  function pickSaved(id) {
    setSelectedSavedId(id);
    const rec = (savedList || []).find((p) => String(p.id) === String(id));
    const holdings = holdingsFromSavedPortfolio(rec);
    if (!holdings.length) {
      setError("That saved portfolio has no readable holdings.");
      return;
    }
    setRows(holdings.map((x) => ({ ticker: x.ticker, weight: String(x.weight) })));
    setError("");
  }

  // ── editor operations ────────────────────────────────────────────────────────
  const updateRow = (i, field, value) =>
    setRows((prev) => {
      const copy = [...prev];
      copy[i] = { ...copy[i], [field]: field === "ticker" ? value.toUpperCase() : value };
      return copy;
    });
  const addRow = () => setRows((prev) => [...prev, emptyRow()]);
  const removeRow = (i) => setRows((prev) => (prev.length > 1 ? prev.filter((_, j) => j !== i) : prev));

  const weightSum = useMemo(
    () => rows.reduce((s, r) => s + (r.weight.trim() === "" ? 0 : Number(r.weight) || 0), 0),
    [rows]
  );

  // ── validation + submit ──────────────────────────────────────────────────────
  function validate() {
    const filled = rows.filter((r) => r.ticker.trim() !== "");
    if (filled.length === 0) return "Add at least one ETF with a ticker.";
    const seen = new Set();
    for (const r of filled) {
      const t = r.ticker.trim().toUpperCase();
      if (seen.has(t)) return `Duplicate ticker "${t}". Enter each ETF once.`;
      seen.add(t);
      if (r.weight.trim() === "" || Number.isNaN(Number(r.weight)))
        return `Enter a weight for ${t}.`;
      if (Number(r.weight) < 0) return `Weight for ${t} must not be negative.`;
    }
    if (weightSum <= 0) return "Portfolio weights must total a positive amount.";
    const cash = Number(initialCash);
    if (Number.isNaN(cash) || cash <= 0) return "Enter a positive investment amount.";
    if (!startDate) return "Choose a portfolio start date.";
    if (startDate > TODAY) return "The start date must not be in the future.";
    if (endDate && endDate <= startDate) return "The end date must be after the start date.";
    return null;
  }

  async function runAnalysis() {
    const v = validate();
    if (v) {
      setError(v);
      setResult(null);
      return;
    }
    setError("");
    setLoading(true);
    setResult(null);
    try {
      const portfolio = rows
        .filter((r) => r.ticker.trim() !== "")
        .map((r) => ({ ticker: r.ticker.trim().toUpperCase(), weight: Number(r.weight) / 100 }));
      const body = {
        portfolio,
        initial_cash: Number(initialCash),
        requested_start_date: startDate,
        end_date: endDate || null,
        allow_fractional_shares: allowFractional,
        dividend_treatment: dividendTreatment,
        frequency,
      };
      const res = await fetch(`${API_URL}/api/cash-analysis`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const detail = err.detail;
        throw new Error(
          typeof detail === "string"
            ? detail
            : Array.isArray(detail)
            ? detail.map((d) => d.msg).join("; ")
            : `Request failed (${res.status})`
        );
      }
      setResult(await res.json());
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="cash-analysis">
      <h1>Cash Analysis</h1>
      <p className="ca-intro">
        See what a specific dollar amount would have done in a portfolio bought on
        a historical date — shares purchased, dividends received, gains and losses,
        and total value over time.
      </p>

      <section className="ca-region">
        <div className="ca-region-head">
          <span className="ca-region-eyebrow">Configuration</span>
        </div>

        <PortfolioSource source={source} onSelect={applySource} />

        {source === "saved" && (
          <SavedPicker
            savedList={savedList}
            savedError={savedError}
            selectedSavedId={selectedSavedId}
            onPick={pickSaved}
            onReload={loadSaved}
          />
        )}

        <HoldingsEditor
          rows={rows}
          weightSum={weightSum}
          updateRow={updateRow}
          addRow={addRow}
          removeRow={removeRow}
        />

        <InvestmentSettings
          initialCash={initialCash}
          setInitialCash={setInitialCash}
          startDate={startDate}
          setStartDate={setStartDate}
          endDate={endDate}
          setEndDate={setEndDate}
          allowFractional={allowFractional}
          setAllowFractional={setAllowFractional}
          dividendTreatment={dividendTreatment}
          setDividendTreatment={setDividendTreatment}
          frequency={frequency}
          setFrequency={setFrequency}
        />

        <button className="ca-run" onClick={runAnalysis} disabled={loading}>
          {loading ? "Running Cash Analysis…" : "Run Cash Analysis"}
        </button>

        {error && <p className="error">{error}</p>}
      </section>

      {loading && <LoadingState />}

      {result && !loading && <Results result={result} />}
      {!result && !loading && !error && <EmptyState />}
    </div>
  );
}

// ── Portfolio source ──────────────────────────────────────────────────────────
function PortfolioSource({ source, onSelect }) {
  return (
    <section className="ca-card">
      <h2>
        <span className="ca-step">1</span> Portfolio Source
      </h2>
      <p className="ca-blurb">
        Start from a portfolio you already have, or enter one by hand. You can
        review and edit the holdings below before running.
      </p>
      <div className="ca-source-grid">
        {SOURCES.map((s) => (
          <button
            key={s.id}
            type="button"
            className={`ca-source${source === s.id ? " active" : ""}`}
            onClick={() => onSelect(s.id)}
          >
            {s.label}
          </button>
        ))}
      </div>
    </section>
  );
}

function SavedPicker({ savedList, savedError, selectedSavedId, onPick, onReload }) {
  return (
    <div className="ca-saved-picker">
      {savedError && <p className="error">{savedError}</p>}
      {savedList == null && !savedError && (
        <button type="button" className="ca-secondary" onClick={onReload}>
          Load saved portfolios
        </button>
      )}
      {savedList != null && (
        <label className="ca-field">
          Choose a saved portfolio
          <select value={selectedSavedId} onChange={(e) => onPick(e.target.value)}>
            <option value="">— select —</option>
            {savedList.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.type})
              </option>
            ))}
          </select>
        </label>
      )}
    </div>
  );
}

// ── Holdings editor ───────────────────────────────────────────────────────────
function HoldingsEditor({ rows, weightSum, updateRow, addRow, removeRow }) {
  const off = Math.abs(weightSum - 100);
  const sumClass = off < 0.5 ? "ok" : off <= 2 ? "warn" : "bad";
  return (
    <section className="ca-card">
      <h2>
        <span className="ca-step">2</span> Portfolio Holdings
      </h2>
      <p className="ca-blurb">
        Each holding needs a ticker and a target weight (in %). Weights should
        total 100% — small rounding is normalized automatically.
      </p>
      <div className="ca-holdings-head">
        <span>Ticker</span>
        <span>Weight (%)</span>
        <span />
      </div>
      {rows.map((r, i) => (
        <div key={i} className="ca-holding-row">
          <input
            value={r.ticker}
            placeholder="VTI"
            onChange={(e) => updateRow(i, "ticker", e.target.value)}
          />
          <input
            type="number"
            step="0.01"
            min="0"
            value={r.weight}
            placeholder="50"
            onChange={(e) => updateRow(i, "weight", e.target.value)}
          />
          <button
            type="button"
            className="ca-remove"
            aria-label={`Remove ${r.ticker || "row"}`}
            onClick={() => removeRow(i)}
          >
            ✕
          </button>
        </div>
      ))}
      <div className="ca-editor-footer">
        <button type="button" className="ca-secondary" onClick={addRow}>
          + Add ETF
        </button>
        <span className={`ca-weight-sum ${sumClass}`}>
          Total: {weightSum.toFixed(2)}%
          {sumClass === "bad" && " — will be normalized to 100%"}
        </span>
      </div>
    </section>
  );
}

// ── Investment settings ───────────────────────────────────────────────────────
function InvestmentSettings(props) {
  const {
    initialCash, setInitialCash, startDate, setStartDate, endDate, setEndDate,
    allowFractional, setAllowFractional, dividendTreatment, setDividendTreatment,
    frequency, setFrequency,
  } = props;
  return (
    <section className="ca-card">
      <h2>
        <span className="ca-step">3</span> Investment Settings
      </h2>
      <div className="ca-settings-grid">
        <label className="ca-field">
          Initial investment ($)
          <input
            type="number"
            min="0"
            step="100"
            value={initialCash}
            onChange={(e) => setInitialCash(e.target.value)}
          />
        </label>
        <label className="ca-field">
          Start date
          <Info text="If this isn't a trading day, the analysis uses the next day all holdings had prices." />
          <input
            type="date"
            max={TODAY}
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
          />
        </label>
        <label className="ca-field">
          End date <span className="ca-optional">optional</span>
          <Info text="Defaults to the latest available market date." />
          <input
            type="date"
            max={TODAY}
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
          />
        </label>
        <label className="ca-field">
          Chart frequency
          <select value={frequency} onChange={(e) => setFrequency(e.target.value)}>
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
            <option value="monthly">Monthly</option>
          </select>
        </label>
        <label className="ca-field ca-check">
          <input
            type="checkbox"
            checked={allowFractional}
            onChange={(e) => setAllowFractional(e.target.checked)}
          />
          Allow fractional shares
          <Info text="On: buy partial shares so the allocation matches exactly. Off: whole shares only, leaving residual cash." />
        </label>
        <label className="ca-field">
          Dividends
          <Info text="Cash: distributions accumulate as cash. Reinvestment can be added later." />
          <select
            value={dividendTreatment}
            onChange={(e) => setDividendTreatment(e.target.value)}
          >
            <option value="cash">Take as cash</option>
            <option value="reinvest" disabled>
              Reinvest (coming soon)
            </option>
          </select>
        </label>
      </div>
    </section>
  );
}

// ── States ────────────────────────────────────────────────────────────────────
function LoadingState() {
  return (
    <section className="ca-card ca-state">
      <div className="ca-spinner" />
      <p>Fetching historical prices and dividends, then running the simulation…</p>
    </section>
  );
}

function EmptyState() {
  return (
    <section className="ca-card ca-state">
      <p className="ca-empty-title">No analysis yet</p>
      <p className="ca-blurb">
        Pick a portfolio source, set your investment amount and start date, then
        run the analysis to see holdings, dividends and total value over time.
      </p>
    </section>
  );
}

// ── Results ───────────────────────────────────────────────────────────────────
function Results({ result }) {
  return (
    <div className="ca-results ca-region ca-region-analytics">
      <div className="ca-region-head">
        <span className="ca-region-eyebrow">Analysis</span>
      </div>
      <ExecutionNotice execution={result.execution} />
      <SummaryCards summary={result.summary} />
      <HoldingsTable holdings={result.holdings} />
      <MonthlyTable rows={result.monthly_cash_flows} />
      <DividendChart data={result.dividend_by_month} />
      <GainLossChart series={result.portfolio_time_series} meta={result.metadata} />
      <HoldingsGainLossChart holdings={result.holdings} />
      <AssumptionsWarnings result={result} />
    </div>
  );
}

function ExecutionNotice({ execution }) {
  const adjusted = execution.date_adjusted || execution.ending_date_adjusted;
  return (
    <section className={`ca-execution${adjusted ? " adjusted" : ""}`}>
      <div className="ca-exec-item">
        <span className="ca-exec-label">Requested start</span>
        <span className="ca-exec-value">{execution.requested_start_date}</span>
      </div>
      <div className="ca-exec-arrow" aria-hidden="true">
        →
      </div>
      <div className="ca-exec-item">
        <span className="ca-exec-label">Execution date</span>
        <span className="ca-exec-value">{execution.actual_execution_date}</span>
      </div>
      <div className="ca-exec-item">
        <span className="ca-exec-label">Ending date</span>
        <span className="ca-exec-value">{execution.ending_date}</span>
      </div>
      <div className="ca-exec-item">
        <span className="ca-exec-label">Price basis</span>
        <span className="ca-exec-value">Unadjusted close</span>
      </div>
      {execution.adjustment_reason && (
        <p className="ca-exec-reason">{execution.adjustment_reason}</p>
      )}
      {execution.ending_adjustment_reason && (
        <p className="ca-exec-reason">{execution.ending_adjustment_reason}</p>
      )}
    </section>
  );
}

function Card({ label, value, delta, pct, hint }) {
  return (
    <div className="ca-summary-card">
      <span className="ca-card-label">
        {label}
        {hint && <Info text={hint} />}
      </span>
      <span className="ca-card-value">
        {delta ? <Delta value={value} pct={pct} /> : value}
      </span>
    </div>
  );
}

function SummaryCards({ summary }) {
  const s = summary;
  return (
    <section className="ca-summary-grid">
      <Card label="Initial Investment" value={fmtCurrency(s.initial_investment)} />
      <Card label="Current Holdings Value" value={fmtCurrency(s.current_holdings_value)} />
      <Card label="Total Dividend Income" value={fmtCurrency(s.total_dividend_income)} hint="Actual cash distributions received over the period." />
      <Card label="Residual Cash" value={fmtCurrency(s.residual_cash)} hint="Uninvested cash left over (from whole-share rounding)." />
      <Card label="Total Portfolio Value" value={fmtCurrency(s.total_portfolio_value)} hint="Holdings + cumulative dividends + residual cash." />
      <Card label="Paper Gain / Loss" value={s.paper_gain_loss} delta hint="Unrealized change in holdings value vs. cost basis (not sold)." />
      <Card label="Realized Income" value={fmtCurrency(s.realized_income)} hint="Dividend cash actually received (realized)." />
      <Card label="Total Gain / Loss" value={s.total_gain_loss} delta />
      <Card label="Total Return" value={s.total_return_pct} delta pct />
      <Card label="Execution Date" value={s.actual_execution_date} />
    </section>
  );
}

// ── Holdings table (sortable) ─────────────────────────────────────────────────
const HOLDING_COLS = [
  { key: "ticker", label: "Ticker", type: "text" },
  { key: "target_weight", label: "Target %", type: "pct" },
  { key: "allocated_cash", label: "Allocated", type: "money" },
  { key: "execution_price", label: "Exec Price", type: "price" },
  { key: "shares", label: "Shares", type: "shares" },
  { key: "cost_basis", label: "Cost Basis", type: "money" },
  { key: "ending_price", label: "End Price", type: "price" },
  { key: "ending_market_value", label: "End Value", type: "money" },
  { key: "price_gain_loss", label: "Price G/L", type: "delta" },
  { key: "price_return_pct", label: "Price %", type: "deltapct" },
  { key: "total_dividends", label: "Dividends", type: "money" },
  { key: "dividend_return_pct", label: "Div %", type: "pct" },
  { key: "total_gain_loss", label: "Total G/L", type: "delta" },
  { key: "total_return_pct", label: "Total %", type: "deltapct" },
  { key: "current_weight", label: "Curr %", type: "pct" },
  { key: "weight_drift", label: "Drift", type: "deltapct" },
];

function fmtCell(type, v) {
  switch (type) {
    case "money":
      return fmtCurrency(v);
    case "price":
      return fmtCurrency(v, 2);
    case "shares":
      return Number(v).toLocaleString("en-US", { maximumFractionDigits: 4 });
    case "pct":
      return `${Number(v).toFixed(2)}%`;
    case "delta":
      return <Delta value={v} />;
    case "deltapct":
      return <Delta value={v} pct />;
    default:
      return v;
  }
}

function HoldingsTable({ holdings }) {
  const [sortKey, setSortKey] = useState("target_weight");
  const [dir, setDir] = useState("desc");

  const sorted = useMemo(() => {
    const copy = [...holdings];
    copy.sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (typeof av === "string") return dir === "asc" ? av.localeCompare(bv) : bv.localeCompare(av);
      return dir === "asc" ? av - bv : bv - av;
    });
    return copy;
  }, [holdings, sortKey, dir]);

  const onSort = (key) => {
    if (key === sortKey) setDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortKey(key);
      setDir("desc");
    }
  };

  return (
    <section className="ca-table-section">
      <h2>Holdings</h2>
      <div className="ca-table-scroll">
        <table className="ca-table">
          <thead>
            <tr>
              {HOLDING_COLS.map((c) => (
                <th
                  key={c.key}
                  className={`sortable${sortKey === c.key ? " sorted" : ""}`}
                  onClick={() => onSort(c.key)}
                >
                  {c.label}
                  {sortKey === c.key ? (dir === "asc" ? " ▲" : " ▼") : ""}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((h) => (
              <tr key={h.ticker}>
                {HOLDING_COLS.map((c) => (
                  <td key={c.key} className={`col-${c.type}`}>
                    {fmtCell(c.type, h[c.key])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

// ── Monthly cash-flow table ───────────────────────────────────────────────────
const MONTHLY_COLS = [
  { key: "month", label: "Month", type: "text" },
  { key: "beginning_value", label: "Beginning", type: "money" },
  { key: "contributions", label: "Contributions", type: "money" },
  { key: "dividend_income", label: "Dividends", type: "money" },
  { key: "realized_sale_proceeds", label: "Sale Proceeds", type: "money" },
  { key: "ending_value", label: "Ending", type: "money" },
  { key: "paper_gain_loss", label: "Paper G/L", type: "delta" },
  { key: "cumulative_dividend_income", label: "Cum. Div", type: "money" },
  { key: "total_portfolio_value", label: "Total Value", type: "money" },
  { key: "monthly_gain_loss", label: "Monthly G/L", type: "delta" },
  { key: "cumulative_gain_loss", label: "Cum. G/L", type: "delta" },
  { key: "monthly_return_pct", label: "Monthly %", type: "deltapct" },
  { key: "cumulative_return_pct", label: "Cum. %", type: "deltapct" },
];

function MonthlyTable({ rows }) {
  const [open, setOpen] = useState(true);
  return (
    <section className="ca-table-section">
      <h2>
        Monthly Cash Analysis{" "}
        <button className="ca-toggle-link" onClick={() => setOpen((o) => !o)}>
          {open ? "Hide" : "Show"}
        </button>
      </h2>
      {open && (
        <div className="ca-table-scroll">
          <table className="ca-table">
            <thead>
              <tr>
                {MONTHLY_COLS.map((c) => (
                  <th key={c.key}>{c.label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.month}>
                  {MONTHLY_COLS.map((c) => (
                    <td key={c.key} className={`col-${c.type}`}>
                      {fmtCell(c.type, r[c.key])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

// ── Dividend payout chart ─────────────────────────────────────────────────────
function DividendChart({ data }) {
  const [mode, setMode] = useState("stacked");
  const [cumulative, setCumulative] = useState(false);
  const [hidden, setHidden] = useState({});

  const hasAny = data.totals.some((v) => v > 0);

  // Fold beyond 8 series into "Other" so categorical hues are never cycled.
  const built = useMemo(() => {
    const tickers = data.tickers;
    const base = tickers.slice(0, 8);
    const overflow = tickers.slice(8);
    const series = base.map((t, i) => ({
      key: t,
      label: t,
      color: seriesColor(i),
      values: data.series[t] || data.months.map(() => 0),
    }));
    if (overflow.length) {
      const otherVals = data.months.map((_, mi) =>
        overflow.reduce((s, t) => s + (data.series[t]?.[mi] || 0), 0)
      );
      series.push({ key: "__other", label: "Other", color: "#6b7a73", values: otherVals });
    }
    return series;
  }, [data]);

  const displaySeries = useMemo(() => {
    const s = built.filter((x) => !hidden[x.key]);
    if (!cumulative) return s;
    return s.map((x) => {
      let run = 0;
      return { ...x, values: x.values.map((v) => (run += v)) };
    });
  }, [built, hidden, cumulative]);

  const legendItems = built.map((s) => ({ ...s, visible: !hidden[s.key] }));

  if (!hasAny) {
    return (
      <section className="ca-chart-card">
        <h2>Monthly Dividend Payout</h2>
        <p className="ca-blurb ca-nodata">
          No dividend distributions were recorded for these holdings during the
          analysis period.
        </p>
      </section>
    );
  }

  return (
    <section className="ca-chart-card">
      <div className="ca-chart-head">
        <h2>Monthly Dividend Payout</h2>
        <div className="ca-chart-controls">
          <div className="ca-segmented">
            <button className={mode === "stacked" ? "on" : ""} onClick={() => setMode("stacked")}>
              Stacked
            </button>
            <button className={mode === "grouped" ? "on" : ""} onClick={() => setMode("grouped")}>
              Grouped
            </button>
          </div>
          <label className="ca-inline-check">
            <input
              type="checkbox"
              checked={cumulative}
              onChange={(e) => setCumulative(e.target.checked)}
            />
            Cumulative
          </label>
        </div>
      </div>
      <ChartLegend
        items={legendItems}
        onToggle={(key) => setHidden((h) => ({ ...h, [key]: !h[key] }))}
      />
      <BarChart
        categories={data.months}
        series={displaySeries}
        mode={mode}
        valueFormat={(v) => `$${Math.round(v)}`}
        tooltipValueFormat={(v) => fmtCurrency(v)}
        ariaLabel="Monthly dividend payout by ETF"
      />
    </section>
  );
}

// ── Portfolio gain/loss time-series chart ─────────────────────────────────────
const GL_LINES = [
  { key: "total_portfolio_value", label: "Total Portfolio Value", color: seriesColor(0), field: "total_portfolio_value", default: true },
  { key: "initial_cash", label: "Initial Investment", color: "#898781", field: "initial_cash", dashed: true, default: true },
  { key: "holdings_value", label: "Holdings Value", color: seriesColor(2), field: "holdings_value", default: false },
  { key: "cumulative_dividends", label: "Cumulative Dividends", color: seriesColor(3), field: "cumulative_dividends", default: false },
  { key: "gain_loss", label: "Total Gain / Loss", color: seriesColor(1), field: "gain_loss", default: false },
];

// client-side downsample of a daily series to weekly/monthly (period-end points)
function downsample(points, freq, baseFreq) {
  if (freq === "daily" || baseFreq === "monthly") return points;
  const bucketKey = (dateStr) => {
    const d = new Date(dateStr + "T00:00:00");
    if (freq === "monthly") return dateStr.slice(0, 7);
    // weekly: ISO year-week
    const day = (d.getUTCDay() + 6) % 7;
    const monday = new Date(d);
    monday.setUTCDate(d.getUTCDate() - day);
    return monday.toISOString().slice(0, 10);
  };
  const lastByBucket = new Map();
  for (const p of points) lastByBucket.set(bucketKey(p.date), p);
  const kept = [...lastByBucket.values()];
  // recompute per-period dividend cash from cumulative diffs
  let prevCum = 0;
  return kept.map((p) => {
    const period = { ...p, dividend_cash_period: Number((p.cumulative_dividends - prevCum).toFixed(2)) };
    prevCum = p.cumulative_dividends;
    return period;
  });
}

function GainLossChart({ series, meta }) {
  const baseFreq = meta.time_series_frequency; // "daily" | "monthly"
  const [freq, setFreq] = useState(baseFreq === "monthly" ? "monthly" : meta.frequency);
  const [visible, setVisible] = useState(() =>
    Object.fromEntries(GL_LINES.map((l) => [l.key, l.default]))
  );

  const points = useMemo(() => downsample(series, freq, baseFreq), [series, freq, baseFreq]);
  const xLabels = points.map((p) => p.date);

  const chartSeries = GL_LINES.filter((l) => visible[l.key]).map((l) => ({
    key: l.key,
    label: l.label,
    color: l.color,
    dashed: l.dashed,
    values: points.map((p) => p[l.field]),
  }));

  const legendItems = GL_LINES.map((l) => ({ ...l, visible: visible[l.key] }));
  const canDownsample = baseFreq !== "monthly";

  return (
    <section className="ca-chart-card">
      <div className="ca-chart-head">
        <h2>Total Portfolio Gain / Loss</h2>
        <div className="ca-chart-controls">
          <div className="ca-segmented">
            {["daily", "weekly", "monthly"].map((f) => (
              <button
                key={f}
                className={freq === f ? "on" : ""}
                disabled={!canDownsample && f !== "monthly"}
                onClick={() => setFreq(f)}
                title={!canDownsample && f !== "monthly" ? "Long window: only monthly points were returned" : ""}
              >
                {f[0].toUpperCase() + f.slice(1)}
              </button>
            ))}
          </div>
        </div>
      </div>
      <ChartLegend
        items={legendItems}
        onToggle={(key) => setVisible((v) => ({ ...v, [key]: !v[key] }))}
      />
      <LineChart
        xLabels={xLabels}
        series={chartSeries}
        tooltipValueFormat={(v) => fmtCurrency(v)}
        ariaLabel="Total portfolio value and gain/loss over time"
      />
      {!canDownsample && (
        <p className="ca-blurb ca-note">
          The window is long, so the series is aggregated to month-end points.
        </p>
      )}
    </section>
  );
}

// ── Holdings gain/loss chart (stacked: price + dividend) ──────────────────────
function HoldingsGainLossChart({ holdings }) {
  const categories = holdings.map((h) => h.ticker);
  const series = [
    { key: "price", label: "Price Gain / Loss", color: seriesColor(0), values: holdings.map((h) => h.price_gain_loss) },
    { key: "dividend", label: "Dividend Income", color: seriesColor(3), values: holdings.map((h) => h.total_dividends) },
  ];
  return (
    <section className="ca-chart-card">
      <h2>Gain / Loss by Holding</h2>
      <p className="ca-blurb">
        Capital appreciation (price) stacked with dividend income — the combined
        bar is each holding's total gain or loss.
      </p>
      <ChartLegend items={series.map((s) => ({ ...s, visible: true }))} />
      <BarChart
        categories={categories}
        series={series}
        mode="stacked"
        tooltipValueFormat={(v) => fmtSignedCurrency(v)}
        ariaLabel="Gain or loss by holding, split into price and dividends"
      />
    </section>
  );
}

// ── Assumptions & warnings ────────────────────────────────────────────────────
function AssumptionsWarnings({ result }) {
  const { warnings, metadata, execution } = result;
  return (
    <section className="ca-card ca-assumptions">
      <h2>Assumptions & Warnings</h2>
      {warnings.length > 0 ? (
        <ul className="ca-warn-list">
          {warnings.map((w, i) => (
            <li key={i} className={`ca-warn ${w.severity}`}>
              <span className="ca-warn-badge">{w.severity}</span>
              {w.message}
            </li>
          ))}
        </ul>
      ) : (
        <p className="ca-blurb">No warnings — all holdings had valid pricing on the execution and ending dates.</p>
      )}
      <ul className="ca-assume-list">
        <li>Prices use the <strong>unadjusted close</strong>; dividends are added separately as actual cash — never double-counted.</li>
        <li>Dividends are credited only when the ex-date falls after the execution date (entitlement rule) and are treated as <strong>{metadata.dividend_treatment}</strong>.</li>
        <li>{metadata.allow_fractional_shares ? "Fractional shares" : "Whole shares only"} — the portfolio is <strong>not rebalanced</strong>, so realized capital gains are $0.</li>
        <li>All holdings were executed together on {execution.actual_execution_date} (earliest common trading day). Timezone: {metadata.timezone}.</li>
      </ul>
    </section>
  );
}
