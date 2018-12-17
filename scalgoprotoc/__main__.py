# -*- mode: python; tab-width: 4; indent-tabs-mode: t; python-indent-offset: 4; coding: utf-8 -*-
"""
Main executable
"""
import argparse
import sys

from . import cpp_generator, magic, python_generator, validate
from .parser import ParseError, Parser

parser = argparse.ArgumentParser(description="Process schema.")
subparsers = parser.add_subparsers(help="Subcommand to run")
validate.setup(subparsers)
magic.setup(subparsers)
cpp_generator.setup(subparsers)
python_generator.setup(subparsers)


def main():
    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
