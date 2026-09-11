# PyVM - Python Bytecode Virtual Machine

A modular, high-performance stack-based virtual machine written in pure Python that disassembles, interprets, and executes Python bytecode with isolated call frames.

## Features

- **O(1) Opcode Dispatch Table:** Replaces linear conditional chains with a direct dictionary dispatch pattern for minimal opcode decoding overhead.
- **Frame-Isolated Execution:** Each function invocation instantiates an isolated `Frame` containing its own instruction pointer, evaluation stack, and local scope.
- **Python 3.11 - 3.13 Compatible:** Supports modern calling conventions (`PUSH_NULL`, `CALL`), modern container optimizations (`BUILD_CONST_KEY_MAP`, `SET_UPDATE`), and instruction caching.
- **Fast Local & Name Scopes:** Optimized variable lookups mimicking CPython's evaluation order (`LOAD_FAST`, `STORE_FAST`, `LOAD_GLOBAL`, `LOAD_NAME`).
- **Interactive REPL & Tracer:** Built-in command-line shell with live instruction-by-instruction stack inspection via the `--trace` flag.

---

## Project Structure

```text
pyvm/
│
├── vm.py              # Core execution engine, frame allocator, and opcode dispatchers
├── cli.py             # REPL interface, script executor, and bytecode execution tracer
├── main.py            # Entry point running verification scenarios and benchmarks
├── tests/
│   └── test_vm.py     # Unittest suite (arithmetic, recursion, control flow, data structures)
├── .gitignore         # Clean repository exclusions
└── README.md          # Technical documentation
Getting Started
1. Setup Virtual Environment (PowerShell)
PowerShell
python -m venv venv
.\venv\Scripts\Activate.ps1
2. Run Verification Benchmarks
PowerShell
python main.py
3. Run Unit Test Suite
PowerShell
python -m unittest discover tests
4. Interactive REPL
Start the interactive bytecode shell:

PowerShell
python cli.py
Useful REPL commands:

.globals - Inspect variables defined in global scope.

.clear   - Clear current input buffer.

.exit    - Exit the shell.

5. Execution Tracer Mode
To inspect instructions, arguments, and the evaluation stack in real-time:

PowerShell
python cli.py --trace
Example run inside the tracer:

Plaintext
pyvm>>> x = 2 + 3 * 4

======================================================================
IP    | OPCODE                    | ARG             | STACK
----------------------------------------------------------------------
0     | RESUME                    | 0               | []
1     | LOAD_CONST                | 14              | []
2     | STORE_NAME                | x               | [14]
3     | RETURN_CONST              |                 | []
======================================================================
6. Execute Script Files
Run any arbitrary .py file through the VM:

PowerShell
python cli.py path/to/script.py
Supported Opcode Categories
Stack Operations: POP_TOP, PUSH_NULL, RESUME, CACHE, NOP.

Loading & Storing: LOAD_CONST, LOAD_NAME, STORE_NAME, LOAD_GLOBAL, STORE_GLOBAL, LOAD_FAST, STORE_FAST, LOAD_ATTR, STORE_ATTR.

Data Structures: BUILD_LIST, BUILD_TUPLE, BUILD_SET, BUILD_MAP, BUILD_CONST_KEY_MAP, BINARY_SUBSCR, STORE_SUBSCR, LIST_APPEND, LIST_EXTEND, SET_UPDATE, MAP_ADD, DICT_UPDATE.

Arithmetic & Logic: BINARY_OP, BINARY_ADD, BINARY_SUBTRACT, BINARY_MULTIPLY, BINARY_TRUE_DIVIDE, UNARY_NEGATIVE, UNARY_NOT, UNARY_INVERT.

Comparisons: COMPARE_OP (==, !=, <, <=, >, >=, in, not in, is, is not).

Control Flow: JUMP_FORWARD, JUMP_BACKWARD, JUMP_ABSOLUTE, POP_JUMP_IF_FALSE, POP_JUMP_IF_TRUE.

Iteration: GET_ITER, FOR_ITER, END_FOR.

Functions: MAKE_FUNCTION, CALL, RETURN_VALUE, RETURN_CONST.

License
This project is open-source software licensed under the MIT License.