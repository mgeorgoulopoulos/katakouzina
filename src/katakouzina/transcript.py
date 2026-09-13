"""Read exact subtitle wording, retaining cue boundaries."""
import re

def load_transcript(path):
    if not path.exists():return {}
    result={}
    for block in re.split(r'\n\s*\n',path.read_text(encoding='utf-8-sig').replace('\r\n','\n').strip()):
        lines=block.splitlines()
        if len(lines)<3 or not lines[0].strip().isdigit() or ' --> ' not in lines[1]:
            raise ValueError(f'Malformed SRT block: {block[:80]}')
        cue=lines[0].strip()
        if cue in result:raise ValueError(f'Duplicate SRT cue: {cue}')
        start,end=lines[1].split(' --> ',1)
        result[cue]=(start,end,'\n'.join(lines[2:]))
    return result
