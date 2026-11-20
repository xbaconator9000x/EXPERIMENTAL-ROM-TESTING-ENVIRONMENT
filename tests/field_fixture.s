.syntax unified
.arm
.global _start
.text
_start:
    ldr r0, =0x03000000
    ldr r1, =0x02001000
    str r1, [r0]
    mov r2, #0
    str r2, [r1]
    ldr r2, =0x0201
    strh r2, [r1,#4]
    ldr r0, =0x02000020
    ldr r2, =layout
    str r2, [r0]
    ldr r0, =0x03000010
    mov r2, #18
    str r2, [r0]
    mov r2, #16
    str r2, [r0,#4]
    ldr r2, =0x02002000
    str r2, [r0,#8]
    ldr r3, =grid
    mov r4, #144
copy:
    ldr r5, [r3],#4
    str r5, [r2],#4
    subs r4,r4,#1
    bne copy
    mov r2,#42
    str r2,[r0,#16]
    ldr r0, =0x04000130
    mov r7,#0
poll:
    ldrh r2,[r0]
    mvn r2,r2
    and r2,r2,#0xf0
    cmp r2,#0
    moveq r7,#0
    beq poll
    cmp r7,#0
    bne poll
    mov r7,#1
    ldrh r3,[r1]
    ldrh r4,[r1,#2]
    cmp r2,#16
    addeq r3,r3,#1
    cmp r2,#32
    subeq r3,r3,#1
    cmp r2,#64
    subeq r4,r4,#1
    cmp r2,#128
    addeq r4,r4,#1
    cmp r3,#3
    bhs poll
    cmp r4,#2
    bhs poll
    add r5,r4,#7
    add r6,r3,#7
    add r6,r6,r5,lsl #4
    add r6,r6,r5,lsl #1
    ldr r5, =0x02002000
    add r5,r5,r6,lsl #1
    ldrh r6,[r5]
    tst r6,#0xc00
    bne poll
    strh r3,[r1]
    strh r4,[r1,#2]
    b poll
.ltorg
.align 2
layout:
    .word 3,2
grid:
    .rept 7*18+7
    .hword 0x3ff
    .endr
    .hword 1,0xc01,1
    .rept 15
    .hword 0x3ff
    .endr
    .hword 1,1,1
    .rept 18*16-(8*18+7+3)
    .hword 0x3ff
    .endr
