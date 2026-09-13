"""Soft deletion is independent of canonical data and review decisions."""
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

class DeletionStore:
    def __init__(self,path):self.path=Path(path).with_suffix('.deletions.json')
    def read(self):
        return json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else {'nodes':{},'edges':{}}
    def active(self):
        data=self.read()
        return tuple({key for key,value in data[kind].items() if value['deleted']} for kind in ('nodes','edges'))
    def set(self,kind,key,deleted=True):
        if kind not in ('nodes','edges'):raise ValueError('Invalid deletion kind')
        lock=self.path.with_suffix('.json.lock');handle=lock.open('x')
        try:
            before=self.path.read_bytes() if self.path.exists() else None
            data=self.read();record=data[kind].setdefault(key,{'history':[]})
            record['deleted']=deleted
            record['history'].append({'deleted':deleted,'author':'human','at':datetime.now(timezone.utc).isoformat()})
            fd,temp=tempfile.mkstemp(dir=self.path.parent,suffix='.tmp')
            try:
                with os.fdopen(fd,'w',encoding='utf-8') as stream:
                    json.dump(data,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
                if (self.path.read_bytes() if self.path.exists() else None)!=before:raise ValueError('Deletion records changed; reload before retrying.')
                os.replace(temp,self.path)
            finally:
                if os.path.exists(temp):os.unlink(temp)
        finally:handle.close();lock.unlink()
