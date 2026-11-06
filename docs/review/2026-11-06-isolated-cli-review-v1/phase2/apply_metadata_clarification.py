"""Apply only the user-authorized receipt-to-form metadata mapping.

Retain both original review programs. The derived validator changes only the
receipt-field mapping; it rechecks the existing semantic artifact unchanged.
"""
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

def load(name):
    return json.loads(Path(name).read_text())

def sha(name):
    return hashlib.sha256(Path(name).read_bytes()).hexdigest()

def preserve(source, destination):
    data = Path(source).read_bytes()
    target = Path(destination)
    if target.exists():
        assert target.read_bytes() == data, 'Existing backup differs; refusing to overwrite.'
    else:
        with target.open('xb') as stream:
            stream.write(data)
    assert target.read_bytes() == data
    return data

seal = load('input_seal.json')
baseline = load('stage2_preservation_baseline.json')
assert all(sha(name) == digest for name, digest in baseline.items())
assert sha('input_review.json') == seal['input_review_sha256']
assert seal['sealed_at'] == '2026-11-06T02:44:42.913163+00:00'
assert 'input_review_completed_at' not in seal
immutable_names = ['input_seal.json', 'author_claim_review.py', 'validate_claim_review.py', 'output_reading_log.json']
immutable_before = {name: sha(name) for name in immutable_names}
old_bytes = preserve('claim_review.json', 'claim_review.before_metadata.json')
preserve('output_context.json', 'output_context.before_metadata.json')
preserve('output_validation_report.json', 'output_validation_report.before_metadata.json')
old = json.loads(old_bytes)
assert old['sealed_input_review_completed_at'] is None
old_report = load('output_validation_report.before_metadata.json')

# Byte substitution preserves all other text, including every original item row.
needle = b'"sealed_input_review_completed_at": null'
assert old_bytes.count(needle) == 1
replacement = ('"sealed_input_review_completed_at": ' + json.dumps(seal['sealed_at'])).encode()
new_bytes = old_bytes.replace(needle, replacement, 1)
new = json.loads(new_bytes)
assert new['items'] == old['items']
assert set(new) == set(old)
assert [key for key in old if old[key] != new[key]] == ['sealed_input_review_completed_at']
assert new['sealed_input_review_completed_at'] == seal['sealed_at']
Path('claim_review.json').write_bytes(new_bytes)

now = datetime.now(timezone(timedelta(hours=8))).isoformat()
context = load('output_context.json')
context['sealed_input_review_completed_at'] = seal['sealed_at']
context['seal_completion_metadata_status'] = 'resolved_by_schema_clarification: sealed_input_review_completed_at = input_seal.json.sealed_at'
context['metadata_clarified_at'] = now
context['metadata_clarification'] = {
    'source': 'metadata_clarification.md',
    'mapping': 'sealed_input_review_completed_at = input_seal.json.sealed_at',
    'receipt_unchanged': True,
    'stage1_completion_time_preserved_separately': True,
    'claim_review_items_changed': False,
    'semantic_feedback_received': False,
    'claims_rejudged': False
}
context['exposure_description'] += ' Metadata clarification: metadata_clarification.md supplies only the canonical receipt-to-form mapping, using sealed_at for sealed_input_review_completed_at. It supplies no author ratings or semantic feedback. The receipt, all stage-1 files, and every answer-review item and judgment remain unchanged.'
Path('output_context.json').write_text(json.dumps(context, ensure_ascii=False, indent=2) + '\n')

# Preserve the original validator as provenance; derive a schema-corrected copy.
validator = Path('validate_claim_review.py').read_text()
old_test = "seal_time_present='input_review_completed_at' in seal and isinstance(seal['input_review_completed_at'],str)"
new_test = "seal_time_present='sealed_at' in seal and isinstance(seal['sealed_at'],str)"
assert validator.count(old_test) == 1
validator = validator.replace(old_test, new_test)
validator = validator.replace("==seal['input_review_completed_at']", "==seal['sealed_at']")
validator = validator.replace(
    'input_seal.json omits input_review_completed_at; the required sealed_input_review_completed_at remains null rather than being invented or copied from a different source. A clarification request was sent.',
    'input_seal.json omits sealed_at, the canonical source for sealed_input_review_completed_at under metadata_clarification.md.')
Path('validate_claim_review_metadata.py').write_text(
    '# Derived from the preserved validate_claim_review.py; only receipt-field mapping is corrected.\n' + validator)
subprocess.run([sys.executable, 'validate_claim_review_metadata.py'], check=True, capture_output=True, text=True)

# Explicit metadata-only validation, in addition to the complete original checks.
assert Path('claim_review.json').read_bytes() == new_bytes
assert Path('claim_review.before_metadata.json').read_bytes() == old_bytes
assert load('claim_review.json')['items'] == load('claim_review.before_metadata.json')['items']
assert all(sha(name) == digest for name, digest in baseline.items())
assert all(sha(name) == digest for name, digest in immutable_before.items())
report = load('output_validation_report.json')
assert report['validation_passed'] is True
assert report['counts'] == old_report['counts']
assert report['claim_review_sha256'] == sha('claim_review.json')
report['metadata_clarification'] = {
    'source': 'metadata_clarification.md',
    'canonical_mapping': 'sealed_input_review_completed_at = input_seal.json.sealed_at',
    'canonical_value': seal['sealed_at'],
    'previous_schema_interpretation_resolved': True,
    'only_claim_review_field_changed': 'sealed_input_review_completed_at',
    'all_55_original_item_rows_exactly_equal': True,
    'original_item_row_bytes_preserved': True,
    'all_endpoints_judgments_and_citations_unchanged': True,
    'original_manually_authored_program_unchanged': True,
    'original_validator_preserved': True,
    'input_seal_unchanged': True,
    'stage1_files_unchanged': True
}
report['checks_passed'] += [
    'canonical completion-time mapping exactly matches input_seal.json.sealed_at',
    'claim-review byte difference is exactly one top-level metadata-value substitution',
    'all 55 original item rows and all semantic review counts exactly equal the preserved prior form',
    'original review program, original validator, reading log, and immutable receipt unchanged'
]
Path('output_validation_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
provenance = {
    'updated_at': now,
    'validation_passed': True,
    'claim_review_before_sha256': hashlib.sha256(old_bytes).hexdigest(),
    'claim_review_after_sha256': sha('claim_review.json'),
    'changed_claim_review_fields': ['sealed_input_review_completed_at'],
    'canonical_value': seal['sealed_at'],
    'original_item_rows_equal': True,
    'semantic_counts_unchanged': True,
    'stage1_file_hashes_verified': baseline,
    'other_immutable_file_hashes_verified': immutable_before,
    'preserved_originals': ['claim_review.before_metadata.json', 'output_context.before_metadata.json', 'output_validation_report.before_metadata.json'],
    'semantic_feedback_received': False,
    'claims_rejudged': False
}
Path('metadata_update_report.json').write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({
    'validation_passed': report['validation_passed'],
    'sealed_input_review_completed_at': new['sealed_input_review_completed_at'],
    'item_rows_exactly_equal': len(new['items']),
    'atomic_claims_unchanged': report['counts']['atomic_claims'],
    'stage1_files_unchanged': len(baseline),
    'receipt_unchanged': True,
    'claim_review_sha256': sha('claim_review.json')
}, indent=2))
