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
from .util import cescape, ucamel, lcamel, usnake, snake

TypeInfo = NamedTuple("TypeInfo", [("n", str), ("p", str)])

typeMap: Dict[TokenType, TypeInfo] = {
    TokenType.I8: TypeInfo("Int8", "i8"),
    TokenType.I16: TypeInfo("Int16", "i16"),
    TokenType.I32: TypeInfo("Int32", "i32"),
    TokenType.I64: TypeInfo("Int64", "i64"),
    TokenType.U8: TypeInfo("Uint8", "u8"),
    TokenType.U16: TypeInfo("Uint16", "u16"),
    TokenType.UI32: TypeInfo("Uint32", "u32"),
    TokenType.UI64: TypeInfo("Uint64", "u64"),
    TokenType.F32: TypeInfo("Float32", "f32"),
    TokenType.F64: TypeInfo("Float64", "f64"),
    TokenType.BOOL: TypeInfo("Bool", "bool"),
}


class Generator:
    def __init__(self, documents: Documents, out: TextIO) -> None:
        self.documents: Documents = documents
        self.out: TextIO = out

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
            return ("boolean", "        return this._reader._getBoolList(%s)" % (os))
        elif node.type_.type in typeMap:
            ti = typeMap[node.type_.type]
            return (ti.p, "        return this._reader._get%sList(%s)" % (ti.n, os))
        elif node.struct:
            return (
                node.struct.name,
                "        return this._reader._getStructList(%s, %s)"
                % (os, node.struct.name),
            )
        elif node.enum:
            return (
                node.enum.name + " | null",
                "        return this._reader._getEnumList<%s>(%s)" % (node.enum.name, os),
            )
        elif node.table:
            return (
                node.table.name + "In | null",
                "        return this._reader._getTableList(%s, %sIn)"
                % (os, node.table.name),
            )
        elif node.union:
            return (
                node.union.name + "In",
                "        return this._reader._getUnionList(%s, %sIn)"
                % (os, node.union.name),
            )
        elif node.type_.type == TokenType.TEXT:
            return (
                "string | null",
                "        return this._reader._getTextList(%s)" % (os,),
            )
        elif node.type_.type == TokenType.BYTES:
            return (
                "ArrayBuffer | null",
                "        return this._reader._getBytesList(%s)" % (os,),
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

        self.output_doc(node, "    ")
        self.o("    get %s() : scalgoproto.ListIn<%s> | null {" % (lname, tn))
        self.o(
            "        const [o, s] = this._getPtr%s(%d, scalgoproto.LIST_MAGIC)"
            % ("Inplace" if node.inplace else "", node.offset)
        )
        self.o("        if (o === 0) return null;")
        self.o(acc)
        self.o("    }")
        self.o()

    def generate_union_list_in(self, node: Value, lname: str) -> None:
        (tn, acc) = self.in_list_help(node, "o, s")
        self.output_doc(node, "    ")
        self.o("    get %s() : scalgoproto.ListIn<%s> | null {" % (lname, tn))
        self.o("        if (!this.is%s) return null;" % (ucamel(lname)))
        self.o("        const [o, s] = this._getPtr(scalgoproto.LIST_MAGIC)")
        self.o("        if (o === 0) return null;")
        self.o(acc)
        self.o("    }")
        self.o()

    def generate_list_out(self, node: Value, lname: str, size: int) -> None:
        it = "scalgoproto.ListIn<%s>" % self.in_list_help(node, "")[0]
        ot = self.out_list_type(node)
        if not node.inplace:
            self.output_doc(node, "    ")
            self.o("    set %s(value: %s | %s) {" % (lname, it, ot))
            self.o("        if (value instanceof scalgoproto.ListIn) {")
            self.o("            this.add%s(value.length)._copy(value);" % (ucamel(lname)))
            self.o("            return;")
            self.o("        }")
            self.o("        console.assert(value instanceof scalgoproto.ListOut);")
            self.o("        this._setList(%d, value);" % (node.offset))
            self.o("    }")
            self.o()

            self.output_doc(node, "    ")
            self.o(
                "    add%s(size:number) : %s {"
                % (ucamel(lname), self.out_list_type(node))
            )
            self.o("        const res = this._writer.%s;" % self.out_list_constructor(node))
            self.o("        this._setList(%d, res);" % (node.offset))
            self.o("        return res;")
            self.o("    }")
            self.o()
        else:
            self.output_doc(node, "    ")
            self.o("    set %s(value: %s) {" % (lname, it))
            self.o("        console.assert(value instanceof scalgoproto.ListIn);")
            self.o("        this.add%s(value.length)._copy(value);" % (ucamel(lname)))
            self.o("    }")

            self.output_doc(node, "    ")
            self.o(
                "    add%s(size: number) : %s {"
                % (ucamel(lname), self.out_list_type(node))
            )
            self.o(
                "        console.assert(this._writer._size == this._offset + %s);" % size
            )
            self.o(
                "        const l = this._writer.%s;" % self.out_list_constructor(node, True)
            )
            self.o("        this._setInplaceList(%d, size);" % (node.offset))
            self.o("        return l;")
            self.o("    }")
            self.o()

    def generate_union_list_out(
        self, node: Value, lname: str, idx: int, inplace: bool
    ) -> None:
        it = "scalgoproto.ListIn<%s>" % self.in_list_help(node, "")[0]
        ot = self.out_list_type(node)
        if not inplace:
            self.output_doc(node, "    ")
            self.o("    set %s(value: %s |%s ) {" % (lname, ot, it))
            self.o("        if (value instanceof scalgoproto.ListIn) {")
            self.o("            this.add%s(value.length)._copy(value)" % (ucamel(lname)))
            self.o("            return;")
            self.o("        }")
            self.o("        console.assert(value instanceof scalgoproto.ListOut);")
            self.o("        this._set(%d, value._offset - 10);" % (idx,))
            self.o("    }")
            self.o()

            self.output_doc(node, "    ")
            self.o(
                "    add%s(size:number) : %s {"
                % (ucamel(lname), self.out_list_type(node))
            )
            self.o("        const res = this._writer.%s;" % self.out_list_constructor(node))
            self.o("        this._set(%d, res._offset - 10);" % (idx,))
            self.o("        return res;")
            self.o("    }")
            self.o()
        else:
            self.output_doc(node, "    ")
            self.o("    set %s(value: %s) {" % (lname, it))
            self.o("        console.assert(value instanceof scalgoproto.ListIn);")
            self.o("        this.add%s(value.length)._copy(value);" % (ucamel(lname)))
            self.o("    }")
            self.o()
            self.output_doc(node, "    ")
            self.o(
                "    add%s(size: number) : %s {"
                % (ucamel(lname), self.out_list_type(node))
            )
            self.o("        this._set(%d, size);" % (idx,))
            self.o(
                "        return this._writer.%s;" % self.out_list_constructor(node, True)
            )
            self.o("    }")
            self.o()

    def generate_bool_in(self, node: Value, lname: str) -> None:
        if node.inplace:
            raise ICE()
        self.output_doc(node, "    ")
        if node.optional:
            self.o("    fn %s(&self) -> Option<bool> {if self.reader.get_bit(%d, %d) {Some(self.reader.get_bit(%d, %d))} else {None}}"%(
                lname, node.has_offset, node.has_bit, node.offset, node.bit
            ))
        else:
            self.o("    fn %s(&self) -> bool {self.reader.get_bit(%d, %d)}"%(
                lname, node.offset, node.bit
            ))
    def generate_bool_out(self, node: Value, lname: str) -> None:
        self.output_doc(node, "    ")
        self.o("    set %s(value: boolean) {" % (lname,))
        if node.optional:
            self.o("        this._setBit(%d, %d);" % (node.has_offset, node.has_bit))
        self.o("        if (value) this._setBit(%d, %d);" % (node.offset, node.bit))
        self.o("        else this._unsetBit(%d, %d);" % (node.offset, node.bit))
        self.o("    }")
        self.o()

    def generate_basic_in(self, node: Value, lname: str) -> None:
        if node.inplace:
            raise ICE()
        ti = typeMap[node.type_.type]
        self.output_doc(node, "    ")
        if node.optional:
            if node.type_.type in (TokenType.F32, TokenType.F64):
                self.o(
                    "    fn %s(&self) -> Option<%s> {match self.reader.get_pod(%d) {None => None, Some(v) if v.is_nan() => None, Some(v) => Some(v)}}"% (
                        lname, ti.p, node.offset
                    ))
            else:
                self.o(
                    "    fn %s(&self) -> Option<%s> {if self.reader.get_bit(%d, %d) {Some(self.reader.get_pod(%d))} else {None}}"% (
                        lname, ti.p, node.has_offset, node.has_bit, node.offset
                    ))
        else:
            self.o(
                "    fn %s(&self) -> %s {self.reader.get_pod(%d).unwrap_or(%s)}"% (
                    lname, ti.p, node.offset, node.parsed_value if not math.isnan(node.parsed_value) else "std::%s::NAN"%ti.p
                ))


    def generate_basic_out(self, node: Value, lname: str) -> None:
        if node.inplace:
            raise ICE()
        ti = typeMap[node.type_.type]
        self.output_doc(node, "    ")
        self.o("    set %s(value: %s) {" % (lname, ti.p))
        if node.optional and node.type_.type not in (TokenType.F32, TokenType.F64):
            self.o("        this._setBit(%d, %d);" % (node.has_offset, node.has_bit))
        self.o("        this._set%s(%d, value);" % (ti.n, node.offset))
        self.o("    }")
        self.o()

    def generate_enum_in(self, node: Value, lname: str) -> None:
        if node.inplace:
            raise ICE()
        self.output_doc(node, "    ")
        self.o("    fn %s(&self) -> Optional<%s> {self.reader.get_enum(%d, %d)}" % (lname, node.enum.name, node.offset, len(node.enum.members)))


    def generate_enum_out(self, node: Value, lname: str) -> None:
        if node.inplace:
            raise ICE()
        self.output_doc(node, "    ")
        self.o("    set %s(value: %s) {" % (lname, node.enum.name))
        self.o("        this._setUint8(%d, value as number)" % (node.offset))
        self.o("    }")
        self.o()

    def generate_struct_in(self, node: Value, lname: str) -> None:
        if node.inplace:
            raise ICE()
        self.output_doc(node, "    ")
        if node.optional:
            self.o("    fn %s(&self) -> Option<%sOut> {if self.reader.get_bit(%d, %d) {Some(self.reader.get_struct(%d))} else {None}}"%(
                lname, node.struct.name, node.has_offset, node.has_bit, node.offset))
        else:
            self.o("    fn %s(&self) -> %sOut {self.reader.get_struct(%d)}"%(lname, node.struct.name, node.offset))

    def generate_struct_out(self, node: Value, lname: str) -> None:
        if node.inplace:
            raise ICE()
        self.output_doc(node, "    ")
        self.o("    set %s(value: %s) {" % (lname, node.struct.name))
        if node.optional:
            self.o("        this._setBit(%d, %d)" % (node.has_offset, node.has_bit))
        self.o(
            "        %s._write(this._writer, this._offset + %d, value)"
            % (node.struct.name, node.offset)
        )
        self.o("    }")
        self.o()

    def generate_table_in(self, node: Value, lname: str) -> None:
        if not node.table.empty:
            self.output_doc(node, "    ")
            self.o("    get %s() : %sIn | null {" % (lname, node.table.name))
            self.o(
                "        const [offset, size] = this._getPtr%s(%d, %sIn._MAGIC);"
                % ("Inplace" if node.inplace else "", node.offset, node.table.name)
            )
            self.o("        if (offset === 0) return null;")
            self.o(
                "        return new %sIn(this._reader, offset, size);" % (node.table.name,)
            )
            self.o("    }")
            self.o()

    def generate_union_table_in(self, node: Value, lname: str) -> None:
        if not node.table.empty:
            self.output_doc(node, "    ")
            self.o("    get %s() : %sIn | null {" % (lname, node.table.name))
            self.o("        if (!this.is%s) return null;" % (ucamel(lname)))
            self.o(
                "        const [offset, size] = this._getPtr(%sIn._MAGIC);"
                % (node.table.name)
            )
            self.o("        if (offset === 0) return null;")
            self.o(
                "        return new %sIn(this._reader, offset, size);" % (node.table.name,)
            )
            self.o("    }")
            self.o()

    def generate_table_out(self, node: Value, lname: str, size: int) -> None:
        if not node.inplace:
            self.output_doc(node, "    ")
            self.o(
                "    set %s(value: %sOut | %sIn) {"
                % (lname, node.table.name, node.table.name)
            )
            self.o("        if (value instanceof %sIn) {" % (node.table.name))
            self.o("            const v = value;")
            self.o(
                "            value = this._writer.constructTable(%sOut);" % node.table.name
            )
            self.o("            value._copy(v);")
            self.o("        }")
            self.o("        console.assert(value instanceof %sOut);" % (node.table.name))
            self.o("        this._setTable(%d, value);" % (node.offset))
            self.o("    }")
            self.o()
            self.output_doc(node, "    ")
            self.o("    add%s() : %sOut {" % (ucamel(lname), node.table.name))
            self.o(
                "        const res = this._writer.constructTable(%sOut);" % node.table.name
            )
            self.o("        this._setTable(%d, res);" % (node.offset,))
            self.o("        return res;")
            self.o("    }")
            self.o()
        elif not node.table.empty:
            self.output_doc(node, "    ")
            self.o("    set %s(value: %sIn) {" % (lname, node.table.name))
            self.o("        console.assert(value instanceof %sIn);" % (node.table.name))
            self.o("        this.add%s()._copy(value);" % (ucamel(lname),))
            self.o("    }")
            self.o()
            self.output_doc(node, "    ")
            self.o("    add%s() : %sOut {" % (ucamel(lname), node.table.name))
            self.o(
                "        console.assert(this._writer._size == this._offset + %s);" % size
            )
            self.o(
                "        this._setUint48(%d, %d);" % (node.offset, len(node.table.default))
            )
            self.o("        return new %sOut(this._writer, false);" % node.table.name)
            self.o("    }")
            self.o()
        else:
            self.output_doc(node, "    ")
            self.o("    add%s(self) {" % (ucamel(lname)))
            self.o("        this._setUint48(%d, %d);" % (node.offset, 0))
            self.o("    }")
            self.o()

    def generate_union_table_out(
        self, node: Value, lname: str, idx: int, inplace: bool
    ) -> None:
        table = node.table
        if table.empty:
            self.output_doc(node, "    ")
            self.o("    add%s() {" % (ucamel(lname)))
            self.o("        this._set(%d, 0);" % (idx))
            self.o("    }")
            self.o()
        elif not inplace:
            self.output_doc(node, "    ")
            self.o("    set %s(value: %sOut | %sIn) {" % (lname, table.name, table.name))
            self.o("        if (value instanceof %sIn) {" % (node.table.name))
            self.o("            const v = value;")
            self.o(
                "            value = this._writer.constructTable(%sOut);" % node.table.name
            )
            self.o("            value._copy(v);")
            self.o("        }")
            self.o("        console.assert(value instanceof %sOut);" % (node.table.name))
            self.o("        this._set(%d, value._offset - 10);" % (idx))
            self.o("    }")
            self.o()
            self.output_doc(node, "    ")
            self.o("    add%s() : %sOut {" % (ucamel(lname), table.name))
            self.o(
                "        const res = this._writer.constructTable(%sOut);" % node.table.name
            )
            self.o("        this._set(%d, res._offset - 10);" % (idx,))
            self.o("        return res;")
            self.o("    }")
            self.o()
        else:
            self.output_doc(node, "    ")
            self.o("    set %s(value: %sIn) {" % (lname, node.table.name))
            self.o("        console.assert(value instanceof %sIn);" % (node.table.name))
            self.o("        this.add%s()._copy(value);" % (ucamel(lname),))
            self.o("    }")
            self.o()
            self.output_doc(node, "    ")
            self.o("    add%s() : %sOut {" % (ucamel(lname), table.name))
            self.o("        console.assert(this._end == this._writer._size);")
            self.o("        this._set(%d, %d);" % (idx, table.bytes))
            self.o("        return new %sOut(this._writer, false)" % table.name)
            self.o("    }")
            self.o()

    def generate_text_in(self, node: Value, lname: str) -> None:
        self.output_doc(node, "    ")
        self.o("    get %s() : string | null {" % (lname))
        self.o(
            "        const [o, s] = this._getPtr%s(%d, scalgoproto.TEXT_MAGIC)"
            % ("Inplace" if node.inplace else "", node.offset)
        )
        self.o("        if (o === 0) return null;")
        self.o("        return this._reader._readText(o, s);")
        self.o("    }")
        self.o()

    def generate_union_text_in(self, node: Value, lname: str) -> None:
        self.output_doc(node, "    ")
        self.o("    get %s() : string | null {" % (lname))
        self.o("        if(!this.is%s) return null;" % ucamel(lname))
        self.o("        const [o, s] = this._getPtr(scalgoproto.TEXT_MAGIC)")
        self.o("        if (o === 0) return null;")
        self.o("        return this._reader._readText(o, s);")
        self.o("    }")
        self.o()

    def generate_text_out(self, node: Value, lname: str, size: int) -> None:
        self.output_doc(node, "    ")
        if node.inplace:
            self.o("    set %s(text: string) {" % (lname))
        else:
            self.o("    set %s(t: scalgoproto.TextOut | string) {" % (lname))
        if node.inplace:
            self.o(
                "        console.assert(this._writer._size == this._offset + %s);" % size
            )
            self.o("        this._addInplaceText(%d, text);" % (node.offset))
        else:
            self.o("        this._setText(%d, t);" % (node.offset))
        self.o("    }")
        self.o()

    def generate_union_text_out(
        self, node: Value, lname: str, idx: int, inplace: bool
    ) -> None:
        self.output_doc(node, "    ")
        if inplace:
            self.o("    set %s(value: string) {" % (lname))
        else:
            self.o("    set %s(value: scalgoproto.TextOut | string) {" % (lname))
        if inplace:
            self.o("        this._addInplaceText(%d, value);" % (idx))
        else:
            self.o("        this._setText(%d, value);" % (idx))
        self.o("}")
        self.o()

    def generate_bytes_in(self, node: Value, lname: str) -> None:
        self.output_doc(node, "    ")
        self.o("    get %s() : ArrayBuffer | null {" % (lname))
        self.o(
            "        const [o, s] = this._getPtr%s(%d, scalgoproto.BYTES_MAGIC)"
            % ("Inplace" if node.inplace else "", node.offset)
        )
        self.o("        if (o === 0) return null;")
        self.o("        const oo = (this._reader._data.byteOffset || 0) + o")
        self.o("        return this._reader._data.buffer.slice(oo, oo+s);")
        self.o("    }")
        self.o()

    def generate_union_bytes_in(self, node: Value, lname: str) -> None:
        self.output_doc(node, "    ")
        self.o("    get %s() : ArrayBuffer | null {" % (lname))
        self.o("        if (!this.is%s) return null;" % (ucamel(lname)))
        self.o("        const [o, s] = this._getPtr(scalgoproto.BYTES_MAGIC)")
        self.o("        if (o === 0) return null;")
        self.o("        const oo = (this._reader._data.byteOffset || 0) + o")
        self.o("        return this._reader._data.buffer.slice(oo, oo+s);")
        self.o("    }")
        self.o()

    def generate_bytes_out(self, node: Value, lname: str, size: int) -> None:
        self.output_doc(node, "    ")
        if node.inplace:
            self.o("    set %s(value: ArrayBuffer) {" % (lname))
        else:
            self.o("    set %s(value: scalgoproto.BytesOut | ArrayBuffer) {" % (lname))
        if node.inplace:
            self.o(
                "        console.assert(this._writer._size == this._offset + %s);" % (size)
            )
            self.o("        this._addInplaceBytes(%d, value);" % (node.offset))
        else:
            self.o("        this._setBytes(%d, value);" % (node.offset))
        self.o("    }")
        self.o()

    def generate_union_bytes_out(
        self, node: Value, lname: str, idx: int, inplace: bool
    ) -> None:
        self.output_doc(node, "        ")
        if inplace:
            self.o("    set %s(value: ArrayBuffer) {" % (lname))
        else:
            self.o("    set %s(value: scalgoproto.BytesOut | ArrayBuffer) {" % (lname))
        if inplace:
            self.o("        this._addInplaceBytes(%d, value);" % (idx))
        else:
            self.o("        this._setBytes(%d, value);" % (idx))
        self.o("    }")
        self.o()

    def generate_union_in(self, node: Value, lname: str, table: Table) -> None:
        self.output_doc(node, "    ")
        self.o("    get %s() : %sIn  {" % (lname, node.union.name))
        if node.inplace:
            self.o(
                "        return new %sIn(this._reader, this._getUint16(%d, 0), this._offset + this._size, this._getUint48(%d))"
                % (node.union.name, node.offset, node.offset + 2)
            )
        else:
            self.o(
                "        return new %sIn(this._reader, this._getUint16(%d, 0), this._getUint48(%d))"
                % (node.union.name, node.offset, node.offset + 2)
            )
        self.o("    }")
        self.o()

    def generate_union_out(self, node: Value, lname: str, table: Table) -> None:
        self.o(
            "    get %s() : %s%sOut {"
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
        self.o("    }")
        self.o()

    def generate_value_in(self, table: Table, node: Value) -> None:
        lname = snake(self.value(node.identifier))
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
        self.o("    _copy(i:%sIn) {" % union.name)
        self.o("        switch(i.type) {")
        for node in union.members:
            lname = self.value(node.identifier)
            self.o("        case %sType.%s:" % (union.name, lname.upper()))
            if node.table and node.table.empty:
                self.o("            this.add%s();" % (ucamel(lname)))
            else:
                self.o("            this.%s = i.%s!;" % (lname, lname))
            self.o("            break;")
        self.o("        }")
        self.o("    }")
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
        self.o("    NONE,")
        for member in union.members:
            if not isinstance(member, (Table, Value)):
                raise ICE()
            self.o("    %s," % (self.value(member.identifier).upper()))
        self.o("}")
        self.o()

        self.output_doc(union, "    ")
        self.o("export class %sIn extends scalgoproto.UnionIn {" % union.name)
        self.o(
            "    /** Private constructor. Call factory methods on scalgoproto.Reader to construct instances */"
        )
        self.o(
            "    constructor(reader: scalgoproto.Reader, type: number, offset: number, size: number|null = null) {"
        )

        self.o("        super(reader, type, offset, size);")
        self.o("    }")
        self.o()

        self.o("    get type() : %sType {" % (union.name))
        self.output_doc(union, "    ")
        self.o("        return this._type as %sType;" % (union.name))
        self.o("    }")
        self.o()
        for member in union.members:
            n = self.value(member.identifier)
            lname = lcamel(n)
            self.o("    get is%s() : boolean {" % (ucamel(lname)))
            self.o("        return this.type == %sType.%s;" % (union.name, n.upper()))
            self.o("    }")
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
        self.o("    static readonly _IN = %sIn;" % (union.name))
        self.o(
            "    /***Private constructor. Call factory methods on scalgoproto.Writer to construct instances*/"
        )
        self.o(
            "    constructor(writer: scalgoproto.Writer, offset: number, end: number = 0) {"
        )
        self.o("        super(writer, offset, end);")
        self.o("    }")
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
            "    /** Private constructor. Call factory methods on scalgoproto.Writer to construct instances */"
        )
        self.o(
            "    constructor(writer: scalgoproto.Writer, offset: number, end: number = 0) {"
        )

        self.o("        super(writer, offset, end);")
        self.o("    }")
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
        self.o("    _copy(i:%sIn) {" % table.name)
        for ip in (True, False):
            for node in table.members:
                lname = lcamel(self.value(node.identifier))
                uname = ucamel(lname)
                if bool(node.inplace) != ip:
                    continue
                if node.list_:
                    self.o(
                        "        if (i.%s !== null) this.add%s(i.%s.length)._copy(i.%s);"
                        % (lname, uname, lname, lname)
                    )
                elif (
                    node.optional
                    or node.enum
                    or node.type_.type == TokenType.TEXT
                    or node.type_.type == TokenType.BYTES
                ):
                    self.o(
                        "        if (i.%s !== null) this.%s = i.%s;" % (lname, lname, lname)
                    )
                elif (
                    node.type_.type in typeMap
                    or node.type_.type == TokenType.BOOL
                    or node.enum
                    or node.struct
                ):
                    self.o("        this.%s = i.%s;" % (lname, lname))
                elif node.table:
                    if node.table.empty:
                        self.o("         if (i.%s !== null) this.add%s();" % (lname, uname))
                    else:
                        self.o(
                            "         if (i.%s !== null) this.add%s()._copy(i.%s);"
                            % (lname, uname, lname)
                        )
                elif node.union:
                    self.o("        this.%s._copy(i.%s);" % (lname, lname))
                else:
                    raise ICE()
        self.o("    }")
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

        self.output_doc(table, "")
        self.o("struct %s<'a> {}" % table.name)
        self.output_doc(table, "")
        self.o("struct %sIn<'a> {" % table.name)
        self.o("    reader: scalgo_proto::Reader<'a>,")
        self.o("}")
        self.o("impl<'a> %sIn<'a> {" % table.name)
        for node in table.members:
            self.generate_value_in(table, node)
        self.o("}")

        self.o("impl<'a> fmt::Debug for %sIn<'a> {"%table.name)
        self.o("    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {")
        self.o("        write!(")
        self.o("            f, \"%s {{ %s }}\","%(table.name, ", ".join(["%s: {:?}"%self.value(v.identifier) for v in table.members])))
        self.o("            %s"%", ".join(["self.%s()"%self.value(v.identifier) for v in table.members]))
        self.o("        )")
        self.o("    }")
        self.o("}") 

        self.o("impl<'a> scalgo_proto::TableInFactory<'a> for %s {"%table.name)
        self.o("    type T = %sIn<'a>;"%table.name)
        self.o("    fn magic() -> u32 {0x%08X}" % table.magic)
        self.o("    fn new(reader: scalgo_proto::Reader<'a>) -> Self::T {Self::T { reader }}")
        self.o("}")


        # Generate Table writer
        self.output_doc(table, "")
        self.o("struct %sOut<'a> {" % table.name)
        self.o("    arena: &'a scalgo_proto::Arena,")
        self.o("    offset: usize,")
        self.o("}")
        self.o("impl<'a> %sOut<'a> {" % table.name)
        for node in table.members:
            self.generate_value_out(table, node)
        #self.generate_table_copy(table)
        self.o("}")
        self.o("impl<'a> scalgo_proto::TableOut for %sOut<'a> {")
        self.o("    fn offset(&self) -> usize {self.offset}")
        self.o("}")
        self.o("impl<'a> scalgo_proto::TableOutFactory<'a> for %s {"%table.name)
        self.o("    type T = %sIn<'a>;"%table.name)
        self.o("    fn magic() -> u32 {0x%08X}" % table.magic)
        self.o("    fn size() -> usize {%d}" % table.bytes)
        self.o("    fn new(arena: &'a scalgo_proto::Arena, offset: usize) -> Self::T {Self::T { arena, offset }}")
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
        self.o("pub struct %s {}" % node.name)
        self.output_doc(node, "")
        self.o("pub struct %sIn<'a> {"%node.name)
        self.o("    bytes: &'a [u8; %s],"%node.bytes)
        self.o("}")
        self.o("impl <'a> %sIn<'a> {"%node.name)
        for v in node.members:
            if not isinstance(v, Value):
                raise ICE()
            if v.type_.type == TokenType.BOOL:
                self.o("    pub fn %s(&self) -> bool {scalgo_proto::to_bool(self.bytes[%d])}"%(self.value(v.identifier), v.offset))
            elif v.type_.type in typeMap:
                self.o("    pub fn %s(&self) -> %s {unsafe{scalgo_proto::to_pod(&self.bytes[%d..%d])}}"%(
                    self.value(v.identifier), typeMap[v.type_.type][1], v.offset, v.offset+v.bytes
                ))
            elif v.struct:
                self.o("    pub fn %s(&self) -> %sIn<'a> {unsafe{scalgo_proto::to_struct::<%s>(&self.bytes[%d..%d])}}"%(
                    self.value(v.identifier), v.struct.name, v.struct.name, v.offset, v.offset + v.bytes
                ))
            elif v.enum:
                self.o("    pub fn %s(&self) -> Option<%s> {unsafe{scalgo_proto::to_enum(self.bytes[%d], %d)}}"%(
                    self.value(v.identifier), v.enum.name, v.enum.offset, len(v.enum.members)
                ))
            else:
                raise ICE()
        self.o("}")
        self.o("impl<'a> fmt::Debug for %sIn<'a> {"%node.name)
        self.o("    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {")
        self.o("        write!(")
        self.o("            f, \"%s {{ %s }}\","%(node.name, ", ".join(["%s: {:?}"%self.value(v.identifier) for v in node.members])))
        self.o("            %s"%", ".join(["self.%s()"%self.value(v.identifier) for v in node.members]))
        self.o("        )")
        self.o("    }")
        self.o("}") 
        self.o("impl<'a> scalgo_proto::StructInFactory<'a> for %s {"%node.name)
        self.o("    type T = %sIn<'a>;"%node.name)
        self.o("    type B = [u8; %s];"%node.bytes)
        self.o("    fn new(bytes: &'a Self::B) -> Self::T {Self::T{bytes}}")
        self.o("}")
        self.o("pub struct %sOut<'a> {"%node.name)
        self.o("    arena: &'a scalgo_proto::Arena,")
        self.o("    offset: usize,")
        self.o("}")
        self.o("impl <'a> %sOut<'a> {"%node.name)
        for v in node.members:
            if not isinstance(v, Value):
                raise ICE()
            if v.type_.type == TokenType.BOOL:
                self.o("    pub fn %s(&mut self, v: bool) {unsafe{self.arena.set_bool(self.offset + %d, v)}}"%(
                    self.value(v.identifier), v.offset
                ))
            elif v.type_.type in typeMap:
                self.o("    pub fn %s(&mut self, v: %s) {unsafe{self.arena.set_pod(self.offset + %d, &v)}}"%(
                    self.value(v.identifier), typeMap[v.type_.type][1], v.offset
                ))
            elif v.struct:
                 self.o("    pub fn %s(&mut self) -> %sOut<'a> {<%s as scalgo_proto::StructOutFactory<'a>>::new(&self.arena, self.offset + %d}}"%(
                    self.value(v.identifier), v.struct.name, v.struct.name, v.offset
                ))
            elif v.enum:
                self.o("    pub fn %s(&mut self, v: Option<%s>) {unsafe{self.arena.set_enum(self.offset + %d, v)}}"%(
                    self.value(v.identifier), v.enum.name, v.offset
                ))
            else:
                raise ICE()
        self.o("}")
        self.o("impl<'a> scalgo_proto::StructOutFactory<'a> for %s {"%node.name)
        self.o("    type T = %sIn<'a>;"%node.name)
        self.o("    fn new(arena: &'a Arena, offset: usize) -> Self::T {Self::T{arena, offset}}")
        self.o("}")
        self.o()


    def generate_enum(self, node: Enum) -> None:
        self.output_doc(node, "")
        self.o("#[repr(u8)]")
        self.o("#[derive(Copy, Clone, Debug)]")
        self.o("pub enum %s {" % node.name)
        for ev in node.members:
            self.o("    %s," % (usnake(self.value(ev.identifier))))
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
                i = imports.setdefault(u.document, set())
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
    out = open(os.path.join(args.output, "%s.rs" % documents.root.name), "w")
    try:
        ast = p.parse_document()
        if not annotate(documents, ast):
            print("Schema is invalid")
            return 1
        g = Generator(documents, out)
        print("//! This file was generated by scalgoprotoc", file=out)
        print("", file=out)

        g.generate(ast)
        return 0
    except ParseError as err:
        err.describe(documents)
    return 1


def setup(subparsers) -> None:
    cmd = subparsers.add_parser("rust", help="Generate rust code")
    cmd.add_argument("schema", help="schema to generate things from")
    cmd.add_argument("output", help="where do we store the output")
    cmd.set_defaults(func=run)
