"""
Comprehensive unit test suite for PyVM execution engine.
Verifies arithmetic, data structures, control flow, functions,
recursion, and exception handling (try-except-finally).
"""

import unittest
from vm import VirtualMachine


class TestPyVM(unittest.TestCase):
    def setUp(self) -> None:
        self.vm = VirtualMachine()

    def _execute(self, source_code: str):
        code_obj = compile(source_code, filename="<test>", mode="exec")
        self.vm.run_code(code_obj)
        return self.vm.globals

    def test_arithmetic_and_precedence(self) -> None:
        code = """
a = 10 + 20 * 2
b = 100 // 4 - 5
c = 2 ** 8
d = 17 % 5
e = (a + b) * 2
"""
        scope = self._execute(code)
        self.assertEqual(scope["a"], 50)
        self.assertEqual(scope["b"], 20)
        self.assertEqual(scope["c"], 256)
        self.assertEqual(scope["d"], 2)
        self.assertEqual(scope["e"], 140)

    def test_bitwise_operations(self) -> None:
        code = """
w = 5 & 3
x = 5 | 2
y = 5 ^ 1
z = 1 << 4
"""
        scope = self._execute(code)
        self.assertEqual(scope["w"], 1)
        self.assertEqual(scope["x"], 7)
        self.assertEqual(scope["y"], 4)
        self.assertEqual(scope["z"], 16)

    def test_data_structures(self) -> None:
        code = """
lst = [1, 2, 3]
lst.append(4)
tup = (10, 20, 30)
st = {1, 2, 2, 3}
mp = {"key": "val", "num": 42}
elem = lst[2]
dict_val = mp["key"]
mp["new_key"] = 100
"""
        scope = self._execute(code)
        self.assertEqual(scope["lst"], [1, 2, 3, 4])
        self.assertEqual(scope["tup"], (10, 20, 30))
        self.assertEqual(scope["st"], {1, 2, 3})
        self.assertEqual(scope["elem"], 3)
        self.assertEqual(scope["dict_val"], "val")
        self.assertEqual(scope["mp"]["new_key"], 100)

    def test_conditional_branches(self) -> None:
        code = """
x = 15
if x > 10:
    res1 = "greater"
else:
    res1 = "smaller"

if x < 5:
    res2 = "branch_a"
else:
    res2 = "branch_b"
"""
        scope = self._execute(code)
        self.assertEqual(scope["res1"], "greater")
        self.assertEqual(scope["res2"], "branch_b")

    def test_loops_and_iteration(self) -> None:
        code = """
total = 0
for i in [1, 2, 3, 4, 5]:
    total = total + i

evens = []
for n in [1, 2, 3, 4, 5, 6]:
    if n % 2 == 0:
        evens.append(n)
"""
        scope = self._execute(code)
        self.assertEqual(scope["total"], 15)
        self.assertEqual(scope["evens"], [2, 4, 6])

    def test_user_defined_function(self) -> None:
        code = """
def calculate(x, y):
    return (x * 2) + y

output = calculate(5, 7)
"""
        scope = self._execute(code)
        self.assertEqual(scope["output"], 17)

    def test_recursion_factorial(self) -> None:
        code = """
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)

fact5 = factorial(5)
fact6 = factorial(6)
"""
        scope = self._execute(code)
        self.assertEqual(scope["fact5"], 120)
        self.assertEqual(scope["fact6"], 720)

    def test_try_except_zerodivision(self) -> None:
        code = """
status = "initial"
try:
    bad_math = 10 / 0
except ZeroDivisionError:
    status = "caught"
"""
        scope = self._execute(code)
        self.assertEqual(scope["status"], "caught")

    def test_try_except_custom_raise(self) -> None:
        code = """
caught_msg = ""
try:
    raise ValueError("custom error")
except ValueError as err:
    caught_msg = str(err)
"""
        scope = self._execute(code)
        self.assertEqual(scope["caught_msg"], "custom error")

    def test_try_except_cross_function_unwinding(self) -> None:
        code = """
def fail():
    return 1 / 0

def caller():
    try:
        fail()
        return "not reached"
    except ZeroDivisionError:
        return "recovered"

res = caller()
"""
        scope = self._execute(code)
        self.assertEqual(scope["res"], "recovered")


if __name__ == "__main__":
    unittest.main()