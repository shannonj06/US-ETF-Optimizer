import {useNavigate} from 'react-router-dom';
import {useState} from 'react';


function LoginPanel(){
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    return(
        <form onSubmit={handleSubmit}>
            <h1>Login</h1>
            <input type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
            <input type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} />
            <button type="submit">Login</button>
        </form>
    );}

function handleSubmit(event) {
    const navigate = useNavigate();
    event.preventDefault();}

export default LoginPanel;

