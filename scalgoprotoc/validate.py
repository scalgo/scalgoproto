# -*- mode: python; tab-width: 4; indent-tabs-mode: t; python-indent-offset: 4; coding: utf-8 -*-
"""
Validate a schema
"""
from typing import NoReturn, Tuple
from .annotate import annotate
from .parser import (
    ParseError,
    Parser,
    Struct,
    Enum,
    Table,
    Union,
    Namespace,
    AstNode,
    Value,
)
from .documents import Documents, addDocumentsParams
from .sp_tokenize import Token
from .error import error
from itertools import zip_longest


def ct(t: Token | None) -> Token:
    assert t is not None
    return t


def run(args) -> int:
    documents = Documents()
    documents.read_root(args.schema)
    p = Parser(documents)
    try:
        ast = p.parse_document(strict=args.strict)
        checked: set[Tuple[AstNode, AstNode]] = set()
        if not annotate(documents, ast):
            return 1
        if args.old is not None:
            try:
                old_documents = Documents()
                old_documents.read_root(args.old)
                old_p = Parser(old_documents)
                old_ast = old_p.parse_document()
                if not annotate(old_documents, old_ast):
                    print("Old is not valid")
                    return 1
            except ParseError as err:
                print("Old is not valid")
                err.describe(old_documents)
                return 1
            ok = True

            def missing_member(old: Token, new: AstNode, name: str) -> None:
                nonlocal ok
                print(old)
                error(documents, p.context, ct(new.token), f"Missing member {name}")
                error(old_documents, old_p.context, old, "Was here")
                ok = False

            def invalid_type(old: AstNode, new: AstNode) -> None:
                nonlocal ok
                error(documents, p.context, ct(new.token), "Type changed")
                error(
                    old_documents, old_p.context, ct(new.token), "Used to be defined as"
                )
                ok = False

            def nv(t: Token) -> str:
                return documents.by_id[t.document].content[t.index : t.index + t.length]

            def ov(t: Token) -> str:
                return old_documents.by_id[t.document].content[
                    t.index : t.index + t.length
                ]

            def check_renamed(old: Token, new: Token) -> None:
                if ov(old) == nv(new):
                    return
                error(documents, p.context, new, "Member renamed", "Warning")
                error(old_documents, old_p.context, old, "Was", "Warning")

            def check_flag(
                om: Value, nm: Value, ov: Token | None, nv: Token | None, flag: str
            ) -> None:
                nonlocal ok
                if (ov is None) == (nv is None):
                    return
                error(documents, p.context, nm.type_, f"{flag} changed")
                error(old_documents, old_p.context, om.type_, "Previous definition")
                ok = False

            def match_value(om: Value, nm: Value) -> None:
                nonlocal ok
                check_renamed(om.identifier, nm.identifier)
                assert om.type_ is not None
                assert nm.type_ is not None
                tn = nv(nm.type_)

                if (
                    nm.table
                    or nm.union
                    or nm.direct_table
                    or nm.list_
                    or nm.direct_union
                    or tn in ("F32", "F64", "Text", "Bytes")
                ):
                    pass
                else:
                    check_flag(om, nm, om.optional, nm.optional, "Optionality")
                check_flag(om, nm, om.inplace, nm.inplace, "Inplace")
                check_flag(om, nm, om.list_, nm.list_, "List")
                check_flag(om, nm, om.direct, nm.direct, "Direct")
                if om.table and nm.table:
                    if om.table.magic != nm.table.magic:
                        error(
                            documents,
                            p.context,
                            nm.identifier,
                            f"Magic differs is {nm.table.magic:08X}",
                        )
                        error(
                            old_documents,
                            old_p.context,
                            om.identifier,
                            f"Previously was {om.table.magic:08X}",
                        )
                    match_tables(om.table, nm.table)
                elif om.union and nm.union:
                    match_unions(om.union, nm.union)
                elif om.struct and nm.struct:
                    match_structs(om.struct, nm.struct)
                elif ov(om.type_) != nv(nm.type_):
                    error(documents, p.context, nm.type_, "Type changed")
                    error(old_documents, old_p.context, om.type_, "Was")
                    ok = False

            def match_structs(old: AstNode, new: Struct) -> None:
                if (old, new) in checked:
                    return
                checked.add((old, new))
                nonlocal ok
                if not isinstance(old, Struct):
                    invalid_type(old, new)
                    return
                for (om, nm) in zip_longest(old.members, new.members):
                    if om is None:
                        assert nm is not None
                        error(documents, p.context, ct(nm.identifier), f"Added member")
                        error(
                            old_documents,
                            old_p.context,
                            ct(old.token),
                            "Was not here before",
                        )
                        ok = False
                        continue
                    if nm is None:
                        missing_member(om.identifier, new, ov(om.identifier))
                        continue
                    match_value(om, nm)

            def match_enums(old: AstNode, new: Enum) -> None:
                if (old, new) in checked:
                    return
                checked.add((old, new))
                if not isinstance(old, Enum):
                    invalid_type(old, new)
                    return
                for (om, nm) in zip_longest(old.members, new.members):
                    if om is None:
                        continue
                    if nm is None:
                        missing_member(om.identifier, new, ov(om.identifier))
                        continue
                    check_renamed(om.identifier, nm.identifier)

            def match_tables(old: AstNode, new: Table) -> None:
                if (old, new) in checked:
                    return
                checked.add((old, new))
                if not isinstance(old, Table):
                    invalid_type(old, new)
                    return
                if old.magic != new.magic:
                    # TODO warn about magic change
                    return
                for (om, nm) in zip_longest(old.members, new.members):
                    if om is None:
                        continue
                    if nm is None:
                        missing_member(om.identifier, new, ov(om.identifier))
                        continue
                    match_value(om, nm)

            def match_unions(old: AstNode, new: Union) -> None:
                if (old, new) in checked:
                    return
                checked.add((old, new))
                if not isinstance(old, Union):
                    invalid_type(old, new)
                    return
                for (om, nm) in zip_longest(old.members, new.members):
                    if om is None:
                        continue
                    if nm is None:
                        missing_member(om, new, ov(om.identifier))
                        continue
                    match_value(om, nm)

            old_global: dict[str, AstNode] = {}
            for node in old_ast:
                if isinstance(node, Struct):
                    assert node.name is not None
                    old_global[node.name] = node
                elif isinstance(node, Enum):
                    assert node.name is not None
                    old_global[node.name] = node
                elif isinstance(node, Table):
                    assert node.name is not None
                    old_global[node.name] = node
                elif isinstance(node, Union):
                    assert node.name is not None
                    old_global[node.name] = node
                elif isinstance(node, Namespace):
                    assert node.namespace is not None
                    old_global[node.namespace] = node
            for node in ast:
                if isinstance(node, Struct):
                    assert node.name is not None
                    old_node = old_global.get(node.name)
                    if old_node is None:
                        continue
                    match_structs(old_node, node)
                elif isinstance(node, Enum):
                    assert node.name is not None
                    old_node = old_global.get(node.name)
                    if old_node is None:
                        continue
                    match_enums(old_node, node)
                elif isinstance(node, Table):
                    assert node.name is not None
                    old_node = old_global.get(node.name)
                    if old_node is None:
                        continue
                    match_tables(old_node, node)
                elif isinstance(node, Union):
                    assert node.name is not None
                    old_node = old_global.get(node.name)
                    if old_node is None:
                        continue
                    match_unions(old_node, node)
                elif isinstance(node, Namespace):
                    pass
    except ParseError as err:
        err.describe(documents)
        pass
    return 1


def setup(subparsers) -> None:
    cmd = subparsers.add_parser("validate", help="Validate schema")
    cmd.add_argument("schema", help="schema to validate")
    cmd.add_argument("--strict", help="Be strict when parsing", action="store_true")
    cmd.add_argument("--old", help="old schema to validate for consistency against")
    addDocumentsParams(cmd)
    cmd.set_defaults(func=run)
