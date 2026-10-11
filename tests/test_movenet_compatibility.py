"""Compatibility contract and recorded image-coordinate inverse regressions."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('check_movenet_compatibility', ROOT/'scripts/check_movenet_compatibility.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def tensor_spec(shape, dtype):
    return SimpleNamespace(shape=SimpleNamespace(as_list=lambda:shape), dtype=SimpleNamespace(name=dtype))


def signature(input_key='actual_name', dtype='int32', shape=None):
    return SimpleNamespace(structured_input_signature=((), {input_key:tensor_spec(shape or [1,None,None,3],dtype)}),
        structured_outputs={'output_0':tensor_spec([1,6,56],'float32')})


def geometry():
    mask=np.zeros((256,256),dtype=np.float32)
    mask[55:199,:]=1
    return gate.geometry_from_mask(mask,720,1280)


class MovenetGateTests(unittest.TestCase):
    def test_runtime_guard_detects_changed_installed_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve()
            executable=root/'python.exe';executable.write_bytes(b'isolated-runtime')
            library=root/'library.py';library.write_bytes(b'original')
            inventory=root/'inventory.json'
            inventory.write_text(json.dumps({'files':{'library.py':gate.sha(library)}}))
            lock=root/'lock.json'
            lock.write_text(json.dumps({'packages':[],'python':gate.sys.version,
                'executable_sha256':gate.sha(executable),
                'installed_inventory':{'path':'inventory.json','sha256':gate.sha(inventory)}}))
            ref={'path':'lock.json','sha256':gate.sha(lock)}
            with patch.object(gate.importlib.metadata,'distributions',return_value=[]), patch.object(gate.sys,'executable',str(executable)):
                gate.verify_runtime(root,ref)
                library.write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError,'Changed or outside'):
                    gate.verify_runtime(root,ref)

    def test_runtime_guard_detects_changed_python_executable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve()
            executable=root/'python.exe';executable.write_bytes(b'original')
            lock=root/'lock.json'
            lock.write_text(json.dumps({'packages':[],'python':gate.sys.version,
                                        'executable_sha256':gate.sha(executable)}))
            ref={'path':'lock.json','sha256':gate.sha(lock)}
            executable.write_bytes(b'changed')
            with patch.object(gate.importlib.metadata,'distributions',return_value=[]), patch.object(gate.sys,'executable',str(executable)):
                with self.assertRaisesRegex(ValueError,'executable differs'):
                    gate.verify_runtime(root,ref)

    def test_signature_records_real_argument_name_without_assuming_input(self):
        self.assertEqual(gate.inspect_signature(signature('unusual_name'))['input_key'],'unusual_name')

    def test_wrong_input_dtype_and_shape_fail_without_coercion(self):
        for item in (signature(dtype='uint8'),signature(shape=[1,256,256,3])):
            with self.assertRaises(ValueError):gate.inspect_signature(item)

    def test_output_contract_cannot_silently_switch_variant(self):
        for outputs in ({'other':tensor_spec([1,6,56],'float32')},
                        {'output_0':tensor_spec([1,1,17,3],'float32')},
                        {'output_0':tensor_spec([1,6,56],'float64')}):
            item=signature();item.structured_outputs=outputs
            with self.assertRaises(ValueError):gate.inspect_signature(item)

    def test_multiple_or_positional_inputs_rejected(self):
        item=signature();item.structured_input_signature=((tensor_spec([1,None,None,3],'int32'),),{})
        with self.assertRaises(ValueError):gate.inspect_signature(item)
        item=signature();item.structured_input_signature[1]['extra']=tensor_spec([1],'int32')
        with self.assertRaises(ValueError):gate.inspect_signature(item)

    def test_observed_asymmetric_padding_and_all_four_edges(self):
        g=geometry()
        self.assertEqual((g['resized_width'],g['resized_height'],g['pad_top'],g['pad_bottom']),(256,144,55,57))
        for source,native in (((0,0),(55/256,0)),((1280,720),(199/256,1)),((640,360),(127/256,.5))):
            np.testing.assert_allclose(gate.to_source_xy(*native,g),source,atol=1e-12)
            np.testing.assert_allclose(gate.to_target_yx(*source,g),native,atol=1e-12)

    def test_outside_content_kept_unclipped_and_nonfinite_rejected(self):
        self.assertLess(gate.to_source_xy(0,0,geometry())[1],0)
        self.assertGreater(gate.to_source_xy(1,1,geometry())[1],720)
        with self.assertRaises(ValueError):gate.to_source_xy(float('nan'),0,geometry())

    def test_mask_holes_soft_edges_empty_and_nonfinite_are_rejected(self):
        for kind in ('hole','soft','empty','nonfinite'):
            mask=np.zeros((256,256),dtype=np.float32);mask[55:199,:]=1
            if kind=='hole':mask[60,60]=0
            elif kind=='soft':mask[60,60]=.5
            elif kind=='empty':mask[:]=0
            else:mask[60,60]=np.nan
            with self.subTest(kind=kind),self.assertRaises(ValueError):gate.geometry_from_mask(mask,720,1280)

    def test_native_slots_preserve_all_low_scores_without_person_claims(self):
        raw=np.zeros((1,6,56),dtype=np.float32)
        raw[0,4,0:3]=[.5,.25,.001]
        slots=gate.native_slots(raw,geometry())
        self.assertEqual(len(slots),6)
        np.testing.assert_array_equal(slots[4]['native_yx_score'][0],raw[0,4,:3])
        self.assertEqual(len(slots[0]['joint_order']),17)
        self.assertTrue(all(s['subject_identity'] is None and s['observability'] is None for s in slots))
        self.assertNotIn('z',slots[0]);self.assertNotIn('visibility',slots[0]);self.assertNotIn('presence',slots[0])

    def test_nonfinite_or_different_native_output_fails(self):
        raw=np.zeros((1,6,56),dtype=np.float32);raw[0,0,0]=np.inf
        for value in (raw,raw.astype(np.float64),np.zeros((1,1,51),dtype=np.float32)):
            with self.assertRaises(ValueError):gate.native_slots(value,geometry())

    def test_scores_outside_contract_do_not_count_as_compatible(self):
        for index,value in ((2,-.01),(50,1.01),(55,-.1),(55,1.1)):
            raw=np.zeros((1,6,56),dtype=np.float32);raw[0,3,index]=value
            with self.assertRaises(ValueError):gate.native_slots(raw,geometry())

    def test_loaded_model_must_be_the_complete_bound_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);model=root/'model';model.mkdir()
            pb=model/'saved_model.pb';pb.write_bytes(b'savedmodel')
            refs=[{'path':'model/saved_model.pb','sha256':gate.sha(pb)}]
            gate.verify_model(root,model,refs)
            extra=model/'unbound';extra.write_bytes(b'extra')
            with self.assertRaises(ValueError):gate.verify_model(root,model,refs)
            extra.unlink()
            other=root/'other';other.mkdir();(other/'saved_model.pb').write_bytes(b'savedmodel')
            with self.assertRaises(ValueError):gate.verify_model(root,other,refs)

    def test_bound_sources_cannot_change_or_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=root/'sample';p.write_bytes(b'fixed')
            ref={'path':'sample','sha256':gate.sha(p)}
            self.assertEqual(gate.bound(root,ref),p)
            p.write_bytes(b'changed')
            with self.assertRaises(ValueError):gate.bound(root,ref)
            with self.assertRaises(ValueError):gate.bound(root,{'path':'../outside','sha256':'0'})

    def test_report_writer_preserves_prior_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'attempt.json';gate.write(path,{'attempt':1})
            with self.assertRaises(FileExistsError):gate.write(path,{'attempt':2})


if __name__=='__main__':unittest.main()
