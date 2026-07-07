import { use, useState } from "react";

function InputEtfsPage(){
    return(
    <div className='Input Your Portfolio'>
        <h1>Use Existing ETFs</h1>
    </div>
    );
}
function AddHoldings(){
    return(
    <div> 
        <p>
            <span className="step-number">1</span>
            Add your Holdings
        </p>
        <p className="text-blurb">Add a ticker for each ETF you hold, weights
            are normalized automatically
        </p>

        <button className= "add-ticker-button"onClick={addTicker}>Add Ticker</button>
    </div> 
    );
    }

function addTicker(){

}

function Settings(){
    const [history, setHistory] = useState("5y");
    const [riskfree, setRiskFree] = useState(.04);
    return(
    <div> 
        <p>
            <span className="step-number">2</span>
            Settings <span className="option">optional</span>
        </p>
        <div className="history-window">
            <p>History Window</p>
            <select value ={history} onChange={(e) => setHistory(e.target.value)}>
                <option value="1y">1y</option>
                <option value="2y">2y</option>
                <option value="3y">3y</option>
                <option value="4y">4y</option>
                <option value="5y">5y</option>
            </select>
        </div>
        <div className="Risk-free_rate">
            <p>Risk Free Rate</p>
            <input
            type="number"
            step=".01"
            value={riskfree}
            onChange={(e)=>setRiskFree(Number(e.target.value))} />
        </div>
    </div>
    );
}

export default InputEtfsPage;
