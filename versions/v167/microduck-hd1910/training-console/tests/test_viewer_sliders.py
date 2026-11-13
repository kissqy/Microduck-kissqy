import copy
import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
from training.runtime_adapter import fix_velocity_gui_sliders

class SliderTests(unittest.TestCase):
    def test_scoped_fix_leaves_normal_and_unrelated_sliders_unchanged(self):
        calls=[]
        def original(label,**kw):calls.append((label,kw));return kw
        gui=NS(add_slider=original);restore=fix_velocity_gui_sliders(NS(gui=gui))
        with patch('training.runtime_adapter.emit'):
            for label,value in [('Max lin_vel_x',.01),('Max lin_vel_y',.01),('Max ang_vel_z',.05),('Max lin_vel_x',0)]:
                kw=gui.add_slider(label,initial_value=value,min=.1,max=10.,step=.1)
                self.assertEqual(kw['initial_value'],value);self.assertEqual(kw['min'],0)
                self.assertGreater(kw['step'],0)
            for label,value in [('Max lin_vel_x',.4),('Other slider',.01)]:
                kw={'initial_value':value,'min':.1,'max':10.,'step':.1}
                self.assertEqual(gui.add_slider(label,**kw),kw)
        restore();self.assertIs(gui.add_slider,original)

    @unittest.skipUnless(importlib.util.find_spec('viser'), 'Optional Viser integration dependency not installed')
    def test_real_viser_reproduces_then_accepts_upstream_small_and_zero_limits(self):
        import viser
        from importlib.metadata import version
        print("Real Viser API:",version("viser"))
        spec=importlib.util.spec_from_file_location('velocity_fixture',Path(__file__).parent/'fixtures/velocity_gui_mjlab.py')
        fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
        server=viser.ViserServer(host='127.0.0.1',port=0)
        ranges=NS(lin_vel_x=(-.01,.01),lin_vel_y=(-.01,.01),ang_vel_z=(-.05,.05))
        term=NS(cfg=NS(ranges=ranges));before=copy.deepcopy(ranges)
        try:
            with self.assertRaises((AssertionError, ValueError)):fixture.create_gui(term,'broken',server,lambda:0)
            restore=fix_velocity_gui_sliders(server)
            with patch('training.runtime_adapter.emit'):
                fixture.create_gui(term,'fixed',server,lambda:0)
                self.assertEqual(term.cfg.ranges,before)
                self.assertFalse(term._joystick_enabled.value)
                self.assertEqual([s.value for s in term._joystick_sliders],[0.,0.,0.])
                zero=NS(cfg=NS(ranges=NS(lin_vel_x=(0.,0.),lin_vel_y=(0.,0.),ang_vel_z=(0.,0.))))
                fixture.create_gui(zero,'zero',server,lambda:0)
                self.assertEqual([s.value for s in zero._joystick_sliders],[0.,0.,0.])
                walk=NS(cfg=NS(ranges=NS(lin_vel_x=(-.4,.4),lin_vel_y=(-.3,.3),ang_vel_z=(-1.,1.))))
                fixture.create_gui(walk,'walk',server,lambda:0)
                self.assertEqual([s.max for s in walk._joystick_sliders],[.4,.3,1.])
            restore()
        finally:server.stop()

if __name__=='__main__':unittest.main()
