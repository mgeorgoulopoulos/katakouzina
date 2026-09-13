"""Optional local-only editorial notes, independent of the public graph."""
import json
import os
import tempfile
from pathlib import Path

class LocalNotes:
    def __init__(self,root,episode):
        self.path=Path(root)/'.local'/'notes'/f'{episode}.json'
        self.values=json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else {}
    def reason(self,row):return self.values.get(row['edge_id'],row.get('reason',''))
    def save(self,row,reason):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        values=dict(self.values);values[row['edge_id']]=reason
        fd,temp=tempfile.mkstemp(dir=self.path.parent,suffix='.tmp')
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as stream:
                json.dump(values,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
            os.replace(temp,self.path);self.values=values
        finally:
            if os.path.exists(temp):os.unlink(temp)
