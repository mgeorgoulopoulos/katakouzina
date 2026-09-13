"""Local configuration; relative paths resolve from the config directory."""
import json
from pathlib import Path

DEFAULTS={'data_path':'example-data','show_rejected_edges':False,'hide_leaves':False,'graph_font_size':18,'start_maximized':True}

def read_settings(root,create=True):
    root=Path(root).resolve();path=root/'config.json'
    if not path.exists() and create:
        try:
            with path.open('x',encoding='utf-8') as stream:json.dump(DEFAULTS,stream,indent=2);stream.write('\n')
        except FileExistsError:pass
    data=json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else dict(DEFAULTS)
    if not isinstance(data,dict):raise ValueError('config.json must contain an object')
    for key in ('show_rejected_edges','hide_leaves','start_maximized'):
        if key in data and not isinstance(data[key],bool):raise ValueError(key+' must be a boolean')
    size=data.get('graph_font_size',18)
    if type(size) is not int or not 6<=size<=48:raise ValueError('graph_font_size must be an integer from 6 to 48')
    return {**DEFAULTS,**data}

def load_config(root,create=True):
    root=Path(root).resolve()
    data=read_settings(root,create)
    value=data.get('data_path','example-data')
    if value is not None and (not isinstance(value,str) or not value.strip()):raise ValueError('data_path must be null or a non-empty directory path')
    if value is None:value='example-data'
    directory=Path(value).expanduser()
    return (directory if directory.is_absolute() else root/directory).resolve()

def save_preferences(root,preferences):
    import os,tempfile
    root=Path(root).resolve()
    data=read_settings(root,create=False)
    data.update({key:preferences[key] for key in DEFAULTS if key in preferences})
    fd,temp=tempfile.mkstemp(dir=root,suffix='.tmp')
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as stream:
            json.dump(data,stream,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
        os.replace(temp,root/'config.json')
    finally:
        if os.path.exists(temp):os.unlink(temp)
