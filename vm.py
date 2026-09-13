"""
A modular, high-performance Python Bytecode Virtual Machine.
Uses a direct O(1) dispatch table pattern, isolated frame stacks,
native Exception Table unwinding, and Context Manager (with statement) support.
Compatible with Python 3.11 - 3.13.
"""

import builtins
import dis
import operator
import types
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Tuple


class _NullSentinel:
    """Represents the NULL pushed by PUSH_NULL in modern Python bytecode."""
    __slots__ = ()

    def __repr__(self) -> str:
        return "<NULL>"


NULL = _NullSentinel()


class ExceptionTableEntry(NamedTuple):
    """Represents a range of bytecode offsets covered by an exception handler."""
    start: int
    end: int
    target: int
    depth: int
    lasti: bool


def _parse_exception_table(code_obj: types.CodeType) -> List[ExceptionTableEntry]:
    """Parse modern co_exceptiontable into structured entries."""
    if not hasattr(code_obj, "co_exceptiontable") or not code_obj.co_exceptiontable:
        return []

    if hasattr(dis, "_parse_exception_table"):
        try:
            raw_entries = dis._parse_exception_table(code_obj.co_exceptiontable)
            return [
                ExceptionTableEntry(e.start, e.end, e.target, e.depth, e.lasti)
                for e in raw_entries
            ]
        except Exception:
            pass

    raw = code_obj.co_exceptiontable
    iterator = iter(raw)
    entries: List[ExceptionTableEntry] = []

    try:
        while True:
            def parse_varint() -> int:
                b = next(iterator)
                val = b & 63
                while b & 64:
                    val <<= 6
                    b = next(iterator)
                    val |= (b & 63)
                return val

            start = parse_varint() * 2
            length = parse_varint() * 2
            end = start + length
            target = parse_varint() * 2
            dl = parse_varint()
            depth = dl >> 1
            lasti = bool(dl & 1)
            entries.append(ExceptionTableEntry(start, end, target, depth, lasti))
    except StopIteration:
        pass

    return entries


# Cache disassembled instructions, offsets, and exception tables per code object
_CODE_CACHE: Dict[types.CodeType, Tuple[List[dis.Instruction], Dict[int, int], List[ExceptionTableEntry]]] = {}


def _get_cached_code_data(code_obj: types.CodeType) -> Tuple[List[dis.Instruction], Dict[int, int], List[ExceptionTableEntry]]:
    if code_obj not in _CODE_CACHE:
        instructions = list(dis.get_instructions(code_obj))
        offset_map = {instr.offset: idx for idx, instr in enumerate(instructions)}
        exc_entries = _parse_exception_table(code_obj)
        _CODE_CACHE[code_obj] = (instructions, offset_map, exc_entries)
    return _CODE_CACHE[code_obj]


class Frame:
    """Represents an isolated call frame with its own stack and instruction pointer."""
    __slots__ = (
        "code_obj",
        "globals",
        "locals",
        "builtins",
        "stack",
        "instructions",
        "offset_to_index",
        "exception_entries",
        "block_stack",
        "ip",
    )

    def __init__(
        self,
        code_obj: types.CodeType,
        globals_scope: Dict[str, Any],
        locals_scope: Dict[str, Any],
        builtins_scope: Dict[str, Any],
    ) -> None:
        self.code_obj = code_obj
        self.globals = globals_scope
        self.locals = locals_scope
        self.builtins = builtins_scope
        self.stack: List[Any] = []
        (
            self.instructions,
            self.offset_to_index,
            self.exception_entries,
        ) = _get_cached_code_data(code_obj)
        self.block_stack: List[Tuple[str, int, int]] = []
        self.ip: int = 0

    def push(self, value: Any) -> None:
        self.stack.append(value)

    def pop(self) -> Any:
        try:
            return self.stack.pop()
        except IndexError:
            raise IndexError("pop from empty execution stack") from None

    def top(self) -> Any:
        try:
            return self.stack[-1]
        except IndexError:
            raise IndexError("peek from empty execution stack") from None

    def popn(self, n: int) -> List[Any]:
        """Pop n items maintaining original left-to-right order."""
        if n == 0:
            return []
        items = self.stack[-n:]
        del self.stack[-n:]
        return items


class Function:
    """User-defined callable function inside the VM."""
    __slots__ = ("code_obj", "vm", "name", "defaults")

    def __init__(
        self,
        code_obj: types.CodeType,
        vm: "VirtualMachine",
        name: Optional[str] = None,
        defaults: Tuple[Any, ...] = (),
    ) -> None:
        self.code_obj = code_obj
        self.vm = vm
        self.name = name or code_obj.co_name
        self.defaults = defaults

    def __call__(self, *args: Any) -> Any:
        local_env: Dict[str, Any] = {}
        arg_names = self.code_obj.co_varnames[: self.code_obj.co_argcount]

        if self.defaults:
            offset = len(arg_names) - len(self.defaults)
            for idx, default_val in enumerate(self.defaults):
                local_env[arg_names[offset + idx]] = default_val

        for name, val in zip(arg_names, args):
            local_env[name] = val

        frame = Frame(
            code_obj=self.code_obj,
            globals_scope=self.vm.globals,
            locals_scope=local_env,
            builtins_scope=self.vm.builtins,
        )
        return self.vm.run_frame(frame)


class VirtualMachine:
    """Execution engine with O(1) table-driven opcode dispatching and exception handling."""

    _dispatch_table: Dict[str, Callable[["VirtualMachine", Frame, dis.Instruction], Any]] = {}

    BINARY_OPS: Dict[str, Callable[[Any, Any], Any]] = {
        "+": operator.add,
        "-": operator.sub,
        "*": operator.mul,
        "/": operator.truediv,
        "//": operator.floordiv,
        "%": operator.mod,
        "**": operator.pow,
        "&": operator.and_,
        "|": operator.or_,
        "^": operator.xor,
        "<<": operator.lshift,
        ">>": operator.rshift,
    }

    COMPARE_OPS: Dict[str, Callable[[Any, Any], bool]] = {
        "==": operator.eq,
        "!=": operator.ne,
        "<": operator.lt,
        "<=": operator.le,
        ">": operator.gt,
        ">=": operator.ge,
        "in": lambda a, b: a in b,
        "not in": lambda a, b: a not in b,
        "is": operator.is_,
        "is not": operator.is_not,
    }

    @classmethod
    def register(cls, *opnames: str):
        """Decorator to map opcodes directly into the dispatch table."""
        def decorator(func: Callable[["VirtualMachine", Frame, dis.Instruction], Any]):
            for op in opnames:
                cls._dispatch_table[op] = func
            return func
        return decorator

    def __init__(self) -> None:
        self.globals: Dict[str, Any] = {}
        self.builtins: Dict[str, Any] = builtins.__dict__ if not isinstance(builtins, dict) else builtins
        self.frames: List[Frame] = []
        self.exc_value: Optional[BaseException] = None

    def run_code(self, code_obj: types.CodeType, local_env: Optional[Dict[str, Any]] = None) -> Any:
        locals_scope = local_env if local_env is not None else self.globals
        frame = Frame(
            code_obj=code_obj,
            globals_scope=self.globals,
            locals_scope=locals_scope,
            builtins_scope=self.builtins,
        )
        return self.run_frame(frame)

    def _handle_exception(self, frame: Frame, current_offset: int, exc: BaseException) -> bool:
        """Locate matching exception handler and unwind the stack."""
        matching_entry: Optional[ExceptionTableEntry] = None

        for entry in frame.exception_entries:
            if entry.start <= current_offset < entry.end:
                if matching_entry is None or (entry.end - entry.start) < (matching_entry.end - matching_entry.start):
                    matching_entry = entry

        if matching_entry is not None:
            del frame.stack[matching_entry.depth:]
            if matching_entry.lasti:
                frame.push(current_offset)
            self.exc_value = exc
            frame.push(exc)
            frame.ip = frame.offset_to_index[matching_entry.target] - 1
            return True

        if frame.block_stack:
            _, target_offset, depth = frame.block_stack.pop()
            del frame.stack[depth:]
            self.exc_value = exc
            frame.push(exc)
            frame.ip = frame.offset_to_index[target_offset] - 1
            return True

        return False

    def run_frame(self, frame: Frame) -> Any:
        self.frames.append(frame)
        try:
            while frame.ip < len(frame.instructions):
                instr = frame.instructions[frame.ip]
                handler = self._dispatch_table.get(instr.opname)

                if handler is None:
                    raise NotImplementedError(f"Opcode '{instr.opname}' is not supported.")

                try:
                    result = handler(self, frame, instr)
                    if instr.opname in ("RETURN_VALUE", "RETURN_CONST"):
                        return result
                except BaseException as exc:
                    handled = self._handle_exception(frame, instr.offset, exc)
                    if not handled:
                        raise

                frame.ip += 1
        finally:
            self.frames.pop()
        return None


# ---------------------------------------------------------
# Opcode Handlers Registration
# ---------------------------------------------------------

@VirtualMachine.register("LOAD_CONST")
def _load_const(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    frame.push(instr.argval)


@VirtualMachine.register("LOAD_GLOBAL")
def _load_global(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    name = instr.argval
    if name in frame.globals:
        frame.push(frame.globals[name])
    elif name in frame.builtins:
        frame.push(frame.builtins[name])
    else:
        raise NameError(f"global name '{name}' is not defined")


@VirtualMachine.register("STORE_GLOBAL")
def _store_global(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    frame.globals[instr.argval] = frame.pop()


@VirtualMachine.register("DELETE_GLOBAL")
def _delete_global(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    name = instr.argval
    if name in frame.globals:
        del frame.globals[name]
    else:
        raise NameError(f"global name '{name}' is not defined")


@VirtualMachine.register("LOAD_NAME")
def _load_name(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    name = instr.argval
    if name in frame.locals:
        frame.push(frame.locals[name])
    elif name in frame.globals:
        frame.push(frame.globals[name])
    elif name in frame.builtins:
        frame.push(frame.builtins[name])
    else:
        raise NameError(f"name '{name}' is not defined")


@VirtualMachine.register("STORE_NAME")
def _store_name(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    frame.locals[instr.argval] = frame.pop()


@VirtualMachine.register("DELETE_NAME")
def _delete_name(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    name = instr.argval
    if name in frame.locals:
        del frame.locals[name]
    elif name in frame.globals:
        del frame.globals[name]
    else:
        raise NameError(f"name '{name}' is not defined")


@VirtualMachine.register("LOAD_FAST")
def _load_fast(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    name = instr.argval
    if name in frame.locals:
        frame.push(frame.locals[name])
    else:
        raise UnboundLocalError(f"local variable '{name}' referenced before assignment")


@VirtualMachine.register("STORE_FAST")
def _store_fast(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    frame.locals[instr.argval] = frame.pop()


@VirtualMachine.register("DELETE_FAST")
def _delete_fast(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    name = instr.argval
    if name in frame.locals:
        del frame.locals[name]
    else:
        raise UnboundLocalError(f"local variable '{name}' referenced before assignment")


@VirtualMachine.register("COPY")
def _copy(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    idx = instr.arg or 1
    if idx <= len(frame.stack):
        frame.push(frame.stack[-idx])
    else:
        frame.push(frame.stack[-1] if frame.stack else vm.exc_value)


@VirtualMachine.register("SWAP")
def _swap(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    idx = instr.arg or 2
    if idx <= len(frame.stack):
        frame.stack[-1], frame.stack[-idx] = frame.stack[-idx], frame.stack[-1]


@VirtualMachine.register("LOAD_ATTR")
def _load_attr(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    owner = frame.pop()
    attr = instr.argval if isinstance(instr.argval, str) else instr.argrepr
    frame.push(getattr(owner, attr))


@VirtualMachine.register("STORE_ATTR")
def _store_attr(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    val = frame.pop()
    owner = frame.pop()
    attr = instr.argval if isinstance(instr.argval, str) else instr.argrepr
    setattr(owner, attr, val)


@VirtualMachine.register("BINARY_SUBSCR")
def _binary_subscr(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    sub = frame.pop()
    container = frame.pop()
    frame.push(container[sub])


@VirtualMachine.register("STORE_SUBSCR")
def _store_subscr(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    sub = frame.pop()
    container = frame.pop()
    container[sub] = frame.pop()


@VirtualMachine.register("BUILD_LIST")
def _build_list(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    frame.push(frame.popn(instr.arg or 0))


@VirtualMachine.register("BUILD_TUPLE")
def _build_tuple(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    frame.push(tuple(frame.popn(instr.arg or 0)))


@VirtualMachine.register("BUILD_SET")
def _build_set(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    frame.push(set(frame.popn(instr.arg or 0)))


@VirtualMachine.register("BUILD_MAP")
def _build_map(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    count = instr.arg or 0
    items = frame.popn(count * 2)
    frame.push({items[i]: items[i + 1] for i in range(0, len(items), 2)})


@VirtualMachine.register("BUILD_CONST_KEY_MAP")
def _build_const_key_map(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    keys = frame.pop()
    count = len(keys)
    values = frame.popn(count)
    frame.push(dict(zip(keys, values)))


@VirtualMachine.register("LIST_EXTEND")
def _list_extend(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    items = frame.pop()
    target_list = frame.stack[-(instr.arg or 1)]
    target_list.extend(items)


@VirtualMachine.register("LIST_APPEND")
def _list_append(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    item = frame.pop()
    target_list = frame.stack[-(instr.arg or 1)]
    target_list.append(item)


@VirtualMachine.register("SET_UPDATE")
def _set_update(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    items = frame.pop()
    target_set = frame.stack[-(instr.arg or 1)]
    target_set.update(items)


@VirtualMachine.register("MAP_ADD")
def _map_add(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    val = frame.pop()
    key = frame.pop()
    target_map = frame.stack[-(instr.arg or 1)]
    target_map[key] = val


@VirtualMachine.register("DICT_UPDATE")
def _dict_update(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    items = frame.pop()
    target_dict = frame.stack[-(instr.arg or 1)]
    target_dict.update(items)


@VirtualMachine.register("UNARY_NEGATIVE", "UNARY_NOT", "UNARY_INVERT")
def _unary_ops(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    val = frame.pop()
    if instr.opname == "UNARY_NEGATIVE":
        frame.push(-val)
    elif instr.opname == "UNARY_NOT":
        frame.push(not val)
    else:
        frame.push(~val)


@VirtualMachine.register("BINARY_OP", "BINARY_ADD", "BINARY_SUBTRACT", "BINARY_MULTIPLY", "BINARY_TRUE_DIVIDE")
def _binary_ops(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    right = frame.pop()
    left = frame.pop()
    sym = instr.argrepr.replace("=", "").strip()
    op_func = vm.BINARY_OPS.get(sym)
    if op_func is None:
        raise NotImplementedError(f"Unsupported binary operator: '{instr.argrepr}'")
    frame.push(op_func(left, right))


@VirtualMachine.register("COMPARE_OP")
def _compare_op(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    right = frame.pop()
    left = frame.pop()
    raw = instr.argrepr.replace("bool(", "").replace(")", "").strip()
    cmp_func = vm.COMPARE_OPS.get(raw)
    if cmp_func is None:
        raise NotImplementedError(f"Unsupported comparison operator: '{raw}'")
    frame.push(cmp_func(left, right))


@VirtualMachine.register("JUMP_FORWARD", "JUMP_BACKWARD", "JUMP_ABSOLUTE")
def _jump(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    frame.ip = frame.offset_to_index[instr.argval] - 1


@VirtualMachine.register("POP_JUMP_IF_FALSE", "POP_JUMP_FORWARD_IF_FALSE", "POP_JUMP_BACKWARD_IF_FALSE")
def _jump_if_false(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    if not bool(frame.pop()):
        frame.ip = frame.offset_to_index[instr.argval] - 1


@VirtualMachine.register("POP_JUMP_IF_TRUE", "POP_JUMP_FORWARD_IF_TRUE", "POP_JUMP_BACKWARD_IF_TRUE")
def _jump_if_true(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    if bool(frame.pop()):
        frame.ip = frame.offset_to_index[instr.argval] - 1


@VirtualMachine.register("GET_ITER")
def _get_iter(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    frame.push(iter(frame.pop()))


@VirtualMachine.register("FOR_ITER", "FOR_ITER_GEN")
def _for_iter(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    iterator = frame.top()
    try:
        frame.push(next(iterator))
    except StopIteration:
        frame.pop()
        frame.ip = frame.offset_to_index[instr.argval] - 1


@VirtualMachine.register("END_FOR")
def _end_for(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    if frame.stack and not isinstance(frame.top(), (int, float, str, dict, list, set, tuple)):
        frame.pop()


@VirtualMachine.register("MAKE_FUNCTION")
def _make_function(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    code_target = frame.pop()
    frame.push(Function(code_target, vm))


@VirtualMachine.register("PUSH_NULL")
def _push_null(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    frame.push(NULL)


@VirtualMachine.register("CALL", "CALL_FUNCTION")
def _call(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    argc = instr.arg or 0
    args = frame.popn(argc)
    candidate = frame.pop()

    if candidate is NULL:
        callable_target = frame.pop()
    elif callable(candidate):
        callable_target = candidate
        if frame.stack and frame.top() is NULL:
            frame.pop()
    else:
        # Method call where candidate is self/first argument and callable sits underneath
        args.insert(0, candidate)
        callable_target = frame.pop()
        if frame.stack and frame.top() is NULL:
            frame.pop()

    frame.push(callable_target(*args))


@VirtualMachine.register("RETURN_CONST")
def _return_const(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> Any:
    return instr.argval


@VirtualMachine.register("RETURN_VALUE")
def _return_value(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> Any:
    return frame.pop() if frame.stack else None


@VirtualMachine.register("POP_TOP")
def _pop_top(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    if frame.stack:
        frame.pop()


# ---------------------------------------------------------
# Exception Handling Opcodes
# ---------------------------------------------------------

@VirtualMachine.register("PUSH_EXC_INFO")
def _push_exc_info(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    new_exc = frame.top()
    prev_exc = vm.exc_value
    vm.exc_value = new_exc
    frame.push(prev_exc)
    frame.push(new_exc)


@VirtualMachine.register("CHECK_EXC_MATCH")
def _check_exc_match(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    target_type = frame.pop()
    exc = frame.pop()

    if isinstance(exc, BaseException):
        match = isinstance(exc, target_type)
    elif isinstance(exc, type) and issubclass(exc, BaseException):
        match = issubclass(exc, target_type)
    else:
        match = False

    frame.push(match)


@VirtualMachine.register("POP_EXCEPT")
def _pop_except(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    if frame.stack:
        from_exc = frame.pop()
        vm.exc_value = from_exc


@VirtualMachine.register("RERAISE")
def _reraise(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    depth = instr.arg or 0
    exc = None
    if depth > 0 and len(frame.stack) >= depth:
        exc = frame.stack[-depth]
    elif frame.stack:
        exc = frame.pop()

    if exc is None:
        exc = vm.exc_value
    if exc is None:
        raise RuntimeError("No active exception to reraise")
    raise exc


@VirtualMachine.register("RAISE_VARARGS")
def _raise_varargs(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    argc = instr.arg or 0
    if argc == 0:
        if vm.exc_value:
            raise vm.exc_value
        raise RuntimeError("No active exception to reraise")
    elif argc == 1:
        exc = frame.pop()
        if isinstance(exc, type) and issubclass(exc, BaseException):
            raise exc()
        raise exc
    elif argc == 2:
        cause = frame.pop()
        exc = frame.pop()
        if isinstance(exc, type) and issubclass(exc, BaseException):
            exc = exc()
        raise exc from cause


@VirtualMachine.register("SETUP_FINALLY")
def _setup_finally(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    frame.block_stack.append(("finally", instr.argval, len(frame.stack)))


@VirtualMachine.register("POP_BLOCK")
def _pop_block(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    if frame.block_stack:
        frame.block_stack.pop()


# ---------------------------------------------------------
# Context Manager (With Statement) Opcodes
# ---------------------------------------------------------

@VirtualMachine.register("BEFORE_WITH")
def _before_with(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    """Prepare context manager by calling __enter__ and pushing bound __exit__."""
    cm = frame.pop()
    exit_method = getattr(type(cm), "__exit__", getattr(cm, "__exit__", None))
    enter_method = getattr(type(cm), "__enter__", getattr(cm, "__enter__", None))

    if enter_method is None or exit_method is None:
        raise TypeError(f"'{type(cm).__name__}' object does not support the context manager protocol")

    bound_exit = exit_method.__get__(cm, type(cm))
    enter_res = enter_method(cm)
    frame.push(bound_exit)
    frame.push(enter_res)


@VirtualMachine.register("WITH_EXCEPT_START")
def _with_except_start(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    """Execute context manager's __exit__ upon exception."""
    exc = frame.top()
    # Locate exit method on stack
    exit_func = None
    for item in reversed(frame.stack):
        if callable(item):
            exit_func = item
            break
    if exit_func is None:
        exit_func = frame.stack[0]

    res = exit_func(type(exc), exc, exc.__traceback__ if hasattr(exc, "__traceback__") else None)
    frame.push(res)


@VirtualMachine.register("SETUP_WITH")
def _setup_with(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    cm = frame.top()
    exit_method = getattr(cm, "__exit__")
    enter_res = getattr(cm, "__enter__")()
    frame.push(exit_method)
    frame.push(enter_res)


@VirtualMachine.register("RESUME", "NOP", "PRECALL", "CACHE")
def _noop(vm: VirtualMachine, frame: Frame, instr: dis.Instruction) -> None:
    pass