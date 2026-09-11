FORBIDDEN_TERMS = ["salary", "ssn", "cpf", "passport", "email"]

def validate_question(question: str):
    q = question.lower()
    for term in FORBIDDEN_TERMS:
        if term in q:
            return False, f"Forbidden term: {term}"
    return True, "OK"