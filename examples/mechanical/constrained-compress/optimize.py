# WECO-MUTABLE: only PROMPT may be edited by the loop
PROMPT = "Please classify the user message carefully and thoroughly with lots of extra words."

def classify(text: str) -> str:
    # Toy: label is POSITIVE if 'good' in text else NEGATIVE
    return "POSITIVE" if "good" in text.lower() else "NEGATIVE"
