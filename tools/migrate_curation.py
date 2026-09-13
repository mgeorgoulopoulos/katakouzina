"""One-time, lossless migration. Run with the app closed and a dataset path."""
import csv
import json
import shutil
import sqlite3
import sys
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from katakouzina.review import ReviewStore, fingerprint


def migrate(root):
    root = Path(root).resolve()
    for graph in sorted(root.glob('*/*.tsv')):
        with graph.open(encoding='utf-8-sig', newline='') as stream:
            rows = {r['edge_id']: r for r in csv.DictReader(stream, delimiter='\t')}
        dbpath = graph.with_suffix('.reviews.sqlite3')
        notespath = root / '.local' / 'notes' / (graph.parent.name + '.json')
        if not dbpath.exists() and not notespath.exists(): continue
        target = graph.parent / 'curation.json'
        if target.exists(): raise RuntimeError(f'Refusing to overwrite {target}')
        notes = json.loads(notespath.read_text(encoding='utf-8')) if notespath.exists() else {}
        reviews, rejections = [], []
        if dbpath.exists():
            with closing(sqlite3.connect(dbpath.as_uri() + '?mode=ro', uri=True)) as db:
                tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if 'reviews' in tables: reviews = list(db.execute('SELECT edge_id, fingerprint, reviewed_at FROM reviews'))
                if 'rejections' in tables: rejections = list(db.execute('SELECT edge_id, reason, rejected_at FROM rejections'))
        values = {}
        def record(key):
            if key not in rows: raise ValueError(f'Unknown edge ID: {key}')
            return values.setdefault(key, dict(decision='unreviewed', why=notes.get(key, rows[key].get('reason', '')), author='unknown', updated_at=None, based_on=fingerprint(rows[key])))
        for key in notes: record(key)
        for key, basis, stamp in reviews: record(key).update(decision='accepted', author='human', based_on=basis, updated_at=stamp)
        for key, reason, stamp in rejections:
            entry = record(key)
            if entry['decision'] == 'accepted': raise ValueError(f'Conflicting review: {key}')
            entry.update(previous_why=entry['why'], decision='rejected', author='human', why=reason, updated_at=stamp)
        backup = root / '.local' / 'curation-migration' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') / graph.parent.name
        backup.mkdir(parents=True)
        for source in (dbpath, notespath):
            if source.exists():
                shutil.copy2(source, backup / source.name)
                assert source.read_bytes() == (backup / source.name).read_bytes()
        with target.open('x', encoding='utf-8') as stream:
            json.dump(values, stream, ensure_ascii=False, indent=2, sort_keys=True); stream.write('\n')
        store = ReviewStore(graph)
        assert store.records() == values
        for key, reason in notes.items():
            entry = values[key]
            assert entry.get('previous_why', entry['why']) == reason
        for key, basis, stamp in reviews:
            assert values[key]['based_on'] == basis and values[key]['updated_at'] == stamp
            assert store.verified(rows[key]) == (basis == fingerprint(rows[key]))
        assert store.rejections() == {key: reason for key, reason, stamp in rejections}
        for source in (dbpath, notespath):
            if source.exists(): source.unlink()
        print(f'{graph.parent.name}: {len(notes)} explanations, {len(reviews)} acceptances, {len(rejections)} rejections preserved; {len(values)} curation records')

if __name__ == '__main__': migrate(sys.argv[1])
