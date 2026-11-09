"""Instruction definitions shared by the assembler and simulator."""
from fractions import Fraction
import re

# Preserve the original project's opcodes and source/source/destination order.
A = {'add': 16, 'sub': 17, 'mul': 22, 'xor': 26, 'or': 27, 'and': 28,
     'addf': 0, 'subf': 1}
B = {'movi': 18, 'rs': 24, 'ls': 25, 'movf': 2}
C = {'mov': 19, 'div': 23, 'not': 29, 'cmp': 30}
D = {'ld': 20, 'st': 21}
E = {'jmp': 31, 'jlt': 12, 'jgt': 13, 'je': 15}
OPCODES = {**A, **B, **C, **D, **E, 'hlt': 10}
DECODE = {v: k for k, v in OPCODES.items()}
REGISTERS = {f'R{i}': i for i in range(7)} | {'FLAGS': 7}
NAME = re.compile(r'[A-Za-z_][A-Za-z0-9_]*\Z')


def encode_float(value):
    """Exact unsigned mini-float: (1 + mantissa/32) * 2**exponent."""
    value = Fraction(value)
    if not 1 <= value <= 252:
        raise ValueError('float must be between 1 and 252')
    exponent = 0
    while value >= 2:
        value /= 2
        exponent += 1
    mantissa = (value - 1) * 32
    if mantissa.denominator != 1:
        raise ValueError('float is not exactly representable with 5 mantissa bits')
    return (exponent << 5) | int(mantissa)


def decode_float(bits):
    return Fraction(32 + (bits & 31), 32) * (2 ** ((bits >> 5) & 7))
