import json
import unittest
from katakouzina.arcs import build_arcs,timestamp


def edge(key,a,b,ranges):
    return {'edge_id':key,'from':a,'to':b,'evidence_refs':json.dumps([
        {'episode':'demo','start':start,'end':end} for start,end in ranges])}

class ArcTests(unittest.TestCase):
    def test_cross_product_uses_range_midpoints(self):
        a=edge('a','X','Y',[('00:00:00,000','00:00:02,000'),('00:00:04,000','00:00:08,000')])
        b=edge('b','Y','Z',[('00:00:10,000','00:00:12,000'),('00:00:20,000','00:00:24,000'),('00:00:30,000','00:00:32,000')])
        arcs=build_arcs([a,b])
        self.assertEqual(len(arcs),6)
        self.assertEqual({(a.time_a,a.time_b) for a in arcs},{(x,y) for x in (1,6) for y in (11,22,31)})
        self.assertTrue(all(a.shared_nodes==('Y',) for a in arcs))

    def test_nonadjacent_and_missing_evidence_produce_no_arcs(self):
        r=[('00:00:00,000','00:00:01,000')]
        self.assertEqual(build_arcs([edge('a','A','B',r),edge('b','C','D',r),edge('c','A','E',[])]),[])

    def test_equal_times_are_retained_and_pair_not_duplicated(self):
        r=[('00:00:00,000','00:00:01,000')]
        arcs=build_arcs([edge('a','A','B',r),edge('b','B','A',r)])
        self.assertEqual(len(arcs),1)
        self.assertEqual(arcs[0].shared_nodes,('A','B'))
        self.assertEqual(arcs[0].time_a,arcs[0].time_b)
        self.assertEqual(timestamp(arcs[0].time_a),'00:00:00.500')

    def test_physical_n_toggles_labels_without_redraw(self):
        from types import SimpleNamespace
        from unittest.mock import Mock,patch
        from katakouzina.arcs import ArcWindow
        ui=SimpleNamespace(show_names=True,canvas=Mock())
        with patch('katakouzina.arcs.ctypes.windll') as dll:
            dll.user32.MapVirtualKeyW.return_value=0x31
            self.assertEqual(ArcWindow.keypress(ui,SimpleNamespace(state=4|8,keycode=78)),'break')
            self.assertFalse(ui.show_names)
            ui.canvas.itemconfigure.assert_called_with('arc-name',state='hidden')
            ArcWindow.keypress(ui,SimpleNamespace(state=4,keycode=78))
            self.assertTrue(ui.show_names)
            ArcWindow.keypress(ui,SimpleNamespace(state=4|0x20000,keycode=78))
            self.assertTrue(ui.show_names)

    def test_close_cancels_pending_draw(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from katakouzina.arcs import ArcWindow
        ui=SimpleNamespace(pending='job',after_cancel=Mock(),destroy=Mock())
        self.assertEqual(ArcWindow.close(ui),'break')
        ui.after_cancel.assert_called_once_with('job')
        ui.destroy.assert_called_once()

    def test_pixel_bins_merge_pairs_and_refine_with_width(self):
        from katakouzina.arcs import TemporalArc,bin_arcs
        arcs=[TemporalArc('a','b',('X',),'demo','demo',1,11),
              TemporalArc('c','d',('Y',),'demo','demo',2,12),
              TemporalArc('e','f',('X',),'demo','demo',11,1)]
        coarse=bin_arcs(arcs,20,20)
        self.assertEqual(len(coarse),1)
        self.assertEqual(coarse[(0,1)]['count'],3)
        self.assertEqual(coarse[(0,1)]['nodes'],{'X','Y'})
        fine=bin_arcs(arcs,20,200)
        self.assertEqual(len(fine),2)
        self.assertEqual(sum(v['count'] for v in fine.values()),3)

    def test_bin_end_boundary_and_same_bin_loop(self):
        from katakouzina.arcs import TemporalArc,bin_arcs
        arc=TemporalArc('a','b',('X',),'demo','demo',19,20)
        self.assertEqual(set(bin_arcs([arc],20,20)),{(1,1)})
