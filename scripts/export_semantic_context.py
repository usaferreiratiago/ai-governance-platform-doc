import pandas as pd

tables = [{"table": "Sales", "description": "Sales fact table"}]
measures = [{"table": "Sales", "measure": "Net Revenue", "description": "Net revenue excluding taxes"}]

pd.DataFrame(tables).to_csv("semantic-model/tables.csv", index=False)
pd.DataFrame(measures).to_csv("semantic-model/measures.csv", index=False)

print("Semantic context exported")