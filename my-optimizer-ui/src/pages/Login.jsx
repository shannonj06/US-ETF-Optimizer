import {useNavigate} from 'react-router-dom';
import {useState} from 'react';
import {supabase} from '../config/supabaseClient.js';

function LoginPanel(){
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState("");
    const navigate = useNavigate();
    return(
        <form className= "Login" onSubmit={(event) => handleSubmit(event, email, password, navigate, setError)}>
            <h1>Login</h1>
            <input type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
            <input type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} />
            <p className="hint">Password must be at least 8 characters long and contain at least one number.</p>
            <button type="submit">Login</button>
            {error && <p className="error-message">{error}</p>}
        </form>
    );}

async function handleSubmit(event, email, password, navigate, setError) {
    event.preventDefault();
    setError("");

    if (!email.trim() || !password){
        setError("Please enter both your email and password.");
        return;
    }

    const { data, error } = await supabase.auth.signInWithPassword({ email: email.trim(), password });
    if (error) {
        console.error("Error logging in:", error.message);
        setError(error.message);
        return;
    }

    console.log(data);
    navigate("/build");
}

export default LoginPanel;
