from mcp.gemini_client import ask_gemini 

TEMPLATE = """ 
You are a Power BI semantic modeling expert.
Explain this DAX measure in business language and provide
synonyms. 

DAX: 
{dax} 
""" 
def generate_description(dax: str) -> str:
    return ask_gemini(TEMPLATE.format(dax=dax))