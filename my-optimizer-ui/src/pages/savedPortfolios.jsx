import { listPortfolios, deletePortfolio} from "../config/portfolios"
import { useNavigate } from "react-router-dom"
import {useEffect, useState} from "react"
import { METHOD_LABELS } from "../config/labels.js"
import { formatPercent } from "../config/format.js"

function SavedPortfoliosPage(){
    const [portfolios, setPortfolios] = useState([]);
    const [selectedPortfolio, setSelectedPortfolio] = useState(null);
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(true);
    const [confirmingDelete, setConfirmingDelete] = useState(false);
    const navigate = useNavigate();

    useEffect(() => {
        async function loadPortfolios(){
            try{
                const data = await listPortfolios();
                setPortfolios(data);
            }
            catch (e){
                setError(e.message);
            }
            finally{
                setLoading(false);
            }
        }
        loadPortfolios();
    }, []);

    async function handleDelete(id){
        try {
            await deletePortfolio(id);
            setPortfolios((prev) => prev.filter((p) => p.id !== id));
            setSelectedPortfolio(null);
            setConfirmingDelete(false);
        } catch (e) {
            setError(e.message);
        }
    }

    function selectPortfolio(portfolio){
        setSelectedPortfolio(portfolio);
        setConfirmingDelete(false);
    }

    if (loading) return <p>Loading…</p>;
    if (error) return <p className="error">{error}</p>;

    return(
        <div>
            <h2>Your Saved Portfolios</h2>
            <Portfolios
                portfolios={portfolios}
                setSelectedPortfolio={selectPortfolio}
            />
            {selectedPortfolio && (
                <div>
                    <h3>{selectedPortfolio.name}</h3>
                    <p>Type: {selectedPortfolio.type}</p>
                    <p>Created on: {selectedPortfolio.created_at}</p>
                    
                    {selectedPortfolio.type == "evaluate" &&(
                        <div>
                            <EvaluatedPortfolioDetails
                                portfolio={selectedPortfolio} />
                        </div>
                    )}

                    {selectedPortfolio.type == "optimize" &&(
                        <div>
                            <OptimizedPortfolioDetails
                                portfolio={selectedPortfolio} />
                            <button onClick={() => navigate("/graphs", { state: { result: selectedPortfolio.results, inputs: selectedPortfolio.inputs } })}>
                                View Graphs
                            </button>
                        </div>
                    )}

                    {/* Every portfolio gets a button to open the full results page. */}
                    <button onClick={() => navigate("/results", { state: { result: selectedPortfolio.results, inputs: selectedPortfolio.inputs } })}>
                        View Results
                    </button>

                    {confirmingDelete ? (
                        <span className="confirm-delete">
                            <span>Delete "{selectedPortfolio.name}"? This can't be undone.</span>
                            <button className="danger" onClick={() => handleDelete(selectedPortfolio.id)}>Yes, delete</button>
                            <button onClick={() => setConfirmingDelete(false)}>Cancel</button>
                        </span>
                    ) : (
                        <button onClick={() => setConfirmingDelete(true)}>Delete</button>
                    )}
                </div>
            )}

                
        </div>
    );
}

function PortfolioButton({portfolio, setSelectedPortfolio}){
    return(
        <button onClick={() => setSelectedPortfolio(portfolio)}>
            {portfolio.name}
        </button>
    );
}

function Portfolios({portfolios, setSelectedPortfolio}){
    return(
        <div>
            {portfolios.map((portfolio) => (
                <PortfolioButton
                    key={portfolio.id}
                    portfolio={portfolio}
                    setSelectedPortfolio={setSelectedPortfolio}
                    />
            ))}
        </div>
    )
}

function EvaluatedPortfolioDetails({portfolio}){
    const inputs = portfolio.inputs;
    const results = portfolio.results
    return(
        <div>
            <p>Period: {inputs.period}</p>
            <p>Risk Free Rate: {formatPercent(inputs.rf)}</p>
            <h3>Weights and Metrics</h3>
            <table>
                <thead>
                    <tr>
                        <th>Ticker</th>
                        <th>Weight</th>
                    </tr>
                </thead>
                <tbody>
                    {inputs.etfs.map((etf) =>(
                        <tr key= {etf.ticker}>
                            <td>{etf.ticker}</td>
                            <td>{formatPercent(etf.weight)}</td>
                        </tr>
                    ))}
                </tbody>

            </table>
            
            <table>
                <thead>
                    <tr>
                        <th>Metric</th>
                        <th>Value</th>
                    </tr>
                </thead>
                <tbody>
                    {results.metrics.map((value) =>(
                        <tr key= {value.index}>
                            <td>{value.index}</td>
                            <td>{value.Value}</td>
                        </tr>
                    ))}
                </tbody>

            </table>

        </div>
    );
}

function OptimizedPortfolioDetails({portfolio}){
    const inputs = portfolio.inputs;
    const results = portfolio.results
    return(
        <div>
            <p>Style: {inputs.profile}</p>
            <h3>Weights and Metrics</h3>
            <h4>{METHOD_LABELS.slsqp.label}</h4>
            <table>
                <thead>
                    <tr>
                        <th>Ticker</th>
                        <th>Weight</th>
                    </tr>
                </thead>
                <tbody>
                    {results.methods.slsqp.core4.weights.map((etf) =>(
                        <tr key= {etf.ETF}>
                            <td>{etf.ETF}</td>
                            <td>{formatPercent(etf.Weight)}</td>
                        </tr>
                    ))}
                </tbody>

            </table>
            
            <table>
                <thead>
                    <tr>
                        <th>Metric</th>
                        <th>Value</th>
                    </tr>
                </thead>
                <tbody>
                    {results.methods.slsqp.core4.metrics.map((value) =>(
                        <tr key= {value.index}>
                            <td>{value.index}</td>
                            <td>{value.Value}</td>
                        </tr>
                    ))}
                </tbody>

            </table>

            <h4>{METHOD_LABELS.cvxpy.label}</h4>
            <table>
                <thead>
                    <tr>
                        <th>Ticker</th>
                        <th>Weight</th>
                    </tr>
                </thead>
                <tbody>
                    {results.methods.cvxpy.core4.weights.map((etf) =>(
                        <tr key= {etf.ETF}>
                            <td>{etf.ETF}</td>
                            <td>{formatPercent(etf.Weight)}</td>
                        </tr>
                    ))}
                </tbody>

            </table>
            
            <table>
                <thead>
                    <tr>
                        <th>Metric</th>
                        <th>Value</th>
                    </tr>
                </thead>
                <tbody>
                    {results.methods.cvxpy.core4.metrics.map((value) =>(
                        <tr key= {value.index}>
                            <td>{value.index}</td>
                            <td>{value.Value}</td>
                        </tr>
                    ))}
                </tbody>

            </table>

            <h4>{METHOD_LABELS.hrp.label}</h4>
            <table>
                <thead>
                    <tr>
                        <th>Ticker</th>
                        <th>Weight</th>
                    </tr>
                </thead>
                <tbody>
                    {results.methods.hrp.core4.weights.map((etf) =>(
                        <tr key= {etf.ETF}>
                            <td>{etf.ETF}</td>
                            <td>{formatPercent(etf.Weight)}</td>
                        </tr>
                    ))}
                </tbody>

            </table>
            
            <table>
                <thead>
                    <tr>
                        <th>Metric</th>
                        <th>Value</th>
                    </tr>
                </thead>
                <tbody>
                    {results.methods.hrp.core4.metrics.map((value) =>(
                        <tr key= {value.index}>
                            <td>{value.index}</td>
                            <td>{value.Value}</td>
                        </tr>
                    ))}
                </tbody>

            </table>

        </div>
    );
}



export default SavedPortfoliosPage