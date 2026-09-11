"""Recompute the submission's data-integrity headline using only Python stdlib."""

import argparse
import ast
import csv
import hashlib
import json
import struct
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def reproduce():
    started = time.perf_counter()
    processed = ROOT / 'data/processed/comcast'
    counts, conversations = {}, {}
    for split in ('train', 'validation', 'evaluation', 'golden', 'quarantine'):
        counts[split], conversations[split] = 0, set()
        with (processed / f'{split}.jsonl').open() as stream:
            for line in stream:
                row = json.loads(line)
                assert row['company_id'] == 'comcast', 'Wrong company in processed data'
                counts[split] += 1
                conversations[split].add(row['conversation_id'])
    split_names = list(conversations)
    for i, left in enumerate(split_names):
        for right in split_names[i + 1:]:
            assert not conversations[left] & conversations[right], 'Conversation split leakage'
    manifest = json.loads((processed / 'manifest.json').read_text())
    assert counts == manifest['messages_by_split'], 'Processed counts do not match manifest'
    search = ROOT / 'artifacts/comcast/search'
    pointer = json.loads((search / 'current.json').read_text())
    folder = (search / pointer['generation']).resolve()
    assert folder.parent == search.resolve(), 'Invalid index path'
    assert digest(folder / 'manifest.json') == pointer['manifest_sha256'], 'Index manifest changed'
    index = json.loads((folder / 'manifest.json').read_text())
    for name, expected in index['source_state']['files'].items():
        if name != 'golden_annotations':
            assert digest(processed / name) == expected, f'Processed input changed: {name}'
    for name, expected in index['source_state']['implementation'].items():
        assert digest(ROOT / 'support_agent' / name) == expected, f'Indexed implementation changed: {name}'
    for name, expected in index['files'].items():
        assert name in ('evidence.jsonl', 'vectors.npy'), 'Unexpected index file'
        assert digest(folder / name) == expected, f'{name} checksum mismatch'
    evidence_ids, evidence_conversations = set(), set()
    with (folder / 'evidence.jsonl').open() as stream:
        for line in stream:
            row = json.loads(line)
            assert row['company_id'] == 'comcast'
            assert row['conversation_id'] in conversations['train'], 'Non-training evidence'
            assert row['evidence_id'] not in evidence_ids, 'Duplicate evidence ID'
            evidence_ids.add(row['evidence_id'])
            evidence_conversations.add(row['conversation_id'])
    with (folder / 'vectors.npy').open('rb') as stream:
        assert stream.read(6) == b'\x93NUMPY'
        major, minor = stream.read(2)
        length = struct.unpack('<H' if major == 1 else '<I', stream.read(2 if major == 1 else 4))[0]
        header = ast.literal_eval(stream.read(length).decode('latin1').strip())
    assert header['shape'] == (len(evidence_ids), index['embedding_identity']['dimension'])
    assert len(evidence_ids) == index['record_count']
    reviews = {}
    for name in ('golden', 'training'):
        with (ROOT / f'submission/data/{name}_review.csv').open() as stream:
            rows = list(csv.DictReader(stream))
        reviews[name] = {
            'examples': len(rows),
            'distinct_conversations': len({row['conversation_id'] for row in rows}),
            'filled_intents': sum(bool(row['intent'].strip()) for row in rows),
        }
        for row in rows:
            split = 'evaluation' if name == 'golden' else 'train'
            assert row['conversation_id'] in conversations[split]
            if name == 'golden':
                assert row['conversation_id'] not in evidence_conversations
    observed = {
        'selected_messages': sum(counts.values()),
        'messages_by_split': counts,
        'distinct_conversations': sum(map(len, conversations.values())),
        'indexed_pairs': len(evidence_ids),
        'vector_dimension': header['shape'][1],
        'review_sets': reviews,
        'quality_results': 'pending_human_labels_and_judge_human_ratings',
    }
    return observed, time.perf_counter() - started


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', action='store_true')
    parser.add_argument('--require-complete', action='store_true')
    args = parser.parse_args()
    observed, elapsed = reproduce()
    expected = ROOT / 'submission/evidence/observed_counts.json'
    if args.record:
        expected.write_text(json.dumps(observed, indent=2) + '\n')
    else:
        assert observed == json.loads(expected.read_text()), 'Submission snapshot differs'
    print(json.dumps({'verified': observed, 'elapsed_seconds': round(elapsed, 3)}, indent=2))
    if args.require_complete:
        raise SystemExit('INCOMPLETE: this snapshot has no human-labelled quality evaluation or judge–human agreement.')


if __name__ == '__main__':
    main()
