import json
import unittest

from core.firered import Field
from core.jj_tile_memory import (
    blocked_tiles, confirm_native_position, diagnostics, failures, probe_frames, record,
    refresh_on_verified_arrival,
)


def field(pos=(2,2),map_id=(1,2),callback=0x08001235,tiles=None):
    return (Field(map_id,pos,7,7,tuple(tiles or [0]*49)),callback,set())


class NativeTileMemoryTests(unittest.TestCase):
    def test_one_short_noop_is_not_an_impassable_tile(self):
        meta={}
        start=field()
        cmd=("move",(3,2))
        self.assertEqual(record(meta,start,start,cmd,
                         verified_before=True,verified_after=True),"retry")
        self.assertEqual(failures(meta,(1,2),(3,2)),1)
        self.assertEqual(probe_frames(meta,(1,2),(3,2)),12)
        self.assertEqual(blocked_tiles(meta,(1,2)),set())
        self.assertEqual(record(meta,start,start,cmd,
                         verified_before=True,verified_after=True),"blocked")
        self.assertEqual(blocked_tiles(meta,(1,2)),{(3,2)})
        self.assertEqual(diagnostics(meta)["blocked_tiles"],1)
        self.assertEqual(json.loads(json.dumps(meta))["tile_observations"],meta["tile_observations"])

    def test_authoritative_player_position_clears_stale_blocked_warp(self):
        meta={};start=field((2,2),(43,1))
        command=("move",(3,2))
        for _ in range(2):
            record(meta,start,start,command,
                   verified_before=True,verified_after=True)
        self.assertEqual(blocked_tiles(meta,(43,1)),{(3,2)})
        # A screenshot or an unverified script/fade cannot clear collision.
        self.assertFalse(confirm_native_position(meta,(43,1),(3,2),verified=False))
        self.assertEqual(blocked_tiles(meta,(43,1)),{(3,2)})
        # Once a fully corroborated native field reports the player there,
        # the provisional wall is disproved, so a door reentry is possible.
        self.assertTrue(confirm_native_position(meta,(43,1),(3,2),verified=True))
        self.assertEqual(blocked_tiles(meta,(43,1)),set())
        self.assertFalse(confirm_native_position(meta,(43,1),(3,2),verified=True))

    def test_arrival_overrides_old_observed_collision(self):
        meta={};s=field();command=("move",(3,2))
        for i in range(2):
            record(meta,s,s,command,verified_before=True,verified_after=True)
        moved=field((3,2))
        self.assertEqual(record(meta,s,moved,command,
                         verified_before=True,verified_after=True),"moved")
        self.assertEqual(blocked_tiles(meta,(1,2)),set())
        self.assertEqual(probe_frames(meta,(1,2),(3,2)),1)

    def test_no_false_bump_during_script_lock_battle_menu_or_warp(self):
        meta={};s=field();cmd=("move",(3,2))
        trials=[
            (s,s,False,True), (s,s,True,False), (s,None,True,True),
            (s,field((2,2),(5,6)),True,True),
            (s,field((2,2),callback=0x08009999),True,True),
            (s,field((4,2)),True,True),
        ]
        for before,after,ok1,ok2 in trials:
            self.assertIsNone(record(meta,before,after,cmd,
                verified_before=ok1,verified_after=ok2))
        self.assertIsNone(record(meta,s,s,("cross",None),
                               verified_before=True,verified_after=True))
        self.assertIsNone(record(meta,s,s,("move",(0,0)),
                               verified_before=True,verified_after=True))
        self.assertNotIn("tile_observations",meta)

    def test_native_collision_tile_not_override_with_guessed_passability(self):
        meta={};tiles=[0]*49;tiles[2*7+3]=0x03ff
        s=field(tiles=tiles)
        self.assertIsNone(record(meta,s,s,("move",(3,2)),
                         verified_before=True,verified_after=True))
        self.assertNotIn("tile_observations",meta)

    def test_reenter_map_forgets_only_dynamic_obstacles_with_native_proof(self):
        meta={}
        s=field((2,2),(1,2));dest=("move",(3,2))
        for _ in range(2):
            record(meta,s,s,dest,verified_before=True,verified_after=True)
        self.assertEqual(blocked_tiles(meta,(1,2)),{(3,2)})
        self.assertFalse(refresh_on_verified_arrival(meta,[3,4],[1,2],verified=False))
        self.assertFalse(refresh_on_verified_arrival(meta,[1,2],[1,2],verified=True))
        self.assertEqual(blocked_tiles(meta,(1,2)),{(3,2)})
        self.assertTrue(refresh_on_verified_arrival(meta,[3,4],[1,2],verified=True))
        self.assertEqual(blocked_tiles(meta,(1,2)),set())
        self.assertEqual(probe_frames(meta,(1,2),(3,2)),1)

    def test_per_map_and_storage_bounds(self):
        meta={}
        for i in range(78):
            start=field((2,2),(i//50,i%50))
            record(meta,start,start,("move",(3,2)),
                   verified_before=True,verified_after=True)
        self.assertLessEqual(diagnostics(meta)["maps"],48)
        self.assertEqual(failures(meta,(0,0),(3,2)),0)
        self.assertEqual(failures(meta,(1,27),(3,2)),1)


if __name__=="__main__":
    unittest.main()
