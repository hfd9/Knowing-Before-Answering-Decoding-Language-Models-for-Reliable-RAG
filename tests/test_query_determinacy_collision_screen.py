import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import query_determinacy_collision_screen as screen


class CollisionScreenTests(unittest.TestCase):
    def test_nfkc_casefold_and_punctuation(self):
        result = screen.compare('ＡＢＣ，某个对象？', 'abc某个对象')
        self.assertTrue(result['exact'])
        self.assertTrue(result['short'])
        self.assertIsNone(result['near'])

    def test_long_containment_and_overlap(self):
        core = '甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳午未申酉'
        result = screen.compare(core, '前缀文本' + core + '后缀文本')
        self.assertFalse(result['exact'])
        self.assertTrue(result['containment'])
        self.assertTrue(result['near'])

    def test_nonmatch_is_not_unknown_for_long_and_short_stays_unknown(self):
        result = screen.compare('abcdefghijklmnop', 'qrstuvwxyz012345')
        self.assertFalse(result['exact'])
        self.assertFalse(result['containment'])
        self.assertFalse(result['near'])
        self.assertIsNone(screen.compare('甲乙', '丙丁')['containment'])

    def test_empty_text_rejected(self):
        with self.assertRaises(ValueError):
            screen.compare('？！', '有效文字')
        with self.assertRaises(TypeError):
            screen.compare(None, '有效文字')


if __name__ == '__main__':
    unittest.main()
