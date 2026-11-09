"""Bounded, step-by-step 16-bit machine. Importing performs no I/O."""
import argparse
import sys
from isa import A, B, C, D, E, DECODE, decode_float, encode_float


class SimulationError(ValueError):
    pass


def parse_machine_code(source):
    words = []
    for line, text in enumerate(source.splitlines(), 1):
        text = text.strip()
        if not text:
            continue
        if len(text) != 16 or set(text) - {'0', '1'}:
            raise SimulationError(f'Line {line}: expected exactly 16 binary digits')
        words.append(text)
    if not 1 <= len(words) <= 256:
        raise SimulationError('Machine code must contain 1..256 words')
    return words


class Machine:
    def __init__(self, words):
        words = parse_machine_code('\n'.join(words))
        self.memory = [int(word, 2) for word in words] + [0] * (256 - len(words))
        self.registers = [0] * 8
        self.pc = 0
        self.halted = False
        self.cycle = 0

    def step(self):
        if self.halted:
            raise SimulationError('Machine is already halted')
        if not 0 <= self.pc < 256:
            raise SimulationError(f'Program counter outside memory: {self.pc}')
        pc = self.pc
        word = self.memory[pc]
        op = DECODE.get(word >> 11)
        if op is None:
            raise SimulationError(f'Unknown opcode at address {pc}')
        x, y, z = (word >> 6) & 7, (word >> 3) & 7, word & 7
        r, imm = (word >> 8) & 7, word & 255
        # Reject illegal FLAGS operands and nonzero reserved bits in raw input.
        invalid = False
        if op in A:
            invalid = bool(word & 0x600) or 7 in (x, y, z)
        elif op in B or op in D:
            invalid = r == 7
        elif op in C:
            invalid = bool(word & 0x7C0) or y == 7 or (z == 7 and op != 'mov')
        elif op in E:
            invalid = bool(word & 0x700)
        elif op == 'hlt':
            invalid = bool(word & 0x7FF)
        if invalid:
            raise SimulationError(f'Illegal operands or reserved bits at address {pc}')
        regs = self.registers
        previous_flags = regs[7]
        # Read all operands before writing any destination (notably div R0 R1).
        a, b = regs[y], regs[z]
        next_pc, flags, access = pc + 1, 0, None
        if op in A:
            a, b = regs[x], regs[y]
            if op == 'add':
                value = a + b
            elif op == 'sub':
                value = a - b
            elif op == 'mul':
                value = a * b
            elif op == 'xor':
                value = a ^ b
            elif op == 'or':
                value = a | b
            elif op == 'and':
                value = a & b
            else:
                result = decode_float(a) + decode_float(b) if op == 'addf' else decode_float(a) - decode_float(b)
                if result < 1:
                    value, flags = 0, 8
                elif result > 252:
                    value, flags = 255, 8
                else:
                    # Round toward zero by discarding excess mantissa bits.
                    exponent, scaled = 0, result
                    while scaled >= 2:
                        exponent, scaled = exponent + 1, scaled / 2
                    value = exponent << 5 | int((scaled - 1) * 32)
            if value < 0:
                value, flags = 0, 8
            elif value > 65535:
                value, flags = value & 65535, 8
            regs[z] = value
        elif op in ('movi', 'movf'):
            regs[r] = imm
        elif op == 'mov':
            regs[y] = b
        elif op == 'div':
            if b == 0:
                raise SimulationError(f'Division by zero at address {pc}')
            regs[0], regs[1] = divmod(a, b)
        elif op == 'not':
            regs[z] = (~a) & 65535
        elif op == 'cmp':
            flags = 4 if a < b else 2 if a > b else 1
        elif op in ('ls', 'rs'):
            regs[r] = ((regs[r] << imm) if op == 'ls' else (regs[r] >> imm)) & 65535
        elif op == 'ld':
            regs[r] = self.memory[imm]
            access = {'kind': 'read', 'address': imm, 'value': regs[r]}
        elif op == 'st':
            self.memory[imm] = regs[r]
            access = {'kind': 'write', 'address': imm, 'value': regs[r]}
        elif op in E:
            if op == 'jmp' or previous_flags & {'jlt': 4, 'jgt': 2, 'je': 1}[op]:
                next_pc = imm
        elif op == 'hlt':
            self.halted = True
        regs[7] = flags
        self.pc = next_pc
        self.cycle += 1
        return {'cycle': self.cycle, 'pc': pc, 'next_pc': next_pc,
                'instruction': f'{word:016b}', 'operation': op,
                'registers': regs.copy(), 'memory_access': access, 'halted': self.halted}


def run(words, max_steps=10000):
    if not 1 <= max_steps <= 100000:
        raise SimulationError('Step limit must be in 1..100000')
    machine = Machine(words)
    trace = []
    while not machine.halted:
        if len(trace) >= max_steps:
            raise SimulationError(f'Execution stopped after {max_steps} steps; possible infinite loop')
        trace.append(machine.step())
    return machine, trace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--max-steps', type=int, default=10000)
    args = parser.parse_args()
    try:
        machine, trace = run(parse_machine_code(sys.stdin.read()), args.max_steps)
    except SimulationError as exc:
        print(f'Simulation error: {exc}', file=sys.stderr)
        return 1
    for state in trace:
        print(f"{state['pc']:08b}", *(f'{v:016b}' for v in state['registers']))
    print('\n'.join(f'{v:016b}' for v in machine.memory))
    return 0


if __name__ == '__main__':
    sys.exit(main())
