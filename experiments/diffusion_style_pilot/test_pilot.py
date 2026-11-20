"""Offline contract checks for the standalone pilot."""
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np

from contracts import ARMS, sha256
from paper import pair
from train_pair import freeze_lists


class PaperTest(unittest.TestCase):
    def test_only_paper_changes_across_tile_boundaries(self):
        render = np.full((67, 113), 255, dtype=np.uint8)
        render[29:51, 36:87] = 45
        render[52, 87] = 250  # Protected antialiasing counts as glyph support.
        tiles = np.random.default_rng(123).integers(231, 256, (8, 64, 64), dtype=np.uint8)
        a, b, _ = pair(render, tiles, 'fixture')
        protected = render != 255
        np.testing.assert_array_equal(a[protected], render[protected])
        np.testing.assert_array_equal(b[protected], render[protected])
        np.testing.assert_array_equal(b, pair(render, tiles, 'fixture')[1])
        self.assertTrue(np.any(a[~protected] != b[~protected]))
        self.assertEqual(a.shape, b.shape)


class PairListTest(unittest.TestCase):
    def test_lists_follow_the_frozen_order_and_refuse_a_changed_encoding(self):
        with TemporaryDirectory(dir=Path.cwd()) as tmp:
            root = Path(tmp)
            work = root / 'work'
            work.mkdir()
            rows = []
            for i in (3, 1, 2):
                line_id = hashlib.sha256(str(i).encode()).hexdigest()
                row = {'id': line_id, 'label_sha256': line_id}
                for arm in ARMS:
                    relative = f'paired/{arm}/{line_id}.lstmf'
                    sample = root / relative
                    sample.parent.mkdir(parents=True, exist_ok=True)
                    sample.write_text(f'{arm} fixture {i}')
                    row[arm] = {'lstmf': relative, 'sha256': sha256(sample)}
                rows.append(row)
            manifest = root / 'pairs.jsonl'
            manifest.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            (root / 'pair-audit.json').write_text(json.dumps({
                'sha256': sha256(manifest), 'status': 'PASS', 'record': 'fixture', 'examined_pairs': 50,
            }))
            lists, count, _ = freeze_lists(root, work, minimum=1)
            self.assertEqual(count, 3)
            for name in ARMS:
                self.assertEqual(lists[name].read_text().splitlines(), [row[name]['lstmf'] for row in rows])
            sample.write_text('changed')
            with self.assertRaisesRegex(ValueError, 'diverges'):
                freeze_lists(root, work, minimum=1)


if __name__ == '__main__':
    unittest.main()
