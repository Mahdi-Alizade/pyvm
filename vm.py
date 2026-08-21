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

    def _eval_compare(self, left: Any, right: Any, raw_op: str) -> bool:
        """Evaluate comparison operation cleanly across different Python version dis formats."""
        op = raw_op.replace("bool(", "").replace(")", "").strip()

        if op == "==":
            return left == right
        elif op == "!=":
            return left != right
        elif op == "<":
            return left < right
        elif op == "<=":
            return left <= right
        elif op == ">":
            return left > right
        elif op == ">=":
            return left >= right
        elif op in ("in", "IN"):
            return left in right
        elif op in ("not in", "NOT_IN"):
            return left not in right
        elif op in ("is", "IS"):
            return left is right
        elif op in ("is not", "IS_NOT"):
            return left is not right
        else:
            raise NotImplementedError(f"Unsupported comparison symbol: '{raw_op}' (parsed as '{op}')")

    def run_code(self, code_obj: types.CodeType) -> Any:
        """
        Disassemble and execute a Python code object instruction by instruction.
        """
        instructions = list(dis.get_instructions(code_obj))
        # Build map from instruction offset to index in list for accurate jump branching
        offset_to_index = {instr.offset: idx for idx, instr in enumerate(instructions)}

        instruction_pointer = 0

        while instruction_pointer < len(instructions):
            instr = instructions[instruction_pointer]
            opname = instr.opname
            argval = instr.argval
            jump_taken = False

            # Opcode: Load Constant
            if opname == "LOAD_CONST":
                self.push(argval)

            # Opcode: Load Variable (Global/Name)
            elif opname in ("LOAD_NAME", "LOAD_GLOBAL"):
                if argval in self.environment:
                    self.push(self.environment[argval])
                elif argval in self.builtins:
                    self.push(self.builtins[argval])
                else:
                    raise NameError(f"name '{argval}' is not defined")

            # Opcode: Store Variable (Global/Name)
            elif opname in ("STORE_NAME", "STORE_GLOBAL"):
                val = self.pop()
                self.environment[argval] = val

            # Opcode: Fast Local Variable Access
            elif opname == "LOAD_FAST":
                if argval in self.environment:
                    self.push(self.environment[argval])
                else:
                    raise UnboundLocalError(f"local variable '{argval}' referenced before assignment")

            elif opname == "STORE_FAST":
                val = self.pop()
                self.environment[argval] = val

            # Opcode: Build and Manipulate List
            elif opname == "BUILD_LIST":
                count = instr.arg if instr.arg is not None else 0
                items = [self.pop() for _ in range(count)]
                items.reverse()
                self.push(items)

            elif opname == "LIST_EXTEND":
                # arg is the 1-based index from the top of the stack pointing to the target list
                i = instr.arg if instr.arg is not None else 1
                items_to_extend = self.pop()
                target_list = self.stack[-i]
                target_list.extend(items_to_extend)

            elif opname == "LIST_APPEND":
                i = instr.arg if instr.arg is not None else 1
                item_to_append = self.pop()
                target_list = self.stack[-i]
                target_list.append(item_to_append)

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

            # Opcode: Comparison Operations
            elif opname == "COMPARE_OP":
                right = self.pop()
                left = self.pop()
                result = self._eval_compare(left, right, instr.argrepr)
                self.push(result)

            # Opcode: Unconditional Jumps
            elif opname in ("JUMP_FORWARD", "JUMP_BACKWARD", "JUMP_ABSOLUTE"):
                target_offset = instr.argval
                instruction_pointer = offset_to_index[target_offset]
                jump_taken = True

            # Opcode: Conditional Jumps
            elif opname in ("POP_JUMP_IF_FALSE", "POP_JUMP_FORWARD_IF_FALSE", "POP_JUMP_BACKWARD_IF_FALSE"):
                val = self.pop()
                if not bool(val):
                    target_offset = instr.argval
                    instruction_pointer = offset_to_index[target_offset]
                    jump_taken = True

            elif opname in ("POP_JUMP_IF_TRUE", "POP_JUMP_FORWARD_IF_TRUE", "POP_JUMP_BACKWARD_IF_TRUE"):
                val = self.pop()
                if bool(val):
                    target_offset = instr.argval
                    instruction_pointer = offset_to_index[target_offset]
                    jump_taken = True

            # Opcode: Iterators & For Loops
            elif opname == "GET_ITER":
                iterable = self.pop()
                self.push(iter(iterable))

            elif opname in ("FOR_ITER", "FOR_ITER_GEN"):
                iterator = self.top()
                try:
                    next_value = next(iterator)
                    self.push(next_value)
                except StopIteration:
                    # Pop the exhausted iterator off the stack
                    self.pop()
                    target_offset = instr.argval
                    instruction_pointer = offset_to_index[target_offset]
                    jump_taken = True

            elif opname == "END_FOR":
                if self.stack:
                    self.pop()

            # Opcode: Function Call
            elif opname in ("CALL", "CALL_FUNCTION"):
                argc = instr.arg if instr.arg is not None else 0
                args = [self.pop() for _ in range(argc)]
                args.reverse()

                func = self.pop()
                result = func(*args)
                self.push(result)

            # Opcode: Push NULL before callable (Python 3.11+ requirement)
            elif opname == "PUSH_NULL":
                pass

            # Opcode: Pop Top (Discard value)
            elif opname == "POP_TOP":
                if self.stack:
                    self.pop()

            # Opcode: Return Constant (Python 3.12+ optimization)
            elif opname == "RETURN_CONST":
                return argval

            # Opcode: Return Value
            elif opname == "RETURN_VALUE":
                return self.pop() if self.stack else None

            # Opcode: Resume and administrative opcodes
            elif opname in ("RESUME", "NOP", "PRECALL"):
                pass

            else:
                raise NotImplementedError(f"Opcode '{opname}' is not yet supported in this VM.")

            if not jump_taken:
                instruction_pointer += 1

        return None