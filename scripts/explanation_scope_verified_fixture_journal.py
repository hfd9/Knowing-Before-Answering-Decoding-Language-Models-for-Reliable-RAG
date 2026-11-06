"""Real tokenizer + temporary synthetic journal integration; never loads a model."""
from contextlib import contextmanager

import explanation_scope_transaction_prototype as transaction


class VerifiedFixtureJournal:
    """Synthetic /tmp-only integration. Not a production collector."""

    def __init__(self, directory, runtime):
        self.base = transaction.SyntheticJournal(directory)
        self.runtime = runtime
        if self.base.plan_sha != runtime.plan_sha:
            raise transaction.JournalBlocked('runtime and journal plan differ')

    @contextmanager
    def locked(self):
        with self.base.locked():
            yield self

    def initialize(self):
        self.base.initialize()

    @staticmethod
    def _outer(record):
        return {'index': record['index'], 'id': record['id'], 'plan_sha256': record['plan_sha256'],
                'prompt_sha256': record['prompt_sha256'], 'output_sha256': record['raw_output_sha256'],
                'output_tokens': record['generated_tokens'], 'ended_with_eos': record['ended_with_eos'],
                'hit_output_limit': record['hit_output_limit'], 'nonempty_output': bool(record['raw_output'].strip()),
                'synthetic_text': record['raw_output'], 'synthetic_token_ids': record['generated_token_ids'],
                'runtime_record': record}

    def _verified(self):
        payload, state = self.base._load()
        records = []
        for index, outer in enumerate(payload['records']):
            record = outer.get('runtime_record')
            try:
                self.runtime.validate_record(record, index)
            except (ValueError, KeyError, TypeError, IndexError) as error:
                raise transaction.JournalBlocked('real-tokenizer record validation failed') from error
            if outer != self._outer(record):
                raise transaction.JournalBlocked('synthetic journal and token-bound record differ')
            records.append(record)
        smoke = None
        if payload['smoke'] is not None:
            smoke = self.runtime.make_smoke_receipt(records)
            if smoke['passed'] != payload['smoke']['passed']:
                raise transaction.JournalBlocked('synthetic and decoded smoke results differ')
        # The base already flags any uncommitted marker; validate only committed records here.
        try:
            check = self.runtime.validate_cache(payload['attempts'][:len(records)], records, smoke)
        except ValueError as error:
            raise transaction.JournalBlocked('committed token-bound cache failed') from error
        return payload, state, records, smoke, check

    def status(self):
        return self._verified()[1]

    def begin(self):
        self._verified()
        return self.base.begin()

    def commit_fixture_tokens(self, token_ids, elapsed_seconds, completed_at):
        payload, state, records, _, _ = self._verified()
        if state['state'] != 'blocked_uncommitted_attempt':
            raise transaction.JournalBlocked('one current-session marker is required')
        if self.base._owned_attempt is None or self.base._owned_attempt != payload['attempts'][-1]:
            raise transaction.JournalBlocked('old or foreign marker cannot be committed')
        if len(records) >= 4 and (payload['smoke'] is None or not payload['smoke']['passed']):
            raise transaction.JournalBlocked('cannot skip the technical smoke')
        try:
            record = self.runtime.make_record(len(records), token_ids, elapsed_seconds, completed_at)
        except ValueError as error:
            raise transaction.JournalBlocked('invalid fabricated token sequence') from error
        if self.base._owned_attempt != {k: record[k] for k in ('index', 'id', 'plan_sha256')}:
            raise transaction.JournalBlocked('attempt and input do not match')
        # A single atomic replacement contains both declared metadata and the full token-bound record.
        new_records = payload['records'] + [self._outer(record)]
        transaction._atomic_replace(self.base.root / 'records.json',
            {'synthetic': True, 'plan_sha256': self.base.plan_sha, 'records': new_records})
        self.base._owned_attempt = None
        return record

    def check_smoke(self):
        self._verified()
        result = self.base.check_smoke()
        self._verified()
        return result

    def complete_fixture_review(self):
        payload, state, records, smoke, _ = self._verified()
        if state['state'] != 'synthetic_complete':
            raise transaction.JournalBlocked('complete validated synthetic journal required')
        artifacts = self.runtime.review_artifacts(payload['attempts'], records, smoke)
        artifacts['synthetic_fixture_only'] = True
        return artifacts
