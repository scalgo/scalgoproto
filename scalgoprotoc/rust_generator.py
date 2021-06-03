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


def add_lifetime(t: str, lt="a") -> str:
    if not "<" in t:
        t = t + "<>"
    l, r = t.split("<", 1)
    return "%s<'%s, %s" % (l, lt, r)


class Generator:
    def __init__(self, documents: Documents, out: TextIO) -> None:
        self.documents: Documents = documents
        self.out: TextIO = out

    def out_list_type(self, node: Value) -> str:
        assert node.type_ is not None
        if node.type_.type == TokenType.BOOL:
            return "scalgoproto::BoolListWrite"
        elif node.type_.type in typeMap:
            return "scalgoproto::PodListWrite<%s>" % (typeMap[node.type_.type].p)
        elif node.struct:
            return "scalgoproto::StructListWrite<'a, %sOut<'a>>" % (node.struct.name)
        elif node.enum:
            return "scalgoproto::EnumListWrite<%s>" % (node.enum.name)
        elif node.table and node.direct:
            return "scalgoproto::DirectTableListWrite<'a, %sOut<'a, Normal>>" % (
                node.table.name
            )
        elif node.table:
            return "scalgoproto::TableListWrite<%sOut<'a, Normal>>" % (node.table.name)
        elif node.union:
            return "scalgoproto::UnionListWrite<%s>" % (node.union.name)
        elif node.type_.type == TokenType.TEXT:
            return "scalgoproto::TextListWrite"
        elif node.type_.type == TokenType.BYTES:
            return "scalgoproto::BytesListWrite"
        else:
            raise ICE()

    def out_list_constructor(self, node: Value, inplace: bool = False) -> str:
        assert node.type_ is not None
        x = ", true" if inplace else ""
        if node.type_.type == TokenType.BOOL:
            return "constructBoolList(size%s)" % x
        elif node.type_.type in typeMap:
            return "construct%sList(size%s)" % (typeMap[node.type_.type].n, x)
        elif node.struct:
            return "constructStructList<%sOut>(%sOut, size%s)" % (
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
        assert node.type_ is not None
        if node.type_.type == TokenType.BOOL:
            return ("boolean", "        return this._reader._getBoolList(%s)" % (os))
        elif node.type_.type in typeMap:
            ti = typeMap[node.type_.type]
            return (ti.p, "        return this._reader._get%sList(%s)" % (ti.n, os))
        elif node.struct:
            assert node.struct.name is not None
            return (
                node.struct.name,
                "        return this._reader._getStructList(%s, %s)"
                % (os, node.struct.name),
            )
        elif node.enum:
            assert node.enum.name is not None
            return (
                node.enum.name + " | null",
                "        return this._reader._getEnumList<%s>(%s)"
                % (node.enum.name, os),
            )
        elif node.table:
            assert node.table.name is not None
            return (
                node.table.name + "In | null",
                "        return this._reader._getTableList(%s, %sIn)"
                % (os, node.table.name),
            )
        elif node.union:
            assert node.union.name is not None
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

    def list_access_type_lt(self, node: Value) -> str:
        assert node.type_ is not None
        if node.type_.type == TokenType.BOOL:
            return "scalgoproto::BoolListRead<'a>"
        elif node.type_.type in typeMap:
            return "scalgoproto::PodListRead<'a, %s>" % (typeMap[node.type_.type].p)
        elif node.struct:
            return "scalgoproto::StructListRead<'a, %sIn<'a>>" % (node.struct.name)
        elif node.enum:
            return "scalgoproto::EnumListRead<'a, %s>" % (node.enum.name)
        elif node.table and node.direct:
            return "scalgoproto::DirectTableListRead<'a, %sIn<'a>>" % (node.table.name)
        elif node.table:
            return "scalgoproto::TableListRead<'a, %sIn<'a>>" % (node.table.name)
        elif node.union:
            return "scalgoproto::UnionListRead<'a, %sIn<'a>>" % (node.union.name)
        elif node.type_.type == TokenType.TEXT:
            return "scalgoproto::TextListRead<'a>"
        elif node.type_.type == TokenType.BYTES:
            return "scalgoproto::BytesListRead<'a>"
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
        tn = self.list_access_type_lt(node)
        self.output_doc(node, "    ")
        directTable_ = "direct_table_" if node.direct else ""
        an = f"{node.table.name}In" if node.direct and node.table else tn
        self.o(
            f"""    #[inline]
    pub fn {lname}(&self) -> Result<std::option::Option<scalgoproto::ListIn<'a, {tn}>>> {{
        self._reader.get_{directTable_}list{"_inplace" if node.inplace else ""}::<{an}>({node.offset})
    }}
"""
        )

    def generate_list_out(self, node: Value, lname: str, size: int) -> None:
        ot = self.out_list_type(node)
        directTable = "DirectTable" if node.direct else ""
        directTable_ = "direct_table_" if node.direct else ""
        at = f"{node.table.name}Out<'a, Normal>" if node.direct and node.table else ot
        if not node.inplace:
            self.output_doc(node, "    ")
            self.o(
                f"""    #[inline]
    pub fn set_{lname}(&mut self, v: std::option::Option<&scalgoproto::ListOut::<'a, {ot}, Normal>>) {{
        self._slice.set_list({node.offset}, v)
    }}
"""
            )
            self.output_doc(node, "    ")
            self.o(
                f"""    #[inline]
    pub fn add_{lname}(&mut self, len: usize) -> scalgoproto::ListOut::<'a, {ot}, Normal> {{
        self._slice.add_{directTable_}list::<{at}>({node.offset}, len)
    }}
"""
            )
        else:
            self.output_doc(node, "    ")
            self.o(
                f""" #[inline]
    pub fn add_{lname}(&mut self, len: usize) -> scalgoproto::ListOut::<'a, {ot}, Inplace> {{
        self._slice.add_{directTable_}list_inplace::<{at}>({node.offset}, len, None)
    }}
"""
            )

    def generate_union_list_out(
        self, node: Value, lname: str, idx: int, inplace: bool
    ) -> None:
        ot = self.out_list_type(node)
        tn = self.list_access_type_lt(node).replace("'a", "'b")

        if not inplace:
            self.output_doc(node, "    ")
            self.o(
                f"""    #[inline]
    pub fn set_{lname}(&mut self, v: &scalgoproto::ListOut<'a, {ot}, Normal>) {{
        self._slice.set_pod::<u16>(0, &{idx});
        self._slice.set_list(2, Some(v))
    }}
"""
            )

            self.output_doc(node, "    ")
            self.o(
                f"""    #[inline]
    pub fn add_{lname}(&mut self, len: usize) -> scalgoproto::ListOut::<'a, {ot}, Normal> {{
        self._slice.set_pod::<u16>(0, &{idx});
        self._slice.add_list::<{ot}>(2, len)
    }}
"""
            )

            self.output_doc(node, "    ")
            # TODO We would like to return a in this method but, we cannot get the lifetimes to work out
            self.o(
                f"""    #[inline]
    #[allow(clippy::needless_lifetimes)]
    pub fn copy_{lname}<'b>(&mut self, i: scalgoproto::ListIn<'b, {tn}>) -> Result<()> {{
        let s: usize = i.len();
        let mut a = self.add_{lname}(s);
        a.copy_in(i)?;
        Ok(())
    }}
"""
            )
        else:
            self.output_doc(node, "    ")
            self.o(
                f"""    #[inline]
        pub fn add_{lname}(&mut self, len: usize) -> scalgoproto::ListOut::<'a, {ot}, Inplace> {{
        self._slice.set_pod::<u16>(0, &{idx});
        self._slice.add_list_inplace::<{ot}>(2, len, Some(self._container_end))
    }}
"""
            )
            # TODO We would like to return a in this method but, we cannot get the lifetimes to work out
            self.o(
                f"""    #[inline]
    #[allow(clippy::needless_lifetimes)]
    pub fn copy_{lname}<'b>(&mut self, i: scalgoproto::ListIn<'b, {tn}>) -> Result<()> {{
        let s: usize = i.len();
        let mut a = self.add_{lname}(s);
        a.copy_in(i)?;
        Ok(())
    }}
"""
            )

    def generate_bool_in(self, node: Value, lname: str) -> None:
        if node.inplace:
            raise ICE()
        self.output_doc(node, "    ")
        if node.optional:
            self.o(
                f"""    #[inline]
    pub fn {lname}(&self) -> std::option::Option<bool> {{
        if self._reader.get_bit({node.has_offset}, {node.has_bit}) {{
            Some(self._reader.get_bit({node.offset}, {node.bit}))
        }} else {{
            None
        }}
    }}
"""
            )
        else:
            self.o(
                f"""    #[inline]
    pub fn {lname}(&self) -> bool {{
        self._reader.get_bit({node.offset}, {node.bit})
    }}
"""
            )

    def generate_bool_out(self, node: Value, lname: str) -> None:
        self.output_doc(node, "    ")
        if node.optional:
            self.o(
                f"""    #[inline]
    pub fn {lname}(&mut self, v : std::option::Option<bool>) {{
        match v {{
            None => self._slice.set_bit({node.has_offset}, {node.has_bit}, false),
            Some(b) => {{
                self._slice.set_bit({node.has_offset}, {node.has_bit}, true);
                self._slice.set_bit({node.offset}, {node.bit}, b)
            }}
        }}
    }}
"""
            )
        else:
            self.o(
                f"""    #[inline]
    pub fn {lname}(&mut self, v : bool) {{
        self._slice.set_bit({node.offset}, {node.bit}, v)
    }}
"""
            )

    def generate_basic_in(self, node: Value, lname: str) -> None:
        if node.inplace:
            raise ICE()
        assert node.type_ is not None
        ti = typeMap[node.type_.type]
        self.output_doc(node, "    ")
        if node.optional:
            if node.type_.type in (TokenType.F32, TokenType.F64):
                self.o(
                    f"""    #[inline]
    pub fn {lname}(&self) -> std::option::Option<{ti.p}> {{
        match self._reader.get_pod::<{ti.p}>({node.offset}) {{
            None => None,
            Some(v) if v.is_nan() => None,
            Some(v) => Some(v)
        }}
    }}
"""
                )
            else:
                self.o(
                    f"""    #[inline]
    pub fn {lname}(&self) -> std::option::Option<{ti.p}> {{
        if self._reader.get_bit({node.has_offset}, {node.has_bit}) {{
            self._reader.get_pod({node.offset})
        }} else {{
            None
        }}
    }}
"""
                )
        else:
            self.o(
                f"""    #[inline]
    pub fn {lname}(&self) -> {ti.p} {{
        self._reader.get_pod({node.offset}).unwrap_or({node.parsed_value
                    if not math.isnan(node.parsed_value)
                    else "std::%s::NAN" % ti.p})
    }}
"""
            )

    def generate_basic_out(self, node: Value, lname: str) -> None:
        if node.inplace:
            raise ICE()
        assert node.type_ is not None
        ti = typeMap[node.type_.type]
        self.output_doc(node, "    ")
        if node.optional and ti.p in ("f32", "f64"):
            self.o(
                f"""    #[inline]
    pub fn {lname}(&mut self, v : std::option::Option<{ti.p}>) {{
        match v {{
            None => self._slice.set_pod({node.offset}, &std::{ti.p}::NAN),
            Some(b) => self._slice.set_pod({node.offset}, &b)
        }}
    }}
"""
            )
        elif node.optional:
            self.o(
                f"""    #[inline]
    pub fn {lname}(&mut self, v : std::option::Option<{ti.p}>) {{
        match v {{
            None => self._slice.set_bit({node.has_offset}, {node.has_bit}, false),
            Some(b) => {{
                self._slice.set_bit({node.has_offset}, {node.has_bit}, true);
                self._slice.set_pod({node.offset}, &b)
            }}
        }}
    }}
"""
            )
        else:
            self.o(
                f"""    #[inline]
    pub fn {lname}(&mut self, v : {ti.p}) {{
        self._slice.set_pod({node.offset}, &v)
    }}
"""
            )

    def generate_enum_in(self, node: Value, lname: str) -> None:
        if node.inplace:
            raise ICE()
        assert node.enum is not None and node.enum.name is not None
        self.output_doc(node, "    ")
        self.o(
            f"""    #[inline]
    pub fn {lname}(&self) -> std::option::Option<{node.enum.name}> {{
        self._reader.get_enum({node.offset}, {node.parsed_value})
    }}
"""
        )

    def generate_enum_out(self, node: Value, lname: str) -> None:
        if node.inplace:
            raise ICE()
        assert node.enum is not None and node.enum.name is not None
        self.output_doc(node, "    ")
        self.o(
            f"""    #[inline]
    pub fn {lname}(&mut self, v: std::option::Option<{node.enum.name}>) {{
        self._slice.set_enum({node.offset}, v)
    }}
"""
        )

    def generate_struct_in(self, node: Value, lname: str) -> None:
        if node.inplace:
            raise ICE()
        assert node.struct is not None and node.struct.name is not None
        self.output_doc(node, "    ")
        if node.optional:
            self.o(
                f"""    #[inline]
    pub fn {lname}(&self) -> std::option::Option<{node.struct.name}In> {{
        if self._reader.get_bit({node.has_offset}, {node.has_bit}) {{
            Some(self._reader.get_struct::<{node.struct.name}In>({node.offset}))
        }} else {{
            None
        }}
    }}
"""
            )
        else:
            self.o(
                f"""    #[inline]
    pub fn {lname}(&self) -> {node.struct.name}In {{
        self._reader.get_struct::<{node.struct.name}In>({node.offset})
    }}
"""
            )

    def generate_struct_out(self, node: Value, lname: str) -> None:
        if node.inplace:
            raise ICE()
        assert node.struct is not None and node.struct.name is not None
        self.output_doc(node, "    ")

        if node.optional:
            self.o(
                f"""    #[inline]
    pub fn {lname}(&mut self) -> {node.struct.name}Out {{
        self._slice.set_bit({node.has_offset}, {node.has_bit}, true);
        self._slice.get_struct::<{node.struct.name}>({node.offset})
    }}
"""
            )
        else:
            self.o(
                f"""    #[inline]
    pub fn {lname}(&mut self) -> {node.struct.name}Out {{
        self._slice.get_struct::<{node.struct.name}>({node.offset})
    }}
"""
            )

    def generate_table_in(self, node: Value, lname: str) -> None:
        assert node.table is not None
        tname = node.table.name
        if not node.inplace:
            self.output_doc(node, "    ")
            self.o(
                f"""    #[inline]
    pub fn {lname}(&self) -> Result<std::option::Option<{tname}In>> {{
        self._reader.get_table::<{tname}In>({node.offset})
    }}
"""
            )
        else:
            self.output_doc(node, "    ")
            self.o(
                f"""    #[inline]
    pub fn {lname}(&self) -> Result<std::option::Option<{tname}In>> {{
        self._reader.get_table_inplace::<{tname}In>({node.offset})
    }}
"""
            )

    def generate_table_out(self, node: Value, lname: str) -> None:
        assert node.table is not None
        tname = node.table.name
        if not node.inplace:
            self.output_doc(node, "    ")
            self.o(
                f"""    #[inline]
    pub fn set_{lname}(&mut self, v: std::option::Option<& {tname}Out<'a, Normal>>) {{
        self._slice.set_table({node.offset}, v)
    }}
"""
            )
            self.output_doc(node, "    ")
            self.o(
                f"""    #[inline]
    pub fn add_{lname}(&mut self) -> {tname}Out<'a, Normal> {{
        self._slice.add_table::<{tname}Out<Normal>>({node.offset})
    }}
"""
            )
            # TODO (jakob) add table copy
        elif not node.table.empty:
            self.output_doc(node, "    ")
            self.o(
                f"""    #[inline]
    pub fn add_{lname}(&mut self) -> {tname}Out<'a, Inplace> {{
        self._slice.add_table_inplace::<{tname}Out<Inplace>>({node.offset}, None)
    }}
"""
            )
            # TODO (jakob) add table copy
        else:
            # TODO (jakob) this does no seem to be tested
            self.output_doc(node, "    ")
            self.o(
                f"""    #[inline]
    pub fn  add_{lname}(&mut self) {{
        this._setUint48({node.offset}, 0);
    }}
"""
            )

    def generate_union_table_out(
        self, node: Value, lname: str, idx: int, inplace: bool
    ) -> None:
        assert node.table is not None
        tname = node.table.name
        if node.table.empty:
            self.output_doc(node, "    ")
            self.o(
                f"""    #[inline]
    pub fn add_{lname}(&mut self) {{
        self._slice.set_pod::<u16>(0, &{idx});
        self._slice.set_u48(2, 0);
    }}
"""
            )

        elif not inplace:
            self.output_doc(node, "    ")
            self.o(
                f"""    #[inline]
    pub fn set_{lname}(&mut self, v: &{tname}Out<'a, Normal>) {{
        self._slice.set_pod::<u16>(0, &{idx});
        self._slice.set_table(2, Some(v));
    }}
"""
            )
            self.output_doc(node, "    ")
            self.o(
                f"""    #[inline]
    pub fn add_{lname}(&mut self) -> {tname}Out<'a, Normal> {{
        let a = self._slice.arena.create_table();
        self.set_{lname}(&a); a
    }}
"""
            )

            self.output_doc(node, "    ")
            self.o(
                f"""    #[inline]
    #[allow(clippy::needless_lifetimes)]
    pub fn copy_{lname}<'b>(&mut self, i: {tname}In<'b>)
        -> Result<{tname}Out<'a, Normal>> {{
        let mut a = self.add_{lname}();
        a.copy_in(i)?;
        Ok(a)
    }}
"""
            )
        else:
            self.output_doc(node, "    ")
            self.o(
                f"""    #[inline]
    pub fn add_{lname}(&mut self) -> {tname}Out<'a, Inplace> {{
        self._slice.set_pod::<u16>(0, &{idx});
        self._slice.add_table_inplace::<{tname}Out<Inplace>>(2, Some(self._container_end))
    }}
"""
            )
            self.output_doc(node, "    ")
            self.o(
                f"""    #[inline]
    #[allow(clippy::needless_lifetimes)]
    pub fn copy_{lname}<'b>(&mut self, i: {tname}In<'b>) -> Result<()> {{
        let mut a = self.add_{lname}();
        a.copy_in(i)
    }}"""
            )

    def generate_text_in(self, node: Value, lname: str) -> None:
        self.output_doc(node, "    ")
        self.o(
            f"""    #[inline]
    pub fn {lname}(&self) -> Result<std::option::Option<&'a str>> {{
        self._reader.get_text{"_inplace" if node.inplace else ""}({node.offset})
    }}
"""
        )

    def generate_text_out(self, node: Value, lname: str) -> None:
        self.output_doc(node, "    ")
        if not node.inplace:
            self.output_doc(node, "    ")
            self.o(
                f"""    #[inline]
    pub fn set_{lname}(&mut self, v: std::option::Option<&scalgoproto::TextOut<'a>>) {{
        self._slice.set_text({node.offset}, v)
    }}
"""
            )
            self.output_doc(node, "    ")
            self.o(
                f"""    #[inline]
    pub fn add_{lname}(&mut self, v: & str) -> scalgoproto::TextOut<'a> {{
        self._slice.add_text({node.offset}, v)
    }}
"""
            )
        else:
            self.output_doc(node, "    ")
            self.o(
                f"""    #[inline]
    pub fn add_{lname}(&mut self, v: & str) {{
        self._slice.add_text_inplace({node.offset}, v, None)
    }}
"""
            )

    def generate_union_text_out(
        self, node: Value, lname: str, idx: int, inplace: bool
    ) -> None:
        if inplace:
            self.output_doc(node, "    ")
            self.o(
                f"""    #[inline]
    pub fn add_{lname}(&mut self, v: &str) {{
        self._slice.set_pod::<u16>(0, &{idx});
        self._slice.add_text_inplace(2, v, Some(self._container_end))
    }}
"""
            )
        else:
            self.output_doc(node, "    ")
            self.o(
                f"""    #[inline]
    pub fn set_{lname}(&mut self, v: &scalgoproto::TextOut<'a>) {{
        self._slice.set_pod::<u16>(0, &{idx});
        self._slice.set_text(2, Some(v));
    }}
"""
            )
            self.output_doc(node, "    ")
            self.o(
                f"""    #[inline]
    pub fn add_{lname}(&mut self, v: &str) -> scalgoproto::TextOut {{
        let a = self._slice.arena.create_text(v);
        self.set_{lname}(&a);
        a
    }}
"""
            )

    def generate_bytes_in(self, node: Value, lname: str) -> None:
        self.output_doc(node, "    ")
        self.o(
            f"""    #[inline]
    pub fn {lname}(&self) -> Result<std::option::Option<&[u8]>> {{
        self._reader.get_bytes{"_inplace" if node.inplace else ""}({node.offset})
    }}
"""
        )

    def generate_bytes_out(self, node: Value, lname: str) -> None:
        if not node.inplace:
            self.output_doc(node, "    ")
            self.o(
                f"""    #[inline]
    pub fn add_{lname}(&mut self, bytes: &[u8]) -> scalgoproto::BytesOut<'a> {{
        self._slice.add_bytes({node.offset}, bytes)
    }}
"""
            )
            self.output_doc(node, "    ")
            self.o(
                f"""    #[inline]
    pub fn set_{lname}(&mut self, bytes: std::option::Option<&scalgoproto::BytesOut<'a>>) {{
        self._slice.set_bytes({node.offset}, bytes)
    }}
"""
            )
        else:
            self.o(
                f"""    #[inline]
    pub fn add_{lname}(&mut self, bytes: &[u8]) {{
        self._slice.add_bytes_inplace({node.offset}, bytes, None)
    }}
"""
            )

    def generate_union_bytes_out(
        self, node: Value, lname: str, idx: int, inplace: bool
    ) -> None:
        if inplace:
            self.output_doc(node, "    ")
            self.o(
                f"""    #[inline]
    pub fn add_{lname}(&mut self, v: &[u8]) {{
        self._slice.set_pod::<u16>(0, &{idx});
        self._slice.add_bytes_inplace(2, v, Some(self._container_end))
    }}
"""
            )
        else:
            self.output_doc(node, "    ")
            self.o(
                f"""    #[inline]
    pub fn set_{lname}(&mut self, v: &scalgoproto::BytesOut<'a>) {{
        self._slice.set_pod::<u16>(0, &{idx});
        self._slice.set_bytes(2, Some(v));
    }}
"""
            )
            self.output_doc(node, "    ")
            self.o(
                f"""    #[inline]
    pub fn add_{lname}(&mut self, v: &[u8]) -> scalgoproto::BytesOut {{
        let a = self._slice.arena.create_bytes(v);
        self.set_{lname}(&a);
        a
    }}
"""
            )

    def generate_union_in(self, node: Value, lname: str, table: Table) -> None:
        assert node.union is not None
        self.output_doc(node, "    ")
        self.o(
            f"""    #[inline]
    pub fn {lname}(&self) -> Result<{node.union.name}In<'a>> {{
        self._reader.get_union{"_inplace" if node.inplace else ""}::<{node.union.name}In>({node.offset})
    }}
"""
        )

    def generate_union_out(self, node: Value, lname: str, table: Table) -> None:
        assert node.union is not None
        self.output_doc(node, "    ")
        self.o(
            f"""    #[inline]
    pub fn {lname}(&mut self) -> {node.union.name}Out<{"Inplace" if node.inplace else "Normal"}> {{
        self._slice.get_union{"_inplace" if node.inplace else ""}::<{node.union.name}>({node.offset})
    }}
"""
        )

    def generate_value_in(self, table: Table, node: Value) -> None:
        lname = snake(self.value(node.identifier))
        assert node.type_ is not None
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
        assert node.type_ is not None
        if node.list_:
            assert table.default is not None
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
        name = union.name
        self.output_doc(union, "    ")
        self.o(
            f"""#[derive(Debug, Clone, Copy)]
pub enum {union.name}In<'a> {{
    None,"""
        )
        for member in union.members:
            if not isinstance(member, (Table, Value)):
                raise ICE()
            assert member.type_ is not None
            uname = ucamel(self.value(member.identifier))
            if member.list_:
                self.o(
                    "    %s(scalgoproto::ListIn<'a, %s>),"
                    % (uname, self.list_access_type_lt(member))
                )
            elif member.table:
                self.o("    %s(%sIn<'a>)," % (uname, member.table.name))
            elif member.type_.type == TokenType.BYTES:
                self.o("    %s(&'a [u8])," % (uname))
            elif member.type_.type == TokenType.TEXT:
                self.o("    %s(&'a str)," % (uname))
            else:
                raise ICE()
        self.o(
            f"""}}

impl<'a> scalgoproto::UnionIn<'a> for {union.name}In<'a> {{
    fn new(t: u16, magic: std::option::Option<u32>, offset: usize, size: usize, reader: &scalgoproto::Reader<'a>)
        -> Result<Self> {{
        match t {{"""
        )
        for i, member in enumerate(union.members):
            assert member.type_ is not None
            uname = ucamel(self.value(member.identifier))
            if member.list_:
                self.o(
                    f"        {i+1} => Ok(Self::{uname}(reader.get_list_union(magic, offset, size)?)),"
                )
            elif member.table:
                self.o(
                    f"        {i+1} => Ok(Self::{uname}(reader.get_table_union::<{member.table.name}In>(magic, offset, size)?)),"
                )
            elif member.type_.type == TokenType.BYTES:
                self.o(
                    f"        {i+1} => Ok(Self::{uname}(reader.get_bytes_union(magic, offset, size)?)),"
                )
            elif member.type_.type == TokenType.TEXT:
                self.o(
                    f"        {i+1} => Ok(Self::{uname}(reader.get_text_union(magic, offset, size)?)),"
                )
            else:
                self.o(f"        {i+1} => Ok(Self::None),")

        self.o(
            f"""        _ => Ok(Self::None),
        }}
    }}
}}
"""
        )

        self.output_doc(union, "    ")
        self.o(
            f"""pub struct {union.name}Out<'a, P: Placement> {{
    _slice: ArenaSlice<'a>,
    _container_end: usize,
    _p: PhantomData<P>,
}}
impl<'a> {union.name}Out<'a, Normal> {{
    #[inline]
    pub fn set_none(&mut self) {{
        self._slice.set_pod::<u16>(0, &0);
        self._slice.set_u48(2, 0);
    }}
"""
        )
        for idx, member in enumerate(union.members):
            assert member.type_ is not None
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
        self.o(
            f"""}}

impl<'a> {union.name}Out<'a, Inplace> {{
    #[inline]
    pub fn set_none(&mut self) {{
        self._slice.set_pod::<u16>(0, &0);
        self._slice.set_u48(2, 0);
    }}
"""
        )
        for idx, member in enumerate(union.members):
            assert member.type_ is not None
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

        self.o(
            f"""}}

pub struct {name} {{}}
impl<'a> scalgoproto::Union<'a> for {name} {{
    type Out = {name}Out<'a, Normal>;
    type InplaceOut = {name}Out<'a, Inplace>;

    #[inline]
    fn new_out(slice: ArenaSlice<'a>) -> Self::Out {{
        Self::Out{{_slice: slice, _container_end: 0, _p: PhantomData}}
    }}

    #[inline]
    fn new_inplace_out(slice: ArenaSlice<'a>, container_end: usize) -> Self::InplaceOut {{
        Self::InplaceOut{{_slice: slice, _container_end: container_end, _p: PhantomData}}
    }}
}}

impl<'a, 'b> scalgoproto::CopyIn<{name}In<'b> > for {name}Out<'a, Normal> {{
    fn copy_in(&mut self, i: {name}In<'b>) -> Result<()> {{
        match i {{
            {name}In::None => {{self.set_none();}},"""
        )
        for member in union.members:
            lname = snake(self.value(member.identifier))
            uname = ucamel(self.value(member.identifier))
            if member.table and member.table.empty:
                self.o(f"            {name}In::{uname}(_) => {{self.add_{lname}();}},")
            elif member.list_ or member.table:
                self.o(
                    f"            {name}In::{uname}(v) => {{self.copy_{lname}(v)?;}},"
                )
            else:
                self.o(f"            {name}In::{uname}(v) => {{self.add_{lname}(v);}},")
        self.o(
            f"""        }};
        Ok(())
    }}
}}

impl<'a, 'b> scalgoproto::CopyIn<{name}In<'b> > for {name}Out<'a, Inplace> {{
    fn copy_in(&mut self, i: {name}In<'b>) -> Result<()> {{
        match i {{
            {name}In::None => {{}},"""
        )
        for member in union.members:
            lname = snake(self.value(member.identifier))
            uname = ucamel(self.value(member.identifier))
            if member.table and member.table.empty:
                self.o(f"            {name}In::{uname}(_) => {{self.add_{lname}();}},")
            elif member.list_ or member.table:
                self.o(
                    f"            {name}In::{uname}(v) => {{self.copy_{lname}(v)?;}},"
                )
            else:
                self.o(f"            {name}In::{uname}(v) => {{self.add_{lname}(v);}},")
        self.o(
            f"""        }};
        Ok(())
    }}
}}
"""
        )

    def generate_table_copy(self, table: Table) -> None:
        for ip in (True, False):
            for node in table.members:
                lname = snake(self.value(node.identifier))
                if bool(node.inplace) != ip:
                    continue
                assert node.type_ is not None
                if node.list_:
                    self.o(
                        f"""        if let Some(v) = i.{lname}()? {{
            let mut w = self.add_{lname}(v.len());
            w.copy_in(v)?;
        }}"""
                    )
                elif (
                    node.type_.type in typeMap
                    or node.type_.type == TokenType.BOOL
                    or node.enum
                ):
                    self.o(f"        self.{lname}(i.{lname}());")
                elif node.type_.type in (TokenType.TEXT, TokenType.BYTES):
                    self.o(
                        f"""        if let Some(v) = i.{lname}()? {{
            self.add_{lname}(v);
        }}"""
                    )
                elif node.struct and node.optional:
                    self.o(
                        f"""        if let Some(v) = i.{lname}() {{
            self.{lname}().copy_in(v)?;
        }}"""
                    )
                elif node.struct:
                    self.o(f"        self.{lname}().copy_in(i.{lname}())?;")
                elif node.table:
                    self.o(
                        f"""        if let Some(v) = i.{lname}()? {{
            let mut w = self.add_{lname}();
            w.copy_in(v)?;
        }}"""
                    )
                elif node.union:
                    self.o(f"        self.{lname}().copy_in(i.{lname}()?)?;")
                else:
                    raise ICE()

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

        name = table.name
        magic = table.magic

        self.output_doc(table, "")
        self.o(
            f"""
#[derive(Clone, Copy)]
pub struct {name}In<'a> {{
    _reader: scalgoproto::Reader<'a>,
}}
impl<'a> {name}In<'a> {{"""
        )

        for node in table.members:
            self.generate_value_in(table, node)

        format_str = ", ".join(
            ["%s: {:?}" % snake(self.value(v.identifier)) for v in table.members]
        )
        format_args = ", ".join(
            ["self.%s()" % snake(self.value(v.identifier)) for v in table.members]
        )

        self.o(
            f"""}}

impl<'a> fmt::Debug for {name}In<'a> {{
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {{
        write!(f, "{name} {{{{ {format_str} }}}}", {format_args})
    }}
}}
impl<'a> scalgoproto::TableIn<'a> for {name}In<'a> {{
    #[inline]
    fn magic() -> u32 {{
        {magic:#010x}
    }}

    #[inline]
    fn new(reader: scalgoproto::Reader<'a>) -> Self {{
        Self {{ _reader: reader }}
    }}
}}"""
        )

        # Generate Table writer
        self.output_doc(table, "")
        self.o(
            f"""pub struct {name}Out<'a, P: Placement> {{
    _slice: ArenaSlice<'a>,
    _p: PhantomData<P>,
}}

impl<'a, P: Placement> {name}Out<'a, P> {{"""
        )
        for node in table.members:
            self.generate_value_out(table, node)
        assert table.default is not None
        self.o(
            f"""}}

impl<'a, P: Placement> scalgoproto::TableOut<'a, P> for {name}Out<'a, P> {{
    #[inline]
    fn offset(&self) -> usize {{
        self._slice.get_offset()
    }}

    #[inline]
    fn arena(&self) -> usize {{
        self._slice.arena_id()
    }}

    #[inline]
    fn magic() -> u32 {{
        {magic:#010x}
    }}

    #[inline]
    fn size() -> usize {{
        {table.bytes}
    }}

    #[inline]
    fn default() -> &\'static [u8] {{
        b"{byte_encode(table.default)}"
    }}

    #[inline]
    fn new(slice: ArenaSlice<'a>) -> Self {{
        Self{{_slice: slice, _p: PhantomData}}
    }}
}}

impl<'a, 'b, P: Placement> scalgoproto::CopyIn<{name}In<'b> > for {name}Out<'a, P> {{
    fn copy_in(&mut self, i: {name}In<'b>) -> Result<()> {{"""
        )
        self.generate_table_copy(table)
        self.o(
            f"""        Ok(())
    }}
}}
"""
        )

        self.output_doc(table, "")
        self.o(
            f"""pub struct {name} {{}}
impl<'a> scalgoproto::Table<'a> for {name} {{
    type In = {name}In<'a>;
    type Out = {name}Out<'a, Normal>;
}}
"""
        )

    def generate_struct(self, node: Struct) -> None:
        # Recursively generate direct contained members
        for value in node.members:
            if value.direct_enum:
                self.generate_enum(value.direct_enum)
            if value.direct_struct:
                self.generate_struct(value.direct_struct)

        name = node.name
        size = node.bytes

        self.output_doc(node, "")
        self.o(f"pub struct {name} {{}}")
        self.output_doc(node, "")
        self.o(
            f"""
#[derive(Copy, Clone)]
pub struct {name}In<'a> {{
    _bytes: &'a [u8; {size}],
}}

impl<'a> scalgoproto::StructIn<'a> for {name}In<'a> {{
    type B = [u8; {size}];

    #[inline]
    fn size() -> usize {{
        {size}
    }}

    #[inline]
    fn new(bytes: &'a Self::B) -> Self {{
        Self{{_bytes: bytes}}
    }}
}}

impl <'a> {name}In<'a> {{"""
        )
        for v in node.members:
            if not isinstance(v, Value):
                raise ICE()
            assert v.type_ is not None
            ident = self.value(v.identifier)
            if v.type_.type == TokenType.BOOL:
                self.o(
                    f"""    #[inline]
    pub fn {ident}(&self) -> bool {{
        scalgoproto::to_bool(self._bytes[{v.offset}])
    }}
"""
                )
            elif v.type_.type in typeMap:
                self.o(
                    f"""    #[inline]
    pub fn {ident}(&self) -> {typeMap[v.type_.type][1]} {{
        unsafe{{scalgoproto::to_pod(&self._bytes[{v.offset}..{v.offset + v.bytes}])}}
    }}
"""
                )
            elif v.struct:
                self.o(
                    f"""    #[inline]
    pub fn {ident}(&self) -> {v.struct.name}In<'a> {{
        unsafe{{scalgoproto::to_struct::<{v.struct.name}In>(&self._bytes[{v.offset}..{v.offset + v.bytes}])}}
    }}
"""
                )
            elif v.enum:
                self.o(
                    f"""    #[inline]
    pub fn {ident}(&self) -> std::option::Option<{v.enum.name}> {{
        unsafe{{scalgoproto::to_enum(self._bytes[{v.offset}])}}
    }}
"""
                )
            else:
                raise ICE()
        format_string = ", ".join(
            ["%s: {:?}" % self.value(v.identifier) for v in node.members]
        )
        format_args = ", ".join(
            ["self.%s()" % self.value(v.identifier) for v in node.members]
        )

        self.o(
            f"""}}

impl<'a> fmt::Debug for {name}In<'a> {{
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {{
        write!(f, "{name} {{{{ {format_string} }}}}", {format_args})
    }}
}}

pub struct {name}Out<'a> {{
    _slice: ArenaSlice<'a>,
}}

impl <'a> {name}Out<'a> {{"""
        )
        for v in node.members:
            if not isinstance(v, Value):
                raise ICE()
            assert v.type_ is not None
            ident = self.value(v.identifier)
            if v.type_.type == TokenType.BOOL:
                self.o(
                    f"""    #[inline]
    pub fn {ident}(&mut self, v: bool) {{
        self._slice.set_bool({v.offset}, v)
    }}
"""
                )
            elif v.type_.type in typeMap:
                self.o(
                    f"""    #[inline]
    pub fn {ident}(&mut self, v: {typeMap[v.type_.type][1]}) {{
        self._slice.set_pod({v.offset}, &v)
    }}
"""
                )
            elif v.struct:
                self.o(
                    f"""    #[inline]
    pub fn {ident}(&mut self) -> {v.struct.name}Out {{
        scalgoproto::StructOut::new(self._slice.part({v.offset}, {v.struct.bytes}))
    }}
"""
                )
            elif v.enum:
                self.o(
                    f"""    #[inline]
    pub fn {ident}(&mut self, v: std::option::Option<{v.enum.name}>) {{
        self._slice.set_enum({v.offset}, v)
    }}
"""
                )
            else:
                raise ICE()
        self.o(
            f"""}}

impl<'a> scalgoproto::Struct<'a> for {name} {{
    type Out = {name}Out<'a>;
}}

impl<'a> scalgoproto::StructOut<'a> for {name}Out<'a> {{
    #[inline]
    fn new(slice: ArenaSlice<'a>) -> Self {{
        Self{{_slice: slice}}
    }}

    #[inline]
    fn size() -> usize {{
        {size}
    }}
}}

impl<'a, 'b> scalgoproto::CopyIn<{name}In<'b> > for {name}Out<'a> {{
    fn copy_in(&mut self, i: {name}In<'b>) -> Result<()> {{
        self._slice.set_data(i._bytes);
        Ok(())
    }}
}}

"""
        )

    def generate_enum(self, node: Enum) -> None:
        self.output_doc(node, "")
        self.o(
            f"""#[repr(u8)]
#[derive(Copy, Clone, Debug, PartialEq)]
pub enum {node.name} {{"""
        )
        for ev in node.members:
            self.o("    %s," % (ucamel(self.value(ev.identifier))))
        self.o(
            f"""}}

impl scalgoproto::Enum for {node.name} {{
    fn max_value() -> u8 {{
        {len(node.members)}
    }}
}}
"""
        )

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
                    assert u.name is not None
                    i.add(u.name)
                elif isinstance(u, Enum):
                    assert u.name is not None
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
            for ii in imp:
                self.o(f"use crate::{doc.name}::{ii};")

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
        print(
            """
use crate::scalgoproto;
use crate::scalgoproto::CopyIn;
use crate::scalgoproto::Placement;
use crate::scalgoproto::Normal;
use crate::scalgoproto::Inplace;
use crate::scalgoproto::Result;
use crate::scalgoproto::ArenaSlice;
use std::marker::PhantomData;
use std::fmt;
""",
            file=out,
        )

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
