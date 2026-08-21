"""
A lightweight Python Bytecode Virtual Machine implemented in pure Python.
"""

import builtins
import dis
import types
from typing import Any, List, Dict


class VirtualMachine:
    """
    Core Stack-based Virtual Machine capable of executing Python code objects.
    """

    def __init__(self) -> None:
        self.stack: List[Any] = []
        self.environment: Dict[str, Any] = {}
        # Safely extract builtins namespace whether it is a module or dict
        if isinstance(builtins, dict):
            self.builtins: Dict[str, Any] = builtins
        else:
            self.builtins: Dict[str, Any] = builtins.__dict__

    def push(self, value: Any) -> None:
        """Push a value onto the execution stack."""
        self.stack.append(value)

    def pop(self) -> Any:
        """Pop and return the top value from the execution stack."""
        if not self.stack:
            raise IndexError("pop from empty execution stack")
        return self.stack.pop()

    def top(self) -> Any:
        """Peek at the top value of the stack without removing it."""
        if not self.stack:
            raise IndexError("peek from empty execution stack")
        return self.stack[-1]

    def run_code(self, code_obj: types.CodeType) -> Any:
        """
        Disassemble and execute a Python code object instruction by instruction.
        """
        instructions = list(dis.get_instructions(code_obj))
        instruction_pointer = 0

        while instruction_pointer < len(instructions):
            instr = instructions[instruction_pointer]
            opname = instr.opname
            argval = instr.argval

            # Opcode: Load Constant
            if opname == "LOAD_CONST":
                self.push(argval)

            # Opcode: Load Variable (Name)
            elif opname == "LOAD_NAME":
                if argval in self.environment:
                    self.push(self.environment[argval])
                elif argval in self.builtins:
                    self.push(self.builtins[argval])
                else:
                    raise NameError(f"name '{argval}' is not defined")

            # Opcode: Store Variable (Name)
            elif opname == "STORE_NAME":
                val = self.pop()
                self.environment[argval] = val

            # Opcode: Binary Arithmetic Operations
            elif opname in ("BINARY_OP", "BINARY_ADD", "BINARY_SUBTRACT", "BINARY_MULTIPLY", "BINARY_TRUE_DIVIDE"):
                right = self.pop()
                left = self.pop()

                if opname == "BINARY_ADD" or instr.argrepr == "+":
                    self.push(left + right)
                elif opname == "BINARY_SUBTRACT" or instr.argrepr == "-":
                    self.push(left - right)
                elif opname == "BINARY_MULTIPLY" or instr.argrepr == "*":
                    self.push(left * right)
                elif opname == "BINARY_TRUE_DIVIDE" or instr.argrepr == "/":
                    self.push(left / right)
                elif instr.argrepr == "%":
                    self.push(left % right)
                else:
                    raise NotImplementedError(f"Unsupported binary operator: {instr.argrepr}")

            # Opcode: Function Call (e.g. print)
            elif opname in ("CALL", "CALL_FUNCTION"):
                argc = instr.arg if instr.arg is not None else 0
                args = [self.pop() for _ in range(argc)]
                args.reverse()

                # In Python 3.11+, callable might have an associated NULL or self on stack
                func = self.pop()
                # Clean up any leftover NULL sentinel if pushed by PUSH_NULL
                if self.stack and self.top() is None:
                    # Only pop if it was placed as a callable delimiter
                    pass

                result = func(*args)
                self.push(result)

            # Opcode: Push NULL before callable (Python 3.11+ requirement)
            elif opname == "PUSH_NULL":
                pass

            # Opcode: Pop Top (Discard value)
            elif opname == "POP_TOP":
                if self.stack:
                    self.pop()

            # Opcode: Return Value
            elif opname == "RETURN_VALUE":
                return self.pop() if self.stack else None

            # Opcode: Resume (No-op in 3.11+)
            elif opname in ("RESUME", "NOP", "PRECALL"):
                pass

            else:
                raise NotImplementedError(f"Opcode '{opname}' is not yet supported in this VM.")

            instruction_pointer += 1

        return None