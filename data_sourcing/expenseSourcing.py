import pandas as pd
import time
import yfinance as yf
from pathlib import Path
INPUT_FILE    = "US_Final_ETF_Data.csv"           # <-- your file (.csv or .xlsx)
TICKER_COLUMN = "Symbol"                # <-- the column that holds the tickers

BASE_DIR = Path(__file__).resolve().parent.parent.parent
csv_path = BASE_DIR / "US_Final_ETF_Data.csv"

df = pd.read_csv(csv_path)


# --- loop through every ticker in the dataframe ---
expense_ratios = []
sources        = []
seen           = {}      # remember tickers we already looked up (saves API calls)

for i, raw in enumerate(df[TICKER_COLUMN]):
    ticker = str(raw).strip().upper()

    # already looked this one up? reuse it.
    if ticker in seen:
        er, source = seen[ticker]
        expense_ratios.append(er)
        sources.append(source)
        print(f"{i+1}/{len(df)}  {ticker:8s} -> {er}  (cached)")
        continue

    er, source = None, "not found"

    # look up the expense ratio on yfinance
    try:
        t = yf.Ticker(ticker)
        val = None
        try:
            ov = t.funds_data.fund_overview
            if isinstance(ov, dict):
                for k in ("expense_ratio", "expenseRatio", "annualReportExpenseRatio"):
                    if ov.get(k) not in (None, ""):
                        val = ov[k]
                        break
        except Exception:
            pass
        if val is None:
            info = t.info or {}
            for k in ("annualReportExpenseRatio", "netExpenseRatio", "expenseRatio"):
                if info.get(k) not in (None, ""):
                    val = info[k]
                    break
        if val is not None:
            er = float(val)
            source = "yfinance"
    except Exception:
        pass

    seen[ticker] = (er, source)
    expense_ratios.append(er)
    sources.append(source)
    print(f"{i+1}/{len(df)}  {ticker:8s} -> {er}  ({source})")
    time.sleep(0.25)   # small pause so we don't hammer the API


# --- attach the results and save ---
df["expense_ratio"] = expense_ratios
df["er_source"]     = sources
df.to_csv("etfs_with_er.csv", index=False)

missing = [t for t, (er, _) in seen.items() if er is None]
print("\nDone. Saved -> etfs_with_er.csv")
print(f"{len(missing)} ticker(s) had no expense ratio: {missing}")