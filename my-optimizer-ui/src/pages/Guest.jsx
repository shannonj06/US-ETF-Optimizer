import {useNavigate} from 'react-router-dom';

function GuestPage(){
    const navigate = useNavigate();
    return(
    <div className='guestPage'>
        <h1>Continue as Guest</h1>
        <button onClick={() => navigate("/build")}>Get Started</button>
    </div>
    );
}

export default GuestPage;
