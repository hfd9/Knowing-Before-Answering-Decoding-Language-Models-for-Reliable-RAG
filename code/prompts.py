"""Render the released P0--P5 templates as plain text.

The original renderer was not released. This implementation preserves all
documents, uses the JSON template verbatim, and does not add a chat wrapper.
MAX_DOC_TOKENS is only the original SAD span-matching default.
"""

import json
from pathlib import Path

TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "prompts" / "prompt_robustness_P0_P5.json"
TEMPLATES = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
MAX_DOC_TOKENS = 256
REFUSE_STRING = "Not enough information."
CONFLICT_STRING = "Documents contain conflicting information."
DECODE_CFG = {
    "max_new_tokens": 64,
    "do_sample": False,
    "temperature": 1.0,
    "top_p": 1.0,
    "repetition_penalty": 1.0,
}


def render_prompt(template, question, docs, instruction=None, tokenizer=None):
    if template not in TEMPLATES:
        raise ValueError(f"Unknown template {template!r}; choose from {list(TEMPLATES)}")
    spec = TEMPLATES[template]
    system = spec["system"] if instruction is None else instruction
    parts = [system + "\n\n"] if system else []
    if spec["pre_docs"]:
        parts.append(spec["pre_docs"].format(question=question) + "\n\n")
    for idx, doc in enumerate(docs, start=1):
        if not isinstance(doc, str):
            raise TypeError("Documents must be strings.")
        parts.append(spec["doc_prefix"].format(i=idx, doc=doc))
    parts.append(spec["suffix"].format(question=question))
    return "".join(parts)
