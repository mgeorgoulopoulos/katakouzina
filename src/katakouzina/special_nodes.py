"""Optional dataset-defined node colors."""
import json
import re
from pathlib import Path

def load_special_nodes(data_path):
    path=Path(data_path)/'special_nodes.json'
    if not path.exists():return {}
    colors=json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(colors,dict):raise ValueError('special_nodes.json must map node labels to colors')
    if any(not isinstance(node,str) or not node or not isinstance(color,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',color) for node,color in colors.items()):
        raise ValueError('Special node colors must be #RRGGBB values with non-empty node labels')
    return colors
