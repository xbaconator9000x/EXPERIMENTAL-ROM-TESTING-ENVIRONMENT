"""Source-grounded, read-only Gen III field text-printer driver.

Uses pret/pokefirered include/text.h, src/text_printer.c,
src/field_message_box.c and exact retail symbols as *candidates*.
This is NOT a blanket claim that a modified ROM retained those RAM addresses.
Unrecognized windows, choices, and memory layouts remain unhandled.
Only exact SHA-admitted caller contexts may propose controller input.
"""
import hashlib
from core.live import LiveError

# FireRed US v1.0 symbol reference, 40Cakes/pokebot-gen3 f14ab79:
# sTextPrinters at 02020034; sMessageBoxType at 0203709C.
PRINTER_0=0x02020034
BOX_TYPE=0x0203709C
PRINTER_SIZE=36
# pret/pokefirered field_message_box.h: normal=2, auto-scroll=3.
NORMAL=2
AUTO_SCROLL=3
# pret/pokefirered text.h: HANDLE_CHAR=0, WAIT=1, CLEAR=2,
# SCROLL_START=3, SCROLL=4, WAIT_SE=5, PAUSE=6.
WAITING_STATES=frozenset((1,2,3))
IN_PROGRESS_STATES=frozenset((0,4,5,6))

def floating_choice(rgb):
    """Reject a distinct floating choice panel, not ordinary room furniture.

    This is only a veto; it never establishes that a dialogue is safe.
    Check a bounded top-right orange frame plus light interior, rather
    than interpreting text or attempting a menu selection.
    """
    if not isinstance(rgb,(bytes,bytearray)) or len(rgb)!=240*160*3:return True
    def pixel(x,y):
        p=(y*240+x)*3
        return rgb[p],rgb[p+1],rgb[p+2]
    for y in range(12,101):
        run_start=None
        for x in range(145,235):
            r,g,b=pixel(x,y)
            orange=r>=145 and 20<=g<=165 and b<=145 and r>g+50
            if orange and run_start is None:run_start=x
            if (not orange or x==234) and run_start is not None:
                end=x if not orange else x+1
                if (24<=end-run_start<=85 and end<233 and y+7<110 and
                        sum(min(pixel(xx,y+7))>=220 for xx in range(run_start,end))>=
                        max(12,(end-run_start)//2)):
                    return True
                run_start=None
    return False

def probe(live,rom_size):
    """Inspect a candidate vanilla text printer; return no raw private bytes."""
    if type(rom_size) is not int or not 0<rom_size<=32*1024*1024:return None
    try:
        kind=live.integer(BOX_TYPE,1)
        if kind not in (NORMAL,AUTO_SCROLL):return None
        raw=live.read(PRINTER_0,PRINTER_SIZE)
        if len(raw)!=PRINTER_SIZE:return None
        ptr=int.from_bytes(raw[:4],"little")
        window, font, active, state=raw[4],raw[5],raw[27],raw[28]
        if window!=0 or font>7 or active!=1 or state>6:return None
        if not ((0x02000000<=ptr<0x02040000) or
                (0x08000000<=ptr<0x08000000+rom_size)):return None
        # Do not treat a plausible pointer alone as proof of a live printer.
        if len(live.read(ptr,1))!=1:return None
        mode=("auto" if kind==AUTO_SCROLL else
              "ready" if state in WAITING_STATES else "printing")
        return {"mode":mode,"state":state,"ptr":ptr}
    except (LiveError,ValueError,OSError,TypeError,IndexError):
        return None

def decide(live,rgb,meta,rom_size,*,script_locked=False,recognized=False):
    """Return at most one verified native action; never select a choice.

    A wait state plus a live, ROM-bounded printer and message-box mode is
    stronger than border-colour recognition. A repeated identical text page
    must not result in an infinite series of A presses.
    """
    if not (script_locked or recognized):return None
    p=probe(live,rom_size)
    if p is None:
        meta["native_text_probe"]={"status":"NOT_ADMITTED"}
        meta.pop("native_text_guard",None)
        return None
    if floating_choice(rgb):
        meta["native_text_probe"]={"status":"CHOICE_OR_UNSAFE_PANEL"}
        return None
    meta["native_text_probe"]={"status":"PRINTER_"+p["mode"].upper(),
                               "render_state":p["state"]}
    # The game itself advances AUTO_SCROLL; never press A to accelerate it.
    if p["mode"]=="auto":return {
        "scene":"native_text_auto","objective":"Allow native auto-scroll text",
        "actions":[{"button":"WAIT","frames":24}],"review":False}
    if p["mode"]=="printing":return {
        "scene":"native_text_render","objective":"Allow verified text printer to finish",
        "actions":[{"button":"WAIT","frames":24}],"review":False}
    # Exclude the animated arrow at right and scenery above the dialogue.
    h=hashlib.sha256()
    for y in range(122,148):
        h.update(rgb[(y*240+18)*3:(y*240+204)*3])
    token=hashlib.sha256((str(p["ptr"])+":"+str(p["state"])+":"+
                          h.hexdigest()).encode("ascii")).hexdigest()
    prior=meta.get("native_text_guard",{})
    if isinstance(prior,dict) and prior.get("token")==token:
        meta["native_text_probe"]={"status":"REPEATED_READY_PAGE_GUARDED"}
        return None
    meta["native_text_guard"]={"token":token}
    return {"scene":"native_text_advance",
            "objective":"Advance native-verified text-printer wait state",
            "actions":[{"button":"A","frames":4}],"review":False}
