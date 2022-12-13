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


def ct(t: Token | None) -> Token:
    assert t is not None
    return t


def validate(
    schema: str,
    strict: bool,
    old_schema_path: str | None = None,
    old_schema_data: str | None = None,
) -> int:
    documents = Documents()
    documents.read_root(schema)
    p = Parser(documents)
    try:
        ast = p.parse_document(strict)
        checked: set[Tuple[AstNode, AstNode]] = set()
        if not annotate(documents, ast):
            return 1

        if old_schema_path is not None:
            try:
                old_documents = Documents()
                if old_schema_data:
                    old_documents.add_root(old_schema_path, old_schema_data)
                else:
                    old_documents.read_root(old_schema_path)
                old_p = Parser(old_documents)
                old_ast = old_p.parse_document()
                if not annotate(old_documents, old_ast):
                    print("Old schema is not valid")
                    return 1
            except ParseError as err:
                print("Old schema is not valid")
                err.describe(old_documents)
                return 1

            ok = True

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

            def check_members(
                old_token: Token,
                new_token: Token,
                old_members: list[Value],
                new_members: list[Value],
                allow_append: bool = True,
                check_types: bool = True,
            ) -> None:

                nonlocal ok

                # Matchup old and new names
                s1 = [ov(om.identifier) for om in old_members]
                s2 = [nv(nm.identifier) for nm in new_members]
                m: list[list[int]] = [[0 for _ in range(len(s2) + 1)]]
                for i1, v1 in enumerate(s1):
                    m.append([0])
                    for (i2, v2) in enumerate(s2):
                        m[i1 + 1].append(
                            m[i1][i2]
                            if v1 == v2
                            else min(m[i1 + 1][i2] + 1, m[i1][i2 + 1] + 1)
                        )
                i1 = len(s1)
                i2 = len(s2)
                matches: list[tuple[Value, Value]] = []
                mismatches: list[tuple[Value | None, Value | None]] = []
                while i1 != 0 and i2 != 0:
                    if s1[i1 - 1] == s2[i2 - 1]:
                        i1 -= 1
                        i2 -= 1
                        matches.append((old_members[i1], new_members[i2]))
                    elif m[i1 - 1][i2 - 1] + 2 == m[i1][i2]:
                        i1 -= 1
                        i2 -= 1
                        mismatches.append((old_members[i1], new_members[i2]))
                    elif m[i1 - 1][i2] + 1 == m[i1][i2]:
                        i1 -= 1
                        mismatches.append((old_members[i1], None))
                    elif m[i1][i2 - 1] + 1 == m[i1][i2]:
                        i2 -= 1
                        mismatches.append((None, new_members[i2]))
                    else:
                        assert False
                while i1 != 0:
                    i1 -= 1
                    mismatches.append((old_members[i1], None))
                while i2 != 0:
                    i2 -= 1
                    mismatches.append((None, new_members[i2]))
                mismatches.reverse()

                old_members_by_name = dict(
                    [(ov(om.identifier), om) for om in old_members]
                )
                new_members_by_name = dict(
                    [(nv(nm.identifier), nm) for nm in new_members]
                )
                new_members_indexes = dict(
                    [(nv(nm.identifier), i) for (i, nm) in enumerate(new_members)]
                )
                for (om, nm) in mismatches:
                    oname = ov(om.identifier) if om else None
                    nname = nv(nm.identifier) if nm else None
                    if (
                        om is not None
                        and nm is not None
                        and oname not in new_members_by_name
                        and nname not in old_members_by_name
                    ):
                        error(
                            documents,
                            p.context,
                            nm.identifier,
                            f"Member renamed {oname} to {nname}",
                            "Waring",
                        )
                        error(
                            old_documents,
                            old_p.context,
                            om.identifier,
                            "from",
                            "Warning",
                        )
                        if check_types:
                            match_value(om, nm)
                        continue
                    if om is not None:
                        assert oname is not None
                        if nnm := new_members_by_name.get(oname):
                            error(
                                documents,
                                p.context,
                                nnm.identifier,
                                f"Member {oname} moved",
                            )
                            error(
                                old_documents, old_p.context, om.identifier, "From here"
                            )
                            ok = False
                        else:
                            error(
                                documents,
                                p.context,
                                new_token,
                                f"Member {oname} removed",
                            )
                            error(
                                old_documents, old_p.context, om.identifier, "Was here"
                            )
                            ok = False
                    if nm is not None:
                        assert nname is not None
                        if oom := old_members_by_name.get(nname):
                            # We should already have errored about the move for the member in old_members
                            # error(documents, p.context, nm.identifier, f"Member {oname} moved")
                            # error(old_documents, old_p.context, oom.identifier, "From here")
                            ok = False
                        elif new_members_indexes[nname] >= len(old_members):
                            # We have added a new field
                            if not allow_append:
                                error(
                                    documents,
                                    p.context,
                                    nm.identifier,
                                    f"Member {nname} appended",
                                )
                                error(
                                    old_documents,
                                    old_p.context,
                                    old_token,
                                    "Was not here before",
                                )
                                ok = False
                        else:
                            error(
                                documents,
                                p.context,
                                nm.identifier,
                                f"Member {nname} inserted",
                            )
                            error(
                                old_documents,
                                old_p.context,
                                old_token,
                                "Was not here before",
                            )
                            ok = False

                if check_types:
                    for (om, nm) in matches:
                        match_value(om, nm)

            def match_structs(old: AstNode, new: Struct) -> None:
                if (old, new) in checked:
                    return
                checked.add((old, new))
                nonlocal ok
                if not isinstance(old, Struct):
                    invalid_type(old, new)
                    return
                check_members(
                    ct(old.identifier or old.token),
                    ct(new.identifier or new.token),
                    old.members,
                    new.members,
                    allow_append=False,
                )

            def match_enums(old: AstNode, new: Enum) -> None:
                if (old, new) in checked:
                    return
                checked.add((old, new))
                if not isinstance(old, Enum):
                    invalid_type(old, new)
                    return
                check_members(
                    ct(old.identifier or old.token),
                    ct(new.identifier or new.token),
                    old.members,
                    new.members,
                    check_types=False,
                )

            def match_tables(old: AstNode, new: Table) -> None:
                if (old, new) in checked:
                    return
                checked.add((old, new))
                if not isinstance(old, Table):
                    invalid_type(old, new)
                    return
                if old.magic != new.magic:
                    error(
                        documents,
                        p.context,
                        ct(new.identifier or new.token),
                        f"Magic changed is {new.magic:08X}",
                        "Warning",
                    )
                    error(
                        old_documents,
                        old_p.context,
                        ct(old.identifier or old.token),
                        f"Previously was {old.magic:08X}",
                        "Warning",
                    )
                    return
                check_members(
                    ct(old.identifier or old.token),
                    ct(new.identifier or new.token),
                    old.members,
                    new.members,
                )

            def match_unions(old: AstNode, new: Union) -> None:
                if (old, new) in checked:
                    return
                checked.add((old, new))
                if not isinstance(old, Union):
                    invalid_type(old, new)
                    return
                check_members(
                    ct(old.identifier or old.token),
                    ct(new.identifier or new.token),
                    old.members,
                    new.members,
                )

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
            if ok:
                return 0
        return 0
    except ParseError as err:
        err.describe(documents)
        pass
    return 1


def run(args) -> int:
    return validate(args.schema, args.strict, args.old)


def setup(subparsers) -> None:
    cmd = subparsers.add_parser("validate", help="Validate schema")
    cmd.add_argument("schema", help="schema to validate")
    cmd.add_argument("--strict", help="Be strict when parsing", action="store_true")
    cmd.add_argument("--old", help="old schema to validate for consistency against")
    addDocumentsParams(cmd)
    cmd.set_defaults(func=run)
