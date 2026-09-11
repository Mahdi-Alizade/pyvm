"""
A robust, frame-based Python Bytecode Virtual Machine implemented in pure Python.
Supports Python 3.11 - 3.13 bytecode conventions.
"""

import builtins
import dis
import types
from typing import Any, Dict, List, Optional


class _NullSentinel:
    """Represents the NULL pushed by PUSH_NULL in modern CPython frames."""
    def __repr__(self) -> str:
        return "<NULL>"


NULL = _NullSentinel()


class Frame:
    """
    Represents an isolated call frame containing its own stack,
    instruction pointer, locals, and reference to globals.
    """

    def __init__(
        self,
        code_obj: types.CodeType,
        globals_scope: Dict[str, Any],
        locals_scope: Dict[str, Any],
        builtins_scope: Dict[str, Any],
    ) -> None:
        self.code_obj = code_obj
        self.globals: Dict[str, Any] = globals_scope
        self.locals: Dict[str, Any] = locals_scope
        self.builtins: Dict[str, Any] = builtins_scope
        self.stack: List[Any] = []
        self.instructions: List[dis.Instruction] = list(dis.get_instructions(code_obj))
        self.offset_to_index: Dict[int, int] = {
            instr.offset: idx for idx, instr in enumerate(self.instructions)
        }
        self.ip: int = 0

    def push(self, value: Any) -> None:
        self.stack.append(value)

    def pop(self) -> Any:
        if not self.stack:
            raise IndexError("pop from empty execution stack")
        return self.stack.pop()

    def top(self) -> Any:
        if not self.stack:
            raise IndexError("peek from empty execution stack")
        return self.stack[-1]


class Function:
    """Represents a callable function inside the custom Virtual Machine."""

    def __init__(
        self,
        code_obj: types.CodeType,
        vm: "VirtualMachine",
        name: Optional[str] = None,
        defaults: tuple = (),
    ) -> None:
        self.code_obj = code_obj
        self.vm = vm
        self.name = name or code_obj.co_name
        self.defaults = defaults

    def __call__(self, *args: Any) -> Any:
        local_env: Dict[str, Any] = {}

        # Bind default arguments first
        arg_names = self.code_obj.co_varnames[: self.code_obj.co_argcount]
        if self.defaults:
            offset = len(arg_names) - len(self.defaults)
            for idx, default_val in enumerate(self.defaults):
                local_env[arg_names[offset + idx]] = default_val

        # Bind positional arguments
        for var_name, arg_val in zip(arg_names, args):
            local_env[var_name] = arg_val

        frame = Frame(
            code_obj=self.code_obj,
            globals_scope=self.vm.globals,
            locals_scope=local_env,
            builtins_scope=self.vm.builtins,
        )
        return self.vm.run_frame(frame)


class VirtualMachine:
    """
    Stack-based Virtual Machine capable of executing Python bytecode
    using frame-isolated stacks.
    """

    def __init__(self) -> None:
        self.globals: Dict[str, Any] = {}
        if isinstance(builtins, dict):
            self.builtins: Dict[str, Any] = builtins
        else:
            self.builtins: Dict[str, Any] = builtins.__dict__
        self.frames: List[Frame] = []

    def _eval_compare(self, left: Any, right: Any, raw_op: str) -> bool:
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
            raise NotImplementedError(f"Unsupported comparison operator: '{raw_op}'")

    def run_code(
        self, code_obj: types.CodeType, local_env: Optional[Dict[str, Any]] = None
    ) -> Any:
        locals_scope = local_env if local_env is not None else self.globals
        frame = Frame(
            code_obj=code_obj,
            globals_scope=self.globals,
            locals_scope=locals_scope,
            builtins_scope=self.builtins,
        )
        return self.run_frame(frame)

    def run_frame(self, frame: Frame) -> Any:
        self.frames.append(frame)

        try:
            while frame.ip < len(frame.instructions):
                instr = frame.instructions[frame.ip]
                opname = instr.opname
                argval = instr.argval
                jump_taken = False

                # Constants
                if opname == "LOAD_CONST":
                    frame.push(argval)

                # Scope: Globals & Builtins
                elif opname == "LOAD_GLOBAL":
                    if argval in frame.globals:
                        frame.push(frame.globals[argval])
                    elif argval in frame.builtins:
                        frame.push(frame.builtins[argval])
                    else:
                        raise NameError(f"global name '{argval}' is not defined")

                elif opname == "STORE_GLOBAL":
                    frame.globals[argval] = frame.pop()

                # Scope: Names
                elif opname == "LOAD_NAME":
                    if argval in frame.locals:
                        frame.push(frame.locals[argval])
                    elif argval in frame.globals:
                        frame.push(frame.globals[argval])
                    elif argval in frame.builtins:
                        frame.push(frame.builtins[argval])
                    else:
                        raise NameError(f"name '{argval}' is not defined")

                elif opname == "STORE_NAME":
                    frame.locals[argval] = frame.pop()

                # Scope: Locals (Fast)
                elif opname == "LOAD_FAST":
                    if argval in frame.locals:
                        frame.push(frame.locals[argval])
                    else:
                        raise UnboundLocalError(
                            f"local variable '{argval}' referenced before assignment"
                        )

                elif opname == "STORE_FAST":
                    frame.locals[argval] = frame.pop()

                # Attributes
                elif opname == "LOAD_ATTR":
                    owner = frame.pop()
                    attr_name = argval if isinstance(argval, str) else instr.argrepr
                    frame.push(getattr(owner, attr_name))

                elif opname == "STORE_ATTR":
                    val = frame.pop()
                    owner = frame.pop()
                    attr_name = argval if isinstance(argval, str) else instr.argrepr
                    setattr(owner, attr_name, val)

                # Subscripting & Slicing
                elif opname == "BINARY_SUBSCR":
                    sub = frame.pop()
                    container = frame.pop()
                    frame.push(container[sub])

                elif opname == "STORE_SUBSCR":
                    sub = frame.pop()
                    container = frame.pop()
                    val = frame.pop()
                    container[sub] = val

                # Data Structures
                elif opname == "BUILD_LIST":
                    count = instr.arg if instr.arg is not None else 0
                    items = [frame.pop() for _ in range(count)]
                    items.reverse()
                    frame.push(items)

                elif opname == "BUILD_MAP":
                    count = instr.arg if instr.arg is not None else 0
                    mapping: Dict[Any, Any] = {}
                    pairs = [frame.pop() for _ in range(count * 2)]
                    pairs.reverse()
                    for idx in range(0, len(pairs), 2):
                        mapping[pairs[idx]] = pairs[idx + 1]
                    frame.push(mapping)

                elif opname == "BUILD_TUPLE":
                    count = instr.arg if instr.arg is not None else 0
                    items = [frame.pop() for _ in range(count)]
                    items.reverse()
                    frame.push(tuple(items))

                elif opname == "BUILD_SET":
                    count = instr.arg if instr.arg is not None else 0
                    items = [frame.pop() for _ in range(count)]
                    frame.push(set(items))

                elif opname == "LIST_EXTEND":
                    i = instr.arg if instr.arg is not None else 1
                    items_to_extend = frame.pop()
                    target_list = frame.stack[-i]
                    target_list.extend(items_to_extend)

                elif opname == "LIST_APPEND":
                    i = instr.arg if instr.arg is not None else 1
                    item_to_append = frame.pop()
                    target_list = frame.stack[-i]
                    target_list.append(item_to_append)

                # Arithmetic & Unary
                elif opname == "UNARY_NEGATIVE":
                    frame.push(-frame.pop())

                elif opname == "UNARY_NOT":
                    frame.push(not frame.pop())

                elif opname == "UNARY_INVERT":
                    frame.push(~frame.pop())

                elif opname in (
                    "BINARY_OP",
                    "BINARY_ADD",
                    "BINARY_SUBTRACT",
                    "BINARY_MULTIPLY",
                    "BINARY_TRUE_DIVIDE",
                    "BINARY_FLOOR_DIVIDE",
                    "BINARY_MODULO",
                    "BINARY_POWER",
                ):
                    right = frame.pop()
                    left = frame.pop()
                    sym = instr.argrepr.replace("=", "").strip()

                    if opname == "BINARY_ADD" or sym == "+":
                        frame.push(left + right)
                    elif opname == "BINARY_SUBTRACT" or sym == "-":
                        frame.push(left - right)
                    elif opname == "BINARY_MULTIPLY" or sym == "*":
                        frame.push(left * right)
                    elif opname == "BINARY_TRUE_DIVIDE" or sym == "/":
                        frame.push(left / right)
                    elif opname == "BINARY_FLOOR_DIVIDE" or sym == "//":
                        frame.push(left // right)
                    elif opname == "BINARY_MODULO" or sym == "%":
                        frame.push(left % right)
                    elif opname == "BINARY_POWER" or sym == "**":
                        frame.push(left ** right)
                    elif sym == "&":
                        frame.push(left & right)
                    elif sym == "|":
                        frame.push(left | right)
                    elif sym == "^":
                        frame.push(left ^ right)
                    elif sym == "<<":
                        frame.push(left << right)
                    elif sym == ">>":
                        frame.push(left >> right)
                    else:
                        raise NotImplementedError(f"Unsupported binary operation: {instr.argrepr}")

                # Comparisons
                elif opname == "COMPARE_OP":
                    right = frame.pop()
                    left = frame.pop()
                    frame.push(self._eval_compare(left, right, instr.argrepr))

                # Control Flow & Jumps
                elif opname in ("JUMP_FORWARD", "JUMP_BACKWARD", "JUMP_ABSOLUTE"):
                    frame.ip = frame.offset_to_index[instr.argval]
                    jump_taken = True

                elif opname in (
                    "POP_JUMP_IF_FALSE",
                    "POP_JUMP_FORWARD_IF_FALSE",
                    "POP_JUMP_BACKWARD_IF_FALSE",
                ):
                    val = frame.pop()
                    if not bool(val):
                        frame.ip = frame.offset_to_index[instr.argval]
                        jump_taken = True

                elif opname in (
                    "POP_JUMP_IF_TRUE",
                    "POP_JUMP_FORWARD_IF_TRUE",
                    "POP_JUMP_BACKWARD_IF_TRUE",
                ):
                    val = frame.pop()
                    if bool(val):
                        frame.ip = frame.offset_to_index[instr.argval]
                        jump_taken = True

                # Iterators
                elif opname == "GET_ITER":
                    frame.push(iter(frame.pop()))

                elif opname in ("FOR_ITER", "FOR_ITER_GEN"):
                    iterator = frame.top()
                    try:
                        frame.push(next(iterator))
                    except StopIteration:
                        frame.pop()
                        frame.ip = frame.offset_to_index[instr.argval]
                        jump_taken = True

                elif opname == "END_FOR":
                    if frame.stack and not isinstance(frame.top(), (int, float, str, dict, list)):
                        frame.pop()

                # Functions & Calls
                elif opname == "MAKE_FUNCTION":
                    code_target = frame.pop()
                    func_obj = Function(code_target, self)
                    frame.push(func_obj)

                elif opname == "PUSH_NULL":
                    frame.push(NULL)

                elif opname in ("CALL", "CALL_FUNCTION"):
                    argc = instr.arg if instr.arg is not None else 0
                    args = [frame.pop() for _ in range(argc)]
                    args.reverse()

                    callable_target = frame.pop()

                    # Discard NULL prefix if placed by PUSH_NULL
                    if frame.stack and frame.top() is NULL:
                        frame.pop()

                    result = callable_target(*args)
                    frame.push(result)

                # Returns & Cleanup
                elif opname == "RETURN_CONST":
                    return argval

                elif opname == "RETURN_VALUE":
                    return frame.pop() if frame.stack else None

                elif opname == "POP_TOP":
                    if frame.stack:
                        frame.pop()

                elif opname in ("RESUME", "NOP", "PRECALL", "CACHE"):
                    pass

                else:
                    raise NotImplementedError(
                        f"Opcode '{opname}' (arg={instr.arg}, argval={instr.argval}) is not supported."
                    )

                if not jump_taken:
                    frame.ip += 1

        finally:
            self.frames.pop()

        return None