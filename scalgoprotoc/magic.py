"""
Generate magic values
"""

import random


def run(args) -> int:
    rng = random.SystemRandom()
    for x in range(10):
        print(f"@{rng.randint(0, 2**32):08X}")
    return 0


def setup(subparsers) -> None:
    cmd = subparsers.add_parser("magic", help="Generate magic")
    cmd.set_defaults(func=run)
