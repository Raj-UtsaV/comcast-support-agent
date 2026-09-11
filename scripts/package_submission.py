"""Create a submission ZIP from an explicit allowlist; omit credentials/caches."""

import json
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main():
    paths = set()
    for name in ('README.md', 'report.md', 'decision_log.md', 'requirements.txt', '.env.example', '.gitignore', 'app.py', 'customer_app.py', '.streamlit/config.toml'):
        paths.add(ROOT / name)
    for directory in ('support_agent', 'tests', 'configs', 'docs', 'scripts', 'submission'):
        for path in (ROOT / directory).rglob('*'):
            if path.is_file() and not path.is_symlink() and '__pycache__' not in path.parts and path.suffix in ('.py', '.md', '.yaml', '.csv', '.json', '.jsonl', '.xml', '.txt'):
                paths.add(path)
    for path in (ROOT / 'data/processed/comcast').glob('*'):
        if path.is_file() and path.suffix in ('.csv', '.json', '.jsonl'):
            paths.add(path)
    for name in ('golden_set_template.csv', 'training_labels_template.csv'):
        paths.add(ROOT / 'data' / name)
    search = ROOT / 'artifacts/comcast/search'
    pointer = search / 'current.json'
    generation = json.loads(pointer.read_text())['generation']
    folder = (search / generation).resolve()
    assert folder.parent == search.resolve()
    paths.add(pointer)
    for name in ('manifest.json', 'vectors.npy', 'evidence.jsonl'):
        paths.add(folder / name)
    target = ROOT / 'comcast-support-agent-submission.zip'
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(paths):
            relative = path.relative_to(ROOT)
            assert not path.is_symlink()
            assert path.name != '.env' and not {'.venv', '.cache', '.git'}.intersection(relative.parts)
            archive.write(path, Path('comcast-support-agent') / relative)
    print(f'Created {target.name}: {len(paths)} files, {target.stat().st_size / 1024**2:.1f} MiB')


if __name__ == '__main__':
    main()
