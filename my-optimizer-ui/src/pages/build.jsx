import {useNavigate} from 'react-router-dom';

function BuildPage(){
    const navigate = useNavigate();
    return(
    <div className='buildPage'>
        <h1>Create Portfolios</h1>
        <div className='buildOption'>
            <h2>Develop a Portfolio</h2>
            <p>Start from a set of ETFs and let us build an optimized allocation for you.</p>
            <button onClick={() => navigate("/PortfolioOptimizer")}>Develop a Portfolio</button>
        </div>
        <div className='buildOption'>
            <h2>Input Your Portfolio</h2>
            <p>Already hold a portfolio? Enter your holdings to evaluate and improve it.</p>
            <button onClick={() => navigate("/inputEtfs")}>Input Your Portfolio</button>
        </div>
    </div> )
}




export default BuildPage