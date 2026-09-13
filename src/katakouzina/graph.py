"""Read-only graph discovery and projections, independent of the desktop UI."""
from pathlib import Path
import csv
import networkx as nx
from .evidence import references

REQUIRED = {'edge_id', 'episode', 'from', 'to', 'status', 'layer', 'relation'}
STATUSES = ('CONFIRMED', 'HYPOTHESIS', 'REJECTED')

def discover(data_dir):
    result = {}
    root = Path(data_dir)
    if root.exists():
        for episode in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith('.') and p.name!='srt'):
            graphs = sorted(p for p in episode.rglob('*.tsv') if not any(part.startswith('.') for part in p.relative_to(episode).parts))
            if graphs:
                result[episode.name] = graphs
    return result

def load_edges(path):
    path = Path(path)
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream, delimiter='\t')
        fields=set(reader.fieldnames or [])
        if fields & {'evidence','cue_ids','provenance','text','transcript'}:raise ValueError('Graph must contain timestamp references, not source text')
        missing = REQUIRED - fields
        if missing:
            raise ValueError('Missing columns: ' + ', '.join(sorted(missing)))
        rows = list(reader)
    ids, pairs = set(), set()
    for line, row in enumerate(rows, 2):
        if None in row or any(value is None for value in row.values()):
            raise ValueError(f'Row {line}: malformed TSV record')
        if not all(row[k].strip() for k in REQUIRED):
            raise ValueError(f'Row {line}: empty required field')
        if row['status'] not in STATUSES:
            raise ValueError(f'Row {line}: unknown status {row["status"]}')
        key = (row['episode'], *sorted((row['from'], row['to'])))
        if row['edge_id'] in ids or key in pairs:
            raise ValueError(f'Row {line}: duplicate edge ID or node pair')
        if row['from'] == row['to']:
            raise ValueError(f'Row {line}: self-loop')
        references(row)
        ids.add(row['edge_id']); pairs.add(key)
    return rows

def project(rows, status='ALL', layer='ALL', hide_leaves=False, focus=None, rejected_ids=(), show_rejected=False):
    graph = nx.Graph()
    for row in rows:
        if (status == 'ALL' or row['status'] == status or (show_rejected and row.get('edge_id') in rejected_ids)) and (layer == 'ALL' or row['layer'] == layer):
            if row.get('edge_id') in rejected_ids and not show_rejected:
                graph.add_nodes_from((row['from'],row['to']))
            else:
                graph.add_edge(row['from'], row['to'], record=row)
    global_leaves = {n for n, degree in graph.degree if degree == 1}
    if focus:
        if focus not in graph:
            raise ValueError(f'Node not found in this projection: {focus}')
        visible = set(nx.single_source_shortest_path_length(graph, focus, cutoff=2))
    else:
        visible = set(graph)
    if hide_leaves:
        visible -= global_leaves
    return graph.subgraph(visible).copy()

def layout(graph):
    if not graph:
        return {}
    # Force method avoids the optional SciPy-backed energy solver for large graphs.
    coordinates = nx.spring_layout(graph, seed=42, iterations=90, method='force')
    return {node: (float(xy[0]), float(xy[1])) for node, xy in coordinates.items()}
