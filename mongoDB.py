import certifi
from pymongo import MongoClient
from configuration import MONGODB_URL
from pathlib import Path
from update import update

BASE = Path(__file__).resolve().parent
path = BASE / "data_sourcing" / "US_FINAL_ETF.csv"
df = update(write=False)

client = MongoClient(MONGODB_URL, tlsCAFile=certifi.where())
db = client["etf_data"]
collection = db["US_ETF_DATA"]

collection.delete_many({}) #need this so u dont overwrite
collection.insert_many(df.to_dict("records"))

print("success")
