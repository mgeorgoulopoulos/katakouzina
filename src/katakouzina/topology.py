"""Canonical topology edits, preserving originals and existing curation IDs."""
import csv
import io
import json
import os
import uuid
import tempfile
from pathlib import Path
from .graph import load_edges


def node_names(path, rows):
    sidecar=Path(path).with_suffix('.nodes.json')
    return set(json.loads(sidecar.read_text(encoding='utf-8')) if sidecar.exists() else []) | {r[k] for r in rows for k in ('from','to')}


def transform(rows, nodes, action, original, name, inherit=False, prototype=None):
    name=name.strip()
    if not name:raise ValueError('Enter a node name.')
    if original not in nodes:raise ValueError('The original node no longer exists.')
    if name==original:raise ValueError('Choose a different node name.')
    rows=[dict(r) for r in rows];nodes=set(nodes)
    if action=='merge':
        if name not in nodes:raise ValueError('The retained node no longer exists.')
        # Prefer an existing edge of the retained node when pairs collapse.
        rows.sort(key=lambda r: original in (r['from'],r['to']))
        pairs={};result=[]
        for row in rows:
            row['from']=name if row['from']==original else row['from']
            row['to']=name if row['to']==original else row['to']
            if row['from']==row['to']:continue
            pair=tuple(sorted((row['from'],row['to'])))
            if pair in pairs:
                target=pairs[pair]
                refs=json.loads(target.get('evidence_refs') or '[]')
                for ref in json.loads(row.get('evidence_refs') or '[]'):
                    if ref not in refs:refs.append(ref)
                target['evidence_refs']=json.dumps(refs,ensure_ascii=False)
            else:pairs[pair]=row;result.append(row)
        nodes.remove(original)
        return result,nodes
    if action not in ('split','join'):raise ValueError('Unknown topology operation.')
    if action=='split' and name in nodes:raise ValueError('That node already exists.')
    if action=='join':
        if name not in nodes:raise ValueError('The destination node no longer exists.')
        if any({r['from'],r['to']}=={original,name} for r in rows):
            raise ValueError('These nodes already have an edge.')
    touching=[r for r in rows if original in (r['from'],r['to'])]
    template=touching[0] if touching else rows[0] if rows else prototype
    if template is None:raise ValueError('Cannot determine episode for an empty graph.')
    def new_id():return template['episode']+'-'+uuid.uuid4().hex[:12]
    if inherit and action=='split':
        for source in touching:
            row=dict(source);row['edge_id']=new_id()
            row['from']=name if row['from']==original else row['from']
            row['to']=name if row['to']==original else row['to']
            rows.append(row)
    link={key:'' for key in template}
    link.update(edge_id=new_id(),episode=template['episode'],**{'from':original,'to':name},
                relation='SPLIT_FROM' if action=='split' else 'JOIN',layer=template['layer'],status='CONFIRMED',decision_basis='HUMAN_EDIT',evidence_refs='[]')
    rows.append(link);nodes.add(name)
    return rows,nodes


def edit(path, expected, action, original, name, inherit=False):
    path=Path(path)
    lock=path.with_suffix('.topology.lock')
    handle=lock.open('x')
    try:
        before=path.read_bytes();rows=load_edges(path)
        if rows!=expected:raise ValueError('Graph changed on disk. Refresh before editing.')
        fields=next(csv.reader(io.StringIO(before.decode('utf-8-sig')),delimiter='\t'))
        prototype={k:'' for k in fields};prototype.update(episode=path.parent.name,layer='NARRATIVE')
        result,nodes=transform(rows,node_names(path,rows),action,original,name,inherit,prototype)
        output=io.StringIO(newline='')
        writer=csv.DictWriter(output,fieldnames=fields,delimiter='\t',lineterminator='\n')
        writer.writeheader();writer.writerows(result)
        archive=path.parent/'.history'/uuid.uuid4().hex;archive.mkdir(parents=True)
        (archive/path.name).write_bytes(before)
        sidecar=path.with_suffix('.nodes.json')
        if sidecar.exists():(archive/sidecar.name).write_bytes(sidecar.read_bytes())
        # Record topology lineage; original edge records and Why remain recoverable.
        (archive/'operation.json').write_text(json.dumps(dict(action=action,original=original,name=name,inherit=inherit),ensure_ascii=False),encoding='utf-8')
        temp=archive/'new.tsv';temp.write_text(output.getvalue(),encoding='utf-8')
        load_edges(temp)
        if path.read_bytes()!=before:raise ValueError('Graph changed during edit.')
        old_sidecar=sidecar.read_bytes() if sidecar.exists() else None
        def atomic_write(target,data):
            fd,tempname=tempfile.mkstemp(dir=target.parent,suffix='.tmp')
            try:
                with os.fdopen(fd,'wb') as stream:
                    stream.write(data);stream.flush();os.fsync(stream.fileno())
                os.replace(tempname,target)
            finally:
                if os.path.exists(tempname):os.unlink(tempname)
        try:
            atomic_write(sidecar,json.dumps(sorted(nodes),ensure_ascii=False,indent=2).encode('utf-8'))
            os.replace(temp,path)
        except Exception:
            if old_sidecar is None:sidecar.unlink(missing_ok=True)
            else:atomic_write(sidecar,old_sidecar)
            raise
        return result
    finally:
        handle.close();lock.unlink()


def nearest_nodes(positions, node, limit=5):
    if node not in positions:return []
    x,y=positions[node]
    return sorted((n for n in positions if n!=node),
                  key=lambda n:((positions[n][0]-x)**2+(positions[n][1]-y)**2,n))[:limit]
