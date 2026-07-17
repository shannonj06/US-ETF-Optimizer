import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { METHOD_LABELS } from "../config/labels.js";
import { formatPercent } from "../config/format.js";

function ResultsPage(){
    const location = useLocation();
    const navigate = useNavigate();
    // The optimizer page passes the /optimize response via:
    //   navigate("/results", { state: { result } })
    const result = location.state?.result;
    const inputs = location.state?.inputs;   // carried from the optimizer, forwarded to graphs

    // Navigation state doesn't survive a page refresh / direct URL visit.
    if (!result) {
        return (
            <div className="results-page">
                <h1>Results</h1>
                <p>No results to show. Run the optimizer first.</p>
                <button onClick={() => navigate("/PortfolioOptimizer")}>Back to Optimizer</button>
            </div>
        );
    }

    // `result` is the full JSON from /optimize — render it however you like below.
    return (
        <div className="results-page">
            <ResultsTab result={result}/>
            <button
                    className="see-results"
                    onClick={() => navigate("/graphs", { state: { result, inputs } })}
                >
                    See Graphs
                </button>
        </div>
    );
}

function ResultsTab({result}){
    const [activeTab, setActiveTab] = useState("cvxpy");
    return(
        <div>
        < div className="tabs">
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
        {activeTab == "cvxpy" && (
            <>
                <CVXPY4Table result={result}/>
                <CVXPYTable result={result}/>
                <CVXPYMetrics result={result}/>
                <CVXPY4Metrics result={result}/>
            </>
            )}
        {activeTab == "slsqp" && (
            <>
                <SLSQP4Table result={result}/>
                <SLSQPTable result={result}/>
                <SLSQPMetrics result={result}/>
                <SLSQP4Metrics result={result}/>
            </>
            )}
        {activeTab == "hrp" && (
            <>
                <HRP4Table result={result}/>
                <HRPTable result={result}/>
                <HRPMetrics result={result}/>
                <HRP4Metrics result={result}/>
            </>
            )}
        </div>
    );
}

function CVXPYTable({result}){
    const weights = result.methods.cvxpy.weights;
    return(
        <div>
            <h2>Total Weight</h2>
        <table>
            <thead>
            <tr>
                <th></th>
                <th>ETF</th>
                <th>Weight</th>
            </tr>
            </thead>
            <tbody>
                {weights.map((row, index) => (
                    <tr key={row.ETF}>
                        <td>{index}</td>
                        <td>{row.ETF}</td>
                        <td>{formatPercent(row.Weight)}</td>
                    </tr>
                ))}
            </tbody>
        </table>
        </div>
    );
}

function SLSQPTable({result}){
    const weights = result.methods.slsqp.weights;
    return(
        <div>
            <h2>Total Weight</h2>
        <table>
            <thead>
            <tr>
                <th></th>
                <th>ETF</th>
                <th>Weight</th>
            </tr>
            </thead>
            <tbody>
                {weights.map((row, index) => (
                    <tr key={row.ETF}>
                        <td>{index}</td>
                        <td>{row.ETF}</td>
                        <td>{formatPercent(row.Weight)}</td>
                    </tr>
                ))}
            </tbody>

        </table>
        </div>
    );
}

function HRPTable({result}){
    const weights = result.methods.hrp.weights;
    return(
        <div>
            <h2>Total Weight</h2>
        <table>
            <thead>
            <tr>
                <th></th>
                <th>ETF</th>
                <th>Weight</th>
            </tr>
            </thead>
            <tbody>
                {weights.map((row, index) => (
                    <tr key={row.ETF}>
                        <td>{index}</td>
                        <td>{row.ETF}</td>
                        <td>{formatPercent(row.Weight)}</td>
                    </tr>
                ))}
            </tbody>
        </table>
        </div>
    );
}

function CVXPY4Table({result}){
    const weights = result.methods.cvxpy.core4.weights;
    return(
        <table>
            <thead>
            <tr>
                <th></th>
                <th>ETF</th>
                <th>Weight</th>
            </tr>
            </thead>
            <tbody>
                {weights.map((row, index) => (
                    <tr key={row.ETF}>
                        <td>{index}</td>
                        <td>{row.ETF}</td>
                        <td>{formatPercent(row.Weight)}</td>
                    </tr>
                ))}
            </tbody>

        </table>
    );
}

function SLSQP4Table({result}){
    const weights = result.methods.slsqp.core4.weights;
    return(
        <table>
            <thead>
            <tr>
                <th></th>
                <th>ETF</th>
                <th>Weight</th>
            </tr>
            </thead>
            <tbody>
                {weights.map((row, index) => (
                    <tr key={row.ETF}>
                        <td>{index}</td>
                        <td>{row.ETF}</td>
                        <td>{formatPercent(row.Weight)}</td>
                    </tr>
                ))}
            </tbody>

        </table>
    );
}

function HRP4Table({result}){
    const weights = result.methods.hrp.core4.weights;
    return(
        <table>
            <thead>
            <tr>
                <th></th>
                <th>ETF</th>
                <th>Weight</th>
            </tr>
            </thead>
            <tbody>
                {weights.map((row, index) => (
                    <tr key={row.ETF}>
                        <td>{index}</td>
                        <td>{row.ETF}</td>
                        <td>{formatPercent(row.Weight)}</td>
                    </tr>
                ))}
            </tbody>

        </table>
    );
}

function HRPMetrics({result}){
    const metrics = result.methods.hrp.metrics;
    return(
        <div>
            <h2>Total Metrics</h2>
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
function HRP4Metrics({result}){
    const metrics = result.methods.hrp.core4.metrics;
    return(
        <div>
            <h2>Top 4 Metrics</h2>
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

function CVXPYMetrics({result}){
    const metrics = result.methods.cvxpy.metrics;
    return(
        <div>
            <h2>Total Metrics</h2>
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
function CVXPY4Metrics({result}){
    const metrics = result.methods.cvxpy.core4.metrics;
    return(
        <div>
            <h2>Top 4 Metrics</h2>
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

function SLSQPMetrics({result}){
    const metrics = result.methods.slsqp.metrics;
    return(
        <div>
            <h2>Total Metrics</h2>
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
function SLSQP4Metrics({result}){
    const metrics = result.methods.slsqp.core4.metrics;
    return(
        <div>
            <h2>Top 4 Metrics</h2>
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
export default ResultsPage;
