"""Text curation keyed by stable edge IDs; atomic writes with conflict detection."""
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def fingerprint(row):
    return hashlib.sha256(json.dumps(row, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()


class ReviewStore:
    def __init__(self, graph_path):
        self.graph_path = Path(graph_path)
        self.path = self.graph_path.parent / 'curation.json'

    def records(self):
        values = json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else {}
        if not isinstance(values, dict):
            raise ValueError('Curation must be an object keyed by edge ID')
        for key, value in values.items():
            if not isinstance(value, dict) or value.get('decision') not in ('unreviewed', 'accepted', 'rejected'):
                raise ValueError(f'Invalid curation decision: {key}')
            if not all(isinstance(value.get(field), str) for field in ('why', 'author')):
                raise ValueError(f'Invalid curation explanation or author: {key}')
        return values

    def stale(self, row):
        record = self.records().get(row['edge_id'])
        return bool(record and record.get('based_on') != fingerprint(row))

    def verified(self, row, records=None):
        record = (self.records() if records is None else records).get(row['edge_id'], {})
        return record.get('decision') == 'accepted' and record.get('author') == 'human' and record.get('based_on') == fingerprint(row)

    def rejections(self):
        return {key: value['why'] for key, value in self.records().items()
                if value['decision'] == 'rejected' and value['author'] == 'human'}

    def reason(self, row):
        return self.records().get(row['edge_id'], {}).get('why', row.get('reason', ''))

    def _update(self, row, change):
        lock = self.path.with_suffix('.json.lock')
        handle = lock.open('x')
        try:
            before = self.path.read_bytes() if self.path.exists() else None
            values = self.records()
            record = dict(values.get(row['edge_id'], {'decision': 'unreviewed', 'why': row.get('reason', '')}))
            change(record)
            record.update(author='human', updated_at=datetime.now(timezone.utc).isoformat(), based_on=fingerprint(row))
            values[row['edge_id']] = record
            fd, temp = tempfile.mkstemp(dir=self.path.parent, suffix='.tmp')
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                    json.dump(values, stream, ensure_ascii=False, indent=2, sort_keys=True)
                    stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
                if (self.path.read_bytes() if self.path.exists() else None) != before:
                    raise RuntimeError('Curation changed during save; reload before retrying')
                os.replace(temp, self.path)
            finally:
                if os.path.exists(temp): os.unlink(temp)
        finally:
            handle.close()
            lock.unlink()

    def set_verified(self, row, value):
        self._update(row, lambda record: record.update(decision='accepted' if value else 'unreviewed'))

    def set_rejected(self, row, reason):
        def change(record):
            if reason is None:
                record['decision'] = 'unreviewed'
                if 'previous_why' in record:
                    record['why'] = record.pop('previous_why')
            else:
                if record['decision'] != 'rejected': record['previous_why'] = record['why']
                record.update(decision='rejected', why=reason)
        self._update(row, change)

    def save(self, row, reason):
        self._update(row, lambda record: record.update(why=reason, decision='unreviewed'))
