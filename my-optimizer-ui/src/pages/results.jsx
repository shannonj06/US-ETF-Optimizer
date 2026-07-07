import { useLocation, useNavigate } from "react-router-dom";

function ResultsPage(){
    const location = useLocation();
    const navigate = useNavigate();
    // The optimizer page passes the /optimize response via:
    //   navigate("/results", { state: { result } })
    const result = location.state?.result;

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
            <h1>Results — {result.profile}</h1>
            <pre>{JSON.stringify(result, null, 2)}</pre>
        </div>
    );
}

export default ResultsPage;
