from google.cloud import bigquery
import os

PROJECT_ID = os.getenv('BQ_PROJECT_ID', 'client-project')

client = bigquery.Client(project=PROJECT_ID)

def run_query(sql: str):
    job = client.query(sql)
    return job.result().to_dataframe()