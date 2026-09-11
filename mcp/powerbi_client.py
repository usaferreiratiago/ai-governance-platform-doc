import requests
from msal import ConfidentialClientApplication

class PowerBIClient:
    def __init__(self, tenant_id, client_id, client_secret):
        self.app = ConfidentialClientApplication(
            client_id,
            authority=f'https://login.microsoftonline.com/{tenant_id}',
            client_credential=client_secret,
        )

    def token(self):
        result = self.app.acquire_token_for_client(
            scopes=['https://analysis.windows.net/powerbi/api/.default']
        )
        return result['access_token']

    def execute_query(self, dataset_id, dax_query):
        url = f'https://api.powerbi.com/v1.0/myorg/datasets/{dataset_id}/executeQueries'
        headers = {
            'Authorization': f'Bearer {self.token()}',
            'Content-Type': 'application/json',
        }
        payload = {'queries': [{'query': dax_query}]}
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()