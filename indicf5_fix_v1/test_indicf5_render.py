import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name('indicf5_render.py')
spec = importlib.util.spec_from_file_location('indicf5_render', SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class StateDictTests(unittest.TestCase):
    def test_removes_compile_prefix_and_vocoder(self):
        result = mod._normalise_state_dict({
            '_orig_mod.layer.weight': object(),
            'vocoder.decoder.weight': object(),
        })
        self.assertEqual(list(result), ['layer.weight'])

    def test_handles_wrapped_state_dict(self):
        value = object()
        result = mod._normalise_state_dict({'model_state_dict': {'_orig_mod.a': value}})
        self.assertIs(result['a'], value)

    def test_duplicate_after_prefix_cleanup_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'collision'):
            mod._normalise_state_dict({'_orig_mod.a': 1, 'a': 2})

    def test_empty_checkpoint_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'no usable'):
            mod._normalise_state_dict({'vocoder.a': 1})


if __name__ == '__main__':
    unittest.main(verbosity=2)
