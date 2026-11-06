"""Guarded production-path implementation; the frozen plan always denies collection."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

import explanation_scope_cache_writer_fixture as cache
import explanation_scope_disk_cache as disk
import explanation_scope_generation_fixture as generation
import explanation_scope_transaction_prototype as transaction


FINGERPRINT_SHA256 = 'ad5c7da3292dcfff58b12eec323f029401eb13e21c55119440ba82279bb01aeb'


class ProductionCacheWriter(cache._CacheWriterCore):
    """Production manifest and fixed run location, behind the current denying guard."""

    def __init__(self, runtime):
        runtime.assert_collection_disabled()
        directory = disk.DEFAULT_RUN
        if directory.is_symlink() or not directory.is_dir():
            raise transaction.JournalBlocked('production run must be an existing non-symlink directory')
        super().__init__(directory, runtime, synthetic_fixture=False)

    @contextmanager
    def locked(self):
        self.runtime.assert_collection_disabled()
        with super().locked():
            yield self

    def _require_lock(self):
        self.runtime.assert_collection_disabled()
        super()._require_lock()

    def commit_tokens(self, tokens, elapsed_seconds, completed_at):
        return self._commit_tokens(tokens, elapsed_seconds, completed_at)


def _open_run(runtime):
    """Create only the fixed run directory, and never repair a prior partial creation."""
    runtime.assert_collection_disabled()
    parent = disk.DEFAULT_RUN.parent
    if parent.is_symlink() or not parent.is_dir() or parent.resolve() != (disk.ROOT / 'runs').resolve():
        raise transaction.JournalBlocked('run parent must be the existing project runs directory')
    root = disk.DEFAULT_RUN
    if root.is_symlink():
        raise transaction.JournalBlocked('run directory cannot be a symlink')
    try:
        os.mkdir(root, 0o700)
        created = True
        transaction._fsync_dir(parent)
    except FileExistsError:
        created = False
    return ProductionCacheWriter(runtime), created


def _verify_input_snapshot(runtime):
    raw = disk.INPUT_FINGERPRINTS.read_bytes()
    if hashlib.sha256(raw).hexdigest() != FINGERPRINT_SHA256:
        raise ValueError('archived input fingerprint file changed')
    expected = json.loads(raw)
    current = runtime.input_summary()
    if any(current[key] != expected[key] for key in current):
        raise ValueError('current 48 inputs or tokenizer metadata differ from archived fingerprints')
    for name, sha in expected['historical_implementation_sha256'].items():
        path = Path(name)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('invalid implementation fingerprint path')
        if hashlib.sha256((disk.ROOT / path).read_bytes()).hexdigest() != sha:
            raise ValueError('historical implementation changed: ' + name)


def _verify_model_files(runtime):
    files = runtime.reference['model_files_sha256']
    expected_names = {'config.json', 'model.safetensors.index.json', 'tokenizer.json',
                      'tokenizer_config.json', 'generation_config.json',
                      'model-00001-of-00002.safetensors', 'model-00002-of-00002.safetensors'}
    if set(files) != expected_names:
        raise ValueError('model fingerprint inventory differs')
    for name, expected in files.items():
        digest = hashlib.sha256()
        with (runtime.model_dir / name).open('rb') as stream:
            for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
                digest.update(chunk)
        if digest.hexdigest() != expected:
            raise ValueError('model file fingerprint differs: ' + name)


def _verify_device():
    # Query before initializing CUDA, so this process cannot mistake itself for an existing job.
    gpu = os.environ.get('CUDA_VISIBLE_DEVICES', '0')
    result = subprocess.run(['nvidia-smi', '-i', gpu, '--query-compute-apps=pid,process_name,used_memory',
                             '--format=csv,noheader'], capture_output=True, text=True, check=True)
    if result.stdout.strip():
        raise RuntimeError('GPU has active compute processes')
    import torch

    if not torch.cuda.is_available() or torch.cuda.device_count() != 1 or not torch.cuda.is_bf16_supported():
        raise RuntimeError('one visible CUDA device with bfloat16 support is required')


def _model_device(model):
    import torch

    device = torch.device(model.device)
    if device.type != 'cuda' or device.index not in (None, 0):
        raise ValueError('production model must reside on the sole visible CUDA device')
    return device


def _generate_one(runtime, writer, model):
    import torch

    state = writer.status()
    if state['state'] != 'validated_prefix':
        raise transaction.JournalBlocked('generation requires an intact prefix')
    index = state['records']
    item_id = runtime.plan['ordered_ids'][index]
    prepared = runtime.generation_input(item_id)
    config = generation._config(runtime)
    device = _model_device(model)
    if (model.generation_config.eos_token_id != runtime.eos_ids
            or model.generation_config.bos_token_id != config.bos_token_id):
        raise ValueError('loaded model generation configuration differs')
    input_ids = torch.tensor([prepared['input_ids']], dtype=torch.long, device=device)
    attention_mask = torch.ones_like(input_ids)
    expected_ids, expected_mask = input_ids.clone(), attention_mask.clone()
    if input_ids.shape[1] + config.max_new_tokens > model.config.max_position_embeddings:
        raise ValueError('input and output exceed model context')
    marker = writer.begin()
    if marker['id'] != item_id or marker['index'] != index:
        raise transaction.JournalBlocked('attempt and input differ')
    torch.cuda.synchronize(device)
    started = time.monotonic()
    with torch.inference_mode():
        output = model.generate(input_ids=input_ids, attention_mask=attention_mask,
                                generation_config=config, logits_to_keep=1)
    torch.cuda.synchronize(device)
    elapsed = time.monotonic() - started
    if not torch.equal(input_ids, expected_ids) or not torch.equal(attention_mask, expected_mask):
        raise ValueError('model mutated the bound input')
    if not isinstance(output, torch.Tensor):
        raise ValueError('model output must be a tensor')
    tokens = generation._extract(output.detach().to('cpu'), expected_ids.to('cpu'))
    return writer.commit_tokens(tokens, elapsed, datetime.now(timezone.utc).isoformat())


def collect(runtime):
    """Run only if a future reviewed protocol replaces the currently denying gate."""
    runtime.assert_collection_disabled()  # Before run directory, weights, device or model access.
    _verify_input_snapshot(runtime)
    writer, created = _open_run(runtime)
    with writer.locked():
        if created:
            writer.initialize()
        state = writer.status()
        if state['state'] == 'awaiting_technical_smoke':
            writer.check_smoke()
            state = writer.status()
        if state['state'] == 'validated_complete_unreviewed':
            return state
        if state['state'] != 'validated_prefix':
            raise transaction.JournalBlocked('production cache blocked: ' + state['state'])
        _verify_model_files(runtime)
        _verify_device()
        runtime.assert_collection_disabled()
        import evidence_experiment as renderer
        model = renderer.load_model(str(runtime.model_dir))
        try:
            while True:
                runtime.assert_collection_disabled()
                state = writer.status()
                if state['state'] == 'validated_complete_unreviewed':
                    return state
                if state['state'] != 'validated_prefix':
                    raise transaction.JournalBlocked('production cache blocked: ' + state['state'])
                _generate_one(runtime, writer, model)
                state = writer.status()
                if state['state'] == 'awaiting_technical_smoke':
                    writer.check_smoke()
        finally:
            del model
