"""Actual ONNX Runtime CPU checks with tiny generated test graphs, not GPU QA."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from training.sim_protocol import OnnxPolicy

AVAILABLE=all(importlib.util.find_spec(name) is not None for name in ('numpy','onnx','onnxruntime'))


@unittest.skipUnless(AVAILABLE,'requires the isolated ONNX CPU test environment')
class OnnxExecutionTests(unittest.TestCase):
    def model(self,path,recurrent=False):
        import numpy as np
        import onnx
        from onnx import TensorProto,helper,numpy_helper
        inputs=[helper.make_tensor_value_info('obs',TensorProto.FLOAT,[1,3])]
        outputs=[helper.make_tensor_value_info('actions',TensorProto.FLOAT,[1,2])]
        weights=np.array([[1,0],[0,1],[1,1]],dtype=np.float32)
        initial=[numpy_helper.from_array(np.array([1,2,3],dtype=np.float32),'mean'),numpy_helper.from_array(weights,'w')]
        nodes=[helper.make_node('Sub',['obs','mean'],['normalized']),helper.make_node('MatMul',['normalized','w'],['actions'])]
        if recurrent:
            inputs.append(helper.make_tensor_value_info('h_in',TensorProto.FLOAT,[1,1,2]))
            outputs.append(helper.make_tensor_value_info('h_out',TensorProto.FLOAT,[1,1,2]))
            initial.append(numpy_helper.from_array(np.ones((1,1,2),dtype=np.float32),'one'))
            nodes.append(helper.make_node('Add',['h_in','one'],['h_out']))
        model=helper.make_model(helper.make_graph(nodes,'test',inputs,outputs,initial),opset_imports=[helper.make_opsetid('',17)])
        model.ir_version=9
        onnx.checker.check_model(model);onnx.save(model,path)

    def test_actual_onnx_executes_embedded_normalizer_exactly_once(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'policy.onnx';self.model(path)
            p=OnnxPolicy(path,3,2,['actor'],'cpu')
            np.testing.assert_allclose(p.infer_array([[2,4,6]]),[[4,5]])
            with self.assertRaisesRegex(ValueError,'观测维度'):OnnxPolicy(path,4,2,['actor'],'cpu')
            with self.assertRaisesRegex(ValueError,'动作维度'):OnnxPolicy(path,3,3,['actor'],'cpu')
            with self.assertRaisesRegex(ValueError,'无效值'):p.infer_array([[float('nan'),0,0]])

    def test_recurrent_state_is_carried_and_reset_between_episodes(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'recurrent.onnx';self.model(path,True)
            p=OnnxPolicy(path,3,2,['actor'],'cpu')
            p.infer_array([[1,2,3]]);p.infer_array([[1,2,3]])
            np.testing.assert_allclose(p.states['h_in'],2)
            p.reset();np.testing.assert_allclose(p.states['h_in'],0)


if __name__=='__main__':unittest.main()
