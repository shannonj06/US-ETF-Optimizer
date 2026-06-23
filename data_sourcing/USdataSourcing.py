import pandas as pd
import numpy as np
import yfinance as yf
from style_mapping import classify_etf_name
from pathlib import Path
import time
from durationSourcing import get_duration

BASE_DIR = Path(__file__).resolve().parent.parent
excel_path = BASE_DIR / "datasets" / "US_ETF_DF.xlsx - US ETF Data.csv"

us_df = pd.read_csv(excel_path)

us_df.columns = us_df.columns.str.strip()

keep_cols = ["Symbol", "Beta", "AUM", "Name"]

us_df = us_df[keep_cols]
us_df = us_df.rename(columns = {"Beta" : "BETA"})
us_df = us_df.rename(columns = {"AUM": "aum"})
us_df["Symbol"] = (
    us_df["Symbol"]
    .astype(str)
    .str.strip()
    .str.upper()
)

us_df = us_df.dropna(subset=["Symbol", "BETA", "aum"])
us_df = us_df.drop_duplicates(subset=["Symbol"])
us_df = us_df.reset_index(drop=True)

tickers = us_df["Symbol"].unique().tolist()
yf_metrics = {}

for ticker in tickers:

    try:
        etf = yf.Ticker(ticker)
        print(f"Processing {etf}")
        time.sleep(1)
        hist = etf.history(period="1y")

        if hist.empty:
            continue
        info = etf.info

        current_price = hist["Close"].iloc[-1]
        previous_close = hist["Close"].iloc[-2]
        open_price = hist["Open"].iloc[-1]
        day_high = hist["High"].iloc[-1]
        day_low = hist["Low"].iloc[-1]

        #EXPENSE RATIO
        er = np.nan
        # Path 1: the structured fund data (newer yfinance)
        try:
            
            val = None
            ov = etf.funds_data.fund_overview
            if isinstance(ov, dict):
                for k in ("expense_ratio", "expenseRatio", "annualReportExpenseRatio"):
                    if ov.get(k) not in (None, ""):
                        val = ov[k]
                        break
        except Exception:
            pass

        # Path 2: fall back to the general .info dict
        if val is None:
            info = etf.info or {}
            for k in ("annualReportExpenseRatio", "netExpenseRatio", "expenseRatio"):
                if info.get(k) not in (None, ""):
                    val = info[k]
                    break

        if val is not None:
            er = float(val)

        #this is stored as a pandas series, you wanna get the percentage change
        #of each day in the hist from this 1 yr period
        daily_return = hist["Close"].pct_change().dropna()

        ytd_start = pd.Timestamp(
            year=hist.index[-1].year,
            month=1,
            day=1,
            tz=hist.index.tz
        ) #using this as the start date

        ytd_data = hist[hist.index >= ytd_start]

        #gives total return from jan 1 to now
        ytd_return = (
            (
                ytd_data["Close"].iloc[-1]
                / ytd_data["Close"].iloc[0]
            ) - 1
        ) * 100

        #1 month return
        month_start = hist.index[-1] - pd.Timedelta(days=30)
        month_data = hist[hist.index >= month_start]
        month_return = (
            (
                month_data["Close"].iloc[-1]
                / month_data["Close"].iloc[0]
            ) - 1
        ) * 100 if len(month_data) > 1 else np.nan

        #3 month return
        three_month_start = hist.index[-1] - pd.Timedelta(days=90)

        three_month_data = hist[
            hist.index >= three_month_start
        ]

        three_month_return = (
            (
                three_month_data["Close"].iloc[-1]
                / three_month_data["Close"].iloc[0]
            ) - 1
        ) * 100

        #1 year return
        one_year_return = (
            (
                hist["Close"].iloc[-1]
                / hist["Close"].iloc[0]
            ) - 1
        ) * 100

        #Annual return
        annual_return = (
            (1 + daily_return.mean()) ** 252 - 1
        )

        #volatility
        volatility = daily_return.std()

        annualized_volatility = (
            volatility * np.sqrt(252)
        )

        #beta
        beta = info.get("beta", np.nan)

        risk_free_rate = 0.04

        sharpe = (
            (annual_return - risk_free_rate)
            / annualized_volatility
            if annualized_volatility > 0
            else np.nan
        )

        #dividends
        dividends = etf.dividends

        one_year_ago = (
            hist.index[-1]
            - pd.DateOffset(years=1)
        )

        recent_divs = dividends[
            dividends.index >= one_year_ago
        ]
        trailing_dividend = recent_divs.sum()
        dividend_yield = (
            (trailing_dividend / current_price) 
            if current_price > 0
            else np.nan
        )

        AUMs = info.get("totalAssets", np.nan)

        volume = hist["Volume"]
        avg_volume = volume.mean()
        thirty_day_avg_volume = (
            volume.tail(30).mean()
        )

        PEratio = info.get(
            "trailingPE",
            np.nan
        )
        running_max = hist["Close"].cummax()

        drawdown = (
            (hist["Close"] - running_max)
            / running_max
        )

        max_drawdown = drawdown.min()
        expense_ratio = info.get("expenseRatio")

        week_52_high = hist["High"].max()
        week_52_low = hist["Low"].min()

        etf_name = us_df.loc[
        us_df["Symbol"] == ticker,
            "Name"
            ].values[0]

        style = classify_etf_name(etf_name)
        d = get_duration(ticker, etf_name)

        yf_metrics[ticker] = {
            "Symbol": ticker,
            "AUM": round(AUMs, 2) if pd.notna(AUMs)else np.nan,
            "YIELD": round(dividend_yield, 4) if pd.notna(dividend_yield)else np.nan,
            "SHARPE": round(sharpe, 4) if pd.notna(sharpe)else np.nan,
            "MAX_DD": round(max_drawdown, 4) if pd.notna(max_drawdown)else np.nan,
            "ANNUAL_VOL": round(annualized_volatility, 2) if pd.notna(annualized_volatility)else np.nan,
            "STYLE": style,
            "AVG_VOLUME_30": round(thirty_day_avg_volume, 2) if pd.notna(thirty_day_avg_volume)else np.nan,
            "DURATION": d["duration"] if d else np.nan,
            "ER": round(er, 2) if pd.notna(er) else np.nan
        }

    except Exception as e:
        print(f"Error processing {ticker}: {e}")

#final merging of the yfinance data with the old dataframe
yf_df = pd.DataFrame.from_dict(
    yf_metrics,
    orient="index"
).reset_index(drop=True)

#handling overlapping columns
overlapping_cols = (
    set(us_df.columns)
    & set(yf_df.columns)
) - {"Symbol"}


#merged dataframe
merged_df = pd.merge(
    us_df,
    yf_df,
    on="Symbol",
    how="left"
)

merged_df.to_csv(
    "US_Final_ETF_Data.csv",
    index=False
)
print(merged_df.head())
print(merged_df.columns)
print("All files exported successfully.")