import { useState } from "react";
import { savePortfolio } from "../config/portfolios";

// type:    "optimize" | "evaluate"
// inputs:  the form values that produced this result
// results: the API response to store
function SavePortfolioButton({ type, inputs, results }){
    const [open, setOpen] = useState(false);
    const [name, setName] = useState("");
    const [status, setStatus] = useState("");   // "", "saving", "saved", or an error message

    async function handleSave(){
        if (!name.trim()) {
            setStatus("Enter a name.");
            return;
        }
        setStatus("saving");
        try {
            await savePortfolio(name.trim(), type, inputs, results);
            setStatus("saved");
            setOpen(false);
            setName("");
        } catch (e) {
            setStatus(e.message);   // e.g. "You must be logged in to save."
        }
    }

    // Collapsed state: just the button.
    if (!open) {
        return (
            <div className="save-portfolio">
                <button onClick={() => setOpen(true)}>Save Your Portfolio</button>
                {status === "saved" && <span className="saved-note">Saved ✓</span>}
            </div>
        );
    }

    // Expanded state: name field + confirm/cancel.
    return (
        <div className="save-portfolio">
            <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Portfolio name"
            />
            <button onClick={handleSave} disabled={status === "saving"}>
                {status === "saving" ? "Saving…" : "Save"}
            </button>
            <button onClick={() => { setOpen(false); setStatus(""); }}>Cancel</button>
            {status && status !== "saving" && <p className="error">{status}</p>}
        </div>
    );
}

export default SavePortfolioButton;
