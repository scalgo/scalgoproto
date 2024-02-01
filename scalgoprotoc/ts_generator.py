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
from .util import cescape, ucamel, lcamel

TypeInfo = NamedTuple("TypeInfo", [("n", str), ("p", str)])

typeMap: Dict[TokenType, TypeInfo] = {
    TokenType.I8: TypeInfo("Int8", "number"),
    TokenType.I16: TypeInfo("Int16", "number"),
    TokenType.I32: TypeInfo("Int32", "number"),
    TokenType.I64: TypeInfo("Int64", "number"),
    TokenType.U8: TypeInfo("Uint8", "number"),
    TokenType.U16: TypeInfo("Uint16", "number"),
    TokenType.UI32: TypeInfo("Uint32", "number"),
    TokenType.UI64: TypeInfo("Uint64", "number"),
    TokenType.F32: TypeInfo("Float32", "number"),
    TokenType.F64: TypeInfo("Float64", "number"),
    TokenType.BOOL: TypeInfo("Bool", "boolean"),
}


class Generator:
    def __init__(self, documents: Documents, out: TextIO, import_prefix: str) -> None:
        self.documents: Documents = documents
        self.out: TextIO = out
        if import_prefix and import_prefix[-1] != ".":
            import_prefix += "."
        self.import_prefix: str = import_prefix

    def out_list_type(self, node: Value) -> str:
        if node.type_.type == TokenType.BOOL:
            return "scalgoproto.ListOut<boolean>"
        elif node.type_.type in typeMap:
            return "scalgoproto.ListOut<number>"
        elif node.struct:
            return "scalgoproto.ListOut<%s>" % (node.struct.name)
        elif node.enum:
            return "scalgoproto.ListOut<%s, %s | null>" % (
                node.enum.name,
                node.enum.name,
            )
        elif node.table:
            return "scalgoproto.ListOut<%sOut, %sIn | null>" % (
                node.table.name,
                node.table.name,
            )
        elif node.union:
            return "scalgoproto.ListOut<%sOut, %sIn>" % (
                node.union.name,
                node.union.name,
            )
        elif node.type_.type == TokenType.TEXT:
            return "scalgoproto.ListOut<string | scalgoproto.TextOut, string | null>"
        elif node.type_.type == TokenType.BYTES:
            return "scalgoproto.ListOut<ArrayBuffer | scalgoproto.BytesOut, ArrayBuffer | null>"
        else:
            raise ICE()

    def out_list_constructor(self, node: Value, inplace: bool = False) -> str:
        x = ", true" if inplace else ""
        if node.type_.type == TokenType.BOOL:
            return "constructBoolList(size%s)" % x
        elif node.type_.type in typeMap:
            return "construct%sList(size%s)" % (typeMap[node.type_.type].n, x)
        elif node.struct:
            return "constructStructList<%s>(%s, size%s)" % (
                node.struct.name,
                node.struct.name,
                x,
            )
        elif node.enum:
            return "constructEnumList<%s>(size%s)" % (node.enum.name, x)
        elif node.table:
            return "constructTableList<%sOut>(%sOut, size%s)" % (
                node.table.name,
                node.table.name,
                x,
            )
        elif node.union:
            return "constructUnionList<%sOut>(%sOut, size%s)" % (
                node.union.name,
                node.union.name,
                x,
            )
        elif node.type_.type == TokenType.TEXT:
            return "constructTextList(size%s)" % (x)
        elif node.type_.type == TokenType.BYTES:
            return "constructBytesList(size%s)" % (x)
        else:
            raise ICE()

    def in_list_help(self, node: Value, os: str) -> Tuple[str, str]:
        if node.type_.type == TokenType.BOOL:
            return ("boolean", "\t\treturn this._reader._getBoolList(%s)" % (os))
        elif node.type_.type in typeMap:
            ti = typeMap[node.type_.type]
            return (ti.p, "\t\treturn this._reader._get%sList(%s)" % (ti.n, os))
        elif node.struct:
            return (
                node.struct.name,
                "\t\treturn this._reader._getStructList(%s, %s)"
                % (os, node.struct.name),
            )
        elif node.enum:
            return (
                node.enum.name + " | null",
                "\t\treturn this._reader._getEnumList<%s>(%s)" % (node.enum.name, os),
            )
        elif node.table:
            return (
                node.table.name + "In | null",
                "\t\treturn this._reader._getTableList(%s, %sIn)"
                % (os, node.table.name),
            )
        elif node.union:
            return (
                node.union.name + "In",
                "\t\treturn this._reader._getUnionList(%s, %sIn)"
                % (os, node.union.name),
            )
        elif node.type_.type == TokenType.TEXT:
            return ("string | null", "\t\treturn this._reader._getTextList(%s)" % (os,))
        elif node.type_.type == TokenType.BYTES:
            return (
                "ArrayBuffer | null",
                "\t\treturn this._reader._getBytesList(%s)" % (os,),
            )
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
    ):
        if not node.docstring and not suffix and not prefix:
            return
        self.o("%s/**" % indent)
        for line in prefix:
            self.o("%s * %s" % (indent, line))
        if prefix and (node.docstring or suffix):
            self.o("%s *" % indent)
        if node.docstring:
            for line in node.docstring:
                self.o("%s * %s" % (indent, line))
        if node.docstring and suffix:
            self.o("%s *" % indent)
        for line in suffix:
            self.o("%s * %s" % (indent, line))
        self.o("%s */" % indent)

    def generate_list_in(self, node: Value, lname: str) -> None:
        (tn, acc) = self.in_list_help(node, "o, s")

        self.output_doc(node, "\t")
        self.o("\tget %s() : scalgoproto.ListIn<%s> | null {" % (lname, tn))
        self.o(
            "\t\tconst [o, s] = this._getPtr%s(%d, scalgoproto.LIST_MAGIC)"
            % ("Inplace" if node.inplace else "", node.offset)
        )
        self.o("\t\tif (o === 0) return null;")
        self.o(acc)
        self.o("\t}")
        self.o()

    def generate_union_list_in(self, node: Value, lname: str) -> None:
        (tn, acc) = self.in_list_help(node, "o, s")
        self.output_doc(node, "\t")
        self.o("\tget %s() : scalgoproto.ListIn<%s> | null {" % (lname, tn))
        self.o("\t\tif (!this.is%s) return null;" % (ucamel(lname)))
        self.o("\t\tconst [o, s] = this._getPtr(scalgoproto.LIST_MAGIC)")
        self.o("\t\tif (o === 0) return null;")
        self.o(acc)
        self.o("\t}")
        self.o()

    def generate_list_out(self, node: Value, lname: str, size: int) -> None:
        it = "scalgoproto.ListIn<%s>" % self.in_list_help(node, "")[0]
        ot = self.out_list_type(node)
        if not node.inplace:
            self.output_doc(node, "\t")
            self.o("\tset %s(value: %s | %s) {" % (lname, it, ot))
            self.o("\t\tif (value instanceof scalgoproto.ListIn) {")
            self.o("\t\t\tthis.add%s(value.length)._copy(value);" % (ucamel(lname)))
            self.o("\t\t\treturn;")
            self.o("\t\t}")
            self.o("\t\tconsole.assert(value instanceof scalgoproto.ListOut);")
            self.o("\t\tthis._setList(%d, value);" % (node.offset))
            self.o("\t}")
            self.o()

            self.output_doc(node, "\t")
            self.o(
                "\tadd%s(size:number) : %s {"
                % (ucamel(lname), self.out_list_type(node))
            )
            self.o("\t\tconst res = this._writer.%s;" % self.out_list_constructor(node))
            self.o("\t\tthis._setList(%d, res);" % (node.offset))
            self.o("\t\treturn res;")
            self.o("\t}")
            self.o()
        else:
            self.output_doc(node, "\t")
            self.o("\tset %s(value: %s) {" % (lname, it))
            self.o("\t\tconsole.assert(value instanceof scalgoproto.ListIn);")
            self.o("\t\tthis.add%s(value.length)._copy(value);" % (ucamel(lname)))
            self.o("\t}")

            self.output_doc(node, "\t")
            self.o(
                "\tadd%s(size: number) : %s {"
                % (ucamel(lname), self.out_list_type(node))
            )
            self.o(
                "\t\tconsole.assert(this._writer._size == this._offset + %s);" % size
            )
            self.o(
                "\t\tconst l = this._writer.%s;" % self.out_list_constructor(node, True)
            )
            self.o("\t\tthis._setInplaceList(%d, size);" % (node.offset))
            self.o("\t\treturn l;")
            self.o("\t}")
            self.o()

    def generate_union_list_out(
        self, node: Value, lname: str, idx: int, inplace: bool
    ) -> None:
        it = "scalgoproto.ListIn<%s>" % self.in_list_help(node, "")[0]
        ot = self.out_list_type(node)
        if not inplace:
            self.output_doc(node, "\t")
            self.o("\tset %s(value: %s |%s ) {" % (lname, ot, it))
            self.o("\t\tif (value instanceof scalgoproto.ListIn) {")
            self.o("\t\t\tthis.add%s(value.length)._copy(value)" % (ucamel(lname)))
            self.o("\t\t\treturn;")
            self.o("\t\t}")
            self.o("\t\tconsole.assert(value instanceof scalgoproto.ListOut);")
            self.o("\t\tthis._set(%d, value._offset - 10);" % (idx,))
            self.o("\t}")
            self.o()

            self.output_doc(node, "\t")
            self.o(
                "\tadd%s(size:number) : %s {"
                % (ucamel(lname), self.out_list_type(node))
            )
            self.o("\t\tconst res = this._writer.%s;" % self.out_list_constructor(node))
            self.o("\t\tthis._set(%d, res._offset - 10);" % (idx,))
            self.o("\t\treturn res;")
            self.o("\t}")
            self.o()
        else:
            self.output_doc(node, "\t")
            self.o("\tset %s(value: %s) {" % (lname, it))
            self.o("\t\tconsole.assert(value instanceof scalgoproto.ListIn);")
            self.o("\t\tthis.add%s(value.length)._copy(value);" % (ucamel(lname)))
            self.o("\t}")
            self.o()
            self.output_doc(node, "\t")
            self.o(
                "\tadd%s(size: number) : %s {"
                % (ucamel(lname), self.out_list_type(node))
            )
            self.o("\t\tthis._set(%d, size);" % (idx,))
            self.o(
                "\t\treturn this._writer.%s;" % self.out_list_constructor(node, True)
            )
            self.o("\t}")
            self.o()

    def generate_bool_in(self, node: Value, lname: str) -> None:
        if node.inplace:
            raise ICE()
        self.output_doc(node, "\t")
        self.o("\tget %s(): boolean%s {" % (lname, " | null " if node.optional else ""))
        if node.optional:
            self.o(
                "\t\tif (!this._getBit(%d, %s, false)) return null;"
                % (node.has_offset, node.has_bit)
            )
        self.o("\t\treturn this._getBit(%d, %s, false);" % (node.offset, node.bit))
        self.o("\t}")
        self.o()

    def generate_bool_out(self, node: Value, lname: str) -> None:
        self.output_doc(node, "\t")
        self.o("\tset %s(value: boolean) {" % (lname,))
        if node.optional:
            self.o("\t\tthis._setBit(%d, %d);" % (node.has_offset, node.has_bit))
        self.o("\t\tif (value) this._setBit(%d, %d);" % (node.offset, node.bit))
        self.o("\t\telse this._unsetBit(%d, %d);" % (node.offset, node.bit))
        self.o("\t}")
        self.o()

    def generate_basic_in(self, node: Value, lname: str) -> None:
        if node.inplace:
            raise ICE()
        ti = typeMap[node.type_.type]
        self.output_doc(node, "\t")
        self.o("\tget %s(): %s%s {" % (lname, ti.p, " | null" if node.optional else ""))
        if node.optional:
            if node.type_.type in (TokenType.F32, TokenType.F64):
                self.o(
                    "\t\tif (isNaN(this._get%s(%d, NaN))) return null;"
                    % (ti.n, node.offset)
                )
            else:
                self.o(
                    "\t\tif (!this._getBit(%d, %s, false)) return null;"
                    % (node.has_offset, node.has_bit)
                )
        self.o(
            "\t\treturn this._get%s(%d, %s);"
            % (
                ti.n,
                node.offset,
                node.parsed_value if not math.isnan(node.parsed_value) else "NaN",
            )
        )
        self.o("\t}")
        self.o()

    def generate_basic_out(self, node: Value, lname: str) -> None:
        if node.inplace:
            raise ICE()
        ti = typeMap[node.type_.type]
        self.output_doc(node, "\t")
        self.o("\tset %s(value: %s) {" % (lname, ti.p))
        if node.optional and node.type_.type not in (TokenType.F32, TokenType.F64):
            self.o("\t\tthis._setBit(%d, %d);" % (node.has_offset, node.has_bit))
        self.o("\t\tthis._set%s(%d, value);" % (ti.n, node.offset))
        self.o("\t}")
        self.o()

    def generate_enum_in(self, node: Value, lname: str) -> None:
        if node.inplace:
            raise ICE()
        self.output_doc(node, "\t")
        self.o("\tget %s(): %s | null {" % (lname, node.enum.name))
        self.o(
            "\t\tconst v = this._getUint8(%d, %s);" % (node.offset, node.parsed_value)
        )
        self.o("\t\treturn v == 255 ? null : v as %s;" % (node.enum.name))
        self.o("\t}")
        self.o()

    def generate_enum_out(self, node: Value, lname: str) -> None:
        if node.inplace:
            raise ICE()
        self.output_doc(node, "\t")
        self.o("\tset %s(value: %s) {" % (lname, node.enum.name))
        self.o("\t\tthis._setUint8(%d, value as number)" % (node.offset))
        self.o("\t}")
        self.o()

    def generate_struct_in(self, node: Value, lname: str) -> None:
        if node.inplace:
            raise ICE()
        self.output_doc(node, "\t")
        self.o(
            "\tget %s(): %s%s {"
            % (lname, node.struct.name, " | null " if node.optional else "")
        )
        if node.optional:
            self.o(
                "\t\tif (!this._getBit(%d, %s, false)) return null;"
                % (node.has_offset, node.has_bit)
            )
        self.o(
            "\t\tif (%d >= this._size) return new %s();"
            % (node.offset, node.struct.name)
        )
        self.o(
            "\t\treturn %s._read(this._reader, this._offset+%d);"
            % (node.struct.name, node.offset)
        )
        self.o("\t}")
        self.o()

    def generate_struct_out(self, node: Value, lname: str) -> None:
        if node.inplace:
            raise ICE()
        self.output_doc(node, "\t")
        self.o("\tset %s(value: %s) {" % (lname, node.struct.name))
        if node.optional:
            self.o("\t\tthis._setBit(%d, %d)" % (node.has_offset, node.has_bit))
        self.o(
            "\t\t%s._write(this._writer, this._offset + %d, value)"
            % (node.struct.name, node.offset)
        )
        self.o("\t}")
        self.o()

    def generate_table_in(self, node: Value, lname: str) -> None:
        if not node.table.empty:
            self.output_doc(node, "\t")
            self.o("\tget %s() : %sIn | null {" % (lname, node.table.name))
            self.o(
                "\t\tconst [offset, size] = this._getPtr%s(%d, %sIn._MAGIC);"
                % ("Inplace" if node.inplace else "", node.offset, node.table.name)
            )
            self.o("\t\tif (offset === 0) return null;")
            self.o(
                "\t\treturn new %sIn(this._reader, offset, size);" % (node.table.name,)
            )
            self.o("\t}")
            self.o()

    def generate_union_table_in(self, node: Value, lname: str) -> None:
        if not node.table.empty:
            self.output_doc(node, "\t")
            self.o("\tget %s() : %sIn | null {" % (lname, node.table.name))
            self.o("\t\tif (!this.is%s) return null;" % (ucamel(lname)))
            self.o(
                "\t\tconst [offset, size] = this._getPtr(%sIn._MAGIC);"
                % (node.table.name)
            )
            self.o("\t\tif (offset === 0) return null;")
            self.o(
                "\t\treturn new %sIn(this._reader, offset, size);" % (node.table.name,)
            )
            self.o("\t}")
            self.o()

    def generate_table_out(self, node: Value, lname: str, size: int) -> None:
        if not node.inplace:
            self.output_doc(node, "\t")
            self.o(
                "\tset %s(value: %sOut | %sIn) {"
                % (lname, node.table.name, node.table.name)
            )
            self.o("\t\tif (value instanceof %sIn) {" % (node.table.name))
            self.o("\t\t\tconst v = value;")
            self.o(
                "\t\t\tvalue = this._writer.constructTable(%sOut);" % node.table.name
            )
            self.o("\t\t\tvalue._copy(v);")
            self.o("\t\t}")
            self.o("\t\tconsole.assert(value instanceof %sOut);" % (node.table.name))
            self.o("\t\tthis._setTable(%d, value);" % (node.offset))
            self.o("\t}")
            self.o()
            self.output_doc(node, "\t")
            self.o("\tadd%s() : %sOut {" % (ucamel(lname), node.table.name))
            self.o(
                "\t\tconst res = this._writer.constructTable(%sOut);" % node.table.name
            )
            self.o("\t\tthis._setTable(%d, res);" % (node.offset,))
            self.o("\t\treturn res;")
            self.o("\t}")
            self.o()
        elif not node.table.empty:
            self.output_doc(node, "\t")
            self.o("\tset %s(value: %sIn) {" % (lname, node.table.name))
            self.o("\t\tconsole.assert(value instanceof %sIn);" % (node.table.name))
            self.o("\t\tthis.add%s()._copy(value);" % (ucamel(lname),))
            self.o("\t}")
            self.o()
            self.output_doc(node, "\t")
            self.o("\tadd%s() : %sOut {" % (ucamel(lname), node.table.name))
            self.o(
                "\t\tconsole.assert(this._writer._size == this._offset + %s);" % size
            )
            self.o(
                "\t\tthis._setUint48(%d, %d);" % (node.offset, len(node.table.default))
            )
            self.o("\t\treturn new %sOut(this._writer, false);" % node.table.name)
            self.o("\t}")
            self.o()
        else:
            self.output_doc(node, "\t")
            self.o("\tadd%s(self) {" % (ucamel(lname)))
            self.o("\t\tthis._setUint48(%d, %d);" % (node.offset, 0))
            self.o("\t}")
            self.o()

    def generate_union_table_out(
        self, node: Value, lname: str, idx: int, inplace: bool
    ) -> None:
        table = node.table
        if table.empty:
            self.output_doc(node, "\t")
            self.o("\tadd%s() {" % (ucamel(lname)))
            self.o("\t\tthis._set(%d, 0);" % (idx))
            self.o("\t}")
            self.o()
        elif not inplace:
            self.output_doc(node, "\t")
            self.o("\tset %s(value: %sOut | %sIn) {" % (lname, table.name, table.name))
            self.o("\t\tif (value instanceof %sIn) {" % (node.table.name))
            self.o("\t\t\tconst v = value;")
            self.o(
                "\t\t\tvalue = this._writer.constructTable(%sOut);" % node.table.name
            )
            self.o("\t\t\tvalue._copy(v);")
            self.o("\t\t}")
            self.o("\t\tconsole.assert(value instanceof %sOut);" % (node.table.name))
            self.o("\t\tthis._set(%d, value._offset - 10);" % (idx))
            self.o("\t}")
            self.o()
            self.output_doc(node, "\t")
            self.o("\tadd%s() : %sOut {" % (ucamel(lname), table.name))
            self.o(
                "\t\tconst res = this._writer.constructTable(%sOut);" % node.table.name
            )
            self.o("\t\tthis._set(%d, res._offset - 10);" % (idx,))
            self.o("\t\treturn res;")
            self.o("\t}")
            self.o()
        else:
            self.output_doc(node, "\t")
            self.o("\tset %s(value: %sIn) {" % (lname, node.table.name))
            self.o("\t\tconsole.assert(value instanceof %sIn);" % (node.table.name))
            self.o("\t\tthis.add%s()._copy(value);" % (ucamel(lname),))
            self.o("\t}")
            self.o()
            self.output_doc(node, "\t")
            self.o("\tadd%s() : %sOut {" % (ucamel(lname), table.name))
            self.o("\t\tconsole.assert(this._end == this._writer._size);")
            self.o("\t\tthis._set(%d, %d);" % (idx, table.bytes))
            self.o("\t\treturn new %sOut(this._writer, false)" % table.name)
            self.o("\t}")
            self.o()

    def generate_text_in(self, node: Value, lname: str) -> None:
        self.output_doc(node, "\t")
        self.o("\tget %s() : string | null {" % (lname))
        self.o(
            "\t\tconst [o, s] = this._getPtr%s(%d, scalgoproto.TEXT_MAGIC)"
            % ("Inplace" if node.inplace else "", node.offset)
        )
        self.o("\t\tif (o === 0) return null;")
        self.o("\t\treturn this._reader._readText(o, s);")
        self.o("\t}")
        self.o()

    def generate_union_text_in(self, node: Value, lname: str) -> None:
        self.output_doc(node, "\t")
        self.o("\tget %s() : string | null {" % (lname))
        self.o("\t\tif(!this.is%s) return null;" % ucamel(lname))
        self.o("\t\tconst [o, s] = this._getPtr(scalgoproto.TEXT_MAGIC)")
        self.o("\t\tif (o === 0) return null;")
        self.o("\t\treturn this._reader._readText(o, s);")
        self.o("\t}")
        self.o()

    def generate_text_out(self, node: Value, lname: str, size: int) -> None:
        self.output_doc(node, "\t")
        if node.inplace:
            self.o("\tset %s(text: string) {" % (lname))
        else:
            self.o("\tset %s(t: scalgoproto.TextOut | string) {" % (lname))
        if node.inplace:
            self.o(
                "\t\tconsole.assert(this._writer._size == this._offset + %s);" % size
            )
            self.o("\t\tthis._addInplaceText(%d, text);" % (node.offset))
        else:
            self.o("\t\tthis._setText(%d, t);" % (node.offset))
        self.o("\t}")
        self.o()

    def generate_union_text_out(
        self, node: Value, lname: str, idx: int, inplace: bool
    ) -> None:
        self.output_doc(node, "\t")
        if inplace:
            self.o("\tset %s(value: string) {" % (lname))
        else:
            self.o("\tset %s(value: scalgoproto.TextOut | string) {" % (lname))
        if inplace:
            self.o("\t\tthis._addInplaceText(%d, value);" % (idx))
        else:
            self.o("\t\tthis._setText(%d, value);" % (idx))
        self.o("}")
        self.o()

    def generate_bytes_in(self, node: Value, lname: str) -> None:
        self.output_doc(node, "\t")
        self.o("\tget %s() : ArrayBuffer | null {" % (lname))
        self.o(
            "\t\tconst [o, s] = this._getPtr%s(%d, scalgoproto.BYTES_MAGIC)"
            % ("Inplace" if node.inplace else "", node.offset)
        )
        self.o("\t\tif (o === 0) return null;")
        self.o("\t\tconst oo = (this._reader._data.byteOffset || 0) + o")
        self.o("\t\treturn this._reader._data.buffer.slice(oo, oo+s);")
        self.o("\t}")
        self.o()

    def generate_union_bytes_in(self, node: Value, lname: str) -> None:
        self.output_doc(node, "\t")
        self.o("\tget %s() : ArrayBuffer | null {" % (lname))
        self.o("\t\tif (!this.is%s) return null;" % (ucamel(lname)))
        self.o("\t\tconst [o, s] = this._getPtr(scalgoproto.BYTES_MAGIC)")
        self.o("\t\tif (o === 0) return null;")
        self.o("\t\tconst oo = (this._reader._data.byteOffset || 0) + o")
        self.o("\t\treturn this._reader._data.buffer.slice(oo, oo+s);")
        self.o("\t}")
        self.o()

    def generate_bytes_out(self, node: Value, lname: str, size: int) -> None:
        self.output_doc(node, "\t")
        if node.inplace:
            self.o("\tset %s(value: ArrayBuffer) {" % (lname))
        else:
            self.o("\tset %s(value: scalgoproto.BytesOut | ArrayBuffer) {" % (lname))
        if node.inplace:
            self.o(
                "\t\tconsole.assert(this._writer._size == this._offset + %s);" % (size)
            )
            self.o("\t\tthis._addInplaceBytes(%d, value);" % (node.offset))
        else:
            self.o("\t\tthis._setBytes(%d, value);" % (node.offset))
        self.o("\t}")
        self.o()

    def generate_union_bytes_out(
        self, node: Value, lname: str, idx: int, inplace: bool
    ) -> None:
        self.output_doc(node, "        ")
        if inplace:
            self.o("\tset %s(value: ArrayBuffer) {" % (lname))
        else:
            self.o("\tset %s(value: scalgoproto.BytesOut | ArrayBuffer) {" % (lname))
        if inplace:
            self.o("\t\tthis._addInplaceBytes(%d, value);" % (idx))
        else:
            self.o("\t\tthis._setBytes(%d, value);" % (idx))
        self.o("\t}")
        self.o()

    def generate_union_in(self, node: Value, lname: str, table: Table) -> None:
        self.output_doc(node, "\t")
        self.o("\tget %s() : %sIn  {" % (lname, node.union.name))
        if node.inplace:
            self.o(
                "\t\treturn new %sIn(this._reader, this._getUint16(%d, 0), this._offset + this._size, this._getUint48(%d))"
                % (node.union.name, node.offset, node.offset + 2)
            )
        else:
            self.o(
                "\t\treturn new %sIn(this._reader, this._getUint16(%d, 0), this._getUint48(%d))"
                % (node.union.name, node.offset, node.offset + 2)
            )
        self.o("\t}")
        self.o()

    def generate_union_out(self, node: Value, lname: str, table: Table) -> None:
        self.o(
            "\tget %s() : %s%sOut {"
            % (lname, node.union.name, "Inplace" if node.inplace else "")
        )
        self.o(
            "        return new %s%sOut(this._writer, this._offset + %d, this._offset + %d);"
            % (
                node.union.name,
                "Inplace" if node.inplace else "",
                node.offset,
                table.bytes,
            )
        )
        self.o("\t}")
        self.o()

    def generate_value_in(self, table: Table, node: Value) -> None:
        lname = lcamel(self.value(node.identifier))
        if node.list_:
            self.generate_list_in(node, lname)
        elif node.type_.type == TokenType.BOOL:
            self.generate_bool_in(node, lname)
        elif node.type_.type in typeMap:
            self.generate_basic_in(node, lname)
        elif node.enum:
            self.generate_enum_in(node, lname)
        elif node.struct:
            self.generate_struct_in(node, lname)
        elif node.table:
            self.generate_table_in(node, lname)
        elif node.union:
            self.generate_union_in(node, lname, table)
        elif node.type_.type == TokenType.TEXT:
            self.generate_text_in(node, lname)
        elif node.type_.type == TokenType.BYTES:
            self.generate_bytes_in(node, lname)
        else:
            raise ICE()

    def generate_value_out(self, table: Table, node: Value) -> None:
        lname = lcamel(self.value(node.identifier))
        if node.list_:
            self.generate_list_out(node, lname, len(table.default))
        elif node.type_.type == TokenType.BOOL:
            self.generate_bool_out(node, lname)
        elif node.type_.type in typeMap:
            self.generate_basic_out(node, lname)
        elif node.enum:
            self.generate_enum_out(node, lname)
        elif node.struct:
            self.generate_struct_out(node, lname)
        elif node.table:
            self.generate_table_out(node, lname, len(table.default))
        elif node.union:
            self.generate_union_out(node, lname, table)
        elif node.type_.type == TokenType.TEXT:
            self.generate_text_out(node, lname, len(table.default))
        elif node.type_.type == TokenType.BYTES:
            self.generate_bytes_out(node, lname, len(table.default))
        else:
            raise ICE()

    def generate_union_copy(self, union: Union) -> None:
        self.o("\t_copy(i:%sIn) {" % union.name)
        self.o("\t\tswitch(i.type) {")
        for node in union.members:
            lname = self.value(node.identifier)
            self.o("\t\tcase %sType.%s:" % (union.name, lname.upper()))
            if node.table and node.table.empty:
                self.o("\t\t\tthis.add%s();" % (ucamel(lname)))
            else:
                self.o("\t\t\tthis.%s = i.%s!;" % (lname, lname))
            self.o("\t\t\tbreak;")
        self.o("\t\t}")
        self.o("\t}")
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

        self.o("export enum %sType {" % (union.name))
        self.o("\tNONE,")
        for member in union.members:
            if not isinstance(member, (Table, Value)):
                raise ICE()
            self.o("\t%s," % (self.value(member.identifier).upper()))
        self.o("}")
        self.o()

        self.output_doc(union, "\t")
        self.o("export class %sIn extends scalgoproto.UnionIn {" % union.name)
        self.o(
            "\t/** Private constructor. Call factory methods on scalgoproto.Reader to construct instances */"
        )
        self.o(
            "\tconstructor(reader: scalgoproto.Reader, type: number, offset: number, size: number|null = null) {"
        )

        self.o("\t\tsuper(reader, type, offset, size);")
        self.o("\t}")
        self.o()

        self.o("\tget type() : %sType {" % (union.name))
        self.output_doc(union, "    ")
        self.o("\t\treturn this._type as %sType;" % (union.name))
        self.o("\t}")
        self.o()
        for member in union.members:
            n = self.value(member.identifier)
            lname = lcamel(n)
            self.o("\tget is%s() : boolean {" % (ucamel(lname)))
            self.o("\t\treturn this.type == %sType.%s;" % (union.name, n.upper()))
            self.o("\t}")
            self.o()
            if member.list_:
                self.generate_union_list_in(member, lname)
            elif member.table:
                self.generate_union_table_in(member, lname)
            elif member.type_.type == TokenType.BYTES:
                self.generate_union_bytes_in(member, lname)
            elif member.type_.type == TokenType.TEXT:
                self.generate_union_text_in(member, lname)
            else:
                raise ICE()
        self.o("}")
        self.o()

        self.o("export class %sOut extends scalgoproto.UnionOut {" % union.name)
        self.o("\tstatic readonly _IN = %sIn;" % (union.name))
        self.o(
            "\t/***Private constructor. Call factory methods on scalgoproto.Writer to construct instances*/"
        )
        self.o(
            "\tconstructor(writer: scalgoproto.Writer, offset: number, end: number = 0) {"
        )
        self.o("\t\tsuper(writer, offset, end);")
        self.o("\t}")
        self.o()
        idx = 1
        for member in union.members:
            llname = lcamel(self.value(member.identifier))
            if member.list_:
                self.generate_union_list_out(member, llname, idx, False)
            elif member.table:
                self.generate_union_table_out(member, llname, idx, False)
            elif member.type_.type == TokenType.BYTES:
                self.generate_union_bytes_out(member, llname, idx, False)
            elif member.type_.type == TokenType.TEXT:
                self.generate_union_text_out(member, llname, idx, False)
            else:
                raise ICE()
            idx += 1
        self.generate_union_copy(union)
        self.o("}")
        self.o()

        self.o("export class %sInplaceOut extends scalgoproto.UnionOut {" % union.name)
        self.o(
            "\t/** Private constructor. Call factory methods on scalgoproto.Writer to construct instances */"
        )
        self.o(
            "\tconstructor(writer: scalgoproto.Writer, offset: number, end: number = 0) {"
        )

        self.o("\t\tsuper(writer, offset, end);")
        self.o("\t}")
        self.o()
        idx = 1
        for member in union.members:
            llname = lcamel(self.value(member.identifier))
            if member.list_:
                self.generate_union_list_out(member, llname, idx, True)
            elif member.table:
                self.generate_union_table_out(member, llname, idx, True)
            elif member.type_.type == TokenType.BYTES:
                self.generate_union_bytes_out(member, llname, idx, True)
            elif member.type_.type == TokenType.TEXT:
                self.generate_union_text_out(member, llname, idx, True)
            else:
                raise ICE()
            idx += 1
        self.generate_union_copy(union)
        self.o("}")
        self.o()

    def generate_table_copy(self, table: Table) -> None:
        self.o("\t_copy(i:%sIn) {" % table.name)
        for ip in (True, False):
            for node in table.members:
                lname = lcamel(self.value(node.identifier))
                uname = ucamel(lname)
                if bool(node.inplace) != ip:
                    continue
                if node.list_:
                    self.o(
                        "\t\tif (i.%s !== null) this.add%s(i.%s.length)._copy(i.%s);"
                        % (lname, uname, lname, lname)
                    )
                elif (
                    node.optional
                    or node.enum
                    or node.type_.type == TokenType.TEXT
                    or node.type_.type == TokenType.BYTES
                ):
                    self.o(
                        "\t\tif (i.%s !== null) this.%s = i.%s;" % (lname, lname, lname)
                    )
                elif (
                    node.type_.type in typeMap
                    or node.type_.type == TokenType.BOOL
                    or node.enum
                    or node.struct
                ):
                    self.o("\t\tthis.%s = i.%s;" % (lname, lname))
                elif node.table:
                    if node.table.empty:
                        self.o("\t\t if (i.%s !== null) this.add%s();" % (lname, uname))
                    else:
                        self.o(
                            "\t\t if (i.%s !== null) this.add%s()._copy(i.%s);"
                            % (lname, uname, lname)
                        )
                elif node.union:
                    self.o("\t\tthis.%s._copy(i.%s);" % (lname, lname))
                else:
                    raise ICE()
        self.o("\t}")
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
        self.output_doc(table, "")
        self.o("export class %sIn extends scalgoproto.TableIn {" % table.name)
        self.o("\tstatic readonly _MAGIC = 0x%08X;" % table.magic)
        self.o()
        self.o(
            "\t/** Private constructor. Call factory methods on scalgoproto.Reader to construct instances */"
        )
        self.o(
            "\tconstructor(reader: scalgoproto.Reader, offset: number, size: number) {"
        )
        self.o("\t\tsuper(reader, offset, size);")
        self.o("\t}")
        for node in table.members:
            self.generate_value_in(table, node)
        self.o("}")
        self.o()

        # Generate Table writer
        self.output_doc(table, "")
        self.o("export class %sOut extends scalgoproto.TableOut {" % table.name)
        self.o("\tstatic readonly _MAGIC = 0x%08X;" % table.magic)
        self.o("\tstatic readonly _SIZE = %d;" % len(table.default))
        self.o("\tstatic readonly _IN = %sIn;" % (table.name))
        self.o()
        self.o(
            "\t/** Private constructor. Call factory methods on scalgoproto.Reader to construct instances */"
        )
        self.o("\tconstructor(writer: scalgoproto.Writer, withHeader: boolean) {")
        self.o(
            '\t\tsuper(writer, withHeader, "%s", %sOut._MAGIC);'
            % (cescape(table.default), table.name)
        )
        self.o("\t}")
        self.o()
        for node in table.members:
            self.generate_value_out(table, node)
        self.generate_table_copy(table)
        self.o("}")
        self.o()

    def generate_struct(self, node: Struct) -> None:
        # Recursively generate direct contained members
        for value in node.members:
            if value.direct_enum:
                self.generate_enum(value.direct_enum)
            if value.direct_struct:
                self.generate_struct(value.direct_struct)

        self.output_doc(node, "")
        self.o("export class %s extends scalgoproto.StructType {" % node.name)
        ctor = []
        read = []
        write = []
        for v in node.members:
            thing = ("", "", "", 0, 0, "")
            n = lcamel(self.value(v.identifier))
            if v.type_.type in typeMap:
                ti = typeMap[v.type_.type]
                if v.type_.type in (TokenType.F32, TokenType.F64):
                    ctor.append("public %s: %s = 0.0" % (n, ti.p))
                elif v.type_.type == TokenType.BOOL:
                    ctor.append("public %s: %s = false" % (n, ti.p))
                else:
                    ctor.append("public %s: %s = 0" % (n, ti.p))

                if v.type_.type == TokenType.I8:
                    read.append("reader._data.getInt8(offset + %d)" % (v.offset))
                    write.append(
                        "writer._data.setInt8(offset + %d, ins.%s)" % (v.offset, n)
                    )
                elif v.type_.type == TokenType.I16:
                    read.append("reader._data.getInt16(offset + %d, true)" % (v.offset))
                    write.append(
                        "writer._data.setInt16(offset + %d, ins.%s, true)"
                        % (v.offset, n)
                    )
                elif v.type_.type == TokenType.I32:
                    read.append("reader._data.getInt32(offset + %d, true)" % (v.offset))
                    write.append(
                        "writer._data.setInt32(offset + %d, ins.%s, true)"
                        % (v.offset, n)
                    )
                elif v.type_.type == TokenType.I64:
                    read.append("reader._readInt64(offset + %d)" % (v.offset))
                    write.append(
                        "writer._writeInt64(offset + %d, ins.%s)" % (v.offset, n)
                    )
                elif v.type_.type == TokenType.U8:
                    read.append("reader._data.getUint8(offset + %d)" % (v.offset))
                    write.append(
                        "writer._data.setUint8(offset + %d, ins.%s)" % (v.offset, n)
                    )
                elif v.type_.type == TokenType.U16:
                    read.append(
                        "reader._data.getUint16(offset + %d, true)" % (v.offset)
                    )
                    write.append(
                        "writer._data.setUint16(offset + %d, ins.%s, true)"
                        % (v.offset, n)
                    )
                elif v.type_.type == TokenType.UI32:
                    read.append(
                        "reader._data.getUint32(offset + %d, true)" % (v.offset)
                    )
                    write.append(
                        "writer._data.setUint32(offset + %d, ins.%s, true)"
                        % (v.offset, n)
                    )
                elif v.type_.type == TokenType.UI64:
                    read.append("reader._readUint64(offset + %d)" % (v.offset))
                    write.append(
                        "writer._writeUint64(offset + %d, ins.%s)" % (v.offset, n)
                    )
                elif v.type_.type == TokenType.F32:
                    read.append(
                        "reader._data.getFloat32(offset + %d, true)" % (v.offset)
                    )
                    write.append(
                        "writer._data.setFloat32(offset + %d, ins.%s, true)"
                        % (v.offset, n)
                    )
                elif v.type_.type == TokenType.F64:
                    read.append(
                        "reader._data.getFloat64(offset + %d, true)" % (v.offset)
                    )
                    write.append(
                        "writer._data.setFloat64(offset + %d, ins.%s, true)"
                        % (v.offset, n)
                    )
                elif v.type_.type == TokenType.BOOL:
                    read.append("reader._data.getUint8(offset + %d) != 0" % (v.offset))
                    write.append(
                        "writer._data.setUint8(offset + %d, ins.%s ? 1 : 0)"
                        % (v.offset, n)
                    )
            elif v.enum:
                ctor.append("public %s: %s = 0" % (n, v.enum.name))
                read.append(
                    "reader._data.getUint8(offset + %d) as %s" % (v.offset, v.enum.name)
                )
                write.append(
                    "writer._data.setUint8(offset + %d, +ins.%s)" % (v.offset, n)
                )
            elif v.struct:
                ctor.append(
                    "public %s: %s = new %s()" % (n, v.struct.name, v.struct.name)
                )
                write.append(
                    "%s._write(writer, offset + %d, ins.%s)"
                    % (v.struct.name, v.offset, n)
                )
                read.append("%s._read(reader, offset + %d)" % (v.struct.name, v.offset))
            else:
                raise ICE()
        self.o("\tstatic readonly _WIDTH  = %d;" % node.bytes)
        self.o()
        self.o("\tconstructor(%s) {super();}" % (", ".join(ctor)))
        self.o()
        self.o(
            "\tstatic _write(writer: scalgoproto.Writer, offset: number, ins: %s) {"
            % node.name
        )
        for line in write:
            self.o("\t\t%s;" % line)
        self.o("\t}")
        self.o()
        self.o(
            "\tstatic _read(reader: scalgoproto.Reader, offset: number) : %s {"
            % node.name
        )
        self.o("\t\treturn new %s(" % node.name)
        for line in read:
            self.o("\t\t\t%s," % line)
        self.o("\t\t);")
        self.o("\t}")
        self.o("}")
        self.o()

    def generate_enum(self, node: Enum) -> None:
        self.output_doc(node, "")
        self.o("export enum %s {" % node.name)
        index = 0
        for ev in node.members:
            self.o("    %s," % (self.value(ev.identifier)))
            index += 1
        self.o("}")
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

        for d, imp in imports.items():
            doc = self.documents.by_id[d]
            self.o("import {%s} from '%s'" % (", ".join(imp), doc.name))

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
    out = open(os.path.join(args.output, "%s.ts" % documents.root.name), "w")
    try:
        ast = p.parse_document()
        if not annotate(documents, ast):
            print("Schema is invalid")
            return 1
        g = Generator(documents, out, args.import_prefix)
        print(
            "// -*- mode: typescript; tab-width: 4; indent-tabs-mode: t; coding: utf-8 -*-",
            file=out,
        )
        print("//THIS FILE IS GENERATED DO NOT EDIT", file=out)
        print('import * as scalgoproto from "scalgoproto"', file=out)
        print("", file=out)

        g.generate(ast)
        return 0
    except ParseError as err:
        err.describe(documents)
    return 1


def setup(subparsers) -> None:
    cmd = subparsers.add_parser("ts", help="Generate typescript code")
    cmd.add_argument("schema", help="schema to generate things from")
    cmd.add_argument("output", help="where do we store the output")
    cmd.add_argument(
        "--import-prefix", help="Prefix to put infront of imports", default=""
    )
    cmd.set_defaults(func=run)
