import pandas as pd
from sqlalchemy import create_engine, text
import urllib
from pathlib import Path

def upload_to_sql_db():
    # Configuration
    server = 'freedbserver2433.database.windows.net'
    database = '2433-db'
    username = 'yy'
    password = '123abc!!!'
    driver = '/opt/homebrew/lib/libmsodbcsql.17.dylib'
    
    # Connection string
    params = urllib.parse.quote_plus(
        f'DRIVER={{{driver}}};SERVER={server};PORT=1433;DATABASE={database};UID={username};PWD={password}'
    )
    conn_str = f'mssql+pyodbc:///?odbc_connect={params}'
    
    try:
        engine = create_engine(conn_str)
        print("Successfully created engine.")
        
        # Define files to upload
        base_dir = Path(__file__).resolve().parent.parent
        files_to_upload = [
            {
                "path": base_dir / "Part3/2433_p3_data/KFF_data/exports/kff_combined_2018_2026.csv",
                "table_name": "kff_combined_raw",
                "schema": "datalake"
            },
            {
                "path": base_dir / "Part3/2433_p3_data/healthcare.gov/exports/aggregated/aggregated_all_years.csv",
                "table_name": "cdc_aggregated_raw",
                "schema": "datalake"
            }
        ]
        
        # Create schema if not exists (needs raw connection or separate execution)
        with engine.connect() as connection:
            connection.execute(text("IF NOT EXISTS (SELECT * FROM sys.schemas WHERE name = 'datalake') EXEC('CREATE SCHEMA datalake')"))
            connection.commit()
            print("Ensured 'datalake' schema exists.")

        for file_info in files_to_upload:
            file_path = file_info["path"]
            table_name = file_info["table_name"]
            schema = file_info["schema"]
            
            if file_path.exists():
                print(f"Reading {file_path.name}...")
                df = pd.read_csv(file_path)
                
                print(f"Uploading to {schema}.{table_name}...")
                df.to_sql(
                    table_name, 
                    engine, 
                    schema=schema, 
                    if_exists='replace', 
                    index=False,
                    chunksize=1000 # Upload in chunks to avoid timeouts
                )
                print(f"Successfully uploaded {table_name}.")
            else:
                print(f"File not found: {file_path}")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    upload_to_sql_db()
