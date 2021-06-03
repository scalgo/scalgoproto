# -*- mode: python; tab-width: 4; indent-tabs-mode: t; python-indent-offset: 4; coding: utf-8 -*-
"""
Perform validation of the ast, and assign offsets and such
"""
import enum
import struct
import sys
from typing import Dict, List, Set, Optional, Tuple

from .documents import Documents
from .error import error
from .keywords import keywords
from .parser import (
    AstNode,
    Enum,
    Namespace,
    Struct,
    Table,
    Token,
    TokenType,
    Union,
    Value,
    ICE,
)
from .util import ucamel


class ContentType(enum.Enum):
    TABLE = 0
    STRUCT = 1
    UNION = 2


class Annotater:
    enums: Dict[str, Enum]
    structs: Dict[str, Struct]
    tables: Dict[str, Table]
    unions: Dict[str, Union]
    outer: Optional[AstNode]
    namespace: Dict[int, str]

    def __init__(self, documents: Documents) -> None:
        self.documents = documents
        self.errors = 0
        self.outer = None
        self.namespace = {}

    def attach_namespace(self, node: AstNode):
        node.namespace = self.namespace.get(node.document)

    def value(self, t: Token) -> str:
        return self.documents.by_id[t.document].content[t.index : t.index + t.length]

    def error(self, token: Optional[Token], message: str) -> None:
        assert token is not None
        self.errors += 1
        error(self.documents, self.context, token, message)

    def validate_uname(self, t: Token) -> str:
        name = self.value(t)
        if not name[0].isupper() or name.count("_") or not name.isidentifier():
            self.error(t, "Name must be CamelCase")
        if name in keywords:
            self.error(t, "Illegal name")
        if (
            name in self.enums
            or name in self.structs
            or name in self.tables
            or name in self.unions
        ):
            self.error(t, "Duplicate name")
        if name in self.enums:
            self.error(self.enums[name].identifier, "Previously defined here")
        if name in self.structs:
            self.error(self.structs[name].identifier, "Previously defined here")
        if name in self.tables:
            self.error(self.tables[name].identifier, "Previously defined here")
        if name in self.unions:
            self.error(self.unions[name].identifier, "Previously defined here")
        return name

    def validate_member_name(
        self,
        t: Token,
        name: str,
        seen: Dict[str, Token],
        has: bool = False,
        is_: bool = False,
        add: bool = False,
        get: bool = False,
    ) -> None:
        if t.type == TokenType.REMOVED:
            return
        if name[0].isupper() or name.count("_") or not name.isidentifier():
            self.error(t, "Name must be CamelCase")
        if name in keywords:
            self.error(t, "Illegal name '%s'" % name)
        hasName = "has%s%s" % (name[0].upper(), name[1:]) if has else None
        isName = "is%s%s" % (name[0].upper(), name[1:]) if is_ else None
        getName = "get%s%s" % (name[0].upper(), name[1:]) if has else None
        addName = "add%s%s" % (name[0].upper(), name[1:]) if is_ else None

        for n in [name, hasName, isName, getName, addName]:
            if n and n in seen:
                self.error(t, "Name conflict")
                self.error(seen[n], "Conflicts with this")
            seen[n] = t

    def get_int(self, value: Optional[Token], min: int, max: int, d: int) -> int:
        if value is None:
            return d
        try:
            v = int(self.value(value))
            if min <= v <= max:
                return v
            self.error(value, "Value %d outside allowed range %d to %d" % (v, min, max))
        except ValueError:
            self.error(value, "Must be an integer")
        return d

    def get_float(self, value: Optional[Token], d: float) -> float:
        if value is None:
            return d
        try:
            return float(self.value(value))
        except ValueError:
            self.error(value, "Must be a float")
        return d

    def create_doc_string(self, node: AstNode) -> None:
        if not node.doc_comment:
            return
        v = self.value(node.doc_comment)
        node.docstring = []
        for line in v.split("\n"):
            line = line.strip()
            if line[0:3] in ("/**", "///"):
                line = line[3:]
            elif line[0:2] in ("##", "*/", "//"):
                line = line[2:]
            elif line[0:1] in ("#", "*"):
                line = line[1:]
            if line[0:1] == " ":
                line = line[1:]
            if node.docstring or line:
                node.docstring.append(line)
        while node.docstring and not node.docstring[-1]:
            node.docstring.pop()
        if node.docstring and node.docstring[-1].endswith("*/"):
            node.docstring[-1] = node.docstring[-1][0:-2].strip()
        while node.docstring and not node.docstring[-1]:
            node.docstring.pop()

    def visit_enum(self, node: Enum):
        self.create_doc_string(node)
        enumValues: Dict[str, int] = {}
        index = 0
        for ev in node.members:
            self.create_doc_string(ev)
            vv = self.value(ev.identifier)
            if vv in enumValues:
                self.error(ev.identifier, "Duplicate name")
                continue
            enumValues[vv] = index
            index += 1
        if len(enumValues) > 254:
            self.error(node.identifier, "Too many enum values")
        node.annotatedValues = enumValues

    def assign_magic(self, node: Table, required: bool) -> None:
        if not node.id_:
            if required:
                self.error(node.token, "Magic required in none inline context")
        else:
            node.magic = int(self.value(node.id_)[1:], 16)
            if not 1 <= node.magic < 2 ** 32:
                self.error(node.id_, "Magic outside range")

    def visit_content(
        self, name: str, values: List[Value], t: ContentType, inplace_context: bool
    ) -> Tuple[bytes, List[Value]]:
        content: Dict[str, Token] = {}
        bytes = 0
        default = []
        bool_bit = 8
        bool_offset = 0
        inplace: Optional[Value] = None
        out_values: List[Value] = []
        for v in values:
            self.create_doc_string(v)
            removed = v.identifier.type == TokenType.REMOVED
            val = self.value(v.identifier)

            if not removed and v.direct_enum:
                v.direct_enum.name = name + ucamel(val)
                self.attach_namespace(v.direct_enum)
                self.visit_enum(v.direct_enum)

            if not removed and v.direct_table:
                v.direct_table.name = name + ucamel(val)
                self.attach_namespace(v.direct_table)
                ip = v.inplace != None if t == ContentType.TABLE else inplace_context
                self.assign_magic(v.direct_table, not ip)
                v.direct_table.default, v.direct_table.members = self.visit_content(
                    v.direct_table.name, v.direct_table.members, ContentType.TABLE, ip
                )
                v.direct_table.bytes = len(v.direct_table.default)
                v.direct_table.empty = len(v.direct_table.members) == 0

            if not removed and v.direct_union:
                v.direct_union.name = name + ucamel(val)
                self.attach_namespace(v.direct_union)
                self.visit_content(
                    v.direct_union.name,
                    v.direct_union.members,
                    ContentType.UNION,
                    v.inplace != None,
                )

            if not removed and v.direct_struct:
                v.direct_struct.name = name + ucamel(val)
                self.attach_namespace(v.direct_struct)
                default_bytes, _ = self.visit_content(
                    v.direct_struct.name,
                    v.direct_struct.members,
                    ContentType.STRUCT,
                    False,
                )
                v.direct_struct.bytes = len(default_bytes)

            self.validate_member_name(
                v.identifier,
                val,
                content,
                get=False,
                has=v.optional != None,
                add=v.list_ != None,
            )

            assert v.type_ is not None
            type_name = self.value(v.type_)

            if t == ContentType.STRUCT and v.optional:
                self.error(v.optional, "Not allowed in structs")
            if t == ContentType.UNION and v.optional:
                self.error(v.optional, "Not allowed in unions")

            if t == ContentType.STRUCT and v.inplace:
                self.error(v.inplace, "Not allowed in structs")
            if t == ContentType.UNION and v.inplace:
                self.error(v.inplace, "Not allowed in unions")
            if v.inplace and inplace:
                self.error(v.inplace, "More than one inplace element defined")
                self.error(inplace.inplace, "Previously defined here")
            if v.inplace:
                inplace = v

            if t == ContentType.STRUCT and v.direct:
                self.error(v.direct, "Not allowed in structs")

            if v.direct and not v.list_:
                self.error(v.direct, "Only lists can be direct")

            if (
                v.optional
                and v.type_.type
                in (
                    TokenType.U8,
                    TokenType.U16,
                    TokenType.UI32,
                    TokenType.UI64,
                    TokenType.I8,
                    TokenType.I16,
                    TokenType.I32,
                    TokenType.I64,
                    TokenType.BOOL,
                )
                and not v.list_
            ):
                if bool_bit == 8:
                    bool_bit = 0
                    bool_offset = bytes
                    default.append(b"\0")
                    bytes += 1
                v.has_offset = bool_offset
                v.has_bit = bool_bit
                bool_bit += 1

            typeName = self.value(v.type_)
            if v.list_:
                if v.direct_enum:
                    v.enum = v.direct_enum
                elif v.direct_table:
                    v.table = v.direct_table
                elif v.direct_union:
                    v.union = v.direct_union
                elif v.direct_struct:
                    v.struct = v.direct_struct
                elif v.type_.type == TokenType.IDENTIFIER:
                    typeName = self.value(v.type_)
                    assert self.outer is not None
                    if typeName in self.enums:
                        v.enum = self.enums[typeName]
                        self.outer.uses.add(v.enum)
                    elif typeName in self.tables:
                        v.table = self.tables[typeName]
                        self.outer.uses.add(v.table)
                    elif typeName in self.structs:
                        v.struct = self.structs[typeName]
                        self.outer.uses.add(v.struct)
                    elif typeName in self.unions:
                        v.union = self.unions[typeName]
                        self.outer.uses.add(v.union)
                    else:
                        self.error(v.type_, "Unknown type")

                if v.direct and not v.table:
                    self.error(v.direct, "Only table lists may be marked direct")

                if t == ContentType.STRUCT:
                    self.error(v.list_, "Not allowed in structs")
                if v.optional and t != ContentType.TABLE:
                    self.error(v.optional, "Only allowed in tables")
                default.append(b"\0\0\0\0\0\0")
                v.bytes = 6
                v.offset = bytes
            elif t == ContentType.UNION and v.type_.type in (
                TokenType.BOOL,
                TokenType.U8,
                TokenType.I8,
                TokenType.U8,
                TokenType.I8,
                TokenType.UI32,
                TokenType.I32,
                TokenType.F32,
                TokenType.UI64,
                TokenType.I64,
                TokenType.F64,
            ):
                self.error(v.type_, "Not allowed in unions")
                v.bytes = 0
                v.offset = bytes
            elif t == ContentType.TABLE and v.type_.type == TokenType.BOOL:
                if bool_bit == 8:
                    bool_bit = 0
                    bool_offset = bytes
                    default.append(b"\0")
                    bytes += 1
                v.offset = bool_offset
                v.bit = bool_bit
                bool_bit += 1
            elif v.type_.type in (TokenType.U8, TokenType.I8, TokenType.BOOL):
                if v.inplace:
                    self.error(v.inplace, "Basic types may not be inplace")
                if v.type_.type == TokenType.U8:
                    v.parsed_value = self.get_int(v.value, 0, 255, 0)
                    default.append(struct.pack("<B", v.parsed_value))
                elif v.type_.type == TokenType.I8:
                    v.parsed_value = self.get_int(v.value, -128, 127, 0)
                    default.append(struct.pack("<b", v.parsed_value))
                elif v.type_.type == TokenType.BOOL:
                    default.append(b"\0")
                else:
                    self.error(v.type_, "Internal error")
                v.bytes = 1
                v.offset = bytes
            elif v.type_.type in (TokenType.U16, TokenType.I16):
                if v.inplace:
                    self.error(v.inplace, "Basic types may not be inplace")
                if v.type_.type == TokenType.U16:
                    v.parsed_value = self.get_int(v.value, 0, 2 ** 16 - 1, 0)
                    default.append(struct.pack("<H", v.parsed_value))
                elif v.type_.type == TokenType.I16:
                    v.parsed_value = self.get_int(v.value, -2 ** 15, 2 ** 15 - 1, 0)
                    default.append(struct.pack("<h", v.parsed_value))
                else:
                    self.error(v.type_, "Internal error")
                v.bytes = 2
                v.offset = bytes
            elif v.type_.type in (TokenType.UI32, TokenType.I32, TokenType.F32):
                if v.inplace:
                    self.error(v.inplace, "Basic types may not be inplace")
                if v.type_.type == TokenType.UI32:
                    v.parsed_value = self.get_int(v.value, 0, 2 ** 32 - 1, 0)
                    default.append(struct.pack("<I", v.parsed_value))
                elif v.type_.type == TokenType.I32:
                    v.parsed_value = self.get_int(v.value, -2 ** 31, 2 ** 31 - 1, 0)
                    default.append(struct.pack("<i", v.parsed_value))
                elif v.type_.type == TokenType.F32:
                    v.parsed_value = self.get_float(
                        v.value, float("nan") if v.optional else 0.0
                    )
                    default.append(struct.pack("<f", v.parsed_value))
                else:
                    self.error(v.type_, "Internal error")
                v.bytes = 4
                v.offset = bytes
            elif v.type_.type in (TokenType.UI64, TokenType.I64, TokenType.F64):
                if v.inplace:
                    self.error(v.inplace, "Basic types may not be inplace")
                if v.type_.type == TokenType.UI64:
                    v.parsed_value = self.get_int(v.value, 0, 2 ** 64 - 1, 0)
                    default.append(struct.pack("<Q", v.parsed_value))
                elif v.type_.type == TokenType.I64:
                    v.parsed_value = self.get_int(v.value, -2 ** 64, 2 ** 64 - 1, 0)
                    default.append(struct.pack("<q", v.parsed_value))
                elif v.type_.type == TokenType.F64:
                    v.parsed_value = self.get_float(
                        v.value, float("nan") if v.optional else 0.0
                    )
                    default.append(struct.pack("<d", v.parsed_value))
                else:
                    self.error(v.type_, "Internal error")
                v.bytes = 8
                v.offset = bytes
            elif v.type_.type in (TokenType.BYTES, TokenType.TEXT):
                if v.optional and t != ContentType.TABLE:
                    self.error(v.optional, "Only allowed in tabels")
                if t == ContentType.STRUCT:
                    self.error(v.type_, "Not allowed in structs")
                default.append(b"\0\0\0\0\0\0")
                v.bytes = 6
                v.offset = bytes
            elif typeName in self.enums or v.direct_enum:
                if v.inplace:
                    self.error(v.inplace, "Enums types may not be inplace")
                if v.optional and t != ContentType.TABLE:
                    self.error(v.optional, "Only allowed in tabels")
                v.enum = v.direct_enum or self.enums[typeName]
                if not v.direct_enum:
                    assert self.outer is not None
                    self.outer.uses.add(v.enum)
                d = 255
                if v.value:
                    dn = self.value(v.value)
                    assert v.enum.annotatedValues is not None
                    if dn not in v.enum.annotatedValues:
                        self.error(v.value, "Not member of enum")
                    d = v.enum.annotatedValues[dn]
                v.parsed_value = d
                default.append(struct.pack("<B", d))
                v.bytes = 1
                v.offset = bytes
            elif typeName in self.structs or v.direct_struct:
                if v.inplace:
                    self.error(v.inplace, "Structs types may not be inplace")
                if v.optional:
                    if bool_bit == 8:
                        bool_bit = 0
                        bool_offset = bytes
                        default.append(b"\0")
                        bytes += 1
                    v.has_offset = bool_offset
                    v.has_bit = bool_bit
                    bool_bit += 1
                v.offset = bytes
                v.struct = v.direct_struct or self.structs[typeName]
                if not v.direct_struct:
                    assert self.outer is not None
                    self.outer.uses.add(v.struct)
                v.bytes = v.struct.bytes
                default.append(b"\0" * v.bytes)
            elif typeName in self.tables or v.direct_table:
                if t == ContentType.STRUCT:
                    self.error(v.type_, "tables not allowed in structs")
                if v.optional and t != ContentType.TABLE:
                    self.error(v.optional, "Only allowed in tables")
                default.append(b"\0\0\0\0\0\0")
                v.bytes = 6
                v.offset = bytes
                v.table = v.direct_table or self.tables[typeName]
                if not v.direct_table:
                    assert self.outer is not None
                    self.outer.uses.add(v.table)
            elif typeName in self.unions or v.direct_union:
                if t == ContentType.STRUCT:
                    self.error(v.type_, "Unions not allowed in structs")
                if v.optional and t != ContentType.TABLE:
                    self.error(v.optional, "Only allowed in tables")
                default.append(b"\0\0\0\0\0\0\0\0")
                v.bytes = 8
                v.offset = bytes
                v.union = v.direct_union or self.unions[typeName]
                if not v.direct_union:
                    assert self.outer is not None
                    self.outer.uses.add(v.union)
            else:
                self.error(v.type_, "Unknown identifier")
                v.bytes = 0
                v.offset = bytes

            if v.value:
                if t == ContentType.STRUCT:
                    self.error(v.value, "Not allowed in structs")
                elif t == ContentType.UNION:
                    self.error(v.value, "Not allowed in unions")
                elif v.optional:
                    self.error(v.value, "Not allowed for optionals")
                elif v.list_:
                    self.error(v.value, "Not allowed for lists")
                elif v.value.type in (TokenType.TRUE, TokenType.FALSE):
                    self.error(v.value, "Booleans cannot have default values")
                elif v.value.type == TokenType.NUMBER:
                    if v.type_.type not in (
                        TokenType.U8,
                        TokenType.U16,
                        TokenType.UI32,
                        TokenType.UI64,
                        TokenType.I8,
                        TokenType.I16,
                        TokenType.I32,
                        TokenType.I64,
                        TokenType.F32,
                        TokenType.F64,
                    ):
                        self.error(v.value, "Only allowed for number types")
                elif v.value.type == TokenType.IDENTIFIER:
                    if not v.enum:
                        self.error(v.value, "Only allowed for enumes")
                    elif (
                        v.enum.annotatedValues is None
                        or self.value(v.value) not in v.enum.annotatedValues
                    ):
                        self.error(v.value, "Not member of enum")
                        self.error(v.enum.token, "Enum declared here")
                else:
                    self.error(v.value, "Unhandled value")

            bytes += v.bytes
            if not removed:
                out_values.append(v)

        default2 = b"".join(default)
        if len(default2) != bytes:
            raise ICE()
        return (default2, out_values)

    def annotate(self, ast: List[AstNode]) -> None:
        self.enums = {}
        self.structs = {}
        self.tables = {}
        self.unions = {}
        for node in ast:
            self.context = "outer"
            self.create_doc_string(node)
            self.outer = node
            if isinstance(node, Struct):
                assert node.identifier is not None
                self.context = "struct %s" % self.value(node.identifier)
                name = self.validate_uname(node.identifier)
                node.name = name
                self.attach_namespace(node)
                default, node.members = self.visit_content(
                    name, node.members, ContentType.STRUCT, False
                )
                self.structs[name] = node
                node.bytes = len(default)
            elif isinstance(node, Enum):
                if node.removed:
                    continue
                assert node.identifier is not None
                self.context = "enum %s" % self.value(node.identifier)
                name = self.validate_uname(node.identifier)
                node.name = name
                self.attach_namespace(node)
                self.visit_enum(node)
                self.enums[name] = node
            elif isinstance(node, Table):
                assert node.identifier is not None
                self.context = "table %s" % self.value(node.identifier)
                name = self.validate_uname(node.identifier)
                node.name = name
                self.attach_namespace(node)
                self.assign_magic(node, True)
                node.default, node.members = self.visit_content(
                    name, node.members, ContentType.TABLE, False
                )
                node.bytes = len(node.default)
                node.empty = len(node.members) == 0

                self.tables[name] = node
            elif isinstance(node, Union):
                assert node.identifier is not None
                self.context = "union %s" % self.value(node.identifier)
                name = self.validate_uname(node.identifier)
                node.name = name
                self.attach_namespace(node)
                default, node.members = self.visit_content(
                    name, node.members, ContentType.UNION, False
                )
                self.unions[name] = node
            elif isinstance(node, Namespace):
                assert node.namespace is not None
                self.namespace[node.document] = node.namespace
            else:
                self.error(node.token, "Unknown thing")
                continue


def annotate(documents: Documents, ast: List[AstNode]) -> bool:
    a = Annotater(documents)
    a.annotate(ast)
    return a.errors == 0
