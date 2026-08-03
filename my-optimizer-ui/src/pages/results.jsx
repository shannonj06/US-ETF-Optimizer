import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  setLatestOptimizedPortfolio,
  toCanonicalHoldings,
} from "../config/cashAnalysisState";

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
    const navigate = useNavigate();

    // Keep the "Latest Optimized Portfolio" hand-off in sync with the method the
    // user is looking at, so Cash Analysis can pick it up without re-entry.
    const activeHoldings = toCanonicalHoldings(
        result.methods?.[activeTab]?.weights ?? []
    );
    useEffect(() => {
        if (activeHoldings.length) {
            setLatestOptimizedPortfolio(activeHoldings, {
                method: activeTab,
                profile: result.profile,
                market: result.market,
            });
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [activeTab, result]);

    return(
        <div>
        < div className="tabs">
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
        <button
            className="ca-secondary"
            onClick={() =>
                navigate("/cash-analysis", {
                    state: { holdings: activeHoldings, source: "optimized" },
                })
            }
        >
            Analyze {activeTab.toUpperCase()} in Cash Analysis →
        </button>
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
                        <td>{row.Weight}</td>
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
                        <td>{row.Weight}</td>
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
                        <td>{row.Weight}</td>
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
                        <td>{row.Weight}</td>
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
                        <td>{row.Weight}</td>
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
                        <td>{row.Weight}</td>
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
