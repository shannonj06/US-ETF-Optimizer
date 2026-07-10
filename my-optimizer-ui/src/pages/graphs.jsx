import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import SavePortfolioButton from "../components/save_button.jsx";

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
                >
                    CVXPY
                </button>
                <button
                    className={activeTab === "slsqp" ? "tab active-tab" : "tab"}
                    onClick={() => setActiveTab("slsqp")}
                >
                    SLSQP
                </button>
                <button
                    className={activeTab === "hrp" ? "tab active-tab" : "tab"}
                    onClick={() => setActiveTab("hrp")}
                >
                    HRP
                </button>
            </div>

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
                    <img alt={name} src={`data:image/png;base64,${b64}`}
                        style={{ maxWidth: "100%" }} />
                    <figcaption>{name}</figcaption>
                </figure>
            ))}
        </div>
    );
}

export default GraphsPage;
