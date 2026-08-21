"""
Interactive REPL and CLI Runner for the custom Python Virtual Machine.
"""

import sys
import os
from vm import VirtualMachine


def run_repl() -> None:
    """Run an interactive Read-Eval-Print-Loop (REPL) session using PyVM."""
    print("PyVM - Python Bytecode Virtual Machine")
    print("Type 'exit()' or press Ctrl+C to terminate session.\n")

    vm = VirtualMachine()

    while True:
        try:
            line = input("pyvm >>> ")
            if not line.strip():
                continue
            if line.strip() in ("exit()", "quit()"):
                break

            # Attempt to compile as single/eval expression first, fallback to exec mode
            try:
                code_obj = compile(line, filename="<stdin>", mode="single")
            except SyntaxError:
                code_obj = compile(line, filename="<stdin>", mode="exec")

            vm.run_code(code_obj)

        except (KeyboardInterrupt, EOFError):
            print("\nExiting PyVM.")
            break
        except Exception as err:
            print(f"Runtime Exception: {err}")


def run_file(file_path: str) -> None:
    """Read a python file and execute it on the custom VM."""
    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' does not exist.")
        sys.exit(1)

    with open(file_path, "r", encoding="utf-8") as f:
        source_code = f.read()

    code_obj = compile(source_code, filename=file_path, mode="exec")
    vm = VirtualMachine()
    vm.run_code(code_obj)


def main() -> None:
    if len(sys.argv) > 1:
        run_file(sys.argv[1])
    else:
        run_repl()


if __name__ == "__main__":
    main()