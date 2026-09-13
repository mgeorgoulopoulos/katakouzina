# Technical guide

## Run

Install Python 3.11+ with Tcl/Tk, then double-click `launch.bat`.
Setup creates a virtual environment; later runs work offline.
On first run, gitignored `config.json` is generated with:

```json
{
  "data_path": "example-data",
  "show_rejected_edges": false,
  "hide_leaves": false,
  "graph_font_size": 18,
  "start_maximized": true
}
```

Use an absolute data_path or one relative to config.json. Missing or null data_path
uses the bundled example. Restart after changing it. View preferences save on close.
The optional `--data-path` argument overrides the configured dataset for that launch.

## Dataset layout

```text
dataset-root/
  demo/
    edges.tsv
  srt/
    demo.srt
```

The bundled `example-data` has three nodes, two edges, and two wholly invented,
explicitly labeled synthetic subtitle cues. It is sufficient to explore the UI and
run the tests without any external dataset.

Each episode folder contains graph TSV files. The optional srt subdirectory contains
matching episode-code SRT files. Without it, or without an overlapping subtitle,
evidence displays the episode and timestamps only. There is no summary fallback.
Subtitle cue numbering may differ; recordings must use the same timeline.

The graph stores episode/start/end references, never dialogue. Why is editable curation
text. Curations are stored in each episode's curation.json; node
coordinates are sidecars beside its graph. Existing Why content is preserved.
A dataset can be maintained as an independent Git repository. Only include source
material you are authorized to distribute.

## Controls

- Single-click a graph node or edge. Double-click a connection in a node inspector.
- Click evidence to update the same-panel reader.
- Drag nodes to move; drag blank space to pan; mouse wheel to zoom.
- Ctrl+H: two-hop view. Ctrl+L: leaves. Ctrl+J: rejected edges. Also available in View.
- Ctrl+T: arrange. Ctrl +/−: graph font size. Physical Windows key positions work across input languages.
- View toggles preserve coordinates and viewport. Fit and Arrange change them explicitly.
- Accepted edges are green; rejected edges are hidden by default, red when shown; neutral edges are blue.
- Reject applies immediately. Why can be edited afterward. Coordinates save automatically.

## Development

```powershell
$env:PYTHONPATH = "$PWD\src"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe tools/check_public.py
```

The application repository contains code and synthetic example data only. The
public-file check inspects prospective files and Git's index, and optionally compares
against the configured local corpus. It is not legal clearance. Tests do not perform
visual verification.

Optional special_nodes.json at the dataset root maps exact node labels to #RRGGBB colors. These colors override selection and two-hop colors. The example marks Moon red. Reload the graph after editing this file.

See DATA_MODEL.md for the text curation schema and AI proposal workflow.

Right-click an edge to merge its endpoints, or a node to split it. Split edge inheritance is off by default.

## Arc diagram

Tools → Arc diagram opens a snapshot of the current rendered graph, respecting its
filters and deletions. Original edges become vertices of a line graph: each pair
sharing an original node produces arcs for the full cross-product of its evidence
ranges. A range contributes its midpoint in elapsed seconds. Pairs are unordered
and generated once; equal-time combinations remain as small loops. Edges without
evidence cannot contribute arcs. Colors group arcs by shared node. Endpoints are grouped into 10-pixel bins and each unordered bin pair is drawn once.
Resize or zoom recalculates the bins; wider plots resolve smaller time intervals.
Labels combine the shared node names. The slider zooms horizontally and dragging pans.
Episode timestamps use the same elapsed-time axis. There are no hover details.
No subtitles or graph records are modified by this view.

Arc labels identify shared nodes at each apex. Ctrl+N toggles labels without changing the viewport; Escape closes the arc window.
