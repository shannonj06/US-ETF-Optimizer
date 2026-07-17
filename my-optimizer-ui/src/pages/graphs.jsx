import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import SavePortfolioButton from "../components/save_button.jsx";
import { METHOD_LABELS, CHART_LABELS } from "../config/labels.js";

function GraphsPage(){
    const location = useLocation();
    const navigate = useNavigate();
    // Passed from the results page: navigate("/graphs", { state: { result, inputs } })
    const result = location.state?.result;
    const inputs = location.state?.inputs;

    // Navigation state doesn't survive a refresh / direct URL visit.
    if (!result) {
        return (
            <div className="graphs-page">
                <h1>Graphs</h1>
                <p>No graphs to show. Run the optimizer first.</p>
                <button onClick={() => navigate("/PortfolioOptimizer")}>Back to Optimizer</button>
            </div>
        );
    }

    return (
        <div className="graphs-page">
            <h1>Graphs — {result.profile}</h1>
            <GraphsTab result={result} />
            <SavePortfolioButton type="optimize" inputs={inputs} results={result} />
            <button onClick={() => navigate("/results", { state: { result, inputs } })}>
                Back to Results
            </button>
        </div>
    );
}

function GraphsTab({ result }){
    const [activeTab, setActiveTab] = useState("cvxpy");
    return (
        <div>
            <div className="tabs">
                <button
                    className={activeTab === "cvxpy" ? "tab active-tab" : "tab"}
                    onClick={() => setActiveTab("cvxpy")}
                    title={METHOD_LABELS.cvxpy.hint}
                >
                    {METHOD_LABELS.cvxpy.label}
                </button>
                <button
                    className={activeTab === "slsqp" ? "tab active-tab" : "tab"}
                    onClick={() => setActiveTab("slsqp")}
                    title={METHOD_LABELS.slsqp.hint}
                >
                    {METHOD_LABELS.slsqp.label}
                </button>
                <button
                    className={activeTab === "hrp" ? "tab active-tab" : "tab"}
                    onClick={() => setActiveTab("hrp")}
                    title={METHOD_LABELS.hrp.hint}
                >
                    {METHOD_LABELS.hrp.label}
                </button>
            </div>
            <p className="section-hint">{METHOD_LABELS[activeTab].hint}</p>

            <MethodCharts charts={result.methods[activeTab].charts} />
        </div>
    );
}

// charts is a { chartName: base64PngString } map (or undefined if charts were off).
function MethodCharts({ charts }){
    if (!charts || Object.keys(charts).length === 0) return <p>No charts.</p>;
    return (
        <div className="charts">
            {Object.entries(charts).map(([name, b64]) => (
                <figure key={name}>
                    <img alt={CHART_LABELS[name] ?? name} src={`data:image/png;base64,${b64}`}
                        style={{ maxWidth: "100%" }} />
                    <figcaption>{CHART_LABELS[name] ?? name}</figcaption>
                </figure>
            ))}
        </div>
    );
}

export default GraphsPage;
