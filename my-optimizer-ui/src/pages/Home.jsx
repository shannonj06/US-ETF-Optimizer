import {useNavigate} from 'react-router-dom'

function Header(){
    return(
        <h1>InvestMint</h1>
    );
}
function GuestPanel(){
    const navigate =useNavigate();
    return(
        <section className="panel">
            <button onClick={() => navigate("/Guest")}>Continue as Guest</button>
        </section>
    );
}
function CreateAccountPanel(){
    const navigate = useNavigate();
    return(
        <section className="panel">
            <button onClick={() => navigate("/CreateAccount")}>Create Account</button>
        </section>
    );
}
function LoginPanel(){
    const navigate = useNavigate();
    return(
        <section className="panel">
            <button onClick={() => navigate("/Login")}>Login</button>
        </section>
    )
}

function IntroBlurb(){
    return(
        <p>Build an optimized ETF porfolio, or evaluate one you already hold.
            Log in to begin.</p>
    );
}
function HomePage(){
    return(
    <div className="home-page">
        <Header />
        <main className="home-main">
            <IntroBlurb />
        </main>
        <div className="action-panels">
            <LoginPanel />
            <CreateAccountPanel />
            <GuestPanel />
        </div>
    </div>
    );
}
export default HomePage;