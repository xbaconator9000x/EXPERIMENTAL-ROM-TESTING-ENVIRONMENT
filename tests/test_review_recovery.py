"""Deterministic tests for the unattended review recovery ladder."""
import unittest
from core.review_recovery import LADDER,SPACING_SECONDS,recover,changed

def frame(text=False,field=False):
    b=bytearray(bytes((0,0,0))*38400)
    if text:
        for y in range(126,133):
            b[(y*240+22)*3:(y*240+86)*3]=bytes((220,15,15))*64
    if field:
        for y in range(16,82):
            b[(y*240+25)*3:(y*240+150)*3]=bytes((65,115,190))*125
    return bytes(b)

class RecoveryTests(unittest.TestCase):
    def run_case(self,progress_at=None,visual=None,permit=lambda rgb,key:True,
                 stop_after=None,prior=None):
        calls=[];waits=[];meta=prior if prior is not None else {}
        def press(key,n):
            calls.append((key,n))
            return frame(text=True) if progress_at==len(calls) else frame()
        def delay(n):
            waits.append(n)
            return stop_after is None or len(waits)<stop_after
        status,rgb=recover(meta,frame(),press=press,delay=delay,
                           permit=permit,visual=visual)
        return status,rgb,meta,calls,waits

    def test_first_a_exits_without_vision(self):
        status,rgb,meta,calls,waits=self.run_case(progress_at=1)
        self.assertEqual(status,"PROGRESS")
        self.assertEqual(calls,[("A",4)])
        self.assertEqual(waits,[])

    def test_exact_timed_full_ladder_then_review(self):
        status,_,meta,calls,waits=self.run_case()
        self.assertEqual(status,"EXHAUSTED")
        self.assertEqual(len(calls),32)
        self.assertEqual([x[0] for x in calls],
             [button for button,count in LADDER for _ in range(count)])
        self.assertEqual(waits,[SPACING_SECONDS]*31)
        self.assertEqual(meta["review_recovery"]["status"],"EXHAUSTED")
        # The identical screen cannot consume another 5 minutes of inputs.
        again,_,_,next_calls,_=self.run_case(prior=meta)
        self.assertEqual(again,"EXHAUSTED")
        self.assertEqual(next_calls,[])

    def test_b_after_ten_a_and_direction_after_b(self):
        status,_,_,calls,_=self.run_case(progress_at=11)
        self.assertEqual(status,"PROGRESS")
        self.assertEqual(calls[-1][0],"B")
        status,_,_,calls,_=self.run_case(progress_at=21)
        self.assertEqual(status,"PROGRESS")
        self.assertEqual(calls[-1][0],"UP")

    def test_visual_only_after_deterministic_steps(self):
        consulted=[]
        def visual(rgb,i):
            consulted.append(i)
            return ("A",4) if i==0 else None
        status,_,meta,calls,_=self.run_case(progress_at=33,visual=visual)
        self.assertEqual(status,"PROGRESS")
        self.assertEqual(len(calls),33)
        self.assertEqual(consulted,[0])
        self.assertEqual(meta["review_recovery"]["visual_consults"],1)

    def test_native_position_witness_stops_ladder_without_pixel_change(self):
        calls=[]
        flags={"moved":False}
        def press(button,n):
            calls.append(button)
            flags["moved"]=len(calls)==2
            return frame()
        result,screen=recover({},frame(),press=press,delay=lambda n:True,
                              permit=lambda rgb,key:True,
                              witness=lambda:flags["moved"])
        self.assertEqual(result,"PROGRESS")
        self.assertEqual(calls,["A","A"])

    def test_unsafe_choice_skips_blind_presses(self):
        consulted=[]
        def visual(rgb,i):
            consulted.append(i)
            return None
        status,_,meta,calls,_=self.run_case(permit=lambda rgb,key:False,visual=visual)
        self.assertEqual(status,"EXHAUSTED")
        self.assertEqual(calls,[])
        self.assertEqual(consulted,[0])

    def test_stop_during_interval_is_not_review(self):
        status,_,meta,calls,_=self.run_case(stop_after=1)
        self.assertEqual(status,"INTERRUPTED")
        self.assertEqual(len(calls),1)
        self.assertEqual(meta["review_recovery"]["status"],"INTERRUPTED")

    def test_small_sprites_do_not_signal_game_progress(self):
        a=frame()
        b=bytearray(a)
        for y in range(65,70):
            b[(y*240+120)*3:(y*240+126)*3]=bytes((200,200,200))*6
        self.assertFalse(changed(a,bytes(b)))
        self.assertTrue(changed(a,frame(text=True)))
        self.assertTrue(changed(a,frame(field=True)))

if __name__=="__main__":unittest.main()
