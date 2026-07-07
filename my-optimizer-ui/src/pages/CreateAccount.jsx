import {useNavigate} from 'react-router-dom';
import {useState} from 'react';
import {supabase} from '../config/supabaseClient.js';

function CreateAccountPanel(){
    const navigate = useNavigate();
    const [password, setPassword] = useState("");
    const [email, setEmail] = useState("");
    const [error, setError] = useState("");
    return(
    <form className='createAccount' onSubmit={(event) => createAccount(event, email, password, navigate, setError)}>
        <h1>Create Account</h1>
        <input type='email'
        placeholder='Email'
        value={email}
        onChange={(e) => setEmail(e.target.value)}/>
        <input type="password"
        placeholder='Password'
        value={password}
        onChange={(e)=> setPassword(e.target.value)}/>
        <p className="hint">Password must be at least 8 characters long and contain at least one number.</p>
        <button type='submit'>Create Account</button>
        {error && <p className="error-message">{error}</p>}
    </form>
    );
}

// Returns an error message if the password is invalid, or null if it's valid.
function validatePassword(password){
    if (password.length < 8){
        return "Password must be at least 8 characters long.";
    }
    if (!/[0-9]/.test(password)){
        return "Password must contain at least one number.";
    }
    return null;
}

async function createAccount(event, email, password, navigate, setError){
    event.preventDefault();
    setError("");

    if (!email.trim()){
        setError("Please enter your email.");
        return;
    }

    const passwordError = validatePassword(password);
    if (passwordError){
        setError(passwordError);
        return;
    }

    const {data, error} = await supabase.auth.signUp({email: email.trim(), password});
    if (error){
        setError(error.message);
        console.log(error);
        return;
    }
    console.log(data);
    navigate("/build");
}

export default CreateAccountPanel;
