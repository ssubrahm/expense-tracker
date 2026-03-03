def fibonacci(n: int):
    """Return a list containing the first n terms of the Fibonacci sequence."""
    if n <= 0:
        return []

    sequence = [0]
    if n == 1:
        return sequence

    sequence.append(1)

    while len(sequence) < n:
        next_value = sequence[-1] + sequence[-2]
        sequence.append(next_value)

    return sequence


if __name__ == "__main__":
    import sys

    # Non-interactive mode: accept n from command-line argument if provided.
    if len(sys.argv) > 1:
        try:
            n = int(sys.argv[1])
        except ValueError:
            print("Usage: python fibonacci.py [n]")
            sys.exit(1)
        fib_seq = fibonacci(n)
        print(f"Fibonacci sequence with {n} terms:", fib_seq)
    else:
        # Interactive fallback for normal terminals.
        try:
            n_str = input("Enter the number of terms: ")
            n = int(n_str)
            fib_seq = fibonacci(n)
            print(f"Fibonacci sequence with {n} terms:", fib_seq)
        except EOFError:
            print("No input available. Run as: python fibonacci.py <n>")
        except ValueError:
            print("Please enter a valid integer for the number of terms.")
