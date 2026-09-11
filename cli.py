"""
PyVM Command-Line Interface & Interactive REPL.
Supports interactive bytecode shell, script execution, bytecode tracing,
and direct loading of compiled Python bytecode (.pyc) files.
"""

import argparse
import importlib.util
import marshal
import sys
import traceback
from typing import Optional
from vm import VirtualMachine, Frame


class PyVMCLI:
    """CLI orchestrator for script execution, .pyc loading, and REPL."""

    def __init__(self, trace: bool = False) -> None:
        self.trace = trace
        self.vm = VirtualMachine()

    def _traced_run(self, code_obj) -> None:
        """Execute bytecode with step-by-step console tracing."""
        frame = Frame(
            code_obj=code_obj,
            globals_scope=self.vm.globals,
            locals_scope=self.vm.globals,
            builtins_scope=self.vm.builtins,
        )
        self.vm.frames.append(frame)

        print("\n" + "=" * 70)
        print(f"{'IP':<5} | {'OPCODE':<25} | {'ARG':<15} | {'STACK'}")
        print("-" * 70)

        try:
            while frame.ip < len(frame.instructions):
                instr = frame.instructions[frame.ip]
                handler = self.vm._dispatch_table.get(instr.opname)

                if handler is None:
                    raise NotImplementedError(f"Opcode '{instr.opname}' is not supported.")

                stack_repr = str(frame.stack) if frame.stack else "[]"
                arg_repr = str(instr.argval) if instr.argval is not None else ""
                if len(arg_repr) > 14:
                    arg_repr = arg_repr[:11] + "..."

                print(f"{frame.ip:<5} | {instr.opname:<25} | {arg_repr:<15} | {stack_repr}")

                result = handler(self.vm, frame, instr)
                if instr.opname in ("RETURN_VALUE", "RETURN_CONST"):
                    print(f"\n[VM Exit Value]: {result}")
                    return

                frame.ip += 1
        finally:
            self.vm.frames.pop()
            print("=" * 70 + "\n")

    def run_code_obj(self, code_obj) -> None:
        """Run a pre-compiled CodeType object directly."""
        try:
            if self.trace:
                self._traced_run(code_obj)
            else:
                self.vm.run_code(code_obj)
        except Exception:
            traceback.print_exc(file=sys.stderr)

    def run_source(self, source: str, filename: str = "<stdin>") -> None:
        """Compile and execute source code within the VM instance."""
        try:
            code_obj = compile(source, filename=filename, mode="exec")
            self.run_code_obj(code_obj)
        except Exception:
            traceback.print_exc(file=sys.stderr)

    def run_pyc_file(self, filepath: str) -> None:
        """Parse and execute a compiled .pyc bytecode file directly."""
        try:
            with open(filepath, "rb") as file:
                # Read standard 16-byte .pyc header (Python 3.7+)
                header = file.read(16)
                if len(header) < 16:
                    raise ValueError(f"Corrupted .pyc header in '{filepath}' (less than 16 bytes).")

                magic_number = header[:2]
                expected_magic = importlib.util.MAGIC_NUMBER[:2]
                if magic_number != expected_magic:
                    print(
                        f"[!] Warning: Magic number mismatch ({magic_number} != {expected_magic}). "
                        "The .pyc was compiled with a different Python version.",
                        file=sys.stderr,
                    )

                code_obj = marshal.load(file)

            self.run_code_obj(code_obj)
        except FileNotFoundError:
            print(f"[!] Error: File '{filepath}' not found.", file=sys.stderr)
            sys.exit(1)
        except Exception as exc:
            print(f"[!] Error loading .pyc file '{filepath}': {exc}", file=sys.stderr)
            sys.exit(1)

    def run_file(self, filepath: str) -> None:
        """Inspect file extension and delegate to script runner or .pyc loader."""
        if filepath.endswith(".pyc"):
            self.run_pyc_file(filepath)
            return

        try:
            with open(filepath, "r", encoding="utf-8") as file:
                source = file.read()
            self.run_source(source, filename=filepath)
        except FileNotFoundError:
            print(f"[!] Error: File '{filepath}' not found.", file=sys.stderr)
            sys.exit(1)

    def repl(self) -> None:
        """Run an interactive REPL session."""
        print("PyVM - Python Bytecode Virtual Machine Shell")
        print("Type '.help' for REPL commands or '.exit' to quit.\n")

        buffer = []
        while True:
            try:
                prompt = "... " if buffer else "pyvm>>> "
                line = input(prompt)

                stripped = line.strip()

                if not buffer:
                    if stripped in (".exit", "exit()", "quit()"):
                        print("Goodbye!")
                        break
                    elif stripped == ".help":
                        print("REPL Commands:")
                        print("  .globals  - Show defined global variables")
                        print("  .clear    - Clear current input buffer")
                        print("  .exit     - Terminate session")
                        continue
                    elif stripped == ".globals":
                        user_globals = {
                            k: v for k, v in self.vm.globals.items() if not k.startswith("__")
                        }
                        print(user_globals)
                        continue
                    elif stripped == ".clear":
                        buffer.clear()
                        continue

                if line.endswith(":") or (buffer and line.startswith(" ")) or (buffer and line.strip()):
                    buffer.append(line)
                    continue

                if buffer:
                    buffer.append(line)
                    source = "\n".join(buffer)
                    buffer.clear()
                else:
                    source = line

                if not source.strip():
                    continue

                self.run_source(source)

            except (KeyboardInterrupt, EOFError):
                print("\nKeyboardInterrupt")
                buffer.clear()
                break


def main() -> None:
    parser = argparse.ArgumentParser(description="PyVM - Python Bytecode Virtual Machine CLI")
    parser.add_argument("script", nargs="?", help="Path to Python script (.py) or compiled (.pyc) file")
    parser.add_argument(
        "--trace",
        action="store_true",
        help="Enable step-by-step bytecode and stack tracer",
    )

    args = parser.parse_args()
    cli = PyVMCLI(trace=args.trace)

    if args.script:
        cli.run_file(args.script)
    else:
        cli.repl()


if __name__ == "__main__":
    main()