import unittest
from unittest.mock import patch
from core.upstream_port import ReadOnlyClient, PortError, admit, LeafGreenPort, classic_effectiveness
from core.upstream_leafgreen.pathfinding import find_path
from core.upstream_leafgreen.memory_reader import decrypt_substructs, parse_species
from core.upstream_leafgreen.state import GameContext

class LiveFixture:
    sha256="0"*64
    def __init__(self):
        self.requests=[]
    def read(self,address,length):
        self.requests.append((address,length))
        return bytes((address+i)&255 for i in range(length))

class UpstreamPortTests(unittest.TestCase):
    def test_native_read_contract(self):
        live=LiveFixture()
        client=ReadOnlyClient(live)
        self.assertEqual(client.read32(0x02000001),0x04030201)
        self.assertEqual(len(client.read_range(0x02000000,65537)),65537)
        self.assertEqual(live.requests[-3:],[(0x02000000,32768),(0x02008000,32768),(0x02010000,1)])
        self.assertFalse(hasattr(client,"write8"))
        for address,length in [(0x04000000,1),(0x0203ffff,2),(0x03008000,1),(0x02000000,-1)]:
            with self.assertRaises(PortError):
                client.read_range(address,length)
    def test_real_upstream_decoder(self):
        raw=bytearray(100)
        raw[32:34]=(25).to_bytes(2,"little")
        self.assertEqual(parse_species(decrypt_substructs(raw)),25)
    def test_real_upstream_pathfinder(self):
        grid=[[True,False,True],[True,True,True]]
        path=find_path((0,0),(2,0),lambda x,y:grid[y][x],3,2)
        self.assertEqual(path,["Down","Right","Right","Up"])
    def test_profile_rejects_other_rom(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"test.gba"
            p.write_bytes(b"test")
            with self.assertRaises(PortError):
                admit(p,LiveFixture())
    def test_route_dispatches_to_upstream(self):
        p=LeafGreenPort(ReadOnlyClient(LiveFixture()))
        p.reader.detect_context=lambda:GameContext.OVERWORLD
        p.reader.read_player_pos=lambda:(0,0)
        p.tiles.refresh=lambda:True
        p.tiles._width,p.tiles._height=3,2
        p.tiles.passable_grid=lambda:([[True,False,True],[True,True,True]],3,2)
        self.assertEqual(p.route(2,0),["Down","Right","Right","Up"])
        self.assertIsNone(p.route(2,0,[(1,1)]))
        p.reader.detect_context=lambda:GameContext.IN_BATTLE
        with self.assertRaises(PortError):
            p.route(2,0)
    def test_classic_chart(self):
        self.assertEqual(classic_effectiveness("ELE",["WAT","FLY"]),4)
        self.assertEqual(classic_effectiveness("ELE",["GRD"]),0)
        self.assertEqual(classic_effectiveness("GHO",["STL"]),.5)

if __name__=="__main__":
    unittest.main()
