"""Non-visual startup regression check; the root stays withdrawn."""
import unittest
from pathlib import Path
from unittest.mock import patch
import tkinter as tk
from katakouzina.app import GraphBrowser

class StartupTests(unittest.TestCase):
    def test_widget_construction_and_episode_discovery(self):
        original = tk.Tk.__init__
        roots = []
        def hidden(root, *args, **kwargs):
            original(root, *args, **kwargs)
            root.withdraw()
            roots.append(root)
        try:
            with patch.object(tk.Tk, '__init__', hidden):
                app = GraphBrowser(Path(__file__).resolve().parents[1] / 'example-data')
            self.assertEqual(app.state(), 'withdrawn')
            self.assertTrue(app.paths)
            self.assertEqual(len(app.tree_nodes), 3)
            for child, (path, node) in app.tree_nodes.items():
                self.assertEqual(app.paths[app.tree.parent(child)], path)
                self.assertEqual(app.tree.item(child, 'text'), node)
            self.assertTrue(app.tree.selection())
            self.assertGreater(app.tree.column('#0', 'width'), 0)
            from katakouzina.graph import load_edges, project
            app.rows=load_edges(Path(__file__).resolve().parents[1] / 'example-data/demo/edges.tsv')
            app.graph=project(app.rows)
            row=app.rows[0]
            import tempfile,shutil
            from katakouzina.evidence import EvidenceLibrary,references
            with tempfile.TemporaryDirectory() as folder:
                public=Path(folder)
                app.evidence_library=EvidenceLibrary(public)
                app.inspect_edge(row)
                self.assertEqual(len(app.evidence_cards),len(references(row)))
                self.assertTrue(all(card[1:]==('','') for card in app.evidence_cards))
                self.assertEqual(app.why_editor.get('1.0','end-1c'),row['reason'])
                editor=app.why_editor;title=app.inspector_title.get()
                app.open_evidence(references(row)[0])
                self.assertIs(app.why_editor,editor)
                self.assertEqual(app.inspector_title.get(),title)
                self.assertEqual(app.dialogue_entries,[])
            app.verified_ids={row['edge_id']}
            app.inspect_node(row['from'])
            cards=[w for w in app.inspector_body.winfo_children() if isinstance(w,tk.Frame)]
            self.assertEqual(cards[0].cget('background'),'#243b30')
            app.rejected_reasons={row['edge_id']:''};app.verified_ids=set()
            app.inspect_node(row['from'])
            cards=[w for w in app.inspector_body.winfo_children() if isinstance(w,tk.Frame)]
            self.assertEqual(cards[0].cget('background'),'#402b30')
            self.assertEqual(next(iter(app.connection_rows)),row['edge_id'])
            self.assertTrue(app.connection_rows)
            app.inspect_edge(row)
            self.assertEqual(app.inspected_node,row['from'])
            app.current_path=Path(__file__).resolve().parents[1]/'example-data/demo/edges.tsv'
            app.positions={n:(i*33.5+120,i*17.0-89) for i,n in enumerate(app.graph)}
            original_positions=dict(app.positions)
            app.focus_text.set(row['from'])
            with patch.object(app,'render') as render, patch.object(app,'draw'):
                app.toggle_hops()
                self.assertTrue(app.hops_enabled.get())
                app.toggle_hops()
                self.assertFalse(app.hops_enabled.get())
                self.assertEqual(app.positions,original_positions)
                self.assertEqual(render.call_count,2)
                app.toggle_leaves()
                self.assertTrue(app.hide_leaves.get())
            app.hide_leaves.set(False)
            app.graph=project(app.rows)
            app.positions=original_positions.copy()
            with patch.object(app,'draw'),patch.object(app,'save_positions'),patch('katakouzina.app.layout',side_effect=AssertionError('Visibility must not arrange')):
                app.toggle_rejected_visibility()
                self.assertEqual(app.positions,original_positions)
                app.toggle_rejected_visibility()
                self.assertEqual(app.positions,original_positions)
                app.toggle_leaves()
                app.toggle_leaves()
                self.assertEqual(app.positions,original_positions)
                app.focus_text.set(row['from'])
                app.toggle_hops();app.toggle_hops()
                self.assertEqual(app.positions,original_positions)
            app.set_details()
            self.assertIsNone(app.inspected_edge)
            self.assertFalse(app.connection_rows)
        finally:
            for root in roots:
                root.destroy()

    def test_tree_node_framing_centers_and_preserves_layout(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        import networkx as nx
        graph=nx.path_graph(['a','b','c','d'])
        positions={'a':(0,0),'b':(100,50),'c':(200,0),'d':(1000,0)}
        ui=SimpleNamespace(pending_tree_node='a',graph=graph,positions=positions.copy(),
            all_positions=dict(positions,hidden=(1500,0)),canvas=Mock(),focus_text=Mock(),inspect_node=Mock())
        ui.canvas.winfo_width.return_value=1000;ui.canvas.winfo_height.return_value=700
        GraphBrowser.frame_tree_node(ui)
        self.assertEqual(ui.positions['a'],(500,350))
        self.assertEqual(ui.selected_node,'a')
        self.assertIsNone(ui.pending_tree_node)
        ui.inspect_node.assert_called_once_with('a')
        self.assertEqual(set(ui.positions),set(positions))
        scale=(ui.positions['b'][0]-500)/100
        self.assertAlmostEqual(ui.positions['c'][0],500+200*scale)
        self.assertAlmostEqual(ui.all_positions['hidden'][0],500+1500*scale)
        self.assertLess(ui.positions['c'][0],1000)
        self.assertGreater(ui.positions['d'][0],1000)

    def test_drag_updates_only_node_and_incident_edges(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        import networkx as nx
        ui=SimpleNamespace(drag_origin=(0,0),drag_node='a',positions={'a':(10,20),'b':(30,40),'c':(50,60)},
            all_positions={'a':(10,20),'b':(30,40),'c':(50,60),'hidden':(70,80)},
            node_items={'a':(1,2)},edge_items={frozenset(('a','b')):3,frozenset(('b','c')):4},
            graph=nx.path_graph(['a','b','c']),canvas=Mock(),position_save_job=None,after=Mock(),save_positions=Mock())
        GraphBrowser.drag(ui,SimpleNamespace(x=5,y=7))
        self.assertEqual(ui.positions['a'],(15,27))
        self.assertEqual(ui.positions['b'],(30,40))
        self.assertEqual(ui.all_positions['hidden'],(70,80))
        self.assertEqual(ui.canvas.move.call_count,2)
        ui.canvas.coords.assert_called_once_with(3,15,27,30,40)
        ui.canvas.delete.assert_not_called()
        ui.after.assert_called_once_with(500,ui.save_positions)
