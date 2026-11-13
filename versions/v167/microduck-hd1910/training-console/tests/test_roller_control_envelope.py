"""Verify the frozen official roller push command can reach the simulation adapter."""
import unittest
from training.sim_protocol import SimulationControls

class RollerCommandEnvelopeTest(unittest.TestCase):
    def test_roller_vx_full_official_range(self):
        c=SimulationControls(lambda:100.0, limits=((-0.5,0.6),(0.0,0.0),(0.0,0.0)))
        c.receive({'action':'move','velocity':[0.6,1.0,-1.0],'expires_at':100.7})
        self.assertEqual(c.sample(),(0.6,0.0,0.0))
        c.receive({'action':'move','velocity':[-0.5,-1.0,1.0],'expires_at':100.7})
        self.assertEqual(c.sample(),(-0.5,0.0,0.0))
        c.receive({'action':'zero'})
        self.assertEqual(c.sample(),(0.0,0.0,0.0))
    def test_walker_keeps_unchanged_limits(self):
        c=SimulationControls(lambda:100.0)
        c.receive({'action':'move','velocity':[0.6,0.4,2.0],'expires_at':100.7})
        self.assertEqual(c.sample(),(0.4,0.3,1.0))
    def test_disallows_invalid_envelopes(self):
        with self.assertRaises(ValueError):SimulationControls(limits=((1,-1),(0,0),(0,0)))

if __name__=='__main__':unittest.main()
