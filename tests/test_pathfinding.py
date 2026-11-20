import importlib.util
from pathlib import Path
import unittest

p = Path(__file__).resolve().parents[1] / "vendor/pokemon_agent/pathfinding.py"
spec = importlib.util.spec_from_file_location("vendor_pathfinding", p)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class Navigation(unittest.TestCase):
    def test_path_goes_around_wall(self):
        path = m.find_path((0, 0), (2, 0), lambda x,y: (x,y)!=(1,0), 3, 2)
        self.assertEqual(path, ["Down", "Right", "Right", "Up"])
    def test_no_path(self):
        self.assertIsNone(m.find_path((0,0),(2,0),lambda x,y:x!=1,3,2))
    def test_ledge(self):
        self.assertEqual(m.find_path((0,0),(0,2),lambda x,y:y!=1,1,3,ledge=lambda x,y:"Down" if y==1 else None),["Down"])
    def test_already_there(self):
        self.assertEqual(m.find_path((0,0),(0,0),lambda x,y:True,1,1),[])

if __name__ == "__main__":
    unittest.main()
