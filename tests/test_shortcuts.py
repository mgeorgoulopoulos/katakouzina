import unittest
from katakouzina.shortcuts import action_for_scan

class ShortcutTests(unittest.TestCase):
    def test_physical_keys_and_modifiers(self):
        for scan,action in ((0x23,'hops'),(0x26,'leaves'),(0x24,'rejected'),(0x13,'arrange'),(0x14,'arrange'),(0x0d,'larger'),(0x4e,'larger'),(0x0c,'smaller'),(0x4a,'smaller')):
            self.assertEqual(action_for_scan(scan,4),action)
            self.assertEqual(action_for_scan(scan,5),action)
            for locks in (0x8, 0x2, 0x20, 0x8|0x2|0x20):
                self.assertEqual(action_for_scan(scan,4|locks),action)
                self.assertEqual(action_for_scan(scan,5|locks),action)
                self.assertIsNone(action_for_scan(scan,locks))
                self.assertIsNone(action_for_scan(scan,4|locks|0x20000))
            self.assertIsNone(action_for_scan(scan,0))
            self.assertIsNone(action_for_scan(scan,4|0x20000))
        self.assertIsNone(action_for_scan(0x2e,4))
