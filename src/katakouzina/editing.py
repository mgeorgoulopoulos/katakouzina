"""Atomic edits to canonical edge explanations, with recoverable history."""
import csv
import io
import os
import tempfile
import hashlib
from pathlib import Path
from .graph import load_edges

def save_reason(path, expected, reason):
    path=Path(path)
    original=path.read_bytes()
    rows=load_edges(path)
    row=next((r for r in rows if r['edge_id']==expected['edge_id']),None)
    if row != expected:raise ValueError('This edge changed on disk. Reload the graph before saving.')
    if row['reason']==reason:return
    history=path.parent/'.history'
    history.mkdir(exist_ok=True)
    backup=history/(path.name+'.'+hashlib.sha256(original).hexdigest()+'.bak')
    if not backup.exists():backup.write_bytes(original)
    row['reason']=reason
    output=io.StringIO(newline='')
    writer=csv.DictWriter(output,fieldnames=list(row),delimiter='\t',lineterminator='\n')
    writer.writeheader();writer.writerows(rows)
    fd,temp=tempfile.mkstemp(dir=path.parent,suffix='.tmp')
    try:
        with os.fdopen(fd,'w',encoding='utf-8',newline='') as stream:
            stream.write(output.getvalue());stream.flush();os.fsync(stream.fileno())
        if path.read_bytes()!=original:raise ValueError('Graph changed on disk during save. Please reload.')
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)
