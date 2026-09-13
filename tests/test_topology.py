import json
import tempfile
import unittest
from pathlib import Path
from katakouzina.graph import load_edges
from katakouzina.topology import transform,edit,node_names


def row(key,a,b):
    return dict(edge_id=key,episode='demo',**{'from':a,'to':b},relation='TOPIC',layer='NARRATIVE',status='CONFIRMED',decision_basis='SYNTHETIC',evidence_refs='[]',reason='Original',external_sources='')


class TopologyTests(unittest.TestCase):
    def test_merge_collapses_pairs_and_retains_evidence(self):
        rows=[row('ab','a','b'),row('ac','a','c'),row('bc','b','c')]
        ref={'episode':'demo','start':'00:00:01,000','end':'00:00:02,000'}
        rows[2]['evidence_refs']=json.dumps([ref])
        result,nodes=transform(rows,{'a','b','c'},'merge','b','a')
        self.assertEqual(nodes,{'a','c'})
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['edge_id'],'ac')
        self.assertEqual(json.loads(result[0]['evidence_refs']),[ref])
        self.assertEqual(rows[2]['from'],'b')

    def test_split_inheritance_and_validation(self):
        rows=[row('ab','a','b')]
        for inherit,count in ((False,2),(True,3)):
            result,nodes=transform(rows,{'a','b'},'split','a','new',inherit)
            self.assertEqual(len(result),count)
            self.assertEqual(nodes,{'a','b','new'})
            self.assertEqual(result[-1]['relation'],'SPLIT_FROM')
            self.assertEqual(result[-1]['reason'],'')
            self.assertEqual(len({r['edge_id'] for r in result}),count)
        for name in ('','a','b'):
            with self.assertRaises(ValueError):transform(rows,{'a','b'},'split','a',name)

    def test_save_reload_isolated_node_and_stale_edit(self):
        import shutil
        source=Path(__file__).resolve().parents[1]/'example-data/demo/edges.tsv'
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'edges.tsv';shutil.copy2(source,path)
            rows=load_edges(path);a,b=rows[0]['from'],rows[0]['to']
            result=edit(path,rows,'split',a,'New')
            self.assertEqual(load_edges(path),result)
            with self.assertRaises(ValueError):edit(path,rows,'split',a,'Another')
            self.assertTrue(list((path.parent/'.history').glob('*/edges.tsv')))
            while len(node_names(path,result))>1:
                edge=result[0]
                result=edit(path,result,'merge',edge['from'],edge['to'])
            self.assertEqual(result,[])
            only=next(iter(node_names(path,result)))
            result=edit(path,result,'split',only,'Reborn')
            self.assertEqual(len(result),1)
            self.assertEqual(load_edges(path),result)

    def test_join_and_nearest_five(self):
        from katakouzina.topology import nearest_nodes
        positions={'a':(0,0),'b':(3,4),'c':(1,0),'d':(2,0),'e':(3,0),'f':(4,0),'g':(100,100)}
        self.assertEqual(nearest_nodes(positions,'a'),['c','d','e','f','b'])
        self.assertEqual(nearest_nodes({'a':(0,0)},'a'),[])
        rows=[row('ab','a','b')]
        result,nodes=transform(rows,{'a','b','c'},'join','a','c')
        self.assertEqual(nodes,{'a','b','c'})
        self.assertEqual(result[0],rows[0])
        self.assertEqual(result[-1]['relation'],'JOIN')
        self.assertEqual(result[-1]['evidence_refs'],'[]')
        self.assertEqual(result[-1]['reason'],'')
        for name in ('a','b','missing'):
            with self.assertRaises(ValueError):transform(rows,{'a','b','c'},'join','a',name)
