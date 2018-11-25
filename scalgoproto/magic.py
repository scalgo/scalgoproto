# -*- mode: python; tab-width: 4; indent-tabs-mode: t; python-indent-offset: 4; coding: utf-8 -*-
"""
Generate magic values
"""
import random

def run(args) -> int:
	rng = random.SystemRandom()
	for x in range(10):
		print("@%08X"%rng.randint(0, 2**32))
	return 0

def setup(subparsers) -> None:
	cmd = subparsers.add_parser('magic', help='Generate magic')
	cmd.set_defaults(func=run)

