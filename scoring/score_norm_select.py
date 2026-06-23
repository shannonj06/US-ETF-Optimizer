import pandas as pd
from config.style_ranks import STYLE_RANKS
from utils.logger import logger
import numpy as np


def select_top_etfs(data_df: pd.DataFrame, profile: dict, ptype: str, top_n: int = 40) -> pd.DataFrame:
    df = data_df.copy()

    #ensuring numeric data
    numeric_cols = ["AUM", "BETA", "MAX_DD", "AVG_VOLUME_30", 
                    "ANNUAL_VOL", "SHARPE", "ER", "YIELD", "DURATION"]
    for i in numeric_cols:
        df[i] = pd.to_numeric(df[i], errors = "coerce")

    #filtering data based on profile
    df = df[
    (df["AUM"] >= profile[ptype]["aum_min"]) &
    (df["DURATION"] <= profile[ptype]['max_duration']) &
    (df["ER"]/100 <= profile[ptype]["max_expense"])
]
    #outlier clipping
    for col in numeric_cols:
        q01 = df[col].quantile(.01)
        q99 = df[col].quantile(.99)
        df[col] = df[col].clip(lower = q01, upper = q99)

    #Normalizing the data to [0, 1]
    def normalize(series, invert=False):
        lo, hi = series.min(), series.max()
        n = (series - lo) / (hi - lo + 1e-8)
        return 1 - n if invert else n
    
    weights = profile[ptype]["score_weights"]
    #normalizing the data
    df["n_beta"]    = normalize(df["BETA"],          invert=True)   # lower beta = better
    df["n_yield"]   = normalize(df["YIELD"], invert=False)  # higher yield = better
    df["n_liq"]     = normalize(np.log1p(df["AVG_VOLUME_30"]),invert=False)  # higher volume = better
    df["n_aum"]     = normalize(np.log1p(df["AUM"]),           invert=False)  # larger = better
    df["n_ann_vol"] = normalize(df["ANNUAL_VOL"],        invert=True)   # lower vol = better
    df["n_sharpe"]  = normalize(df["SHARPE"],         invert=False)  # higher Sharpe = better
    df['n_expense_ratio'] = normalize(df["ER"], invert = True)

    df["style_rank"] = df["STYLE"].map(STYLE_RANKS[ptype]).fillna(9)
    df["n_style"]    = normalize(df["style_rank"],   invert=True)

    df["score"] = (
    weights.get("beta", 0) * df["n_beta"] +
    weights.get("yield", 0) * df["n_yield"] +
    weights.get("sharpe", 0) * df["n_sharpe"] +
    weights.get("aum", 0) * df["n_aum"] +
    weights.get("liq", 0) * df["n_liq"] +
    weights.get("ann_vol", 0) * df["n_ann_vol"] +
    weights.get("expense", 0) * df["n_expense_ratio"] +
    weights.get("style", 0) * df["n_style"]
)

    top = df.sort_values("score", ascending = False).head(top_n)
   
    logger.info(
    f"Selected top {len(top)} ETFs | Styles: {top['STYLE'].value_counts().to_dict()}"
)

    return top




    





    