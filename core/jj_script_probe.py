"""Bounded, read-only inspection of standard FRLG event-script *prefixes*.

Command widths are transcribed from pret/pokefirered asm/macros/event.inc.
A ROM hack may replace dispatch handlers, so these are possible INTENTS,
not evidence of what happened or permission to press a controller button.
Unknown opcodes and non-linear control transfer always stop inspection.
No script bytes, ROM pointers, flags, items or dialogue escape in results.
"""
from core.firered import span

ROM_BASE=0x08000000

# Full instruction widths (opcode included). Deliberately NOT an exhaustive
# bytecode table. Never decode an unrecognised opcode as a one-byte command.
WIDTH={
    0x00:1,0x01:1,0x02:1,0x03:1,
    0x04:5,0x05:5,0x06:6,0x07:6,
    0x08:2,0x09:2,0x0a:3,0x0b:3,
    0x0c:1,0x0d:1,0x0e:2,0x0f:6,
    0x16:5,0x17:5,0x18:5,0x19:5,0x1a:5,
    0x21:5,0x22:5,0x23:5,0x24:5,
    0x25:3,0x26:5,0x27:1,
    0x29:3,0x2a:3,0x2b:3,
    0x2f:3,0x30:1,
    0x44:5,0x45:5,0x46:5,0x47:5,
    0x4f:7,0x51:3,0x5a:1,
    0x66:1,0x67:5,0x68:1,0x69:1,0x6a:1,0x6b:1,0x6c:1,0x6d:1,
    0x6e:3,0x6f:5,0x70:6,0x71:6,
    0x97:2,
}
TERMINATORS=frozenset((0x02,0x03,0x0c,0x0d))
# Flow instructions must be explored with a control-flow graph and verified
# variable/flag state, NOT by sequentially decoding their next bytes.
TRANSFERS=frozenset((0x04,0x05,0x06,0x07,0x08,0x0a,0x0b,0x23,0x24))
# These have varying argument widths by subtype; detect intent, then stop.
DYNAMIC=frozenset((0x39,0x3a,0x3b,0x5c))
STD_ITEM=frozenset((0,1))
STD_DIALOGUE=frozenset((2,3,4))


def inspect_prefix(live,rom_size,pointer,*,max_commands=24,max_bytes=160):
    """Describe only a contiguous known-opcode prefix; never execute it."""
    if (type(pointer) is not int or not 0<rom_size<=32*1024*1024
            or not span(pointer,1,ROM_BASE,ROM_BASE+rom_size)):
        raise ValueError("INVALID_ROM_POINTER")
    if not (1<=max_commands<=64 and 1<=max_bytes<=512):
        raise ValueError("INVALID_PROBE_BUDGET")
    available=min(max_bytes,ROM_BASE+rom_size-pointer)
    data=live.read(pointer,available)
    if len(data)!=available:raise ValueError("ROM_READ_SHORT")
    features=set()
    cursor=0
    count=0
    status="PREFIX_BUDGET_EXHAUSTED"
    while count<max_commands and cursor<len(data):
        opcode=data[cursor]
        if opcode in DYNAMIC:
            features.add("battle" if opcode==0x5c else "warp")
            status="DYNAMIC_COMMAND_STOP";count+=1;break
        size=WIDTH.get(opcode)
        if size is None:
            status="UNKNOWN_OPCODE_STOP";break
        if cursor+size>len(data):
            status="TRUNCATED_COMMAND_STOP";break
        args=data[cursor+1:cursor+size]
        count+=1
        if opcode in (0x67,0x66,0x6d):
            features.add("dialogue_or_wait")
        if opcode in (0x6e,0x6f,0x70,0x71):
            features.add("player_choice")
        if opcode in (0x44,0x45,0x46,0x47):
            features.add("item_check_or_change")
        if opcode in (0x29,0x2a,0x2b):
            features.add("flag_check_or_change")
        if opcode in (0x16,0x17,0x18,0x19,0x1a,0x21,0x22):
            features.add("variable_or_comparison")
        if opcode in (0x25,0x26):
            features.add("native_special_unknown_effect")
        if opcode in (0x4f,0x51):
            features.add("object_movement")
        if opcode in (0x08,0x09,0x0a,0x0b):
            standard=args[-1]
            if standard in STD_ITEM:features.add("item_standard_script")
            elif standard in STD_DIALOGUE:features.add("dialogue_standard_script")
            elif standard==5:features.add("player_choice")
            else:features.add("other_standard_script")
        if opcode in (0x06,0x07,0x0a,0x0b):
            features.add("unresolved_condition")
        if opcode in TERMINATORS:
            status="TERMINAL_COMMAND";break
        if opcode in TRANSFERS:
            status="CONTROL_TRANSFER_STOP";break
        cursor+=size
    return {"status":status,"commands_scanned":count,
            "possible_intents":sorted(features),
            "complete_linear_prefix":status=="TERMINAL_COMMAND",
            "runtime_outcome_verified":False,
            "custom_opcode_semantics_verified":False}
