from pymongo import MongoClient
from configuration import MONGODB_URL
from pathlib import Path
import pandas as pd
from update import update

BASE = Path(__file__).resolve().parent
path = BASE / "data_sourcing" / "US_FINAL_ETF.csv"
df = update()

client = MongoClient(MONGODB_URL)
db = client["etf_data"]
collection = db["US_ETF_DATA"]

collection.delete_many({}) #need this so u dont overwrite
collection.insert_many(df.to_dict("records"))

print("success")
