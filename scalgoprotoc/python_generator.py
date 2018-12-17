# -*- mode: python; tab-width: 4; indent-tabs-mode: t; python-indent-offset: 4; coding: utf-8 -*-
"""
Generate python reader/wirter
"""
import math
import typing
from types import SimpleNamespace
from typing import Dict, List, NamedTuple, Set, TextIO, Tuple

from .annotate import annotate
from .parser import (
    AstNode,
    Enum,
    Namespace,
    ParseError,
    Parser,
    Struct,
    Table,
    Union,
    Value,
    ICE,
)
from .sp_tokenize import Token, TokenType
from .util import cescape, snake, ucamel

TypeInfo = NamedTuple("TypeInfo", [("n", str), ("p", str), ("s", str), ("w", int)])

typeMap: Dict[TokenType, TypeInfo] = {
    TokenType.I8: TypeInfo("int8", "int", "b", 1),
    TokenType.I16: TypeInfo("int16", "int", "h", 2),
    TokenType.I32: TypeInfo("int32", "int", "i", 4),
    TokenType.I64: TypeInfo("int64", "int", "q", 8),
    TokenType.U8: TypeInfo("uint8", "int", "B", 1),
    TokenType.U16: TypeInfo("uint16", "int", "H", 2),
    TokenType.UI32: TypeInfo("uint32", "int", "I", 4),
    TokenType.UI64: TypeInfo("uint64", "int", "Q", 8),
    TokenType.F32: TypeInfo("float32", "float", "f", 4),
    TokenType.F64: TypeInfo("float64", "float", "d", 8),
    TokenType.BOOL: TypeInfo("bool", "bool", "?", 1),
}


class Generator:
    out: TextIO = None

    def __init__(self, data: str, out: TextIO) -> None:
        self.data = data
        self.out = out

    def out_list_type(self, node: Value) -> str:
        if node.type_.type == TokenType.BOOL:
            return "scalgoproto.BoolListOut"
        elif node.type_.type in typeMap:
            return "scalgoproto.BasicListOut[%s]" % (typeMap[node.type_.type].p)
        elif node.struct:
            return "scalgoproto.StructListOut[%s]" % (node.struct.name)
        elif node.enum:
            return "scalgoproto.EnumListOut[%s]" % (node.enum.name)
        elif node.table:
            return "scalgoproto.ObjectListOut[%sOut]" % (node.table.name)
        elif node.union:
            return "scalgoproto.UnionListOut[%sOut]" % (node.union.name)
        elif node.type_.type == TokenType.TEXT:
            return "scalgoproto.ObjectListOut[scalgoproto.TextOut]"
        elif node.type_.type == TokenType.BYTES:
            return "scalgoproto.ObjectListOut[scalgoproto.BytesOut]"
        else:
            raise ICE()

    def in_list_help(self, node: Value, os: str) -> Tuple[str, str]:
        if node.type_.type == TokenType.BOOL:
            return ("bool", "\t\treturn self._reader._get_bool_list(%s)" % (os))
        elif node.type_.type in (TokenType.F32, TokenType.F64):
            ti = typeMap[node.type_.type]
            return (
                ti.p,
                "\t\treturn self._reader._get_float_list('%s', %d, %s)"
                % (ti.s, ti.w, os),
            )
        elif node.type_.type in typeMap:
            ti = typeMap[node.type_.type]
            return (
                ti.p,
                "\t\treturn self._reader._get_int_list('%s', %d, %s)"
                % (ti.s, ti.w, os),
            )
        elif node.struct:
            return (
                node.struct.name,
                "\t\treturn self._reader._get_struct_list(%s, %s,)"
                % (node.struct.name, os),
            )
        elif node.enum:
            return (
                node.enum.name,
                "\t\treturn self._reader._get_enum_list(%s, %s)" % (node.enum.name, os),
            )
        elif node.table:
            return (
                node.table.name + "In",
                "\t\treturn self._reader._get_table_list(%sIn, %s)"
                % (node.table.name, os),
            )
        elif node.union:
            return (
                node.union.name + "In",
                "\t\treturn self._reader._get_union_list(%sIn, %s)"
                % (node.union.name, os),
            )
        elif node.type_.type == TokenType.TEXT:
            return ("str", "\t\treturn self._reader._get_text_list(%s)" % (os))
        elif node.type_.type == TokenType.BYTES:
            return ("bytes", "\t\treturn self._reader._get_bytes_list(%s)" % (os))
        else:
            raise ICE()

    def o(self, text="") -> None:
        print(text, file=self.out)

    def value(self, t: Token) -> str:
        return self.data[t.index : t.index + t.length]

    def output_doc(
        self,
        node: AstNode,
        indent: str = "",
        prefix: List[str] = [],
        suffix: List[str] = [],
    ) -> None:
        if not node.docstring and not suffix and not prefix:
            return
        self.o('%s"""' % indent)
        for line in prefix:
            self.o("%s%s" % (indent, line))
        if prefix and (node.docstring or suffix):
            self.o("%s" % indent)
        if node.docstring:
            for line in node.docstring:
                self.o("%s%s" % (indent, line))
        if node.docstring and suffix:
            self.o("%s" % indent)
        for line in suffix:
            self.o("%s%s" % (indent, line))
        self.o('%s"""' % indent)

    def generate_list_in(self, node: Value, uname: str) -> None:
        self.o("\t@property")
        self.o(
            "\tdef has_%s(self) -> bool: return self._get_uint32(%d, 0) != 0"
            % (uname, node.offset)
        )
        (tn, acc) = self.in_list_help(
            node,
            "*self._get_ptr%s(%d, scalgoproto.LIST_MAGIC)"
            % ("_inplace" if node.inplace else "", node.offset),
        )
        self.o("\t@property")
        self.o("\tdef %s(self) -> scalgoproto.ListIn[%s]:" % (uname, tn))
        self.output_doc(node, "\t\t")
        self.o("\t\tassert self.has_%s" % uname)
        self.o(acc)
        self.o("")

    def generate_union_list_in(self, node: Value, uname: str) -> None:
        (tn, acc) = self.in_list_help(node, "*self._get_ptr(scalgoproto.LIST_MAGIC)")
        self.o("\t@property")
        self.o("\tdef %s(self) -> scalgoproto.ListIn[%s]:" % (uname, tn))
        self.output_doc(node, "\t\t")
        self.o("\t\tassert self.is_%s" % (uname))
        self.o(acc)
        self.o("\t")

    def generate_inplace_list_constructor(self, node: Value) -> None:
        if node.type_.type in typeMap:
            ti = typeMap[node.type_.type]
            self.o(
                "\t\tl = scalgoproto.BasicListOut[%s](self._writer, '%s', %d, size, False)"
                % (ti.p, ti.s, ti.w)
            )
        elif node.enum:
            self.o(
                "\t\tl = scalgoproto.EnumListOut[%s](self._writer, %s, size, False)"
                % (node.enum.name, node.enum.name)
            )
        elif node.struct:
            self.o(
                "\t\tl = scalgoproto.StructListOut[%s](self._writer, %s, size, False)"
                % (node.struct.name, node.struct.name)
            )
        elif node.table:
            self.o(
                "\t\tl = scalgoproto.ObjectListOut[%sOut](self._writer, size, False)"
                % (node.table)
            )
        elif node.type_.type == TokenType.TEXT:
            self.o(
                "\t\tl = scalgoproto.ObjectListOut[TextOut](self._writer, size, False)"
            )
        elif node.type_.type == TokenType.BYTES:
            self.o(
                "\t\tl = scalgoproto.ObjectListOut[TextOut](self._writer, size, False)"
            )

    def generate_list_out(self, node: Value, uname: str) -> None:
        if not node.inplace:
            self.o("\t@scalgoproto.Adder")
            self.o("\tdef %s(self, value: %s):" % (uname, self.out_list_type(node)))
            self.output_doc(node, "\t\t")
            self.o("\t\tself._set_list(%d, value)" % (node.offset))
            self.o("\t")
        else:
            self.o(
                "\tdef add_%s(self, size: int) -> %s:"
                % (uname, self.out_list_type(node))
            )
            self.output_doc(node, "\t\t")
            self.generate_inplace_list_constructor(node)
            self.o("\t\tself._set_inplace_list(%d, size)" % (node.offset))
            self.o("\t\treturn l")
            self.o("\t")

    def generate_union_list_out(
        self, node: Value, uname: str, idx: int, inplace: bool
    ) -> None:
        if not inplace:
            self.o("\t@scalgoproto.Adder")
            self.o("\tdef %s(self, value: %s):" % (uname, self.out_list_type(node)))
            self.output_doc(node, "\t\t")
            self.o("\t\tself._set(%d, value._offset - 8)" % (idx))
            self.o("\t")
        else:
            self.o(
                "\tdef add_%s(self, size: int) -> %s:"
                % (uname, self.out_list_type(node))
            )
            self.output_doc(node, "\t\t")
            self.o("\t\tself._set(%d, size)" % (idx))
            self.generate_inplace_list_constructor(node)
            self.o("\t\treturn l")
            self.o("\t")

    def generate_bool_in(self, node: Value, uname: str) -> None:
        if node.inplace:
            raise ICE()
        if node.optional:
            self.o("\t@property")
            self.o(
                "\tdef has_%s(self) -> bool: return self._get_bit(%d, %s, 0)"
                % (uname, node.has_offset, node.has_bit)
            )
        self.o("\t@property")
        self.o("\tdef %s(self) -> bool:" % (uname))
        self.output_doc(node, "\t\t")
        if node.optional:
            self.o("\t\tassert self.has_%s" % uname)
        self.o("\t\treturn self._get_bit(%d, %s, 0)" % (node.offset, node.bit))
        self.o("\t")

    def generate_bool_out(self, node: Value, uname: str) -> None:
        if node.inplace:
            raise ICE()
        self.o("\t@scalgoproto.Adder")
        self.o("\tdef %s(self, value:bool) -> None:" % (uname))
        self.output_doc(node, "\t\t")
        if node.optional:
            self.o("\t\tself._set_bit(%d, %d)" % (node.has_offset, node.has_bit))
        self.o("\t\tif value: self._set_bit(%d, %d)" % (node.offset, node.bit))
        self.o("\t\telse: self._unset_bit(%d, %d)" % (node.offset, node.bit))
        self.o("\t")

    def generate_basic_in(self, node: Value, uname: str) -> None:
        if node.inplace:
            raise ICE()
        ti = typeMap[node.type_.type]
        if node.optional:
            self.o("\t@property")
            if node.type_.type in (TokenType.F32, TokenType.F64):
                self.o(
                    "\tdef has_%s(self) -> bool: return not math_.isnan(self._get_%s(%d, math_.nan))"
                    % (uname, ti.n, node.offset)
                )
            else:
                self.o(
                    "\tdef has_%s(self) -> bool: return self._get_bit(%d, %s, 0)"
                    % (uname, node.has_offset, node.has_bit)
                )
        self.o("\t@property")
        self.o("\tdef %s(self) -> %s:" % (uname, ti.p))
        self.output_doc(node, "\t\t")
        if node.optional:
            self.o("\t\tassert self.has_%s" % uname)
        self.o(
            "\t\treturn self._get_%s(%d, %s)"
            % (
                ti.n,
                node.offset,
                node.parsed_value if not math.isnan(node.parsed_value) else "math_.nan",
            )
        )
        self.o("\t")

    def generate_basic_out(self, node: Value, uname: str) -> None:
        if node.inplace:
            raise ICE()
        ti = typeMap[node.type_.type]
        self.o("\t@scalgoproto.Adder")
        self.o("\tdef %s(self, value: %s) -> None:" % (uname, ti.p))
        self.output_doc(node, "\t\t")
        if node.optional and node.type_.type not in (TokenType.F32, TokenType.F64):
            self.o("\t\tself._set_bit(%d, %d)" % (node.has_offset, node.has_bit))
        self.o("\t\tself._set_%s(%d, value)" % (ti.n, node.offset))
        self.o("\t")

    def generate_enum_in(self, node: Value, uname: str) -> None:
        if node.inplace:
            raise ICE()
        self.o("\t@property")
        self.o(
            "\tdef has_%s(self) -> bool: return self._get_uint8(%d, %d) != 255"
            % (uname, node.offset, node.parsed_value)
        )
        self.o("\t@property")
        self.o("\tdef %s(self) -> %s:" % (uname, node.enum.name))
        self.output_doc(node, "\t\t")
        self.o("\t\tassert self.has_%s" % uname)
        self.o(
            "\t\treturn %s(self._get_uint8(%d, %s))"
            % (node.enum.name, node.offset, node.parsed_value)
        )
        self.o("\t")

    def generate_enum_out(self, node: Value, uname: str) -> None:
        if node.inplace:
            raise ICE()
        self.o("\t@scalgoproto.Adder")
        self.o("\tdef %s(self, value: %s) -> None:" % (uname, node.enum.name))
        self.output_doc(node, "\t\t")
        self.o("\t\tself._set_uint8(%d, int(value))" % (node.offset))
        self.o("\t")

    def generate_struct_in(self, node: Value, uname: str) -> None:
        if node.inplace:
            raise ICE()
        if node.optional:
            self.o("\t@property")
            self.o(
                "\tdef has_%s(self) -> bool: return self._get_bit(%d, %s, 0)"
                % (uname, node.has_offset, node.has_bit)
            )
        self.o("\t@property")
        self.o("\tdef %s(self) -> %s:" % (uname, node.struct.name))
        self.output_doc(node, "\t\t")
        if node.optional:
            self.o("\t\tassert self.has_%s" % uname)
        self.o(
            "\t\treturn %s._read(self._reader, self._offset+%d) if %d < self._size else %s()"
            % (node.struct.name, node.offset, node.offset, node.struct.name)
        )
        self.o("\t")

    def generate_struct_out(self, node: Value, uname: str) -> None:
        if node.inplace:
            raise ICE()
        self.o("\t@scalgoproto.Adder")
        self.o("\tdef %s(self, value: %s) -> None:" % (uname, node.struct.name))
        self.output_doc(node, "\t\t")
        if node.optional:
            self.o("\t\tself._set_bit(%d, %d)" % (node.has_offset, node.has_bit))
        self.o(
            "\t\t%s._write(self._writer, self._offset + %d, value)"
            % (node.struct.name, node.offset)
        )
        self.o("\t")

    def generate_table_in(self, node: Value, uname: str) -> None:
        self.o("\t@property")
        self.o(
            "\tdef has_%s(self) -> bool: return self._get_uint32(%d, 0) != 0"
            % (uname, node.offset)
        )
        if not node.table.empty:
            self.o("\t@property")
            self.o("\tdef %s(self) -> %sIn:" % (uname, node.table.name))
            self.output_doc(node, "\t\t")
            self.o("\t\tassert self.has_%s" % uname)
            self.o(
                "\t\treturn %sIn(self._reader, *self._get_ptr%s(%d, %sIn._MAGIC))"
                % (
                    node.table.name,
                    "_inplace" if node.inplace else "",
                    node.offset,
                    node.table.name,
                )
            )
            self.o("\t")

    def generate_union_table_in(self, node: Value, uname: str) -> None:
        if not node.table.empty:
            self.o("\t@property")
            self.o("\tdef %s(self) -> %sIn:" % (uname, node.table.name))
            self.output_doc(node, "\t\t")
            self.o("\t\tassert self.is_%s" % (uname))
            self.o(
                "\t\treturn %sIn(self._reader, *self._get_ptr(%sIn._MAGIC))"
                % (node.table.name, node.table.name)
            )
            self.o("\t")

    def generate_table_out(self, node: Value, uname: str) -> None:
        if not node.inplace:
            self.o("\t@scalgoproto.Adder")
            self.o("\tdef %s(self, value: %sOut) -> None:" % (uname, node.table.name))
            self.output_doc(node, "\t\t")
            self.o("\t\tself._set_table(%d, value)" % (node.offset))
            self.o("\t")
        elif not node.table.empty:
            self.o("\tdef add_%s(self) -> %sOut:" % (uname, node.table.name))
            self.output_doc(node, "\t\t")
            self.o(
                "\t\tself._set_uint32(%d, %d)" % (node.offset, len(node.table.default))
            )
            self.o("\t\treturn %sOut(self._writer, False)" % node.table.name)
            self.o("\t")
        else:
            self.o("\tdef add_%s(self) -> None:" % (uname))
            self.output_doc(node, "\t\t")
            self.o("\t\tself._set_uint32(%d, %d)" % (node.offset, 0))
            self.o("\t")

    def generate_union_table_out(
        self, node: Value, uname: str, idx: int, inplace: bool
    ) -> None:
        table = node.table
        if table.empty:
            self.o("\tdef add_%s(self) -> None:" % (uname))
            self.output_doc(node, "\t\t")
            self.o("\t\tself._set(%d, 0)" % (idx))
            self.o("\t")
        elif not inplace:
            self.o("\t@scalgoproto.Adder")
            self.o("\tdef %s(self, value: %sOut) -> None:" % (uname, table.name))
            self.output_doc(node, "\t\t")
            self.o("\t\tself._set(%d, value._offset-8)" % (idx))
            self.o("\t")
        else:
            self.o("\tdef add_%s(self) -> %sOut:" % (uname, table.name))
            self.output_doc(node, "\t\t")
            self.o("\t\tassert self._end == self._writer._used")
            self.o("\t\tself._set(%d, %d)" % (idx, table.bytes))
            self.o("\t\treturn %sOut(self._writer, False)" % table.name)
            self.o("\t")

    def generate_text_in(self, node: Value, uname: str) -> None:
        self.o("\t@property")
        self.o(
            "\tdef has_%s(self) -> bool: return self._get_uint32(%d, 0) != 0"
            % (uname, node.offset)
        )
        self.o("\t@property")
        self.o("\tdef %s(self) -> str:" % (uname))
        self.output_doc(node, "\t\t")
        self.o("\t\tassert self.has_%s" % (uname))
        self.o(
            "\t\t(o, s) = self._get_ptr%s(%d, scalgoproto.TEXT_MAGIC)"
            % ("_inplace" if node.inplace else "", node.offset)
        )
        self.o("\t\treturn self._reader._data[o: o+s].decode('utf-8')")
        self.o("\t")

    def generate_union_text_in(self, node: Value, uname: str) -> None:
        self.o("\t@property")
        self.o("\tdef %s(self) -> str:" % (uname))
        self.output_doc(node, "\t\t")
        self.o("\t\tassert self.is_%s" % (uname))
        self.o("\t\t(o, s) = self._get_ptr(scalgoproto.TEXT_MAGIC)")
        self.o("\t\treturn self._reader._data[o: o+s].decode('utf-8')")
        self.o("\t")

    def generate_text_out(self, node: Value, uname: str) -> None:
        self.o("\t@scalgoproto.Adder")
        if node.inplace:
            self.o("\tdef %s(self, text:str) -> None:" % (uname))
        else:
            self.o("\tdef %s(self, t: scalgoproto.TextOut) -> None:" % (uname))
        self.output_doc(node, "\t\t")
        if node.inplace:
            self.o("\t\tself._add_inplace_text(%d, text)" % (node.offset))
        else:
            self.o("\t\tself._set_text(%d, t)" % (node.offset))
        self.o("\t")

    def generate_union_text_out(
        self, node: Value, uname: str, idx: int, inplace: bool
    ) -> None:
        self.o("\t@scalgoproto.Adder")
        if inplace:
            self.o("\tdef %s(self, value: str) -> None:" % (uname))
        else:
            self.o("\tdef %s(self, b: scalgoproto.TextOut) -> None:" % (uname))
        self.output_doc(node, "\t\t")
        if node.inplace:
            self.o("\t\tself._set(%d, len(value))" % (idx))
            self.o("\t\twriter._add_inplace_text(value)")
        else:
            self.o("\t\tself._set(%d, b._offset-8)" % (idx))
        self.o("\t")

    def generate_bytes_in(self, node: Value, uname: str) -> None:
        self.o("\t@property")
        self.o(
            "\tdef has_%s(self) -> bool: return self._get_uint32(%d, 0) != 0"
            % (uname, node.offset)
        )
        self.o("\t@property")
        self.o("\tdef %s(self) -> bytes:" % (uname))
        self.output_doc(node, "\t\t")
        self.o("\t\tassert self.has_%s" % (uname))
        self.o(
            "\t\t(o, s) = self._get_ptr%s(%d, scalgoproto.BYTES_MAGIC)"
            % ("_inplace" if node.inplace else "", node.offset)
        )
        self.o("\t\treturn self._reader._data[o: o+s]")
        self.o("\t")

    def generate_union_bytes_in(self, node: Value, uname: str) -> None:
        self.o("\t@property")
        self.o("\tdef %s(self) -> bytes:" % (uname))
        self.output_doc(node, "\t\t")
        self.o("\t\tassert self.is_%s" % (uname))
        self.o("\t\t(o, s) = self._get_ptr(scalgoproto.BYTES_MAGIC)")
        self.o("\t\treturn self._reader._data[o: o+s]")
        self.o("\t")

    def generate_bytes_out(self, node: Value, uname: str) -> None:
        self.o("\t@scalgoproto.Adder")
        if node.inplace:
            self.o("\tdef %s(self, value: bytes) -> None:" % (uname))
        else:
            self.o("\tdef %s(self, b: scalgoproto.BytesOut) -> None:" % (uname))
        self.output_doc(node, "\t\t")
        if node.inplace:
            self.o("\t\tself._add_inplace_bytes(%d, value)" % (node.offset))
        else:
            self.o("\t\tself._set_bytes(%d, b)" % (node.offset))
        self.o("\t")

    def generate_union_bytes_out(
        self, node: Value, uname: str, idx: int, inplace: bool
    ) -> None:
        self.o("\t@scalgoproto.Adder")
        if inplace:
            self.o("\tdef %s(self, value: bytes) -> None:" % (uname))
        else:
            self.o("\tdef %s(self, b: scalgoproto.BytesOut) -> None:" % (uname))
        self.output_doc(node, "\t\t")
        if node.inplace:
            self.o("\t\tself._set(%d, len(value))" % (idx))
            self.o("\t\twriter._add_inplace_bytes(value)")
        else:
            self.o("\t\tself._set(%d, b._offset-8)" % (idx))
        self.o("\t")

    def generate_union_in(self, node: Value, uname: str, table: Table) -> None:
        self.o("\t@property")
        self.o(
            "\tdef has_%s(self) -> bool: return self._get_uint16(%d, 0) != 0"
            % (uname, node.offset)
        )
        self.o("\t")
        self.o("\t@property")
        self.o("\tdef %s(self) -> %sIn:" % (uname, node.union.name))
        self.output_doc(node, "\t\t")
        self.o("\t\tassert self.has_%s" % (uname))
        if node.inplace:
            self.o(
                "\t\treturn %sIn(self._reader, self._get_uint16(%d, 0), self._offset + self._size, self._get_uint32(%d, 0))"
                % (node.union.name, node.offset, node.offset + 2)
            )
        else:
            self.o(
                "\t\treturn %sIn(self._reader, self._get_uint16(%d, 0), self._get_uint32(%d, 0))"
                % (node.union.name, node.offset, node.offset + 2)
            )
        self.o("\t")

    def generate_union_out(self, node: Value, uname: str, table: Table) -> None:
        self.o("\t@property")
        self.o(
            "\tdef %s(self) -> %s%sOut: return %s%sOut(self._writer, self._offset + %d, self._offset + %d)"
            % (
                uname,
                node.union.name,
                "Inplace" if node.inplace else "",
                node.union.name,
                "Inplace" if node.inplace else "",
                node.offset,
                table.bytes,
            )
        )

    def generate_value_in(self, table: Table, node: Value) -> None:
        uname = snake(self.value(node.identifier))
        if node.list_:
            self.generate_list_in(node, uname)
        elif node.type_.type == TokenType.BOOL:
            self.generate_bool_in(node, uname)
        elif node.type_.type in typeMap:
            self.generate_basic_in(node, uname)
        elif node.enum:
            self.generate_enum_in(node, uname)
        elif node.struct:
            self.generate_struct_in(node, uname)
        elif node.table:
            self.generate_table_in(node, uname)
        elif node.union:
            self.generate_union_in(node, uname, table)
        elif node.type_.type == TokenType.TEXT:
            self.generate_text_in(node, uname)
        elif node.type_.type == TokenType.BYTES:
            self.generate_bytes_in(node, uname)
        else:
            raise ICE()

    def generate_value_out(self, table: Table, node: Value) -> None:
        uname = snake(self.value(node.identifier))
        if node.list_:
            self.generate_list_out(node, uname)
        elif node.type_.type == TokenType.BOOL:
            self.generate_bool_out(node, uname)
        elif node.type_.type in typeMap:
            self.generate_basic_out(node, uname)
        elif node.enum:
            self.generate_enum_out(node, uname)
        elif node.struct:
            self.generate_struct_out(node, uname)
        elif node.table:
            self.generate_table_out(node, uname)
        elif node.union:
            self.generate_union_out(node, uname, table)
        elif node.type_.type == TokenType.TEXT:
            self.generate_text_out(node, uname)
        elif node.type_.type == TokenType.BYTES:
            self.generate_bytes_out(node, uname)
        else:
            raise ICE()

    def generate_union(self, union: Union) -> None:
        # Recursively generate direct contained members
        for value in union.members:
            if value.direct_table:
                self.generate_table(value.direct_table)
            if value.direct_union:
                self.generate_union(value.direct_union)
            if value.direct_enum:
                self.generate_enum(value.direct_enum)
            if value.direct_struct:
                self.generate_struct(value.direct_struct)

        self.o("class %sIn(scalgoproto.UnionIn):" % union.name)
        self.output_doc(union, "\t")
        self.o("\t__slots__ = []")
        self.o(
            "\tdef __init__(self, reader: scalgoproto.Reader, type:int, offset:int, size:int=None):"
        )
        self.o(
            '\t\t"""Private constructor. Call factory methods on scalgoproto.Reader to construct instances"""'
        )
        self.o("\t\tsuper().__init__(reader, type, offset, size)")
        self.o("\t")
        self.o("\tclass Type(enum.IntEnum):")
        self.o("\t\tNONE = 0")
        idx = 1
        for member in union.members:
            if not isinstance(member, (Table, Value)):
                raise ICE()
            self.o("\t\t%s = %d" % (self.value(member.identifier).upper(), idx))
            idx += 1
        self.o("\t")
        self.o("\t@property")
        self.o("\tdef type(self) -> Type:")
        self.output_doc(union, "\t")
        self.o("\t\treturn %sIn.Type(self._type)" % (union.name))
        self.o("\t")
        for member in union.members:
            n = self.value(member.identifier)
            uuname = snake(n)
            self.o("\t@property")
            self.o(
                "\tdef is_%s(self) -> bool: return self.type == %sIn.Type.%s"
                % (uuname, union.name, n.upper())
            )
            self.o("\t")
            if member.table:
                self.generate_union_table_in(member, uuname)
            elif member.list_:
                self.generate_union_list_in(member, uuname)
            elif member.type_.type == TokenType.BYTES:
                self.generate_union_bytes_in(member, uuname)
            elif member.type_.type == TokenType.TEXT:
                self.generate_union_text_in(member, uuname)
            else:
                raise ICE()
        self.o("")

        self.o("class %sOut(scalgoproto.UnionOut):" % union.name)
        self.o("\t__slots__ = []")
        self.o(
            "\tdef __init__(self, writer: scalgoproto.Writer, offset:int, end:int=0):"
        )
        self.o(
            '\t\t"""Private constructor. Call factory methods on scalgoproto.Writer to construct instances"""'
        )
        self.o("\t\tsuper().__init__(writer, offset, end)")
        self.o("\t")
        idx = 1
        for member in union.members:
            uuname = snake(self.value(member.identifier))
            if member.table:
                self.generate_union_table_out(member, uuname, idx, False)
            elif member.list_:
                self.generate_union_list_out(member, uuname, idx, False)
            elif member.type_.type == TokenType.BYTES:
                self.generate_union_bytes_out(member, uuname, idx, False)
            elif member.type_.type == TokenType.TEXT:
                self.generate_union_text_out(member, uuname, idx, False)
            else:
                raise ICE()
            idx += 1

        self.o("class %sInplaceOut(scalgoproto.UnionOut):" % union.name)
        self.o("\t__slots__ = []")
        self.o(
            "\tdef __init__(self, writer: scalgoproto.Writer, offset:int, end:int=0):"
        )
        self.o(
            '\t\t"""Private constructor. Call factory methods on scalgoproto.Writer to construct instances"""'
        )
        self.o("\t\tsuper().__init__(writer, offset, end)")
        self.o("\t")
        idx = 1
        for member in union.members:
            uuname = snake(self.value(member.identifier))
            if member.table:
                self.generate_union_table_out(member, uuname, idx, True)
            elif member.list_:
                self.generate_union_list_out(member, uuname, idx, True)
            elif member.type_.type == TokenType.BYTES:
                self.generate_union_bytes_out(member, uuname, idx, True)
            elif member.type_.type == TokenType.TEXT:
                self.generate_union_text_out(member, uuname, idx, True)
            else:
                raise ICE()
            idx += 1

    def generate_table(self, table: Table) -> None:
        # Recursively generate direct contained members
        for value in table.members:
            if value.direct_table:
                self.generate_table(value.direct_table)
            if value.direct_union:
                self.generate_union(value.direct_union)
            if value.direct_enum:
                self.generate_enum(value.direct_enum)
            if value.direct_struct:
                self.generate_struct(value.direct_struct)

        if table.empty:
            return

        # Generate table reader
        self.o("class %sIn(scalgoproto.TableIn):" % table.name)
        self.output_doc(table, "\t")
        self.o("\t__slots__ = []")
        self.o("\t_MAGIC:typing_.ClassVar[int]=0x%08X" % table.magic)
        self.o(
            "\tdef __init__(self, reader: scalgoproto.Reader, offset:int, size:int):"
        )
        self.o(
            '\t\t"""Private constructor. Call factory methods on scalgoproto.Reader to construct instances"""'
        )
        self.o("\t\tsuper().__init__(reader, offset, size)")
        for node in table.members:
            self.generate_value_in(table, node)
        self.o("")

        # Generate Table writer
        self.o("class %sOut(scalgoproto.TableOut):" % table.name)
        self.output_doc(table, "\t")
        self.o("\t__slots__ = []")
        self.o("\t_MAGIC:typing_.ClassVar[int]=0x%08X" % table.magic)
        self.o(
            "\tdef __init__(self, writer: scalgoproto.Writer, withHeader: bool) -> None:"
        )
        self.o(
            '\t\t"""Private constructor. Call factory methods on scalgoproto.Reader to construct instances"""'
        )
        self.o(
            '\t\tsuper().__init__(writer, withHeader, b"%s")' % (cescape(table.default))
        )
        for node in table.members:
            self.generate_value_out(table, node)
        self.o("")

    def generate_struct(self, node: Struct) -> None:
        # Recursively generate direct contained members
        for value in node.members:
            if value.direct_enum:
                self.generate_enum(value.direct_enum)
            if value.direct_struct:
                self.generate_struct(value.direct_struct)

        self.o("class %s(scalgoproto.StructType):" % node.name)
        init = []
        copy = []
        write = []
        read = []
        slots = []
        for v in node.members:
            thing = ("", "", "", 0, 0, "")
            n = snake(self.value(v.identifier))
            copy.append("self.%s = %s" % (n, n))
            slots.append("'%s'" % n)
            if v.type_.type in typeMap:
                ti = typeMap[v.type_.type]
                if v.type_.type in (TokenType.F32, TokenType.F64):
                    init.append("%s: %s = 0.0" % (n, ti.p))
                elif v.type_.type == TokenType.BOOL:
                    init.append("%s: %s = False" % (n, ti.p))
                else:
                    init.append("%s: %s = 0" % (n, ti.p))
                write.append(
                    "writer._data[offset+%d:offset+%d] = struct.pack('<%s', ins.%s)"
                    % (v.offset, v.offset + ti.w, ti.s, n)
                )
                read.append(
                    "struct.unpack('<%s', reader._data[offset+%d:offset+%d])[0]"
                    % (ti.s, v.offset, v.offset + ti.w)
                )
            elif v.enum:
                init.append("%s: %s = %s(0)" % (n, v.enum.name, v.enum.name))
                write.append("writer._data[offset+%d] = int(ins.%s)" % (v.offset, n))
                read.append("%s(reader._data[offset+%d])" % (v.enum.name, v.offset))
            elif v.struct:
                init.append("%s: %s = %s()" % (n, v.struct.name, v.struct.name))
                write.append(
                    "%s._write(writer, offset+%d, ins.%s)"
                    % (v.struct.name, v.offset, n)
                )
                read.append("%s._read(reader, offset+%d)" % (v.struct.name, v.offset))
            else:
                raise ICE()
        self.o("\t__slots__ = [%s]" % ",".join(slots))
        self.o("\t_WIDTH: typing_.ClassVar[int] = %d" % node.bytes)
        self.o("\tdef __init__(self, %s) -> None:" % (", ".join(init)))
        for line in copy:
            self.o("\t\t%s" % line)
        self.o("\t@staticmethod")
        self.o(
            "\tdef _write(writer: scalgoproto.Writer, offset:int, ins: '%s') -> None:"
            % node.name
        )
        for line in write:
            self.o("\t\t%s" % line)
        self.o("\t@staticmethod")
        self.o(
            "\tdef _read(reader: scalgoproto.Reader, offset:int) -> '%s':" % node.name
        )
        self.o("\t\treturn %s(" % node.name)
        for line in read:
            self.o("\t\t\t%s," % line)
        self.o("\t\t)")
        self.o()

    def generate_enum(self, node: Enum) -> None:
        self.o("class %s(enum.IntEnum):" % node.name)
        self.output_doc(node, "\t")
        index = 0
        for ev in node.members:
            self.o("\t%s = %d" % (self.value(ev.identifier), index))
            index += 1
        self.o()

    def generate(self, ast: List[AstNode]) -> None:
        for node in ast:
            if isinstance(node, Struct):
                self.generate_struct(node)
            elif isinstance(node, Enum):
                self.generate_enum(node)
            elif isinstance(node, Table):
                self.generate_table(node)
            elif isinstance(node, Union):
                self.generate_union(node)
            elif isinstance(node, Namespace):
                pass
            else:
                raise ICE()


def run(args) -> int:
    data = open(args.schema, "r").read()
    p = Parser(data)
    out = open(args.output, "w")
    try:
        ast = p.parse_document()
        if not annotate(data, ast):
            print("Schema is invalid")
            return 1
        g = Generator(data, out)
        print(
            "# -*- mode: python; tab-width: 4; indent-tabs-mode: t; python-indent-offset: 4; coding: utf-8 -*-",
            file=out,
        )
        print("# THIS FILE IS GENERATED DO NOT EDIT", file=out)
        print("import scalgoproto, enum, struct", file=out)
        print("import math as math_", file=out)
        print("import typing as typing_", file=out)
        g.generate(ast)
        return 0
    except ParseError as err:
        err.describe(data)
    return 1


def setup(subparsers) -> None:
    cmd = subparsers.add_parser("py", help="Generate python code")
    cmd.add_argument("schema", help="schema to generate things from")
    cmd.add_argument("output", help="where do we store the output")
    cmd.set_defaults(func=run)
