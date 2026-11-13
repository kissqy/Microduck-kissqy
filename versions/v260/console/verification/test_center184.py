"""Confirmed encoder centering accepts saved calibrations without changing them."""
import copy, unittest
from unittest.mock import Mock, patch
from service_control import ServiceController, ControlError, validate
from telemetry import Store, IDS

class InlineThread:
    def __init__(self,target,args=(),**kwargs): self.target,self.args=target,args
    def start(self): self.target(*self.args)

class CenterTests(unittest.TestCase):
    def setUp(self):
        self.command={'action':'center','unassembled':True,'duration_ms':2000}
        self.snapshot={'service_sample_fresh':True,'saved_calibrated_count':15,'calibrated_count':15,
            'bus':{'build':'1fa8438-feetech-ft6-control.56','mode':'commissioning','phase':'ready','torque_state':'off'},
            'servos':[{'id':i,'status':'live','calibrated':True} for i in IDS]}
        self.store=Store('service');self.store.snapshot=lambda:copy.deepcopy(self.snapshot)
        self.transport=Mock();self.transport.call.return_value={'completed_ids':list(IDS),'position_raw':2048,'torque':'off'}
        self.controller=ServiceController(self.store,transport=self.transport,warm=False)

    def test_confirmed_center_with_fifteen_saved_calibrations_is_forwarded_once(self):
        before=copy.deepcopy(self.snapshot)
        with patch('service_control.threading.Thread',InlineThread):
            reply=self.controller.handle({'client':'center184test','seq':1,'command':self.command})
        self.assertTrue(reply['accepted']);self.transport.call.assert_called_once_with(self.command)
        self.assertEqual(self.controller.job['status'],'completed');self.assertEqual(self.snapshot,before)

    def test_unchecked_and_nonboolean_confirmation_are_rejected(self):
        for confirmed in (False,None,1,'true'):
            with self.subTest(confirmed=confirmed),self.assertRaises(ControlError):
                validate({**self.command,'unassembled':confirmed})

    def test_existing_mode_moving_and_torque_requirements_remain(self):
        states=[('motion','control','off'),('commissioning','moving','off'),('commissioning','ready','single_joint_enabled')]
        for seq,(mode,phase,torque) in enumerate(states,1):
            self.snapshot['bus'].update(mode=mode,phase=phase,torque_state=torque)
            with self.subTest(mode=mode,phase=phase,torque=torque),self.assertRaises(ControlError):
                self.controller.handle({'client':'center184guard','seq':seq,'command':self.command})
        self.transport.call.assert_not_called()

if __name__=='__main__': unittest.main()
