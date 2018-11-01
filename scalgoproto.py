# -*- mode: python; tab-width: 4; indent-tabs-mode: t; python-indent-offset: 4; coding: utf-8 -*-
"""
Main executable
"""
from parser import Parser, ParseError
import argparse
import validate
import magic

parser = argparse.ArgumentParser(description='Process schema.')
subparsers = parser.add_subparsers(help='Subcommand to run')
parser_cpp = subparsers.add_parser('cpp', help='Build cpp')

validate.setup(subparsers)
magic.setup(subparsers)
args = parser.parse_args()
args.func(args)
