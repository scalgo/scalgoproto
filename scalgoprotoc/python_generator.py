# -*- mode: python; tab-width: 4; indent-tabs-mode: nil; python-indent-offset: 4; coding: utf-8 -*-
"""
Generate python reader/wirter
"""
import math
import typing
import os
from types import SimpleNamespace
from typing import Dict, List, NamedTuple, Set, TextIO, Tuple
from .documents import Documents, addDocumentsParams

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
    def __init__(self, documents: Documents, out: TextIO, import_prefix: str) -> None:
        self.documents: Documents = documents
        self.out: TextIo = out
        if import_prefix and import_prefix[-1] != ".":
            import_prefix += "."
        self.import_prefix: str = import_prefix

    def out_list_type(self, node: Value) -> str:
        if node.type_.type == TokenType.BOOL:
            return "scalgoproto.BoolListOut"
        elif node.type_.type in typeMap:
            return "scalgoproto.BasicListOut[%s]" % (typeMap[node.type_.type].p)
        elif node.struct:
            return "scalgoproto.StructListOut[%s]" % (node.struct.name)
        elif node.enum:
            return "scalgoproto.EnumListOut[%s]" % (node.enum.name)
        elif node.table and node.direct:
            return "scalgoproto.DirectTableListOut[%sOut]" % (node.table.name)
        elif node.table:
            return "scalgoproto.TableListOut[%sOut]" % (node.table.name)
        elif node.union:
            return "scalgoproto.UnionListOut[%sOut]" % (node.union.name)
        elif node.type_.type == TokenType.TEXT:
            return "scalgoproto.TextListOut"
        elif node.type_.type == TokenType.BYTES:
            return "scalgoproto.BytesListOut"
        else:
            raise ICE()

    def out_list_constructor(self, node: Value) -> str:
        if node.type_.type == TokenType.BOOL:
            return "construct_bool_list(size)"
        elif node.type_.type in typeMap:
            return "construct_%s_list(size)" % (typeMap[node.type_.type].n)
        elif node.struct:
            return "construct_struct_list(%s, size)" % (node.struct.name)
        elif node.enum:
            return "construct_enum_list(%s, size)" % (node.enum.name)
        elif node.table and node.direct:
            return "construct_direct_table_list(%sOut, size)" % (node.table.name)
        elif node.table:
            return "construct_table_list(%sOut, size)" % (node.table.name)
        elif node.union:
            return "construct_union_list(%sOut, size)" % (node.union.name)
        elif node.type_.type == TokenType.TEXT:
            return "construct_text_list(size)"
        elif node.type_.type == TokenType.BYTES:
            return "construct_bytes_list(size)"
        else:
            raise ICE()

    def in_list_help(self, node: Value, os: str) -> Tuple[str, str]:
        if node.type_.type == TokenType.BOOL:
            return ("bool", "        return self._reader._get_bool_list(%s)" % (os))
        elif node.type_.type in (TokenType.F32, TokenType.F64):
            ti = typeMap[node.type_.type]
            return (
                ti.p,
                "        return self._reader._get_float_list('%s', %d, %s)"
                % (ti.s, ti.w, os),
            )
        elif node.type_.type in typeMap:
            ti = typeMap[node.type_.type]
            return (
                ti.p,
                "        return self._reader._get_int_list('%s', %d, %s)"
                % (ti.s, ti.w, os),
            )
        elif node.struct:
            return (
                node.struct.name,
                "        return self._reader._get_struct_list(%s, %s,)"
                % (node.struct.name, os),
            )
        elif node.enum:
            return (
                node.enum.name,
                "        return self._reader._get_enum_list(%s, %s)"
                % (node.enum.name, os),
            )
        elif node.table:
            return (
                node.table.name + "In",
                f"        return self._reader._get_table_list({node.table.name}In, {os}, direct={'True' if node.direct else 'False'})",
            )
        elif node.union:
            return (
                node.union.name + "In",
                "        return self._reader._get_union_list(%sIn, %s)"
                % (node.union.name, os),
            )
        elif node.type_.type == TokenType.TEXT:
            return ("str", "        return self._reader._get_text_list(%s)" % (os))
        elif node.type_.type == TokenType.BYTES:
            return ("bytes", "        return self._reader._get_bytes_list(%s)" % (os))
        else:
            raise ICE()

    def o(self, text="") -> None:
        print(text, file=self.out)

    def value(self, t: Token) -> str:
        return self.documents.by_id[t.document].content[t.index : t.index + t.length]

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
        self.o("    @property")
        self.o("    def has_%s(self) -> bool:" % (uname,))
        self.o("        return self._get_uint48(%d) != 0" % (node.offset,))
        (tn, acc) = self.in_list_help(
            node,
            f"*self._get_ptr{'_inplace' if node.inplace else ''}({node.offset}, scalgoproto.{'DIRECT_' if node.direct else ''}LIST_MAGIC)",
        )
        self.o()
        self.o("    @property")
        self.o("    def %s(self) -> scalgoproto.ListIn[%s]:" % (uname, tn))
        self.output_doc(node, "        ")
        self.o("        if not self.has_%s:" % uname)
        self.o("            return []")
        self.o(acc)
        self.o()

    def generate_union_list_in(self, node: Value, uname: str) -> None:
        (tn, acc) = self.in_list_help(
            node,
            f"*self._get_ptr(scalgoproto.{'DIRECT_' if node.direct else ''}LIST_MAGIC)",
        )
        self.o("    @property")
        self.o("    def %s(self) -> scalgoproto.ListIn[%s]:" % (uname, tn))
        self.output_doc(node, "        ")
        self.o("        assert self.is_%s" % (uname))
        self.o(acc)
        self.o()

    def generate_inplace_list_constructor(self, node: Value) -> None:
        if node.type_.type in typeMap:
            ti = typeMap[node.type_.type]
            self.o(
                "        l = scalgoproto.BasicListOut[%s](self._writer, '%s', %d, size, False)"
                % (ti.p, ti.s, ti.w)
            )
        elif node.enum:
            self.o(
                "        l = scalgoproto.EnumListOut[%s](self._writer, %s, size, False)"
                % (node.enum.name, node.enum.name)
            )
        elif node.struct:
            self.o(
                "        l = scalgoproto.StructListOut[%s](self._writer, %s, size, False)"
                % (node.struct.name, node.struct.name)
            )
        elif node.table and node.direct:
            self.o(
                "        l = scalgoproto.DirectTableListOut[%sOut](self._writer, %sOut, size, False)"
                % (node.table.name, node.table.name)
            )
        elif node.table:
            self.o(
                "        l = scalgoproto.TableListOut[%sOut](self._writer, %sOut, size, False)"
                % (node.table.name, node.table.name)
            )
        elif node.type_.type == TokenType.TEXT:
            self.o("        l = scalgoproto.TextListOut(self._writer, size, False)")
        elif node.type_.type == TokenType.BYTES:
            self.o("        l = scalgoproto.BytesListOut(self._writer, size, False)")

    def generate_list_out(self, node: Value, uname: str) -> None:
        it = "scalgoproto.ListIn[%s]" % self.in_list_help(node, "")[0]
        ot = self.out_list_type(node)
        if not node.inplace:
            self.o("    @scalgoproto.Adder")
            self.o(
                "    def %s(self, value: typing_.Union[%s,%s]) -> None:"
                % (uname, it, ot)
            )
            self.output_doc(node, "        ")
            self.o("        if isinstance(value, scalgoproto.ListIn):")
            self.o("            self.add_%s(len(value))._copy(value)" % (uname))
            self.o("            return")
            self.o("        assert isinstance(value, scalgoproto.OutList)")
            self.o("        self._set_list(%d, value)" % (node.offset))
            self.o()

            self.o(
                "    def add_%s(self, size:int) -> %s:"
                % (uname, self.out_list_type(node))
            )
            self.output_doc(node, "        ")
            self.o("        res = self._writer.%s" % self.out_list_constructor(node))
            self.o("        self._set_list(%d, res)" % (node.offset))
            self.o("        return res")
            self.o()
        else:
            self.o("    @scalgoproto.Adder")
            self.o("    def %s(self, value: %s) -> None:" % (uname, it))
            self.output_doc(node, "        ")
            self.o("        assert isinstance(value, scalgoproto.ListIn)")
            self.o("        add_%s(len(value))._copy(value)" % (uname))
            self.o()

            self.o(
                "    def add_%s(self, size: int) -> %s:"
                % (uname, self.out_list_type(node))
            )
            self.output_doc(node, "        ")
            self.o("        assert self._writer._used == self._offset + self._SIZE")
            self.generate_inplace_list_constructor(node)
            self.o("        self._set_inplace_list(%d, size)" % (node.offset))
            self.o("        return l")
            self.o()

    def generate_union_list_out(
        self, node: Value, uname: str, idx: int, inplace: bool
    ) -> None:
        it = "scalgoproto.ListIn[%s]" % self.in_list_help(node, "")[0]
        ot = self.out_list_type(node)
        if not inplace:
            self.o("    @scalgoproto.Adder")
            self.o("    def %s(self, value: typing_.Union[%s,%s]):" % (uname, ot, it))
            self.output_doc(node, "        ")
            self.o("        if isinstance(value, scalgoproto.ListIn):")
            self.o("            self.add_%s(len(value))._copy(value)" % (uname))
            self.o("            return")
            self.o("        assert isinstance(value, scalgoproto.OutList)")
            self.o("        self._set(%d, value._offset - 10)" % (idx,))
            self.o()

            self.o(
                "    def add_%s(self, size:int) -> %s:"
                % (uname, self.out_list_type(node))
            )
            self.output_doc(node, "        ")
            self.o("        res = self._writer.%s" % self.out_list_constructor(node))
            self.o("        self._set(%d, res._offset - 10)" % (idx,))
            self.o("        return res")
            self.o()
        else:
            self.o("    @scalgoproto.Adder")
            self.o("    def %s(self, value: %s) -> None:" % (uname, it))
            self.output_doc(node, "        ")
            self.o("        assert isinstance(value, scalgoproto.ListIn)")
            self.o("        add_%s(len(value))._copy(value)" % (uname))
            self.o()
            self.o(
                "    def add_%s(self, size: int) -> %s:"
                % (uname, self.out_list_type(node))
            )
            self.output_doc(node, "        ")
            self.o("        self._set(%d, size)" % (idx,))
            self.generate_inplace_list_constructor(node)
            self.o("        return l")
            self.o()

    def generate_bool_in(self, node: Value, uname: str) -> None:
        if node.inplace:
            raise ICE()
        if node.optional:
            self.o("    @property")
            self.o("    def has_%s(self) -> bool:" % (uname,))
            self.o(
                "        return self._get_bit(%d, %s, 0)"
                % (node.has_offset, node.has_bit)
            )
            self.o()
        self.o("    @property")
        self.o("    def %s(self) -> bool:" % (uname,))
        self.output_doc(node, "        ")
        if node.optional:
            self.o("        assert self.has_%s" % uname)
        self.o("        return self._get_bit(%d, %s, 0)" % (node.offset, node.bit))
        self.o()

    def generate_bool_out(self, node: Value, uname: str) -> None:
        if node.inplace:
            raise ICE()
        self.o("    @scalgoproto.Adder")
        self.o("    def %s(self, value: bool) -> None:" % (uname,))
        self.output_doc(node, "        ")
        if node.optional:
            self.o("        self._set_bit(%d, %d)" % (node.has_offset, node.has_bit))
        self.o("        if value:")
        self.o("            self._set_bit(%d, %d)" % (node.offset, node.bit))
        self.o("        else:")
        self.o("            self._unset_bit(%d, %d)" % (node.offset, node.bit))
        self.o()

    def generate_basic_in(self, node: Value, uname: str) -> None:
        if node.inplace:
            raise ICE()
        ti = typeMap[node.type_.type]
        if node.optional:
            self.o("    @property")
            self.o("    def has_%s(self) -> bool:" % (uname,))
            if node.type_.type in (TokenType.F32, TokenType.F64):
                self.o(
                    "        return not math_.isnan(self._get_%s(%d, math_.nan))"
                    % (ti.n, node.offset)
                )
            else:
                self.o(
                    "        return self._get_bit(%d, %s, 0)"
                    % (node.has_offset, node.has_bit)
                )
            self.o()
        self.o("    @property")
        self.o("    def %s(self) -> %s:" % (uname, ti.p))
        self.output_doc(node, "        ")
        if node.optional:
            self.o("        assert self.has_%s" % uname)
        self.o(
            "        return self._get_%s(%d, %s)"
            % (
                ti.n,
                node.offset,
                node.parsed_value if not math.isnan(node.parsed_value) else "math_.nan",
            )
        )
        self.o()

    def generate_basic_out(self, node: Value, uname: str) -> None:
        if node.inplace:
            raise ICE()
        ti = typeMap[node.type_.type]
        self.o("    @scalgoproto.Adder")
        self.o("    def %s(self, value: %s) -> None:" % (uname, ti.p))
        self.output_doc(node, "        ")
        if node.optional and node.type_.type not in (TokenType.F32, TokenType.F64):
            self.o("        self._set_bit(%d, %d)" % (node.has_offset, node.has_bit))
        self.o("        self._set_%s(%d, value)" % (ti.n, node.offset))
        self.o()

    def generate_enum_in(self, node: Value, uname: str) -> None:
        if node.inplace:
            raise ICE()
        self.o("    @property")
        self.o("    def has_%s(self) -> bool:" % (uname,))
        self.o(
            "        return self._get_uint8(%d, %d) != 255"
            % (node.offset, node.parsed_value)
        )
        self.o()
        self.o("    @property")
        self.o("    def %s(self) -> %s:" % (uname, node.enum.name))
        self.output_doc(node, "        ")
        self.o("        assert self.has_%s" % uname)
        self.o(
            "        return %s(self._get_uint8(%d, %s))"
            % (node.enum.name, node.offset, node.parsed_value)
        )
        self.o()

    def generate_enum_out(self, node: Value, uname: str) -> None:
        if node.inplace:
            raise ICE()
        self.o("    @scalgoproto.Adder")
        self.o("    def %s(self, value: %s) -> None:" % (uname, node.enum.name))
        self.output_doc(node, "        ")
        self.o("        self._set_uint8(%d, int(value))" % (node.offset))
        self.o()

    def generate_struct_in(self, node: Value, uname: str) -> None:
        if node.inplace:
            raise ICE()
        if node.optional:
            self.o("    @property")
            self.o("    def has_%s(self) -> bool:" % (uname,))
            self.o(
                "        return self._get_bit(%d, %s, 0)"
                % (node.has_offset, node.has_bit)
            )
            self.o()
        self.o("    @property")
        self.o("    def %s(self) -> %s:" % (uname, node.struct.name))
        self.output_doc(node, "        ")
        if node.optional:
            self.o("        assert self.has_%s" % uname)
        self.o(
            "        return %s._read(self._reader, self._offset+%d) if %d < self._size else %s()"
            % (node.struct.name, node.offset, node.offset, node.struct.name)
        )
        self.o()

    def generate_struct_out(self, node: Value, uname: str) -> None:
        if node.inplace:
            raise ICE()
        self.o("    @scalgoproto.Adder")
        self.o("    def %s(self, value: %s) -> None:" % (uname, node.struct.name))
        self.output_doc(node, "        ")
        if node.optional:
            self.o("        self._set_bit(%d, %d)" % (node.has_offset, node.has_bit))
        self.o(
            "        %s._write(self._writer, self._offset + %d, value)"
            % (node.struct.name, node.offset)
        )
        self.o()

    def generate_table_in(self, node: Value, uname: str) -> None:
        self.o("    @property")
        self.o("    def has_%s(self) -> bool:" % (uname,))
        self.o("        return self._get_uint48(%d) != 0" % (node.offset))
        self.o()
        if not node.table.empty:
            self.o("    @property")
            self.o("    def %s(self) -> %sIn:" % (uname, node.table.name))
            self.output_doc(node, "        ")
            self.o("        assert self.has_%s" % uname)
            self.o(
                "        return %sIn(self._reader, *self._get_ptr%s(%d, %sIn._MAGIC))"
                % (
                    node.table.name,
                    "_inplace" if node.inplace else "",
                    node.offset,
                    node.table.name,
                )
            )
            self.o()

    def generate_union_table_in(self, node: Value, uname: str) -> None:
        if not node.table.empty:
            self.o("    @property")
            self.o("    def %s(self) -> %sIn:" % (uname, node.table.name))
            self.output_doc(node, "        ")
            self.o("        assert self.is_%s" % (uname))
            self.o(
                "        return %sIn(self._reader, *self._get_ptr(%sIn._MAGIC))"
                % (node.table.name, node.table.name)
            )
            self.o()

    def generate_table_out(self, node: Value, uname: str) -> None:
        if not node.inplace:
            self.o("    @scalgoproto.Adder")
            self.o(
                "    def %s(self, value: typing_.Union[%sOut, %sIn]) -> None:"
                % (uname, node.table.name, node.table.name)
            )
            self.output_doc(node, "        ")
            self.o("        if isinstance(value, %sIn):" % (node.table.name))
            self.o("            v = value")
            self.o(
                "            value = self._writer.construct_table(%sOut)"
                % node.table.name
            )
            self.o("            value._copy(v)")
            self.o("        assert isinstance(value, %sOut)" % (node.table.name))
            self.o("        self._set_table(%d, value)" % (node.offset))
            self.o()
            self.o("    def add_%s(self) -> %sOut:" % (uname, node.table.name))
            self.output_doc(node, "        ")
            self.o(
                "        res = self._writer.construct_table(%sOut)" % node.table.name
            )
            self.o("        self._set_table(%d, res)" % (node.offset,))
            self.o("        return res")
            self.o()

        elif not node.table.empty:
            self.o("    @scalgoproto.Adder")
            self.o("    def %s(self, value: %sIn) -> None:" % (uname, node.table.name))
            self.output_doc(node, "        ")
            self.o("        assert isinstance(value, %sIn)" % (node.table.name))
            self.o("        self.add_%s()._copy(value)" % (uname,))
            self.o()
            self.o("    def add_%s(self) -> %sOut:" % (uname, node.table.name))
            self.output_doc(node, "        ")
            self.o("        assert self._writer._used == self._offset + self._SIZE")
            self.o(
                "        self._set_uint48(%d, %d)"
                % (node.offset, len(node.table.default))
            )
            self.o("        return %sOut(self._writer, False)" % node.table.name)
            self.o()
        else:
            self.o("    def add_%s(self) -> None:" % (uname))
            self.output_doc(node, "        ")
            self.o("        self._set_uint48(%d, %d)" % (node.offset, 0))
            self.o()

    def generate_union_table_out(
        self, node: Value, uname: str, idx: int, inplace: bool
    ) -> None:
        table = node.table
        if table.empty:
            self.o("    def add_%s(self) -> None:" % (uname))
            self.output_doc(node, "        ")
            self.o("        self._set(%d, 0)" % (idx))
            self.o()
        elif not inplace:
            self.o("    @scalgoproto.Adder")
            self.o(
                "    def %s(self, value: typing_.Union[%sOut,%sIn]) -> None:"
                % (uname, table.name, table.name)
            )
            self.output_doc(node, "        ")
            self.o("        if isinstance(value, %sIn):" % (node.table.name))
            self.o("            v = value")
            self.o(
                "            value = self._writer.construct_table(%sOut)"
                % node.table.name
            )
            self.o("            value._copy(v)")
            self.o("        assert isinstance(value, %sOut)" % (node.table.name))
            self.o("        self._set(%d, value._offset - 10)" % (idx))
            self.o()
            self.o("    def add_%s(self) -> %sOut:" % (uname, table.name))
            self.output_doc(node, "        ")
            self.o(
                "        res = self._writer.construct_table(%sOut)" % node.table.name
            )
            self.o("        self._set(%d, res._offset - 10)" % (idx,))
            self.o("        return res")
            self.o()
        else:
            self.o("    @scalgoproto.Adder")
            self.o("    def %s(self, value: %sIn) -> None:" % (uname, node.table.name))
            self.output_doc(node, "        ")
            self.o("        assert isinstance(value, %sIn)" % (node.table.name))
            self.o("        self.add_%s()._copy(value)" % (uname,))
            self.o()
            self.o("    def add_%s(self) -> %sOut:" % (uname, table.name))
            self.output_doc(node, "        ")
            self.o("        assert self._end == self._writer._used")
            self.o("        self._set(%d, %d)" % (idx, table.bytes))
            self.o("        return %sOut(self._writer, False)" % table.name)
            self.o()

    def generate_text_in(self, node: Value, uname: str) -> None:
        self.o("    @property")
        self.o("    def has_%s(self) -> bool:" % (uname,))
        self.o("        return self._get_uint48(%d) != 0" % (node.offset,))
        self.o()
        self.o("    @property")
        self.o("    def %s(self) -> str:" % (uname))
        self.output_doc(node, "        ")
        self.o("        assert self.has_%s" % (uname))
        self.o(
            "        (o, s) = self._get_ptr%s(%d, scalgoproto.TEXT_MAGIC)"
            % ("_inplace" if node.inplace else "", node.offset)
        )
        self.o('        return self._reader._data[o : o + s].decode("utf-8")')
        self.o()

    def generate_union_text_in(self, node: Value, uname: str) -> None:
        self.o("    @property")
        self.o("    def %s(self) -> str:" % (uname))
        self.output_doc(node, "        ")
        self.o("        assert self.is_%s" % (uname))
        self.o("        (o, s) = self._get_ptr(scalgoproto.TEXT_MAGIC)")
        self.o('        return self._reader._data[o : o + s].decode("utf-8")')
        self.o()

    def generate_text_out(self, node: Value, uname: str) -> None:
        self.o("    @scalgoproto.Adder")
        if node.inplace:
            self.o("    def %s(self, text: str) -> None:" % (uname))
        else:
            self.o(
                "    def %s(self, t: typing_.Union[scalgoproto.TextOut, str]) -> None:"
                % (uname)
            )
        self.output_doc(node, "        ")
        if node.inplace:
            self.o("        assert self._writer._used == self._offset + self._SIZE")
            self.o("        self._add_inplace_text(%d, text)" % (node.offset))
        else:
            self.o("        self._set_text(%d, t)" % (node.offset))
        self.o()

    def generate_union_text_out(
        self, node: Value, uname: str, idx: int, inplace: bool
    ) -> None:
        self.o("    @scalgoproto.Adder")
        if inplace:
            self.o("    def %s(self, value: str) -> None:" % (uname))
        else:
            self.o(
                "    def %s(self, value: typing_.Union[scalgoproto.TextOut, str]) -> None:"
                % (uname)
            )
        self.output_doc(node, "        ")
        if inplace:
            self.o("        self._add_inplace_text(%d, value)" % (idx))
        else:
            self.o("        self._set_text(%d, value)" % (idx))
        self.o()

    def generate_bytes_in(self, node: Value, uname: str) -> None:
        self.o("    @property")
        self.o("    def has_%s(self) -> bool:" % (uname,))
        self.o("        return self._get_uint48(%d) != 0" % (node.offset,))
        self.o()
        self.o("    @property")
        self.o("    def %s(self) -> bytes:" % (uname))
        self.output_doc(node, "        ")
        self.o("        assert self.has_%s" % (uname))
        self.o(
            "        (o, s) = self._get_ptr%s(%d, scalgoproto.BYTES_MAGIC)"
            % ("_inplace" if node.inplace else "", node.offset)
        )
        self.o("        return self._reader._data[o : o + s]")
        self.o()

    def generate_union_bytes_in(self, node: Value, uname: str) -> None:
        self.o("    @property")
        self.o("    def %s(self) -> bytes:" % (uname))
        self.output_doc(node, "        ")
        self.o("        assert self.is_%s" % (uname))
        self.o("        (o, s) = self._get_ptr(scalgoproto.BYTES_MAGIC)")
        self.o("        return self._reader._data[o : o + s]")
        self.o()

    def generate_bytes_out(self, node: Value, uname: str) -> None:
        self.o("    @scalgoproto.Adder")
        if node.inplace:
            self.o("    def %s(self, value: bytes) -> None:" % (uname))
        else:
            self.o(
                "    def %s(self, value: typing_.Union[scalgoproto.BytesOut, bytes]) -> None:"
                % (uname)
            )
        self.output_doc(node, "        ")
        if node.inplace:
            self.o("        assert self._writer._used == self._offset + self._SIZE")
            self.o("        self._add_inplace_bytes(%d, value)" % (node.offset))
        else:
            self.o("        self._set_bytes(%d, value)" % (node.offset))
        self.o()

    def generate_union_bytes_out(
        self, node: Value, uname: str, idx: int, inplace: bool
    ) -> None:
        self.o("    @scalgoproto.Adder")
        if inplace:
            self.o("    def %s(self, value: bytes) -> None:" % (uname))
        else:
            self.o(
                "    def %s(self, value: typing_.Union[scalgoproto.BytesOut, bytes]) -> None:"
                % (uname)
            )
        self.output_doc(node, "        ")
        if inplace:
            self.o("        self._add_inplace_bytes(%d, value)" % (idx))
        else:
            self.o("        self._set_bytes(%d, value)" % (idx))
        self.o()

    def generate_union_in(self, node: Value, uname: str, table: Table) -> None:
        self.o("    @property")
        self.o("    def has_%s(self) -> bool:" % (uname,))
        self.o("        return self._get_uint16(%d, 0) != 0" % (node.offset,))
        self.o()
        self.o("    @property")
        self.o("    def %s(self) -> %sIn:" % (uname, node.union.name))
        self.output_doc(node, "        ")
        self.o("        assert self.has_%s" % (uname))
        if node.inplace:
            self.o(
                "        return %sIn(self._reader, self._get_uint16(%d, 0), self._offset + self._size, self._get_uint48(%d))"
                % (node.union.name, node.offset, node.offset + 2)
            )
        else:
            self.o(
                "        return %sIn(self._reader, self._get_uint16(%d, 0), self._get_uint48(%d))"
                % (node.union.name, node.offset, node.offset + 2)
            )
        self.o()

    def generate_union_out(self, node: Value, uname: str, table: Table) -> None:
        self.o("    @property")
        self.o(
            "    def %s(self) -> %s%sOut:"
            % (uname, node.union.name, "Inplace" if node.inplace else "")
        )
        self.o(
            "        return %s%sOut(self._writer, self._offset + %d, self._offset + %d)"
            % (
                node.union.name,
                "Inplace" if node.inplace else "",
                node.offset,
                table.bytes,
            )
        )
        self.o()

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

    def generate_union_copy(self, union: Union) -> None:
        self.o("    def _copy(self, i:%sIn) -> None:" % union.name)
        self.o("        if False:")
        self.o("            pass")
        for node in union.members:
            uuname = snake(self.value(node.identifier))
            self.o("        elif i.is_%s:" % uuname)
            if node.list_:
                self.o(
                    "            self.add_%s(len(i.%s))._copy(i.%s)"
                    % (uuname, uuname, uuname)
                )
            elif (
                node.type_.type == TokenType.TEXT or node.type_.type == TokenType.BYTES
            ):
                self.o("            self.add_%s(i.%s)" % (uuname, uuname))
            elif node.table:
                if node.table.empty:
                    self.o("            self.add_%s()" % (uuname))
                else:
                    self.o("            self.add_%s()._copy(i.%s)" % (uuname, uuname))
            else:
                raise ICE()
        self.o()

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
        self.output_doc(union, "    ")
        self.o("    __slots__ = []")
        self.o("    _MEMBERS = [")
        for node in union.members:
            self.o('        "%s",' % snake(self.value(node.identifier)))
        self.o("    ]")
        self.o()
        self.o(
            "    def __init__(self, reader: scalgoproto.Reader, type: int, offset: int, size: int = None) -> None:"
        )
        self.o(
            '        """Private constructor. Call factory methods on scalgoproto.Reader to construct instances"""'
        )
        self.o("        super().__init__(reader, type, offset, size)")
        self.o()
        self.o("    class Type(enum.IntEnum):")
        self.o("        NONE = 0")
        idx = 1
        for member in union.members:
            if not isinstance(member, (Table, Value)):
                raise ICE()
            self.o("        %s = %d" % (self.value(member.identifier).upper(), idx))
            idx += 1
        self.o()
        self.o("    @property")
        self.o("    def type(self) -> Type:")
        self.output_doc(union, "    ")
        self.o("        return %sIn.Type(self._type)" % (union.name))
        self.o()
        for member in union.members:
            n = self.value(member.identifier)
            uuname = snake(n)
            self.o("    @property")
            self.o("    def is_%s(self) -> bool:" % (uuname,))
            self.o("        return self.type == %sIn.Type.%s" % (union.name, n.upper()))
            self.o()
            if member.list_:
                self.generate_union_list_in(member, uuname)
            elif member.table:
                self.generate_union_table_in(member, uuname)
            elif member.type_.type == TokenType.BYTES:
                self.generate_union_bytes_in(member, uuname)
            elif member.type_.type == TokenType.TEXT:
                self.generate_union_text_in(member, uuname)
            else:
                raise ICE()
        self.o()

        self.o("class %sOut(scalgoproto.UnionOut):" % union.name)
        self.o("    __slots__ = []")
        self.o()
        self.o(
            "    def __init__(self, writer: scalgoproto.Writer, offset: int, end: int = 0) -> None:"
        )
        self.o(
            '        """Private constructor. Call factory methods on scalgoproto.Writer to construct instances"""'
        )
        self.o("        super().__init__(writer, offset, end)")
        self.o()
        idx = 1
        for member in union.members:
            uuname = snake(self.value(member.identifier))
            if member.list_:
                self.generate_union_list_out(member, uuname, idx, False)
            elif member.table:
                self.generate_union_table_out(member, uuname, idx, False)
            elif member.type_.type == TokenType.BYTES:
                self.generate_union_bytes_out(member, uuname, idx, False)
            elif member.type_.type == TokenType.TEXT:
                self.generate_union_text_out(member, uuname, idx, False)
            else:
                raise ICE()
            idx += 1
        self.generate_union_copy(union)
        self.o()

        self.o("class %sInplaceOut(scalgoproto.UnionOut):" % union.name)
        self.o("    __slots__ = []")
        self.o()
        self.o(
            "    def __init__(self, writer: scalgoproto.Writer, offset: int, end: int = 0) -> None:"
        )
        self.o(
            '        """Private constructor. Call factory methods on scalgoproto.Writer to construct instances"""'
        )
        self.o("        super().__init__(writer, offset, end)")
        self.o()
        idx = 1
        for member in union.members:
            uuname = snake(self.value(member.identifier))
            if member.list_:
                self.generate_union_list_out(member, uuname, idx, True)
            elif member.table:
                self.generate_union_table_out(member, uuname, idx, True)
            elif member.type_.type == TokenType.BYTES:
                self.generate_union_bytes_out(member, uuname, idx, True)
            elif member.type_.type == TokenType.TEXT:
                self.generate_union_text_out(member, uuname, idx, True)
            else:
                raise ICE()
            idx += 1
        self.generate_union_copy(union)
        self.o()

    def generate_table_copy(self, table: Table) -> None:
        self.o("    def _copy(self, i:%sIn) -> None:" % table.name)
        for ip in (True, False):
            for node in table.members:
                uname = snake(self.value(node.identifier))
                if bool(node.inplace) != ip:
                    continue
                if node.list_:
                    self.o("        if i.has_%s:" % uname)
                    self.o(
                        "            self.add_%s(len(i.%s))._copy(i.%s)"
                        % (uname, uname, uname)
                    )
                elif (
                    node.type_.type in typeMap
                    or node.type_.type == TokenType.BOOL
                    or node.enum
                    or node.struct
                    or node.type_.type == TokenType.TEXT
                    or node.type_.type == TokenType.BYTES
                ):
                    if (
                        node.optional
                        or node.enum
                        or node.type_.type == TokenType.TEXT
                        or node.type_.type == TokenType.BYTES
                    ):
                        self.o("        if i.has_%s:" % uname)
                        self.o("            self.%s = i.%s" % (uname, uname))
                    else:
                        self.o("        self.%s = i.%s" % (uname, uname))
                elif node.table:
                    self.o("        if i.has_%s:" % (uname))
                    if node.table.empty:
                        self.o("            self.add_%s()")
                    else:
                        self.o("            self.add_%s()._copy(i.%s)" % (uname, uname))
                elif node.union:
                    self.o("        if i.has_%s:" % (uname))
                    self.o("            self.%s._copy(i.%s)" % (uname, uname))
                else:
                    raise ICE()
        self.o()

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
        self.output_doc(table, "    ")
        self.o("    __slots__ = []")
        self.o("    _MAGIC: typing_.ClassVar[int] = 0x%08X" % table.magic)
        self.o("    _MEMBERS = [")
        for node in table.members:
            self.o('        "%s",' % snake(self.value(node.identifier)))
        self.o("    ]")
        self.o()

        for node in table.members:
            self.generate_value_in(table, node)
        self.o()

        # Generate Table writer
        self.o("class %sOut(scalgoproto.TableOut):" % table.name)
        self.output_doc(table, "    ")
        self.o("    __slots__ = []")
        self.o("    _MAGIC: typing_.ClassVar[int] = 0x%08X" % table.magic)
        self.o("    _SIZE: typing_.ClassVar[int] = %d" % len(table.default))
        self.o('    _DEFAULT: typing_.ClassVar[bytes] = b"%s"' % cescape(table.default))
        self.o("    _IN = %sIn" % (table.name))
        self.o()

        for node in table.members:
            self.generate_value_out(table, node)
        self.generate_table_copy(table)
        self.o()

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
            slots.append('"%s"' % n)
            if v.type_.type in typeMap:
                ti = typeMap[v.type_.type]
                if v.type_.type in (TokenType.F32, TokenType.F64):
                    init.append("%s: %s = 0.0" % (n, ti.p))
                elif v.type_.type == TokenType.BOOL:
                    init.append("%s: %s = False" % (n, ti.p))
                else:
                    init.append("%s: %s = 0" % (n, ti.p))
                write.append(
                    'writer._data[offset + %d : offset + %d] = struct.pack("<%s", ins.%s)'
                    % (v.offset, v.offset + ti.w, ti.s, n)
                )
                read.append(
                    'struct.unpack("<%s", reader._data[offset + %d : offset + %d])[0]'
                    % (ti.s, v.offset, v.offset + ti.w)
                )
            elif v.enum:
                init.append("%s: %s = %s(0)" % (n, v.enum.name, v.enum.name))
                write.append("writer._data[offset + %d] = int(ins.%s)" % (v.offset, n))
                read.append("%s(reader._data[offset + %d])" % (v.enum.name, v.offset))
            elif v.struct:
                init.append("%s: %s = %s()" % (n, v.struct.name, v.struct.name))
                write.append(
                    "%s._write(writer, offset + %d, ins.%s)"
                    % (v.struct.name, v.offset, n)
                )
                read.append("%s._read(reader, offset + %d)" % (v.struct.name, v.offset))
            else:
                raise ICE()
        self.o("    __slots__ = [%s]" % ", ".join(slots))
        self.o("    _WIDTH: typing_.ClassVar[int] = %d" % node.bytes)
        self.o()
        self.o("    def __init__(self, %s) -> None:" % (", ".join(init)))
        for line in copy:
            self.o("        %s" % line)
        self.o()
        self.o("    @staticmethod")
        self.o(
            '    def _write(writer: scalgoproto.Writer, offset: int, ins: "%s") -> None:'
            % node.name
        )
        for line in write:
            self.o("        %s" % line)
        self.o()
        self.o("    @staticmethod")
        self.o(
            '    def _read(reader: scalgoproto.Reader, offset: int) -> "%s":'
            % node.name
        )
        self.o("        return %s(" % node.name)
        for line in read:
            self.o("            %s," % line)
        self.o("        )")
        self.o()
        self.o()

    def generate_enum(self, node: Enum) -> None:
        self.o("class %s(enum.IntEnum):" % node.name)
        self.output_doc(node, "   ")
        index = 0
        for ev in node.members:
            self.o("    %s = %d" % (self.value(ev.identifier), index))
            index += 1
        self.o()
        self.o()

    def generate(self, ast: List[AstNode]) -> None:
        imports: Dict[int, Set[str]] = {}
        for node in ast:
            if node.document != 0:
                continue
            for u in node.uses:
                if u.document == 0:
                    continue
                if not u.document in imports:
                    imports[u.document] = set()
                i = imports[u.document]
                if isinstance(u, Struct):
                    i.add(u.name)
                elif isinstance(u, Enum):
                    i.add(u.name)
                elif isinstance(u, Table):
                    i.add("%sIn" % u.name)
                    i.add("%sOut" % u.name)
                elif isinstance(u, Union):
                    i.add("%sIn" % u.name)
                    i.add("%sOut" % u.name)
                else:
                    raise ICE()

        for (d, imp) in imports.items():
            doc = self.documents.by_id[d]
            self.o(
                "from %s%s import %s" % (self.import_prefix, doc.name, ", ".join(imp))
            )

        for node in ast:
            if node.document != 0:
                continue
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
    documents = Documents()
    documents.read_root(args.schema)
    p = Parser(documents)
    out = open(os.path.join(args.output, "%s.py" % documents.root.name), "w")
    try:
        ast = p.parse_document()
        if not annotate(documents, ast):
            print("Schema is invalid")
            return 1
        g = Generator(documents, out, args.import_prefix)
        print(
            "# -*- mode: python; tab-width: 4; indent-tabs-mode: nil; python-indent-offset: 4; coding: utf-8 -*-",
            file=out,
        )
        print("# THIS FILE IS GENERATED DO NOT EDIT", file=out)
        print("import scalgoproto, enum, struct", file=out)
        print("import math as math_", file=out)
        print("import typing as typing_", file=out)

        g.generate(ast)
        return 0
    except ParseError as err:
        err.describe(documents)
    return 1


def setup(subparsers) -> None:
    cmd = subparsers.add_parser("py", help="Generate python code")
    cmd.add_argument("schema", help="schema to generate things from")
    cmd.add_argument("output", help="where do we store the output")
    cmd.add_argument(
        "--import-prefix", help="Prefix to put infront of imports", default=""
    )
    cmd.set_defaults(func=run)
