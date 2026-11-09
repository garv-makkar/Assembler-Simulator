"""Two-pass assembler. CLI: python SimpleAssembler.py < program.asm"""
import sys
from dataclasses import dataclass
from isa import A, B, C, D, E, OPCODES, REGISTERS, NAME, encode_float


class AssemblyError(ValueError):
    pass


@dataclass
class Assembly:
    words: list[str]
    instructions: list[str]
    source_lines: list[int]
    labels: dict[str, int]
    variables: dict[str, int]


def assemble(source):
    labels, variables, instructions, lines = {}, {}, [], []

    def fail(line, message):
        raise AssemblyError(f'Line {line}: {message}')

    def symbol(name, line):
        if not NAME.fullmatch(name) or name in OPCODES or name in REGISTERS or name == 'var':
            fail(line, f'invalid symbol {name!r}')
        if name in labels or name in variables:
            fail(line, f'duplicate symbol {name!r}')

    for line, raw in enumerate(source.splitlines(), 1):
        text = raw.split('#', 1)[0].strip()
        if not text:
            continue
        tokens = text.split()
        if tokens[0] == 'var':
            if instructions:
                fail(line, 'variables must be declared before instructions')
            if len(tokens) != 2:
                fail(line, 'expected var NAME')
            symbol(tokens[1], line)
            variables[tokens[1]] = 0
            continue
        if tokens[0].endswith(':'):
            name = tokens.pop(0)[:-1]
            symbol(name, line)
            labels[name] = len(instructions)
            if not tokens:
                fail(line, 'a label must share a line with an instruction')
        instructions.append(tokens)
        lines.append(line)
    if not instructions:
        raise AssemblyError('Program is empty; add instructions ending in hlt')
    if sum(t[0] == 'hlt' for t in instructions) != 1 or instructions[-1] != ['hlt']:
        raise AssemblyError('Program must contain exactly one hlt as its final instruction')
    if len(instructions) + len(variables) > 256:
        raise AssemblyError('Instructions and variables exceed 256 memory words')
    for index, name in enumerate(variables):
        variables[name] = len(instructions) + index
    words = []
    for tokens, line in zip(instructions, lines):
        op, *args = tokens
        if op not in OPCODES or op == 'movi':
            fail(line, f'unknown instruction {op!r}')
        count = 3 if op in A else 1 if op in E else 0 if op == 'hlt' else 2
        if len(args) != count:
            fail(line, f'{op} expects {count} operand(s), got {len(args)}')

        def reg(name, allow_flags=False):
            if name not in REGISTERS:
                fail(line, f'unknown register {name!r}')
            if name == 'FLAGS' and not allow_flags:
                fail(line, 'FLAGS is only allowed as the source of mov')
            return REGISTERS[name]

        def immediate(text, floating=False):
            # Accept the original bare movf literal as well as $literal.
            if not floating and not text.startswith('$'):
                fail(line, 'integer immediates must start with $')
            literal = text[1:] if text.startswith('$') else text
            try:
                value = encode_float(literal) if floating else int(literal, 10)
            except (ValueError, ZeroDivisionError) as exc:
                fail(line, f'invalid immediate {text!r}: {exc}')
            if not 0 <= value <= 255:
                fail(line, 'integer immediate must be in 0..255')
            return value

        opcode = OPCODES[op]
        if op in A:
            x, y, z = map(reg, args)
            word = opcode << 11 | x << 6 | y << 3 | z
        elif op == 'mov' and not args[1].startswith('$'):
            word = opcode << 11 | reg(args[0]) << 3 | reg(args[1], True)
        elif op in B or op == 'mov':
            opcode = B['movi'] if op == 'mov' else opcode
            word = opcode << 11 | reg(args[0]) << 8 | immediate(args[1], op == 'movf')
        elif op in C:
            word = opcode << 11 | reg(args[0]) << 3 | reg(args[1])
        elif op in D:
            if args[1] not in variables:
                fail(line, f'{op} requires a declared variable: {args[1]!r}')
            word = opcode << 11 | reg(args[0]) << 8 | variables[args[1]]
        elif op in E:
            if args[0] not in labels:
                fail(line, f'{op} requires a defined label: {args[0]!r}')
            word = opcode << 11 | labels[args[0]]
        else:
            word = opcode << 11
        words.append(f'{word:016b}')
    return Assembly(words, [' '.join(t) for t in instructions], lines, labels, variables)


def main():
    try:
        result = assemble(sys.stdin.read())
    except AssemblyError as exc:
        print(f'Assembly error: {exc}', file=sys.stderr)
        return 1
    print('\n'.join(result.words))
    return 0


if __name__ == '__main__':
    sys.exit(main())
