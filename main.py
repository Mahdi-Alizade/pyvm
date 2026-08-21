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
    # Test 1: Function definition and invocation
    test_func = """
def greet(name, age):
    message = "Hello " + name + "! Next year you will be " + str(age + 1) + "."
    return message

res = greet("Mahdi", 24)
print(res)
"""

    # Test 2: Recursive Factorial function
    test_factorial = """
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)

print("Factorial of 5:", factorial(5))
print("Factorial of 6:", factorial(6))
"""

    run_code_string(test_func, "Function Definition and Call")
    run_code_string(test_factorial, "Recursive Function Execution (Factorial)")


if __name__ == "__main__":
    main()