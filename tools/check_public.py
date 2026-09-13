"""Inspect prospective public files and staged blobs. Not legal clearance."""
import csv,io,re,subprocess,sys,unicodedata
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from katakouzina.evidence import references
from katakouzina.transcript import load_transcript
from katakouzina.config import load_config
ROOT_FILES={'.gitattributes','.gitignore','AGENTS.md','DATA_MODEL.md','README.md','LICENSE','screenshot.png','TECHNICAL.md','launch.bat','setup.bat','requirements.txt'}
PUBLIC_DIRS={'src','tests','tools','example-data'}
FORBIDDEN={'.srt','.vtt','.mp4','.mkv','.avi','.mp3','.wav','.sqlite3','.db','.bak','.zip','.png','.jpg','.pdf'}
def git(*args):return subprocess.check_output(['git','-c',f'safe.directory={ROOT.as_posix()}',*args],cwd=ROOT)
def ngrams(text):
    clean=''.join(c for c in unicodedata.normalize('NFD',text.casefold()) if not unicodedata.combining(c))
    tokens=re.findall(r'[^\W_]+',clean)
    return {tuple(tokens[i:i+5]) for i in range(len(tokens)-4)}
def check(name,raw,corpus):
    path=Path(name);errors=[]
    # Explicit README demonstration image; its pixels are not text-audited.
    if name=='screenshot.png':
        return [] if raw.startswith(b'\x89PNG\r\n\x1a\n') else ['Invalid screenshot PNG header']
    if not ((len(path.parts)==1 and name in ROOT_FILES) or path.parts[0] in PUBLIC_DIRS):errors.append('Unexpected public path')
    synthetic=name=='example-data/srt/demo.srt'
    if (path.suffix.lower() in FORBIDDEN and not synthetic) or any(p.startswith('.') for p in path.parts[1:]) or name.endswith('.positions.json'):errors.append('Private or media artifact')
    try:text=raw.decode('utf-8-sig')
    except UnicodeError:return errors+['Non-text public artifact']
    if not synthetic and re.search(r'(?m)^\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}',text):errors.append('Subtitle block')
    if corpus and ngrams(text)&corpus:errors.append('Five-word source-text overlap; review required')
    if path.parts[0]=='example-data' and path.suffix=='.tsv':
        reader=csv.DictReader(io.StringIO(text),delimiter='\t')
        expected={'edge_id','episode','from','to','relation','layer','status','decision_basis','evidence_refs','reason','external_sources'}
        if set(reader.fieldnames or [])!=expected:errors.append('Unexpected graph schema')
        else:
            for row in reader:
                try:references(row)
                except (ValueError,TypeError,KeyError) as exc:errors.append(str(exc));break
    if synthetic:
        lines=text.splitlines()
        dialogue=[line for line in lines if line.strip() and not line.strip().isdigit() and ' --> ' not in line]
        if not dialogue or any(not line.startswith('[SYNTHETIC] ') for line in dialogue):errors.append('Unlabeled synthetic dialogue')
    return errors

def main():
    corpus=set()
    directory=load_config(ROOT,create=False)/'srt'
    for path in directory.glob('*.srt') if directory.resolve()!=(ROOT/'example-data/srt').resolve() else ():
        for _,_,text in load_transcript(path).values():corpus.update(ngrams(text))
    names=lambda raw:{p.decode('utf-8') for p in raw.split(b'\0') if p}
    paths=names(git('ls-files','--cached','--others','--exclude-standard','-z'))
    staged=names(git('ls-files','--cached','-z'));failures=[]
    for name in sorted(paths):
        path=ROOT/name
        if path.exists():failures.extend(f'Working tree {name}: {e}' for e in check(name,path.read_bytes(),corpus))
    for name in sorted(staged):failures.extend(f'Index {name}: {e}' for e in check(name,git('show',':'+name),corpus))
    if failures:print('\n'.join(failures));return 1
    print(f'PASS: {len(paths)} prospective files; {len(staged)} indexed files; no unexpected artifacts or embedded text evidence (declared screenshot excluded).')
    print('Source overlap scan: '+('completed against local corpus.' if corpus else 'unavailable; no local corpus.'))
    print('Automated checks cannot establish copyright ownership or legal clearance.')
    return 0
if __name__=='__main__':raise SystemExit(main())
