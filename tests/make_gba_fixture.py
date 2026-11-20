#!/usr/bin/env python3
"""Create an original, fully synthetic GBA Mode 3 framebuffer test cartridge.

No retail ROM/header/artwork/BIOS/other third-party game bytes are included.
This is intentionally a tiny ARM program written from public CPU instruction
formats. It fills the GBA screen white, then continuously mirrors the A button into EWRAM.
"""
from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path


def assemble() -> bytes:
    # All opcodes are ARM mode (32-bit), located at cartridge offset 0xC0.
    # r0 = DISPCNT; write Mode 3 + BG2. r0 = VRAM; fill 240*160 pixels.
    # CPU address base for the ROM is 0x08000000.
    words = [
        0xE59F0028,  # ldr r0, [pc, #40] -> 0x04000000
        0xE59F1028,  # ldr r1, [pc, #40] -> 0x00000403
        0xE5801000,  # str r1, [r0]
        0xE59F0024,  # ldr r0, [pc, #36] -> 0x06000000
        0xE59F1024,  # ldr r1, [pc, #36] -> 0x7fff7fff
        0xE59F3024,  # ldr r3, [pc, #36] -> 0x00012c00
        0xE3A02000,  # mov r2, #0
        0xE7801002,  # str r1, [r0, r2] -- fill VRAM
        0xE2822004,  # add r2, r2, #4
        0xE1520003,  # cmp r2, r3
        0x1AFFFFFB,  # bne loop (instruction 7)
        0xEA000004,  # jump over literal pool to keypad loop
        0x04000000,  # DISPCNT
        0x00000403,  # Mode3/BG2
        0x06000000,  # VRAM base
        0x7FFF7FFF,  # white pixels (BGR555)
        0x00012C00,  # 240 * 160 * 2 bytes
        0xE59F0010,  # ldr r0, [pc, #16] -> KEYINPUT
        0xE1D010B0,  # ldrh r1, [r0]
        0xE2011001,  # and r1, r1, #1 (A, active low)
        0xE59F2008,  # ldr r2, [pc, #8] -> EWRAM
        0xE5821000,  # str r1, [r2]
        0xEAFFFFF9,  # repeat from keypad read
        0x04000130,  # KEYINPUT
        0x02000000,  # observable input state
    ]
    return struct.pack('<%dI' % len(words), *words)


def make_rom() -> bytes:
    rom = bytearray(b'\xFF' * 0x40000)
    # ARM branch offset ((0xC0 - (0 + 8)) / 4) = 46.
    struct.pack_into('<I', rom, 0, 0xEA00002E)
    # This homebrew deliberately has no Nintendo boot-logo graphic.
    # Some emulators require a boot logo: that should be reported as
    # fixture incompatibility, never silently fixed by copying retail bytes.
    rom[0xA0:0xAC] = b'MGBA CI TEST'
    rom[0xAC:0xB0] = b'TST1'
    rom[0xB0:0xB2] = b'HB'
    rom[0xB2] = 0x96
    rom[0xBC] = 0
    rom[0xBD] = (-(sum(rom[0xA0:0xBD]) + 0x19)) & 0xFF
    code = assemble()
    rom[0xC0:0xC0 + len(code)] = code
    return bytes(rom)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', required=True)
    args = ap.parse_args()
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = make_rom()
    path.write_bytes(data)
    assert data[0xC0:0xC0 + 4] == struct.pack('<I', 0xE59F0028)
    print('synthetic fixture:', path, 'size:', len(data),
          'sha256:', hashlib.sha256(data).hexdigest())


if __name__ == '__main__':
    main()
