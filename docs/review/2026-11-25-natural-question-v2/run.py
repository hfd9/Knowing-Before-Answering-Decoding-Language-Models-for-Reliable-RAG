"""Repeat the exposed Korean question with a concise, frozen response interface."""
from importlib.machinery import SourceFileLoader
from pathlib import Path
import sys
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import query_determinacy_date_pilot as pilot
from query_determinacy_delegation_collect import CpuBackend

original = SourceFileLoader('natural_question_v1', str(HERE.parent / '2026-11-25-natural-question-v1/run.py')).load_module()
local = pilot.local
SYSTEM = ('제공된 사실과 법조문만 사용하라. 사실이 없으면 추측하지 말라. '
          '결론을 길게 설명하지 말고 지정된 JSON만 출력하라.')
INTERFACE = ('JSON 하나만 출력하라. action은 YES, NO, ASK 중 하나. 판단할 날짜마다 '
             'branches에 ["YYYY-MM-DD", "YES 또는 NO", ["E1", "E2", "E3", "F1" 중 필요한 번호]]를 '
             '넣어라. 날짜가 확정되면 그 날짜만 판단하고, 두 날짜의 결론이 다르면 ASK를 선택하라. '
             'ask에는 ASK일 때 필요한 사실을 적고, 그 외에는 null을 넣어라.')
TASKS = [{'case': row['case'], 'messages': [pilot.message('system', SYSTEM),
          pilot.message('user', row['messages'][0]['content'] + '\n\n' + INTERFACE)]} for row in original.TASKS]


def hashes():
    paths = (Path(__file__), HERE / 'protocol.md', Path(original.__file__), HERE.parent / '2026-11-25-natural-question-v1/source.md',
             ROOT / 'scripts/query_determinacy_date_pilot.py', ROOT / 'scripts/query_determinacy_shared_live.py',
             ROOT / 'scripts/query_determinacy_delegation_collect.py')
    return {str(path.relative_to(ROOT)): local.hash_file(path) for path in paths}


def collect(path):
    environment = local.environment_snapshot()
    path.mkdir(mode=0o700)
    pilot.write(path / 'manifest.json', {'hashes': hashes(), 'environment': environment})
    pilot.write(path / 'attempt.json', TASKS)
    data = pilot.generate(CpuBackend(environment), TASKS)
    pilot.write(path / 'record.json', data)
    pilot.write(path / 'seal.json', {f.name: local.hash_file(f) for f in sorted(path.iterdir())})


def verify(path):
    seal, manifest = (pilot.read(path / name) for name in ('seal.json', 'manifest.json'))
    pilot.require(set(seal) | {'seal.json'} == {f.name for f in path.iterdir()} and
                  all(local.hash_file(path / name) == sha for name, sha in seal.items()), 'seal mismatch')
    pilot.require(manifest['hashes'] == hashes() and pilot.read(path / 'attempt.json') == TASKS, 'source mismatch')
    tokenizer = local.load_tokenizer()
    data = pilot.read(path / 'record.json')
    for task, row in zip(TASKS, data['records'], strict=True):
        text, ids = pilot.render(tokenizer, task['messages'])
        tokens, eos = row['generated_token_ids'], manifest['environment']['eos_token_ids']
        output = tokenizer.decode(tokens, skip_special_tokens=True)
        pilot.require(all(row[key] == val for key, val in task.items()) and text == row['rendered_prompt'] and
                      ids == row['input_token_ids'] and 0 < len(tokens) <= pilot.LIMIT and
                      not any(t in eos for t in tokens[:-1]) and (tokens[-1] in eos or len(tokens) == pilot.LIMIT) and
                      output == row['output'] and row['status'] == local.output_status(output, tokens, eos), 'record mismatch')
    return data


if __name__ == '__main__':
    action = sys.argv[1]
    if action == 'collect':
        collect(Path(sys.argv[2]))
    elif action == 'archive':
        path = Path(sys.argv[2])
        result = verify(path)
        with ZipFile(HERE / 'raw.zip', 'x', ZIP_DEFLATED) as archive:
            for f in sorted(path.iterdir()):
                archive.write(f, f.name)
        pilot.write(HERE / 'outputs.json', {'seconds': result['seconds'], 'records': [
            {'case': r['case'], 'output': r['output'], 'status': r['status'],
             'output_sha256': local.sha(r['output'].encode()), 'generated_tokens': len(r['generated_token_ids'])}
            for r in result['records']]})
    elif action == 'check':
        with tempfile.TemporaryDirectory(prefix='natural-v2-') as directory:
            with ZipFile(HERE / 'raw.zip') as archive:
                archive.extractall(directory)
            result = verify(Path(directory))
        saved = pilot.read(HERE / 'outputs.json')
        pilot.require([local.sha(r['output'].encode()) for r in result['records']] ==
                      [r['output_sha256'] for r in saved['records']], 'output hash mismatch')
        print('Korean compact responses replayed.')
