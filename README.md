# Assembler Simulator

A Computer Organisation course project: a two-pass assembler and a simulator for a small 16-bit instruction set, with a Python web interface for demonstrations.

## Quick start: web demonstration

Requires **Python 3.10+** and a browser. No third-party packages or internet connection are needed.

```powershell
python web_interface.py
```

Open **http://127.0.0.1:8000**. Select an example and click **Load**, then **Assemble & run**. Use **Step**, **Back**, **Play**, the cycle slider, or **Reset** to explore execution. Registers, binary instructions, FLAGS, variables and all 256 memory words are displayed. The initial view is cycle zero; advance to see changes. **Download binary** saves the assembled program. Choose **Machine code** to execute your own binary input.

If port 8000 is busy: `python web_interface.py --port 8080`. Stop with Ctrl+C. The server binds to your own computer at 127.0.0.1.

## Example

```asm
var result
mov R0 $12
mov R1 $8
add R0 R1 R2
st R2 result
ld R3 result
hlt
```

At halt, R2 and R3 contain 20, and `result` (address 6) contains 20. The assembler places variables immediately after the instructions and initializes them to zero.

## Assembly syntax

Names are case-sensitive. Instructions are lowercase, registers uppercase. Blank lines, tabs, extra spaces and `# comments` are supported. Declare variables before instructions. Labels must share a line with an instruction, such as `loop: add R0 R1 R2`. Symbols must start with a letter or underscore and contain only letters, digits and underscores; duplicate or reserved names are rejected. Exactly one `hlt` must be the final instruction. Instructions plus variables must fit in 256 words.

**Operand order follows this project's original three-register arithmetic: sources first, destination last.** Register moves use destination first, matching immediate moves.

| Instruction | Effect |
| --- | --- |
| `mov R0 $12` | R0 = integer immediate (0..255) |
| `mov R0 R1` | R0 = R1 |
| `mov R0 FLAGS` | Copy FLAGS to R0, then clear FLAGS |
| `add R0 R1 R2` | R2 = R0 + R1 |
| `sub R0 R1 R2` | R2 = R0 - R1; negative result becomes zero and sets V |
| `mul R0 R1 R2` | R2 = R0 * R1 |
| `div R0 R1` | R0 = quotient, R1 = remainder of original operands |
| `xor R0 R1 R2` | R2 = R0 XOR R1 |
| `or R0 R1 R2` | R2 = R0 OR R1 |
| `and R0 R1 R2` | R2 = R0 AND R1 |
| `not R0 R1` | R1 = 16-bit complement of R0 |
| `ls R0 $2`, `rs R0 $2` | Shift R0 left/right; retain 16 bits |
| `ld R0 name`, `st R0 name` | Load/store a declared variable |
| `cmp R0 R1` | Set L, G or E from comparison |
| `jmp label` | Unconditional jump |
| `jlt label`, `jgt label`, `je label` | Jump if the corresponding flag is set |
| `movf R0 $1.5` | Load an exactly representable mini-float (bare `1.5` also accepted) |
| `addf R0 R1 R2`, `subf R0 R1 R2` | Mini-float arithmetic |
| `hlt` | Stop execution |

R0–R6 are unsigned 16-bit registers. FLAGS is read-only through `mov` and has V/L/G/E in bits 3/2/1/0. Every instruction clears flags except `cmp` and arithmetic that sets V. Conditional jumps inspect the preceding flags before clearing them, so put the jump immediately after `cmp`. Integer addition and multiplication wrap to the low 16 bits on overflow and set V. Shifts discard bits without setting V. Division by zero reports an execution error.

### Mini-floats

The original unsigned 8-bit format is preserved: three **unbiased** exponent bits and five mantissa bits, interpreted as `(1 + mantissa / 32) * 2**exponent`, spanning 1..252. The upper eight register bits are zero after float operations. Immediate values must be exactly representable; arithmetic truncates excess mantissa bits. Overflow saturates to raw 255 and sets V; results below 1 write raw zero and set V. **This format has no representation of numeric zero: raw zero decodes as 1 when used by a subsequent float instruction.** The web demo shows both the raw unsigned register and its mini-float interpretation; the latter is meaningful when interpreting that register as a float. Integer and float operations share registers and memory without type tags.

## Command-line tools

Both scripts read standard input. The assembler emits one 16-bit binary instruction per line. The simulator prints the executed 8-bit PC and eight 16-bit register values after each instruction, followed by a 256-word memory dump. Errors go to standard error with a nonzero exit code. Importing the modules does not read input or start execution.

PowerShell:

```powershell
Get-Content program.asm | python SimpleAssembler.py | Set-Content -Encoding ascii program.bin
Get-Content program.bin | python SimpleSimulator.py
```

Linux/macOS or Windows Command Prompt:

```sh
python SimpleAssembler.py < program.asm > program.bin
python SimpleSimulator.py < program.bin
```

The CLI defaults to 10,000 execution steps; change with `--max-steps 50000` (maximum 100,000). The browser demo stops at 2,000 cycles and preserves the partial trace, keeping looping programs bounded. Raw binary input accepts 1..256 words and validates opcodes, reserved bits and register restrictions during execution. Memory is unified: raw programs may overwrite instructions.

## Files

- `isa.py`: shared opcode definitions and exact mini-float encoding.
- `SimpleAssembler.py`: source validation, symbol resolution, binary encoding; `assemble(source)` returns an Assembly object.
- `SimpleSimulator.py`: `Machine(words).step()` and bounded `run(words)` APIs plus CLI.
- `web_interface.py`: standard-library HTTP server, built-in examples and browser visualization.

## Corrections made

Replaced fragile global state with reusable assembler and machine APIs. Fixed variable address resolution, label and operand validation, blank input crashes, register move direction, division with overlapping inputs, negative subtraction, 16-bit shift masking, and float conversion loops/type inconsistencies. Added clear source-line diagnostics, memory bounds, invalid binary checks and execution limits. Existing opcode values and three-register arithmetic operand order are preserved; register-to-register `mov` now consistently uses destination first.

Testing was left to the project owner as requested; no test suite was run for these changes.
