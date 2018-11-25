# -*- mode: python; tab-width: 4; indent-tabs-mode: t; python-indent-offset: 4; coding: utf-8 -*-
"""
Main executable
"""
from parser import Parser, ParseError
import argparse
import validate
import cpp_generator
import python_generator
import magic
import sys
parser = argparse.ArgumentParser(description='Process schema.')
subparsers = parser.add_subparsers(help='Subcommand to run')
validate.setup(subparsers)
magic.setup(subparsers)
cpp_generator.setup(subparsers)
python_generator.setup(subparsers)
args = parser.parse_args()
sys.exit(args.func(args))
