"""Bounded, auditable recovery before a native gameplay NEEDS_REVIEW hold.

All clock delays refer to real elapsed seconds, not GBA frames. This module
never reads or uploads ROM/save bytes. The host supplies its ordinary native
controller, verified screenshot and checkpoint callbacks.
"""
import hashlib
from core.jj_fast import ordinary_dialogue

SPACING_SECONDS = 10
LADDER = (("A",10),("B",10),("UP",3),("DOWN",3),("LEFT",3),("RIGHT",3))
VISUAL_TRIES = 2

def text_region(rgb):
    """The bottom Gen III message window; ignores animated overworld sprites."""
    if len(rgb)!=240*160*3:return ""
    return hashlib.sha256(b"".join(
        rgb[(y*240+18)*3:(y*240+204)*3] for y in range(120,152)
    )).hexdigest()

def changed(before,after):
    """Candidate UI/field change, never acceptance proof by itself."""
    if len(before)!=115200 or len(after)!=115200:return False
    # The lower-screen character sprite can walk across the usual text-box
    # area (especially on a doorway). Pixel movement there is NOT dialogue
    # progress unless a full-width field textbox was really present.
    before_page=ordinary_dialogue(before)
    after_page=ordinary_dialogue(after)
    if (before_page is not None or after_page is not None) and before_page!=after_page:
        return True
    # Animation of a single sprite is not verified progress. The display must
    # change extensively outside the text region for an unclassified scene.
    changed_blocks=0
    for y in range(8,112,4):
        for x in range(8,232,4):
            p=(y*240+x)*3
            if (abs(before[p]-after[p])+abs(before[p+1]-after[p+1])+
                    abs(before[p+2]-after[p+2])>=120):
                changed_blocks+=1
    return changed_blocks>=95

def recover(meta,rgb,*,press,delay,permit,visual=None,report=None,witness=None):
    """Try the user-ordered ladder, then at most two visual decisions.

    press(button,frames) returns the post-settle RGB and checkpoints it locally.
    delay(seconds) returns False if interrupted by stop/operator control.
    permit(rgb,button) rejects unsafe choice/battle/menu interventions.
    visual(rgb,attempt) returns a validated single short (button,frames)
    proposal or None. No inference is allowed during the deterministic ladder.
    Return 'PROGRESS', 'EXHAUSTED', or 'INTERRUPTED'.
    """
    previous=meta.get("review_recovery")
    fingerprint=hashlib.sha256(rgb).hexdigest()
    if isinstance(previous,dict) and previous.get("screen")==fingerprint and previous.get("status")=="EXHAUSTED":
        return "EXHAUSTED",rgb
    state={"screen":fingerprint,"status":"RUNNING","phase":"A",
           "attempts":0,"visual_consults":0,"last_button":None}
    meta["review_recovery"]=state
    if report:report("A",state)
    current=rgb
    first=True
    for button,count in LADDER:
        state["phase"]=button
        if report:report(button,state)
        for _ in range(count):
            if not first and not delay(SPACING_SECONDS):
                state["status"]="INTERRUPTED"
                return "INTERRUPTED",current
            first=False
            if not permit(current,button):
                # Never blindly confirm a YES/NO or battle/menu selection.
                # An unclassified choice gets visual assistance instead.
                state["phase"]="VISUAL"
                break
            result=press(button,4 if button in ("A","B") else 16)
            state["attempts"]+=1
            state["last_button"]=button
            if changed(current,result) or (witness is not None and witness()):
                state["status"]="PROGRESS"
                state["phase"]=button
                return "PROGRESS",result
            current=result
        if state["phase"]=="VISUAL":break
    state["phase"]="VISUAL"
    if report:report("VISUAL",state)
    for i in range(VISUAL_TRIES):
        if visual is None:break
        state["visual_consults"]+=1
        proposed=visual(current,i)
        if proposed is None:break
        button,frames=proposed
        if not permit(current,button):break
        result=press(button,frames)
        state["attempts"]+=1
        state["last_button"]=button
        if changed(current,result) or (witness is not None and witness()):
            state["status"]="PROGRESS"
            return "PROGRESS",result
        current=result
        if i+1<VISUAL_TRIES and not delay(SPACING_SECONDS):
            state["status"]="INTERRUPTED"
            return "INTERRUPTED",current
    state["status"]="EXHAUSTED"
    return "EXHAUSTED",current
