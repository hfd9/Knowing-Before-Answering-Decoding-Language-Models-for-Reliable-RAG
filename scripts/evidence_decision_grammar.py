"""Token grammar for a finite evidence verdict and source passage identifiers."""


class DecisionGrammar:
    """Constrain the generated JSON itself, with no repair after decoding.

    answer cites 1-4 passages; conflict cites two different documents;
    refuse/unknown cite none. These are source constraints, not entailment checks.
    """

    def __init__(self, tokenizer, spans, eos_ids):
        import json
        self.tokenizer = tokenizer
        self.spans = {s['span_id']: s for s in spans}
        if not self.spans or len(self.spans) != len(spans):
            raise ValueError('Nonempty, unique citation spans required')
        if len({s['doc_id'] for s in spans}) < 2:
            raise ValueError('Conflict needs candidate passages from two documents')
        self.eos_ids = list(eos_ids)
        self.trees = {}
        self.encoded = {}
        headers = [(f'{{"semantic_mode":"{mode}","citation_ids":[', mode)
                   for mode in ['answer', 'refuse', 'conflict', 'unknown']]
        self.header = self._trie(headers)
        self.citations = [(json.dumps(key), key) for key in self.spans]
        for text, _ in self.citations:
            self._encode(text)
        self.maximum_tokens = (max(len(self._encode(s)) for s, _ in headers)
                               + 4*max(len(self._encode(s)) for s, _ in self.citations)
                               + 3*len(self._encode(',')) + len(self._encode(']}')) + 1)

    def _encode(self, text):
        if text not in self.encoded:
            ids = self.tokenizer(text, add_special_tokens=False)['input_ids']
            if not ids or set(ids) & set(self.eos_ids):
                raise ValueError('Invalid grammar token sequence')
            if self.tokenizer.decode(ids, skip_special_tokens=False) != text:
                raise ValueError('Tokenizer cannot losslessly encode grammar segment')
            self.encoded[text] = list(ids)
        return self.encoded[text]

    def _trie(self, choices):
        root = {}
        for text, value in choices:
            node = root
            for token in self._encode(text):
                if None in node:
                    raise ValueError('Grammar segment choices must be prefix-free')
                node = node.setdefault(token, {})
            if node:
                raise ValueError('Duplicate or prefix-overlapping grammar choices')
            node[None] = value
        return root

    def _tree(self, phase, mode, chosen):
        key = (phase, mode, tuple(chosen))
        if key not in self.trees:
            if phase == 'cite':
                choices = [(text, value) for text, value in self.citations if value not in chosen
                           and (mode != 'conflict' or not chosen
                                or self.spans[value]['doc_id'] != self.spans[chosen[0]]['doc_id'])]
            elif phase == 'after':
                if mode == 'conflict' and len(chosen) == 1:
                    choices = [(',', 'more')]
                elif mode == 'answer' and len(chosen) < 4 and len(chosen) < len(self.spans):
                    choices = [(']}', 'end'), (',', 'more')]
                else:
                    choices = [(']}', 'end')]
            elif phase == 'close':
                choices = [(']}', 'end')]
            else:
                raise ValueError('Invalid grammar phase')
            if not choices:
                raise ValueError('Grammar has no legal continuation')
            self.trees[key] = self._trie(choices)
        return self.trees[key]

    def allowed(self, tokens):
        phase, mode, chosen, node = 'mode', None, [], self.header
        for token in tokens:
            if phase == 'done':
                if token not in self.eos_ids:
                    raise ValueError('Unexpected token after complete verdict')
                continue
            if token not in node:
                raise ValueError('Generated prefix violates decision grammar')
            node = node[token]
            if None not in node:
                continue
            value = node[None]
            if phase == 'mode':
                mode = value
                phase = 'close' if mode in ['refuse', 'unknown'] else 'cite'
            elif phase == 'cite':
                chosen.append(value)
                phase = 'after'
            elif value == 'more':
                phase = 'cite'
            else:
                phase = 'done'
            node = {} if phase == 'done' else self._tree(phase, mode, chosen)
        return self.eos_ids if phase == 'done' else list(node)

    def complete(self, tokens):
        return set(self.allowed(tokens)) == set(self.eos_ids)

    def callback(self, prompt_length):
        return lambda batch_id, input_ids: self.allowed(input_ids[prompt_length:].tolist())
