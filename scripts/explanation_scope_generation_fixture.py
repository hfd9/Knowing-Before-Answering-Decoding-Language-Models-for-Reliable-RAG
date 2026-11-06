"""CPU-only synthetic model-call exercise; no model loader or production collector."""
from datetime import datetime, timezone
import hashlib
import json
import time

import explanation_scope_cache_writer_fixture as cache
import explanation_scope_ledger_simulator as plan_loader
import explanation_scope_runtime as scope
import explanation_scope_transaction_prototype as transaction


class SyntheticModel:
    """A fixed token concatenator, not a language model or a model wrapper."""

    def __init__(self, token_ids):
        self.token_ids = token_ids

    def generate(self, *, input_ids, attention_mask, generation_config, logits_to_keep):
        import torch

        if input_ids.device.type != 'cpu' or attention_mask.device.type != 'cpu':
            raise ValueError('synthetic generation is CPU-only')
        if input_ids.ndim != 2 or input_ids.shape[0] != 1 or not torch.equal(attention_mask, torch.ones_like(input_ids)):
            raise ValueError('expected one unpadded input and an all-ones attention mask')
        if logits_to_keep != 1:
            raise ValueError('unexpected logits setting')
        suffix = torch.tensor([self.token_ids], dtype=torch.long, device='cpu')
        return torch.cat((input_ids, suffix), dim=1)


def _config(runtime):
    from transformers import GenerationConfig

    plan, plan_sha = plan_loader.load_plan()
    if plan_sha != runtime.plan_sha or plan != runtime.plan:
        raise ValueError('bound plan changed')
    generation = plan['generation']
    if (plan['max_new_tokens'] != 128 or generation['planned_method'] != 'greedy'
            or generation['sample'] is not False):
        raise ValueError('unexpected generation draft')
    data = (runtime.model_dir / 'generation_config.json').read_bytes()
    if hashlib.sha256(data).hexdigest() != runtime.metadata_hashes['generation_config.json']:
        raise ValueError('generation metadata changed')
    model_config = json.loads(data)
    if model_config.get('eos_token_id') != runtime.eos_ids:
        raise ValueError('EOS metadata changed')
    bos = model_config.get('bos_token_id')
    pad = runtime.tokenizer.pad_token_id
    if pad is None:
        pad = runtime.tokenizer.eos_token_id
    if any(type(value) is not int or not 0 <= value < runtime.vocab_size for value in (bos, pad)):
        raise ValueError('invalid BOS or padding token')
    return GenerationConfig(max_new_tokens=128, do_sample=False, num_beams=1, use_cache=True,
                            eos_token_id=runtime.eos_ids, bos_token_id=bos, pad_token_id=pad)


def _extract(output, input_ids):
    import torch

    if (not isinstance(output, torch.Tensor) or output.ndim != 2 or output.shape[0] != 1
            or output.dtype not in (torch.int32, torch.int64) or output.device.type != 'cpu'):
        raise ValueError('invalid synthetic model output tensor')
    n = input_ids.shape[1]
    if output.shape[1] <= n or not torch.equal(output[:, :n], input_ids):
        raise ValueError('synthetic output did not preserve the input token prefix')
    return output[0, n:].tolist()


def run_one(runtime, writer, model):
    """Commit one fixture only; a failed generation leaves its attempt uncommitted."""
    import torch

    # No arbitrary model, production writer, GPU device, or run directory is accepted.
    if type(writer) is not cache.FixtureCacheWriter or type(model) is not SyntheticModel:
        raise TypeError('synthetic writer and synthetic model required')
    if type(runtime) is not scope.Runtime or writer.runtime is not runtime:
        raise TypeError('writer must be bound to the supplied runtime')
    state = writer.status()
    if state['state'] != 'validated_prefix':
        raise transaction.JournalBlocked('fixture cannot generate: ' + state['state'])
    index = state['records']
    item_id = runtime.plan['ordered_ids'][index]
    inputs = runtime.generation_input(item_id)
    config = _config(runtime)
    input_ids = torch.tensor([inputs['input_ids']], dtype=torch.long, device='cpu')
    attention_mask = torch.ones_like(input_ids)
    expected_input_ids = input_ids.clone()
    expected_attention_mask = attention_mask.clone()
    if input_ids.shape[1] + config.max_new_tokens > runtime.reference['context_tokens']:
        raise ValueError('input and output budget exceed context')
    marker = writer.begin()
    if marker['id'] != item_id or marker['index'] != index:
        raise transaction.JournalBlocked('attempt does not match prepared input')
    started = time.monotonic()
    with torch.inference_mode():
        output = model.generate(input_ids=input_ids, attention_mask=attention_mask,
                                generation_config=config, logits_to_keep=1)
    elapsed = time.monotonic() - started
    if not torch.equal(input_ids, expected_input_ids) or not torch.equal(attention_mask, expected_attention_mask):
        raise ValueError('synthetic model mutated the prepared inputs')
    token_ids = _extract(output, expected_input_ids)
    return writer.commit_fixture_tokens(token_ids, elapsed, datetime.now(timezone.utc).isoformat())


def production_generate(runtime):
    """No production implementation exists and the current frozen plan must deny it."""
    runtime.assert_collection_disabled()
    raise AssertionError('unreachable while collection is disabled')
