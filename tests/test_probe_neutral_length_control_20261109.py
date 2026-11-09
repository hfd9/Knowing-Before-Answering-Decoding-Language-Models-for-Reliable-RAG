import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from contextlib import ExitStack

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import probe_neutral_length_control_20261109 as control


class NeutralLengthControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from transformers import AutoTokenizer
        cls.tokenizer=AutoTokenizer.from_pretrained(control.MODEL,local_files_only=True)
        cls.spec=control.read(control.SPEC)
        cls.originals=control.read(control.SOURCE/'materials/inputs.json')
        cls.saved=control.read(control.SOURCE/'states.json')['records']

    def test_twelve_equal_length_controls_and_one_existing_bridge(self):
        rows, pairs, _=control.build_rows(self.spec,self.originals,self.saved,self.tokenizer)
        self.assertEqual((len(rows),len(pairs)),(13,12))
        self.assertEqual(rows[0]['id'],'bridge_support06_D1')
        self.assertTrue(all(p['negative_identity']['input_tokens']==p['neutral_identity']['input_tokens'] for p in pairs))
        self.assertEqual(len({(p['base'],p['wording']) for p in pairs}),12)
        self.assertTrue(all(len(p['changed_document_slots'])==2 for p in pairs))

    def test_non_suffix_mutation_stops_material_build(self):
        originals=copy.deepcopy(self.originals)
        bad=next(x for x in originals if x['id']=='support02_D1')
        bad['docs'][1]='Unrelated replacement.'
        with self.assertRaises(ValueError):
            control.build_rows(self.spec,originals,self.saved,self.tokenizer)

    def test_uncommitted_attempt_blocks_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp)
            (run/'protocol.json').write_text('{}')
            (run/'attempts').mkdir()
            (run/'attempts'/'0000.json').write_text('{}')
            with patch.object(control,'RUN',run), patch.object(control.d,'cache',return_value=[]):
                with self.assertRaisesRegex(ValueError,'uncommitted'):
                    control.checked_prefix([],None,None)

    def test_bridge_rejects_a_mismatched_recomputed_state(self):
        error={'max_layer_relative_l2':0.03,'max_probability_absolute_error':0.0}
        with patch.object(control.np,'load',return_value=np.ones((36,2048),dtype=np.float16)), \
             patch.object(control.d,'source_state',return_value=np.ones((36,2048),dtype=np.float16)), \
             patch.object(control.d,'bridge_error',return_value=error):
            with self.assertRaisesRegex(ValueError,'bridge failed'):
                control.check_bridge({'source':{}},{'feature_file':'unused'},None,None)

    def test_synthetic_collection_commits_each_attempt_and_reuses_complete_prefix(self):
        import torch

        class Inputs(dict):
            def to(self, _device):
                return self

        class FakeModel:
            device='cpu'
            def model(self, **_kwargs):
                return None

        class FakeCapture:
            def __init__(self, _model):
                pass
            def __enter__(self):
                return self
            def __exit__(self, *_args):
                pass
            def array(self):
                return np.ones((36,2048),dtype=np.float16)

        rows=[{'id':f'id{i}', 'original_id':'b', 'question_level':'A',
               'document_level':'D', 'question':'q', 'docs':['x']*5, 'source':None}
              for i in range(13)]
        prediction={'probe_pred':'answer','probe_probabilities':{'answer':0.8,'refuse':0.1,'conflict':0.1},
                    'probe_layer_zero_based':28}
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            run=Path(tmp)
            (run/'protocol.json').write_text('{}')
            def fake_cache(*_args):
                path=run/'states.json'
                return control.read(path)['records'] if path.exists() else []
            stack.enter_context(patch.object(control,'RUN',run))
            stack.enter_context(patch.object(control.d,'cache',side_effect=fake_cache))
            stack.enter_context(patch.object(control,'check_weights'))
            stack.enter_context(patch.object(control,'check_bridge',return_value={}))
            stack.enter_context(patch.object(control.pilot.s,'assert_gpu_idle'))
            stack.enter_context(patch.object(control.e,'load_model',return_value=FakeModel()))
            stack.enter_context(patch.object(control.e,'encode',return_value=Inputs()))
            stack.enter_context(patch.object(control.e,'LastPromptCapture',FakeCapture))
            stack.enter_context(patch.object(control.d,'prompt',return_value='test'))
            stack.enter_context(patch.object(control.d,'prediction',return_value=prediction))
            stack.enter_context(patch.object(control,'identity',return_value={'prompt_sha256':'a'*64,'input_tokens':1}))
            stack.enter_context(patch.object(torch.cuda,'is_available',return_value=True))
            stack.enter_context(patch.object(torch.cuda,'device_count',return_value=1))
            stack.enter_context(patch.object(torch.cuda,'is_bf16_supported',return_value=True))
            stack.enter_context(patch.object(torch.cuda,'synchronize'))
            stack.enter_context(patch.object(torch.cuda,'empty_cache'))
            stack.enter_context(patch.dict('os.environ',{'CUDA_VISIBLE_DEVICES':'0'}))
            records=control.collect(rows,[],{},None,None,{})
            self.assertEqual(len(records),13)
            self.assertEqual(len(list((run/'attempts').glob('*.json'))),13)
            self.assertEqual(len(list((run/'features').glob('*.npy'))),13)
            self.assertEqual(len(control.collect(rows,[],{},None,None,{})),13)


if __name__=='__main__':
    unittest.main()
