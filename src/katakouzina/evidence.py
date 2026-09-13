"""Resolve episode/time references against optional local subtitles."""
import json
import re
from pathlib import Path
from .transcript import load_transcript

STAMP=re.compile(r'^(\d{2}):([0-5]\d):([0-5]\d),([0-9]{3})$')

def milliseconds(value):
    match=STAMP.fullmatch(value)
    if not match:raise ValueError('Invalid timestamp: '+str(value))
    h,m,s,ms=map(int,match.groups())
    return ((h*60+m)*60+s)*1000+ms

def references(row):
    refs=json.loads(row.get('evidence_refs','[]'))
    if not isinstance(refs,list):raise ValueError('Evidence references must be a list')
    for ref in refs:
        if not isinstance(ref,dict) or set(ref)!={'episode','start','end'}:raise ValueError('Evidence requires only episode, start and end')
        if not isinstance(ref['episode'],str) or not re.fullmatch(r'[A-Za-z0-9_-]+',ref['episode']):raise ValueError('Invalid episode code')
        if milliseconds(ref['start'])>=milliseconds(ref['end']):raise ValueError('Evidence range must have positive duration')
    return refs

def overlaps(a,b):
    return milliseconds(a['start'])<milliseconds(b['end']) and milliseconds(b['start'])<milliseconds(a['end'])

class EvidenceLibrary:
    def __init__(self,root):
        self.root=Path(root);self.srt_path=self.root/'srt';self.cache={}
    def episode(self,episode):
        # Validation also prevents paths escaping the configured folders.
        references({'evidence_refs':json.dumps([{'episode':episode,'start':'00:00:00,000','end':'00:00:00,001'}])})
        if episode not in self.cache:
            subtitles=load_transcript(self.srt_path/f'{episode}.srt') if self.srt_path is not None else {}
            local=[{'episode':episode,'start':start,'end':end,'text':text,'kind':'LOCAL_SRT'} for start,end,text in subtitles.values()]
            self.cache[episode]=sorted(local,key=lambda r:milliseconds(r['start']))
        return self.cache[episode]
    def resolve(self,ref,context=False):
        local=self.episode(ref['episode'])
        matched=[i for i,row in enumerate(local) if overlaps(row,ref)]
        if matched:
            indices=range(max(0,matched[0]-2),min(len(local),matched[-1]+3)) if context else matched
            return [dict(local[i],selected=i in matched) for i in indices]
        return []
    def preview(self,ref):
        rows=self.resolve(ref)
        kind='Local SRT' if rows and rows[0]['kind']=='LOCAL_SRT' else ''
        return kind,'\n'.join(dict.fromkeys(row['text'] for row in rows))
