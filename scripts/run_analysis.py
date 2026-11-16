import os
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

#change the below path to the provided path
config_path = r"Z:\User_Code\configFile.env"

load_dotenv(config_path)

sql_driver = os.getenv("SQL_DRIVER")
sql_server = os.getenv("SQL_SERVER")
sql_database = os.getenv("SQL_DATABASE")
sql_encrypt = os.getenv("SQL_ENCRYPT")
sql_trust_cert = os.getenv("SQL_TRUST_CERT")
sql_timeout = os.getenv("SQL_TIMEOUT")

# Create SQLAlchemy connection URL for Windows Authentication
connection_url = URL.create(
    "mssql+pyodbc",
    query={
        "driver": sql_driver,
        "trusted_connection": "yes",
        "TrustServerCertificate": sql_trust_cert,
        "Connection Timeout": sql_timeout
    },
    host=sql_server,
    database=sql_database
)

# Create engine
engine = create_engine(connection_url)

print("SQLAlchemy engine created")

#Dont change the above configuration write your code from below onwards.
#Changing the above configuration may result incorrect data.

with engine.connect() as conn:
    result = conn.execute(text("SELECT SYSTEM_USER, DB_NAME()"))
    print(result.fetchone())
	
query = """
SELECT 
    TABLE_SCHEMA,
    TABLE_NAME
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_TYPE = 'BASE TABLE'
ORDER BY TABLE_SCHEMA, TABLE_NAME
"""

tables_df = pd.read_sql(query, engine)

print(tables_df)

# MY CODE

# Everything above this line is the Bradford-supplied setup code,
# Edit analysis_settings.py
# This file runs the REAL SQL analysis and MUST remain in the secure environment.

from configuration import load_settings
from analysis_runner import run_pipeline
import sys


if __name__ == "__main__":
    selected_settings = sys.argv[1] if len(sys.argv) > 1 else "analysis_settings"
    if len(sys.argv) > 2:
        raise SystemExit("Usage: python run_analysis.py [analysis_settings_module]")
    study_settings = load_settings(selected_settings)
    try:
        run_pipeline(study_settings, mode="secure", engine=engine)
    finally:
        engine.dispose()
