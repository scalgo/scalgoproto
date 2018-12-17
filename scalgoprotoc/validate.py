# -*- mode: python; tab-width: 4; indent-tabs-mode: t; python-indent-offset: 4; coding: utf-8 -*-
"""
Validate a schema
"""
from .annotate import annotate
from .parser import ParseError, Parser
from .documents import Documents, addDocumentsParams


def run(args) -> int:
    documents = Documents()
    documents.read_root(args.schema)
    p = Parser(documents)
    try:
        ast = p.parse_document()
        if annotate(documents, ast):
            print("Schema is valid")
            return 0
    except ParseError as err:
        err.describe(documents)
        pass
    return 1


def setup(subparsers) -> None:
    cmd = subparsers.add_parser("validate", help="Validate schema")
    cmd.add_argument("schema", help="schema to validate")
    addDocumentsParams(cmd)
    cmd.set_defaults(func=run)
