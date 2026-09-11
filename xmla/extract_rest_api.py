import requests
import json
from msal import ConfidentialClientApplication

TENANT_ID = '...'
CLIENT_ID = '...'
CLIENT_SECRET = '...'

app = ConfidentialClientApplication(
    CLIENT_ID,
    authority=f'https://login.microsoftonline.com/{TENANT_ID}',
    client_credential=CLIENT_SECRET,
)

token = app.acquire_token_for_client(
    scopes=['https://analysis.windows.net/powerbi/api/.default']
)

headers = {'Authorization': f"Bearer {token['access_token']}"}

url = 'https://api.powerbi.com/v1.0/myorg/groups'
resp = requests.get(url, headers=headers)

with open('metadata/raw/workspaces.json', 'w') as f:
    json.dump(resp.json(), f, indent=2)

print('Workspace metadata exported')