"""Version 2 audit prompt; preserve the frozen v1 parser, gate and artifacts."""

from pathlib import Path

import validation_evidence_audit as audit


ROOT = audit.ROOT
CONFIG = ROOT / 'prompts/validation_evidence_audit_v2.json'
DEFAULT_RUN = 'qwen2.5-3b-validation-evidence-audit-v2'
_v1_protocol = audit.protocol


def render(row, config, tokenizer):
    body = '\n\n'.join(f'Document {i}:\n{doc}' for i, doc in enumerate(row['docs'], 1))
    body += '\n\nQuestion: ' + row['question']
    body += ('\n\nReturn the audit JSON for this exact question. No Markdown. '
             'required_facts, missing_facts and reason are strings. '
             'If refuse, name the missing fact in missing_facts. '
             'Copy short quotes exactly from their numbered documents; for refuse citations may be [].')
    return tokenizer.apply_chat_template([
        {'role': 'system', 'content': config['instruction']},
        {'role': 'user', 'content': body}], tokenize=False, add_generation_prompt=True)


def protocol(args, rows, source_spec, config):
    result = _v1_protocol(args, rows, source_spec, config)
    result['audit_version'] = 2
    result['revision_reason'] = ('v1 smoke 0/9 technical structures; explicit string schema, '
                                 'synthetic format examples and short verbatim quote instructions; '
                                 'unchanged strict parser and 6/9 gate')
    for path in [Path(__file__), CONFIG, ROOT/'scripts/run_validation_evidence_audit_v2.sh',
                 ROOT/'scripts/run_validation_evidence_audit_v2_review.sh']:
        result['code_and_prompt_sha256'][str(path.relative_to(ROOT))] = audit.e.repro.digest_file(path)
    return result


def main():
    # Bind only in this process. No v1 source file, config or protocol is edited.
    audit.CONFIG = CONFIG
    audit.DEFAULT_RUN = DEFAULT_RUN
    audit.render = render
    audit.protocol = protocol
    audit.main()


if __name__ == '__main__':
    main()
