"""
Entry point for testing and executing code on the custom Python Virtual Machine.
"""

from vm import VirtualMachine


def run_code_string(source_code: str) -> None:
    """Compile a source code string into bytecode and run it on our VM."""
    print("=" * 50)
    print("Source Code:")
    print(source_code.strip())
    print("=" * 50)
    print("VM Output:")

    # Compile source text to Python code object (bytecode)
    code_obj = compile(source_code, filename="<embedded>", mode="exec")

    # Instantiate VM and execute
    vm = VirtualMachine()
    vm.run_code(code_obj)
    print("=" * 50)


def main() -> None:
    # Test script with variable assignments, arithmetic operations, and print calls
    sample_program = """
a = 15
b = 25
total = a + b
result = total * 2
print("Calculated result:", result)
"""
    run_code_string(sample_program)


if __name__ == "__main__":
    main()