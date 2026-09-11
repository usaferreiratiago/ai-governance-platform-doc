from pathlib import Path

# Directory that stores prompt files
PROMPTS_DIR = Path('prompts')
PROMPTS_DIR.mkdir(exist_ok=True)

PROMPT_FILE = PROMPTS_DIR / 'system_prompt_v1.md'

DEFAULT_PROMPT = '''You are an enterprise analytics assistant.

Rules:
- Answer only using approved semantic model metadata.
- Use business terminology instead of technical field names.
- If the question is ambiguous, ask for clarification.
- Do not invent measures, tables, or values.
- Prefer approved DAX measures when available.
- Keep responses concise and business-oriented.
'''

def load_prompt() -> str:
    """Load the current system prompt from disk."""
    if PROMPT_FILE.exists():
        return PROMPT_FILE.read_text(encoding='utf-8')

    # Create default prompt on first run
    PROMPT_FILE.write_text(DEFAULT_PROMPT, encoding='utf-8')
    return DEFAULT_PROMPT

def save_prompt(prompt: str) -> None:
    """Persist the system prompt to disk."""
    PROMPT_FILE.write_text(prompt.strip(), encoding='utf-8')

def get_prompt_path() -> str:
    """Return the current prompt file path."""
    return str(PROMPT_FILE)