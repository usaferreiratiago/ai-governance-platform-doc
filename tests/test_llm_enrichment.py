import json

def test_average_price_has_synonyms():
    data = json.load(open('llm_enrichment/output/enriched_measures.json'))

    target = next(x for x in data if x['measure'] == 'Average Unit Price')

    assert 'average ticket' in target['llm_enrichment']