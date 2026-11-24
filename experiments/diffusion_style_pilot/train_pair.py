"""Train the control and texture arms on the same frozen training sequence."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import subprocess

from contracts import ARMS, ID, file_under, read_records, sha256, write_json

ITERATIONS = re.compile(r'At iteration \d+/(\d+)/(\d+)')


def freeze_lists(root, work, minimum=500):
    manifest = file_under(root, 'pairs.jsonl')
    audit = json.loads(file_under(root, 'pair-audit.json').read_text())
    manifest_hash = sha256(manifest)
    if (audit['sha256'] != manifest_hash or audit['status'] != 'PASS' or not audit['record']
            or audit['examined_pairs'] != 50):
        raise ValueError('The pair manifest needs a passing 50-pair blinded audit')
    rows = read_records(manifest)
    identifiers = [row['id'] for row in rows]
    if not minimum <= len(rows) <= 1000 or len(set(identifiers)) != len(rows):
        raise ValueError('Paired training list has duplicate IDs or an unexpected size')
    lists = {}
    for arm in ARMS:
        members = []
        for row in rows:
            line_id = row['id']
            if not ID.fullmatch(line_id) or row['label_sha256'] != line_id:
                raise ValueError('Pair violates the shared label and ID contract')
            relative = f'paired/{arm}/{line_id}.lstmf'
            if row[arm]['lstmf'] != relative:
                raise ValueError('Encoding path does not match the pair ID and arm')
            path = file_under(root, relative)
            if sha256(path) != row[arm]['sha256']:
                raise ValueError('Training encoding diverges from the frozen pair manifest')
            members.append(relative)
        listing = work / f'{arm}.list'
        listing.write_text(''.join(f'{member}\n' for member in members))
        lists[arm] = listing
    return lists, len(rows), manifest_hash


def run_with_log(command, cwd, log):
    with log.open('wb') as handle:
        subprocess.run(command, stdout=handle, stderr=subprocess.STDOUT, cwd=cwd, check=True)


def train_arm(arm, listing, starter, lstm, root, work, out, count):
    prefix = work / arm
    checkpoint = work / f'{arm}_checkpoint'
    if checkpoint.exists():
        raise ValueError('Use a fresh work root for each paired run')
    samples = []
    for round_number in range(1, 4):
        target = count * round_number
        log = out / f'{arm}-{target}.log'
        raw_log = work / log.name
        command = ['lstmtraining', '--model_output', str(prefix), '--traineddata', str(starter),
                   '--train_listfile', str(listing), '--learning_rate', '0.0001',
                   '--target_error_rate', '-1', '--max_iterations', str(target),
                   '--sequential_training', '--debug_interval', '-1']
        if round_number == 1:
            command += ['--old_traineddata', str(starter), '--continue_from', str(lstm), '--reset_learning_rate']
        try:
            run_with_log(command, root, raw_log)
        except subprocess.CalledProcessError as error:
            log.write_text(f'Trainer exited {error.returncode} at target {target}\n')
            raise
        progress = ITERATIONS.findall(raw_log.read_text(errors='replace'))
        log.write_text(''.join(f'{steps} updates / {seen} samples\n' for steps, seen in progress))
        if not progress or int(progress[-1][0]) != target:
            raise RuntimeError(f'{arm} failed to reach checkpoint {target}')
        samples.append(int(progress[-1][1]))
        model = out / f'{arm}-{target}.traineddata'
        run_with_log(['lstmtraining', '--stop_training', '--continue_from', str(checkpoint),
                      '--traineddata', str(starter), '--model_output', str(model)], root,
                     out / f'{arm}-{target}-conversion.log')
        if not model.is_file() or not model.stat().st_size:
            raise RuntimeError(f'{arm} conversion produced no model at {target}')
    return samples


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('work', type=Path)
    parser.add_argument('out', type=Path)
    args = parser.parse_args()
    root, work, out = (p.resolve() for p in (args.root, args.work, args.out))
    work.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    lists, count, manifest = freeze_lists(root, work)
    assets = json.loads(file_under(root, 'assets.json').read_text())
    starter = file_under(root, 'tessdata/heb.traineddata')
    if sha256(starter) != assets['tessdata/heb.traineddata']:
        raise ValueError('Stock starter hash changed')
    lstm = work / 'common.lstm'
    run_with_log(['combine_tessdata', '-e', str(starter), str(lstm)], root, out / 'extract.log')
    with ThreadPoolExecutor(2) as pool:
        futures = {arm: pool.submit(train_arm, arm, lists[arm], starter, lstm, root, work, out, count)
                   for arm in ARMS}
        actual = {arm: result.result() for arm, result in futures.items()}
    scheduled = [count, 2 * count, 3 * count]
    if any(sequence != scheduled for sequence in actual.values()):
        raise RuntimeError('At least one arm skipped training samples. Discard the paired run.')
    write_json(out / 'training.json', {'pairs_sha256': manifest, 'starter_sha256': sha256(starter),
                                     'list_sha256': {arm: sha256(file) for arm, file in lists.items()},
                                     'iterations': scheduled, 'samples': actual, 'status': 'complete'})


if __name__ == '__main__':
    main()
