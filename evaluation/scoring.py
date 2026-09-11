def exact_match(predicted, expected):
    return str(predicted).strip().lower() == str(expected).strip().lower()