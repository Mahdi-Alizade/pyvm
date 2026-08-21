# PyVM - Python Bytecode Virtual Machine

A lightweight, stack-based virtual machine written in pure Python that disassembles and executes Python bytecode.

## Features

- **Stack Execution Engine:** Implements push/pop stack operations.
- **Arithmetic & Logic:** Supports basic operators (+, -, *, /, %) and comparisons.
- **Control Flow:** Handles conditional branching (if/else) and jump instructions.
- **Loops & Iteration:** Supports `for` loops, iterators, and dynamic list building.
- **Functions & Recursion:** Full support for user-defined functions and recursion.
- **CLI & REPL:** Interactive shell and script file execution mode.

## Getting Started

### 1. Setup Virtual Environment
```bash
python -m venv venv
.\venv\Scripts\Activate.ps1
2. Run Tests
Bash
python main.py
3. Run Unit Tests
Bash
python -m unittest discover tests
4. Interactive REPL Mode
Bash
python cli.py
5. Run a Script File
Bash
python cli.py path/to/script.py
License
This project is licensed under the MIT License.