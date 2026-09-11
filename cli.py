"""
PyVM Command-Line Interface & Interactive REPL.
Supports interactive bytecode shell, script execution, and step-by-step tracing.
"""

import argparse
import sys
import traceback
from typing import Optional
from vm import VirtualMachine, Frame


class PyVMCLI:
    """CLI orchestrator for script execution and REPL."""

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
                if result is not None:
                    print(f"\n[VM Exit Value]: {result}")
                    return

                frame.ip += 1
        finally:
            self.vm.frames.pop()
            print("=" * 70 + "\n")

    def run_source(self, source: str, filename: str = "<stdin>") -> None:
        """Compile and execute source code within the VM instance."""
        try:
            code_obj = compile(source, filename=filename, mode="exec")
            if self.trace:
                self._traced_run(code_obj)
            else:
                self.vm.run_code(code_obj)
        except Exception as exc:
            traceback.print_exc(file=sys.stderr)

    def run_file(self, filepath: str) -> None:
        """Read a Python script file and run it inside the VM."""
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

                # Handle multi-line block collection (e.g. def, for, if)
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
    parser.add_argument("script", nargs="?", help="Path to Python script file to execute")
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