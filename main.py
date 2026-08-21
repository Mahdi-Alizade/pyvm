"""
Entry point for testing and executing code on the custom Python Virtual Machine.
"""

from vm import VirtualMachine


def run_code_string(source_code: str, title: str = "Test Case") -> None:
    """Compile a source code string into bytecode and run it on our VM."""
    print("=" * 60)
    print(f"Scenario: {title}")
    print("-" * 60)
    print("Source Code:")
    print(source_code.strip())
    print("-" * 60)
    print("VM Output:")

    # Compile source text to Python code object (bytecode)
    code_obj = compile(source_code, filename="<embedded>", mode="exec")

    # Instantiate VM and execute
    vm = VirtualMachine()
    vm.run_code(code_obj)
    print("=" * 60 + "\n")


def main() -> None:
    # Test 1: Arithmetic and Assignments
    test_1 = """
x = 10
y = 20
z = x + y
print("Addition result:", z)
"""

    # Test 2: If / Else branching
    test_2 = """
score = 85
if score >= 50:
    print("Status: Passed! Score is", score)
else:
    print("Status: Failed.")
"""

    # Test 3: Loop with list summation
    test_3 = """
numbers = [1, 2, 3, 4, 5]
total = 0
for num in numbers:
    total = total + num
print("Sum of numbers in list:", total)
"""

    run_code_string(test_1, "Arithmetic and Variables")
    run_code_string(test_2, "Conditional Branching (if/else)")
    run_code_string(test_3, "List Iteration & For-Loop")


if __name__ == "__main__":
    main()