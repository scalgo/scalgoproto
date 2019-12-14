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


def byte_encode(b: bytes) -> str:
    x = []
    m = {
        ord("\r"): "\\r",
        ord("\n"): "\\n",
        ord("\0"): "\\0",
        ord('"'): '\\"',
        ord("\\"): "\\\\",
    }
    for c in b:
        if c in m:
            x.append(m[c])
        elif 32 <= c <= 126:
            x.append(chr(c))
        else:
            x.append("\\x%02x" % c)
    return "".join(x)


def add_lifetime(t: str) -> str:
    if not "<" in t:
        t = t + "<>"
    l, r = t.split("<", 1)
    return "%s<'a, %s" % (l, r)


class Generator:
    def __init__(self, documents: Documents, out: TextIO) -> None:
        self.documents: Documents = documents
        self.out: TextIO = out

    def out_list_type(self, node: Value) -> str:
        if node.type_.type == TokenType.BOOL:
            return "scalgo_proto::BoolType"
        elif node.type_.type in typeMap:
            return "scalgo_proto::PodType<%s>" % (typeMap[node.type_.type].p)
        elif node.struct:
            return "scalgo_proto::StructType<%s>" % (node.struct.name)
        elif node.enum:
            return "scalgo_proto::EnumType<%s>" % (node.enum.name)
        elif node.table:
            return "scalgo_proto::TableType<%s>" % (node.table.name)
        elif node.union:
            return "scalgo_proto::UnionType<%s>" % (node.union.name)
        elif node.type_.type == TokenType.TEXT:
            return "scalgo_proto::TextType"
        elif node.type_.type == TokenType.BYTES:
            return "scalgo_proto::BytesType"
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
                "        return this._reader._getEnumList<%s>(%s)"
                % (node.enum.name, os),
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

    def list_access_type(self, node: Value) -> Tuple[str]:
        if node.type_.type == TokenType.BOOL:
            return "scalgo_proto::BoolListAccess"
        elif node.type_.type in typeMap:
            return "scalgo_proto::PodListAccess<%s>" % (typeMap[node.type_.type].p)
        elif node.struct:
            return "scalgo_proto::StructListAccess<%s>" % (node.struct.name)
        elif node.enum:
            return "scalgo_proto::EnumListAccess<%s>" % (node.enum.name)
        elif node.table:
            return "scalgo_proto::TableListAccess<%s>" % (node.table.name)
        elif node.union:
            return "scalgo_proto::UnionListAccess<%s>" % (node.union.name)
        elif node.type_.type == TokenType.TEXT:
            return "scalgo_proto::TextListAccess"
        elif node.type_.type == TokenType.BYTES:
            return "scalgo_proto::BytesListAccess"
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
        tn = self.list_access_type(node)
        self.output_doc(node, "    ")
        self.o(
            "    pub fn %s(&self) -> scalgo_proto::Result<Option<scalgo_proto::ListIn<%s>>> {"
            % (lname, tn)
        )
        self.o(
            "        self._reader.get_list%s::<%s>(%d)"
            % ("_inplace" if node.inplace else "", tn, node.offset)
        )
        self.o("    }")

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
        # it = "scalgoproto.ListIn<%s>" % self.in_list_help(node, "")[0]
        ot = self.out_list_type(node)
        if not node.inplace:
            self.output_doc(node, "    ")
            self.o(
                "    pub fn set_%s(&mut self, v: Option<&scalgo_proto::ListOut::<'a, %s, scalgo_proto::Normal>>) { self._slice.set_list( %d, v) }"
                % (lname, ot, node.offset)
            )
            self.output_doc(node, "    ")
            self.o(
                "    pub fn add_%s(&mut self, len: usize) -> scalgo_proto::ListOut::<'a, %s, scalgo_proto::Normal> { self._slice.add_list::<%s>(%d, len)}"
                % (lname, ot, ot, node.offset)
            )
        else:
            self.output_doc(node, "    ")
            self.o(
                "    pub fn add_%s(&mut self, len: usize) -> scalgo_proto::ListOut::<'a, %s, scalgo_proto::Inplace> { self._slice.add_list_inplace::<%s>(%d, len)}"
                % (lname, ot, ot, node.offset)
            )

    def generate_union_list_out(
        self, node: Value, lname: str, idx: int, inplace: bool
    ) -> None:
        ot = self.out_list_type(node)
        if not inplace:
            self.output_doc(node, "    ")
            self.o(
                "    pub fn set_%s(&mut self, v: &scalgo_proto::ListOut<'a, %s, scalgo_proto::Normal>) { self._slice.set_pod::<u16>(0, &%d); self._slice.set_list(2, Some(v))}"
                % (lname, ot, idx)
            )
            self.output_doc(node, "    ")
            self.o(
                "    pub fn add_%s(&mut self, len: usize) -> scalgo_proto::ListOut::<'a, %s, scalgo_proto::Normal> { self._slice.set_pod::<u16>(0, &%d); self._slice.add_list::<%s>(2, len)}"
                % (lname, ot, idx, ot)
            )
        else:
            self.output_doc(node, "    ")
            self.o(
                "    pub fn add_%s(&mut self, len: usize) -> scalgo_proto::ListOut::<'a, %s, scalgo_proto::Inplace> { self._slice.set_pod::<u16>(0, &%d); self._slice.add_list_inplace::<%s>(2, len)}"
                % (lname, ot, idx, ot)
            )

    def generate_bool_in(self, node: Value, lname: str) -> None:
        if node.inplace:
            raise ICE()
        self.output_doc(node, "    ")
        if node.optional:
            self.o(
                "    pub fn %s(&self) -> Option<bool> {if self._reader.get_bit(%d, %d) {Some(self._reader.get_bit(%d, %d))} else {None}}"
                % (lname, node.has_offset, node.has_bit, node.offset, node.bit)
            )
        else:
            self.o(
                "    pub fn %s(&self) -> bool {self._reader.get_bit(%d, %d)}"
                % (lname, node.offset, node.bit)
            )

    def generate_bool_out(self, node: Value, lname: str) -> None:
        self.output_doc(node, "    ")
        if node.optional:
            self.o(
                "    pub fn %s(&mut self, v : Option<bool>) {match v {None => self._slice.set_bit(%d, %d, false), Some(b) => {self._slice.set_bit(%d, %d, true); self._slice.set_bit(%d, %d, b)}}}"
                % (
                    lname,
                    node.has_offset,
                    node.has_bit,
                    node.has_offset,
                    node.has_bit,
                    node.offset,
                    node.bit,
                )
            )
        else:
            self.o(
                "    pub fn %s(&mut self, v : bool) {self._slice.set_bit(%d, %d, v)}"
                % (lname, node.offset, node.bit)
            )

    def generate_basic_in(self, node: Value, lname: str) -> None:
        if node.inplace:
            raise ICE()
        ti = typeMap[node.type_.type]
        self.output_doc(node, "    ")
        if node.optional:
            if node.type_.type in (TokenType.F32, TokenType.F64):
                self.o(
                    "    pub fn %s(&self) -> Option<%s> {match self._reader.get_pod::<%s>(%d) {None => None, Some(v) if v.is_nan() => None, Some(v) => Some(v)}}"
                    % (lname, ti.p, ti.p, node.offset)
                )
            else:
                self.o(
                    "    pub fn %s(&self) -> Option<%s> {if self._reader.get_bit(%d, %d) {self._reader.get_pod(%d)} else {None}}"
                    % (lname, ti.p, node.has_offset, node.has_bit, node.offset)
                )
        else:
            self.o(
                "    pub fn %s(&self) -> %s {self._reader.get_pod(%d).unwrap_or(%s)}"
                % (
                    lname,
                    ti.p,
                    node.offset,
                    node.parsed_value
                    if not math.isnan(node.parsed_value)
                    else "std::%s::NAN" % ti.p,
                )
            )

    def generate_basic_out(self, node: Value, lname: str) -> None:
        if node.inplace:
            raise ICE()
        ti = typeMap[node.type_.type]
        self.output_doc(node, "    ")
        if node.optional and ti.p in ("f32", "f64"):
            self.o(
                "    pub fn %s(&mut self, v : Option<%s>) {match v {None => self._slice.set_pod(%d, &std::%s::NAN), Some(b) => self._slice.set_pod(%d, &b)}}"
                % (lname, ti.p, node.offset, ti.p, node.offset)
            )
        elif node.optional:
            self.o(
                "    pub fn %s(&mut self, v : Option<%s>) {match v {None => self._slice.set_bit(%d, %d, false), Some(b) => {self._slice.set_bit(%d, %d, true); self._slice.set_pod(%d, &b)}}}"
                % (
                    lname,
                    ti.p,
                    node.has_offset,
                    node.has_bit,
                    node.has_offset,
                    node.has_bit,
                    node.offset,
                )
            )
        else:
            self.o(
                "    pub fn %s(&mut self, v : %s) {self._slice.set_pod(%d, &v)}"
                % (lname, ti.p, node.offset)
            )

    def generate_enum_in(self, node: Value, lname: str) -> None:
        if node.inplace:
            raise ICE()
        self.output_doc(node, "    ")
        self.o(
            "    pub fn %s(&self) -> Option<%s> {self._reader.get_enum(%d, %d)}"
            % (lname, node.enum.name, node.offset, node.parsed_value)
        )

    def generate_enum_out(self, node: Value, lname: str) -> None:
        if node.inplace:
            raise ICE()
        self.output_doc(node, "    ")
        self.o(
            "    pub fn %s(&mut self, v: Option<%s>) {self._slice.set_enum(%d, v)}"
            % (lname, node.enum.name, node.offset)
        )

    def generate_struct_in(self, node: Value, lname: str) -> None:
        if node.inplace:
            raise ICE()
        self.output_doc(node, "    ")
        if node.optional:
            self.o(
                "    pub fn %s(&self) -> Option<%sIn> {if self._reader.get_bit(%d, %d) {Some(self._reader.get_struct::<%s>(%d))} else {None}}"
                % (
                    lname,
                    node.struct.name,
                    node.has_offset,
                    node.has_bit,
                    node.struct.name,
                    node.offset,
                )
            )
        else:
            self.o(
                "    pub fn %s(&self) -> %sIn {self._reader.get_struct::<%s>(%d)}"
                % (lname, node.struct.name, node.struct.name, node.offset)
            )

    def generate_struct_out(self, node: Value, lname: str) -> None:
        if node.inplace:
            raise ICE()
        self.output_doc(node, "    ")

        if node.optional:
            self.o(
                "    pub fn %s<'b>(&'b mut self) -> %sOut<'b> {self._slice.set_bit(%d, %d, true); self._slice.get_struct::<'b, %s>(%d)}"
                % (
                    lname,
                    node.struct.name,
                    node.has_offset,
                    node.has_bit,
                    node.struct.name,
                    node.offset,
                )
            )
            pass
        else:
            self.o(
                "    pub fn %s<'b>(&'b mut self) -> %sOut<'b> {self._slice.get_struct::<'b, %s>(%d)}"
                % (lname, node.struct.name, node.struct.name, node.offset)
            )

    def generate_table_in(self, node: Value, lname: str) -> None:
        if not node.inplace:
            self.output_doc(node, "    ")
            self.o(
                "    pub fn %s(&self) -> scalgo_proto::Result<Option<%sIn>> {self._reader.get_table::<%s>(%d)}"
                % (lname, node.table.name, node.table.name, node.offset)
            )
        else:
            self.output_doc(node, "    ")
            self.o(
                "    pub fn %s(&self) -> scalgo_proto::Result<Option<%sIn>> {self._reader.get_table_inplace::<%s>(%d)}"
                % (lname, node.table.name, node.table.name, node.offset)
            )

    def generate_table_out(self, node: Value, lname: str) -> None:
        if not node.inplace:
            self.output_doc(node, "    ")
            self.o(
                "    pub fn set_%s(&mut self, v: Option<& %sOut<'a, scalgo_proto::Normal>>) {self._slice.set_table(%d, v)}"
                % (lname, node.table.name, node.offset)
            )
            # TODO (jakob) add table copy

            self.output_doc(node, "    ")
            self.o(
                "    pub fn add_%s(&mut self) -> %sOut<'a, scalgo_proto::Normal> {self._slice.add_table::<%s>(%d)}"
                % (lname, node.table.name, node.table.name, node.offset)
            )
        elif not node.table.empty:
            self.output_doc(node, "    ")
            self.o(
                "    pub fn add_%s(&mut self) -> %sOut<'a, scalgo_proto::Inplace> {self._slice.add_table_inplace::<%s>(%d)}"
                % (lname, node.table.name, node.table.name, node.offset)
            )
        else:
            self.output_doc(node, "    ")
            self.o("    add%s(&mut self) {" % (ucamel(lname)))
            self.o("        this._setUint48(%d, %d);" % (node.offset, 0))
            self.o("    }")
            self.o()

    def generate_union_table_out(
        self, node: Value, lname: str, idx: int, inplace: bool
    ) -> None:
        table = node.table
        if table.empty:
            self.output_doc(node, "    ")
            self.o(
                "    pub fn add_%s(&mut self) {self._slice.set_pod::<u16>(0, &%d); self._slice.set_u48(2, 0);}"
                % (lname, idx)
            )
        elif not inplace:
            self.output_doc(node, "    ")
            self.o(
                "    pub fn set_%s(&mut self, v: &%sOut<'a, scalgo_proto::Normal>) {self._slice.set_pod::<u16>(0, &%d); self._slice.set_table(2, Some(v));}"
                % (lname, table.name, idx)
            )
            self.output_doc(node, "    ")
            self.o(
                "    pub fn add_%s(&mut self) -> %sOut<'a, scalgo_proto::Normal> {let a = self._slice.arena.create_table::<%s>(); self.set_%s(&a); a}"
                % (lname, table.name, table.name, lname)
            )
        else:
            self.output_doc(node, "    ")
            self.o(
                "    pub fn add_%s(&mut self) -> %sOut<'a, scalgo_proto::Inplace> {self._slice.set_pod::<u16>(0, &%d); self._slice.add_table_inplace::<%s>(2)}"
                % (lname, table.name, idx, table.name)
            )

    def generate_text_in(self, node: Value, lname: str) -> None:
        self.output_doc(node, "    ")
        self.o(
            "    pub fn %s(&self) -> scalgo_proto::Result<Option<&str>> {self._reader.get_text%s(%d)}"
            % (lname, "_inplace" if node.inplace else "", node.offset)
        )

    def generate_text_out(self, node: Value, lname: str) -> None:
        self.output_doc(node, "    ")
        if not node.inplace:
            self.output_doc(node, "    ")
            self.o(
                "    pub fn set_%s(&mut self, v: Option<&scalgo_proto::TextOut<'a>>) {self._slice.set_text(%d, v)}"
                % (lname, node.offset)
            )
            self.output_doc(node, "    ")
            self.o(
                "    pub fn add_%s(&mut self, v: & str) -> scalgo_proto::TextOut<'a> {self._slice.add_text(%d, v)}"
                % (lname, node.offset)
            )
        else:
            self.output_doc(node, "    ")
            self.o(
                "    pub fn add_%s(&mut self, v: & str) {self._slice.add_text_inplace(%d, v)}"
                % (lname, node.offset)
            )

    def generate_union_text_out(
        self, node: Value, lname: str, idx: int, inplace: bool
    ) -> None:
        self.output_doc(node, "    ")
        if inplace:
            self.o("    pub fn add_%s(&mut self, v: &str) {}" % (lname))  # TODO(jakobt)
        else:
            self.o(
                "    pub fn set_%s(&mut self, v: &scalgo_proto::TextOut<'a>) {self._slice.set_pod::<u16>(0, &%d); self._slice.set_text(2, Some(v));}"
                % (lname, idx)
            )
            self.o(
                "    pub fn add_%s(&mut self, v: &str) -> scalgo_proto::TextOut {let a = self._slice.arena.create_text(v); self.set_%s(&a); a}"
                % (lname, lname)
            )

    def generate_bytes_in(self, node: Value, lname: str) -> None:
        self.output_doc(node, "    ")
        self.o(
            "    pub fn %s(&self) -> scalgo_proto::Result<Option<&[u8]>> {self._reader.get_bytes%s(%d)}"
            % (lname, "_inplace" if node.inplace else "", node.offset)
        )

    def generate_bytes_out(self, node: Value, lname: str) -> None:
        self.output_doc(node, "    ")
        if not node.inplace:
            self.o(
                "    pub fn add_%s(&mut self, bytes: &[u8]) -> scalgo_proto::BytesOut<'a> {self._slice.add_bytes(%d, bytes)}"
                % (lname, node.offset)
            )
            self.o(
                "    pub fn set_%s(&mut self, bytes: Option<&scalgo_proto::BytesOut<'a>>) {self._slice.set_bytes(%d, bytes)}"
                % (lname, node.offset)
            )
        else:
            self.o(
                "    pub fn add_%s(&mut self, bytes: &[u8]) {self._slice.add_bytes_inplace(%d, bytes)}"
                % (lname, node.offset)
            )

    def generate_union_bytes_out(
        self, node: Value, lname: str, idx: int, inplace: bool
    ) -> None:
        self.output_doc(node, "        ")
        if inplace:
            self.o(
                "    pub fn add_%s(&mut self, v: &[u8]) {}" % (lname)
            )  # TODO(jakobt)
        else:
            self.o(
                "    pub fn set_%s(&mut self, v: &scalgo_proto::BytesOut<'a>) {self._slice.set_pod::<u16>(0, &%d); self._slice.set_bytes(2, Some(v));}"
                % (lname, idx)
            )
            self.o(
                "    pub fn add_%s(&mut self, v: &[u8]) -> scalgo_proto::BytesOut {let a = self._slice.arena.create_bytes(v); self.set_%s(&a); a}"
                % (lname, lname)
            )

    def generate_union_in(self, node: Value, lname: str, table: Table) -> None:
        self.output_doc(node, "    ")
        self.o(
            "    pub fn %s(&self) -> scalgo_proto::Result<%sIn<'a>> {self._reader.get_union%s::<%s>(%d)}"
            % (
                lname,
                node.union.name,
                "_inplace" if node.inplace else "",
                node.union.name,
                node.offset,
            )
        )

    def generate_union_out(self, node: Value, lname: str, table: Table) -> None:
        self.o(
            "    pub fn %s<'b>(&'b mut self) -> %sOut<'b, %s> {self._slice.get_union%s::<%s>(%d)}"
            % (
                lname,
                node.union.name,
                "scalgo_proto::Inplace" if node.inplace else "scalgo_proto::Normal",
                "_inplace" if node.inplace else "",
                node.union.name,
                node.offset,
            )
        )

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
        lname = snake(self.value(node.identifier))
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
            self.generate_table_out(node, lname)
        elif node.union:
            self.generate_union_out(node, lname, table)
        elif node.type_.type == TokenType.TEXT:
            self.generate_text_out(node, lname)
        elif node.type_.type == TokenType.BYTES:
            self.generate_bytes_out(node, lname)
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

        self.output_doc(union, "    ")
        self.o("#[derive(Debug)]")
        self.o("pub enum %sIn<'a> {" % (union.name))
        self.o("    NONE,")
        for member in union.members:
            if not isinstance(member, (Table, Value)):
                raise ICE()
            uname = self.value(member.identifier).upper()
            if member.list_:
                self.o(
                    "    %s(scalgo_proto::ListIn<'a, %s>),"
                    % (uname, add_lifetime(self.list_access_type(member)))
                )
            elif member.table:
                self.o("    %s(%sIn<'a>)," % (uname, member.table.name))
            elif member.type_.type == TokenType.BYTES:
                self.o("    %s(&'a [u8])," % (uname))
            elif member.type_.type == TokenType.TEXT:
                self.o("    %s(&'a str)," % (uname))
            else:
                raise ICE()
        self.o("}")
        self.o()
        self.output_doc(union, "    ")
        self.o("pub struct %sOut<'a, P: scalgo_proto::Placement> {" % (union.name))
        self.o("    _slice: scalgo_proto::ArenaSlice<'a>,")
        self.o("    _p: std::marker::PhantomData<P>,")
        self.o("}")
        self.o("impl<'a> %sOut<'a, scalgo_proto::Normal> {" % (union.name))
        self.o(
            "    pub fn set_none(&mut self) {self._slice.set_pod::<u16>(0, &0); self._slice.set_u48(2, 0);}"
        )
        for idx, member in enumerate(union.members):
            llname = snake(self.value(member.identifier))
            if member.list_:
                self.generate_union_list_out(member, llname, idx + 1, False)
            elif member.table:
                self.generate_union_table_out(member, llname, idx + 1, False)
            elif member.type_.type == TokenType.BYTES:
                self.generate_union_bytes_out(member, llname, idx + 1, False)
            elif member.type_.type == TokenType.TEXT:
                self.generate_union_text_out(member, llname, idx + 1, False)
            else:
                raise ICE()
        self.o("}")

        # TODO(jakobt) copy union
        self.o("impl<'a> %sOut<'a, scalgo_proto::Inplace> {" % (union.name))
        self.o(
            "    pub fn set_none(&mut self) {self._slice.set_pod::<u16>(0, &0); self._slice.set_u48(2, 0);}"
        )
        for idx, member in enumerate(union.members):
            llname = snake(self.value(member.identifier))
            if member.list_:
                self.generate_union_list_out(member, llname, idx + 1, True)
            elif member.table:
                self.generate_union_table_out(member, llname, idx + 1, True)
            elif member.type_.type == TokenType.BYTES:
                self.generate_union_bytes_out(member, llname, idx + 1, True)
            elif member.type_.type == TokenType.TEXT:
                self.generate_union_text_out(member, llname, idx + 1, True)
            else:
                raise ICE()
        self.o("}")
        # TODO(jakobt) copy union inplace

        self.o("#[derive(Copy, Clone)]")
        self.o("pub struct %s {}" % union.name)
        self.o("impl<'a> scalgo_proto::UnionFactory<'a> for %s {" % union.name)
        self.o("    type In = %sIn<'a>;" % union.name)
        self.o("    type Out = %sOut<'a, scalgo_proto::Normal>;" % union.name)
        self.o("    type InplaceOut = %sOut<'a, scalgo_proto::Inplace>;" % union.name)
        self.o(
            "    fn new_in(t: u16, magic: Option<u32>, offset: usize, size: usize, reader: &scalgo_proto::Reader<'a>) -> scalgo_proto::Result<Self::In> {"
        )
        self.o("        match t {")
        for i, member in enumerate(union.members):
            uname = self.value(member.identifier).upper()
            if member.list_:
                self.o(
                    "        %d => Ok(Self::In::%s(reader.get_list_union(magic, offset, size)?)),"
                    % (i + 1, uname)
                )
            elif member.table:
                self.o(
                    "        %d => Ok(Self::In::%s(reader.get_table_union::<%s>(magic, offset, size)?)),"
                    % (i + 1, uname, member.table.name)
                )
            elif member.type_.type == TokenType.BYTES:
                self.o(
                    "        %d => Ok(Self::In::%s(reader.get_bytes_union(magic, offset, size)?)),"
                    % (i + 1, uname)
                )
            elif member.type_.type == TokenType.TEXT:
                self.o(
                    "        %d => Ok(Self::In::%s(reader.get_text_union(magic, offset, size)?)),"
                    % (i + 1, uname)
                )
            else:
                self.o("        %d => Ok(Self::In::NONE)," % (i + 1))
        self.o("        _ => Ok(Self::In::NONE),")
        self.o("        }")
        self.o("    }")
        self.o("    fn new_out(slice: scalgo_proto::ArenaSlice<'a>) -> Self::Out {")
        self.o("        Self::Out{_slice: slice, _p: std::marker::PhantomData{}}")
        self.o("    }")
        self.o(
            "    fn new_inplace_out(slice: scalgo_proto::ArenaSlice<'a>) -> Self::InplaceOut {"
        )
        self.o(
            "        Self::InplaceOut{_slice: slice, _p: std::marker::PhantomData{}}"
        )
        self.o("    }")
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
                        "        if (i.%s !== null) this.%s = i.%s;"
                        % (lname, lname, lname)
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
                        self.o(
                            "         if (i.%s !== null) this.add%s();" % (lname, uname)
                        )
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

        self.output_doc(table, "")
        self.o("pub struct %sIn<'a> {" % table.name)
        self.o("    _reader: scalgo_proto::Reader<'a>,")
        self.o("}")
        self.o("impl<'a> %sIn<'a> {" % table.name)
        for node in table.members:
            self.generate_value_in(table, node)
        self.o("}")

        self.o("impl<'a> fmt::Debug for %sIn<'a> {" % table.name)
        self.o("    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {")
        self.o("        write!(")
        self.o(
            '            f, "%s {{ %s }}",'
            % (
                table.name,
                ", ".join(
                    [
                        "%s: {:?}" % snake(self.value(v.identifier))
                        for v in table.members
                    ]
                ),
            )
        )
        self.o(
            "            %s"
            % ", ".join(
                ["self.%s()" % snake(self.value(v.identifier)) for v in table.members]
            )
        )
        self.o("        )")
        self.o("    }")
        self.o("}")

        # Generate Table writer
        self.output_doc(table, "")
        self.o("pub struct %sOut<'a, P: scalgo_proto::Placement> {" % table.name)
        self.o("    _slice: scalgo_proto::ArenaSlice<'a>,")
        self.o("    _p: std::marker::PhantomData<P>,")
        self.o("}")
        self.o("impl<'a, P: scalgo_proto::Placement> %sOut<'a, P> {" % table.name)
        for node in table.members:
            self.generate_value_out(table, node)
        # self.generate_table_copy(table)
        self.o("}")
        self.o(
            "impl<'a, P: scalgo_proto::Placement> scalgo_proto::TableOut<P> for %sOut<'a, P> {"
            % table.name
        )
        self.o("    fn offset(&self) -> usize {self._slice.get_offset()}")
        self.o("}")
        self.output_doc(table, "")
        self.o("#[derive(Copy, Clone)]")
        self.o("pub struct %s {}" % table.name)
        self.o("impl<'a> scalgo_proto::TableFactory<'a> for %s {" % table.name)
        self.o("    type In = %sIn<'a>;" % table.name)
        self.o("    type Out = %sOut<'a, scalgo_proto::Normal>;" % table.name)
        self.o("    type InplaceOut = %sOut<'a, scalgo_proto::Inplace>;" % table.name)
        self.o("    fn magic() -> u32 {0x%08X}" % table.magic)
        self.o("    fn size() -> usize {%d}" % table.bytes)
        self.o(
            '    fn default() -> &\'static [u8] {b"%s"}' % byte_encode(table.default)
        )
        self.o(
            "    fn new_in(reader: scalgo_proto::Reader<'a>) -> Self::In {Self::In { _reader: reader }}"
        )
        self.o(
            "    fn new_out(slice: scalgo_proto::ArenaSlice<'a>) -> Self::Out {Self::Out { _slice: slice, _p: std::marker::PhantomData}}"
        )
        self.o(
            "    fn new_inplace_out(slice: scalgo_proto::ArenaSlice<'a>) -> Self::InplaceOut {Self::InplaceOut { _slice: slice, _p: std::marker::PhantomData}}"
        )
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
        self.o("#[derive(Copy, Clone)]")
        self.o("pub struct %s {}" % node.name)
        self.output_doc(node, "")
        self.o("pub struct %sIn<'a> {" % node.name)
        self.o("    _bytes: &'a [u8; %s]," % node.bytes)
        self.o("}")
        self.o("impl <'a> %sIn<'a> {" % node.name)
        for v in node.members:
            if not isinstance(v, Value):
                raise ICE()
            if v.type_.type == TokenType.BOOL:
                self.o(
                    "    pub fn %s(&self) -> bool {scalgo_proto::to_bool(self._bytes[%d])}"
                    % (self.value(v.identifier), v.offset)
                )
            elif v.type_.type in typeMap:
                self.o(
                    "    pub fn %s(&self) -> %s {unsafe{scalgo_proto::to_pod(&self._bytes[%d..%d])}}"
                    % (
                        self.value(v.identifier),
                        typeMap[v.type_.type][1],
                        v.offset,
                        v.offset + v.bytes,
                    )
                )
            elif v.struct:
                self.o(
                    "    pub fn %s(&self) -> %sIn<'a> {unsafe{scalgo_proto::to_struct::<%s>(&self._bytes[%d..%d])}}"
                    % (
                        self.value(v.identifier),
                        v.struct.name,
                        v.struct.name,
                        v.offset,
                        v.offset + v.bytes,
                    )
                )
            elif v.enum:
                self.o(
                    "    pub fn %s(&self) -> Option<%s> {unsafe{scalgo_proto::to_enum(self._bytes[%d])}}"
                    % (self.value(v.identifier), v.enum.name, v.enum.offset)
                )
            else:
                raise ICE()
        self.o("}")
        self.o("impl<'a> fmt::Debug for %sIn<'a> {" % node.name)
        self.o("    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {")
        self.o("        write!(")
        self.o(
            '            f, "%s {{ %s }}",'
            % (
                node.name,
                ", ".join(
                    ["%s: {:?}" % self.value(v.identifier) for v in node.members]
                ),
            )
        )
        self.o(
            "            %s"
            % ", ".join(["self.%s()" % self.value(v.identifier) for v in node.members])
        )
        self.o("        )")
        self.o("    }")
        self.o("}")
        self.o("pub struct %sOut<'a> {" % node.name)
        self.o("    _slice: scalgo_proto::ArenaSlice<'a>,")
        self.o("}")
        self.o("impl <'a> %sOut<'a> {" % node.name)
        for v in node.members:
            if not isinstance(v, Value):
                raise ICE()
            if v.type_.type == TokenType.BOOL:
                self.o(
                    "    pub fn %s(&mut self, v: bool) {self._slice.set_bool(%d, v)}"
                    % (self.value(v.identifier), v.offset)
                )
            elif v.type_.type in typeMap:
                self.o(
                    "    pub fn %s(&mut self, v: %s) {self._slice.set_pod(%d, &v)}"
                    % (self.value(v.identifier), typeMap[v.type_.type][1], v.offset)
                )
            elif v.struct:
                self.o(
                    "    pub fn %s<'b>(&'b mut self) -> %sOut<'b> {scalgo_proto::StructOut::new(self._slice.part(%d, %d))}"
                    % (
                        self.value(v.identifier),
                        v.struct.name,
                        v.offset,
                        v.struct.bytes,
                    )
                )
            elif v.enum:
                self.o(
                    "    pub fn %s(&mut self, v: Option<%s>) {self._slice.set_enum(%d, v)}"
                    % (self.value(v.identifier), v.enum.name, v.offset)
                )
            else:
                raise ICE()
        self.o("}")
        self.o("impl<'a> scalgo_proto::StructFactory<'a> for %s {" % node.name)
        self.o("    type In = %sIn<'a>;" % node.name)
        self.o("    type Out = %sOut<'a>;" % node.name)
        self.o("    type B = [u8; %s];" % node.bytes)
        self.o("    fn size() -> usize {%d}" % node.bytes)
        self.o(
            "    fn new_in(bytes: &'a Self::B) -> Self::In {Self::In{_bytes: bytes}}"
        )
        self.o("}")
        self.o("impl<'a> scalgo_proto::StructOut<'a> for %sOut<'a> {" % node.name)
        self.o(
            "    fn new(slice: scalgo_proto::ArenaSlice<'a>) -> Self {Self{_slice: slice}}"
        )
        self.o("}")
        self.o()

    def generate_enum(self, node: Enum) -> None:
        self.output_doc(node, "")
        self.o("#[repr(u8)]")
        self.o("#[derive(Copy, Clone, Debug, PartialEq)]")
        self.o("pub enum %s {" % node.name)
        for ev in node.members:
            self.o("    %s," % (usnake(self.value(ev.identifier))))
        self.o("}")
        self.o(
            "impl scalgo_proto::Enum for %s {fn max_value() -> u8 {%d}}"
            % (node.name, len(node.members))
        )
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
                    i.add("%s" % u.name)
                    i.add("%sIn" % u.name)
                    i.add("%sOut" % u.name)
                elif isinstance(u, Union):
                    i.add("%s" % u.name)
                    i.add("%sIn" % u.name)
                    i.add("%sOut" % u.name)
                else:
                    raise ICE()

        for (d, imp) in imports.items():
            doc = self.documents.by_id[d]
            for i in imp:
                self.o("use crate::%s::%s;" % (doc.name, i))

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
        print("#![allow(dead_code)]", file=out)
        print("use crate::scalgo_proto;", file=out)
        print("use std::fmt;", file=out)
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
