"""Atomic, per-view node-coordinate persistence."""
import json
import math
import os
import tempfile
from pathlib import Path

class PositionStore:
    def __init__(self,graph_path):self.path=Path(graph_path).with_suffix('.positions.json')
    def read(self):
        return json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else {}
    def load(self,key,nodes):
        saved=self.read().get(key,{})
        if not set(nodes).issubset(saved):return None
        result={n:tuple(saved[n]) for n in nodes}
        if not all(len(xy)==2 and all(isinstance(v,(int,float)) and math.isfinite(v) for v in xy) for xy in result.values()):
            raise ValueError('Invalid saved node coordinates')
        return result
    def save(self,key,positions):
        data=self.read();data[key]=positions
        fd,temp=tempfile.mkstemp(dir=self.path.parent,suffix='.tmp')
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as stream:
                json.dump(data,stream,ensure_ascii=False,indent=2,allow_nan=False)
                stream.flush();os.fsync(stream.fileno())
            os.replace(temp,self.path)
        finally:
            if os.path.exists(temp):os.unlink(temp)
