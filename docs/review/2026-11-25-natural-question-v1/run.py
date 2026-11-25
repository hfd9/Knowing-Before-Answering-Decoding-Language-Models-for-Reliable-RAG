"""Archive four CPU generations for the public Korean legal question pilot."""
from pathlib import Path
import json
import sys
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / 'scripts'))
import query_determinacy_date_pilot as pilot
from query_determinacy_delegation_collect import CpuBackend

local = pilot.local
SOURCE = '의원에 포함되지 않는 치과의원, 한의원은 방염대상에 포함되지 않는 것인지?'
EVIDENCE = ('[E1] 2024-12-30 이전에 유효한 제30조 제1호는 근린생활시설 중 의원, 조산원, 산후조리원, '
            '체력단련장, 공연장 및 종교집회장을 열거한다. 치과의원과 한의원은 이 호에 명시되지 않는다.\n'
            '[E2] 2024-12-31 시행된 제30조 제1호는 근린생활시설 중 의원, 치과의원, 한의원, 조산원, '
            '산후조리원, 체력단련장, 공연장 및 종교집회장을 열거한다.\n'
            '[E3] 부칙 제3조는 이 개정사항을 시행 이후 치과의원 및 한의원에 실내장식물을 설치하거나 '
            '기존 실내장식물을 교체하는 경우부터 적용한다.')
TASKS = [{'case': 'original', 'messages': [pilot.message('user', SOURCE)]}]
for name, when in (('old', '2024-12-30에'), ('new', '2024-12-31에'),
                   ('missing', '2024-12-30 또는 2024-12-31 중 하루에')):
    case = ('[F1] 시설은 근린생활시설에 속한 치과의원이다. 다른 호의 대상이 아니라고 가정한다. '
            f'실내장식물은 {when} 처음 설치되었고 이후 교체되지 않았다. '
            '제30조 제1호의 진료소 분류에 따른 대상 여부만 판단하라. 날짜를 명확히 알 수 없다면 필요한 사실을 물어라.')
    TASKS.append({'case': name, 'messages': [pilot.message('user', SOURCE + '\n\n' + EVIDENCE + '\n' + case)]})


def collect(path):
    environment = local.environment_snapshot()
    path.mkdir(mode=0o700)
    hashes = {item.name: local.hash_file(item) for item in (Path(__file__), HERE / 'protocol.md', HERE / 'source.md')}
    pilot.write(path / 'manifest.json', {'hashes': hashes, 'environment': environment})
    pilot.write(path / 'attempt.json', TASKS)
    result = pilot.generate(CpuBackend(environment), TASKS)
    pilot.write(path / 'record.json', result)
    pilot.write(path / 'seal.json', {file.name: local.hash_file(file) for file in sorted(path.iterdir())})


def verify(path):
    seal, manifest = (pilot.read(path / name) for name in ('seal.json', 'manifest.json'))
    pilot.require(set(seal) | {'seal.json'} == {f.name for f in path.iterdir()} and
                  all(local.hash_file(path / name) == digest for name, digest in seal.items()), 'seal mismatch')
    pilot.require(manifest['hashes'] == {f.name: local.hash_file(f) for f in
                  (Path(__file__), HERE / 'protocol.md', HERE / 'source.md')}, 'frozen sources changed')
    pilot.require(pilot.read(path / 'attempt.json') == TASKS, 'tasks changed')
    tokenizer = local.load_tokenizer()
    result = pilot.read(path / 'record.json')
    for item, row in zip(TASKS, result['records'], strict=True):
        text, ids = pilot.render(tokenizer, item['messages'])
        tokens = row['generated_token_ids']
        eos = manifest['environment']['eos_token_ids']
        pilot.require(all(row[key] == val for key, val in item.items()) and text == row['rendered_prompt'] and
                      ids == row['input_token_ids'] and 0 < len(tokens) <= pilot.LIMIT and
                      not any(token in eos for token in tokens[:-1]) and (tokens[-1] in eos or len(tokens) == pilot.LIMIT),
                      'input or token record mismatch')
        output = tokenizer.decode(tokens, skip_special_tokens=True)
        pilot.require(output == row['output'] and row['status'] == local.output_status(output, tokens, eos), 'output mismatch')
    return result


if __name__ == '__main__':
    action = sys.argv[1]
    if action == 'collect':
        collect(Path(sys.argv[2]))
    elif action == 'archive':
        run = Path(sys.argv[2])
        data = verify(run)
        with ZipFile(HERE / 'raw.zip', 'x', ZIP_DEFLATED) as archive:
            for f in sorted(run.iterdir()):
                archive.write(f, f.name)
        pilot.write(HERE / 'outputs.json', {'seconds': data['seconds'], 'records': [
            {'case': row['case'], 'output': row['output'], 'status': row['status'],
             'output_sha256': local.sha(row['output'].encode()), 'generated_tokens': len(row['generated_token_ids'])}
            for row in data['records']]})
    elif action == 'check':
        with tempfile.TemporaryDirectory(prefix='natural-question-') as directory:
            with ZipFile(HERE / 'raw.zip') as archive:
                archive.extractall(directory)
            data = verify(Path(directory))
        recorded = pilot.read(HERE / 'outputs.json')
        pilot.require([local.sha(row['output'].encode()) for row in data['records']] ==
                      [row['output_sha256'] for row in recorded['records']], 'review output hash mismatch')
        print('Four natural-question outputs replayed.')
