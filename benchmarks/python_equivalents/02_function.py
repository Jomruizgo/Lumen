"""Example 02: basic function definition and call."""
from typing import Union

def add(a: Union[int, float], b: Union[int, float]) -> Union[int, float]:
    """Return the sum of a and b."""
    return a + b

def main() -> None:
    result = add(2, 3)
    print(f"Result: {result}")

if __name__ == "__main__":
    main()
