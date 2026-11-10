"""
Generate python reader/wirter
"""

import math
import os
from typing import NamedTuple, TextIO

from .annotate import annotate
from .documents import Documents
from .parser import (
    ICE,
    AstNode,
    Enum,
    Namespace,
    ParseError,
    Parser,
    Struct,
    Table,
    Union,
    Value,
)
from .sp_tokenize import Token, TokenType
from .util import cescape, lcamel, ucamel


class TypeInfo(NamedTuple):
    n: str
    p: str


typeMap: dict[TokenType, TypeInfo] = {
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
            return f"scalgoproto.ListOut<{node.struct.name}>"
        elif node.enum:
            return f"scalgoproto.ListOut<{node.enum.name}, {node.enum.name} | null>"
        elif node.table:
            if node.direct:
                return f"scalgoproto.ListOut<{node.table.name}Out, {node.table.name}In>"
            return f"scalgoproto.ListOut<{node.table.name}Out, {node.table.name}In | null>"
        elif node.union:
            return f"scalgoproto.ListOut<{node.union.name}Out, {node.union.name}In>"
        elif node.type_.type == TokenType.TEXT:
            return "scalgoproto.ListOut<string | scalgoproto.TextOut, string | null>"
        elif node.type_.type == TokenType.BYTES:
            return "scalgoproto.ListOut<ArrayBuffer | scalgoproto.BytesOut, ArrayBuffer | null>"
        else:
            raise ICE()

    def out_list_constructor(self, node: Value, inplace: bool = False) -> str:
        x = ", true" if inplace else ""
        if node.type_.type == TokenType.BOOL:
            return f"constructBoolList(size{x})"
        elif node.type_.type in typeMap:
            return f"construct{typeMap[node.type_.type].n}List(size{x})"
        elif node.struct:
            return f"constructStructList<{node.struct.name}>({node.struct.name}, size{x})"
        elif node.enum:
            return f"constructEnumList<{node.enum.name}>(size{x})"
        elif node.table:
            if node.direct:
                return f"constructDirectTableList<{node.table.name}Out>({node.table.name}Out, size)"
            return f"constructTableList<{node.table.name}Out>({node.table.name}Out, size{x})"
        elif node.union:
            return f"constructUnionList<{node.union.name}Out>({node.union.name}Out, size{x})"
        elif node.type_.type == TokenType.TEXT:
            return f"constructTextList(size{x})"
        elif node.type_.type == TokenType.BYTES:
            return f"constructBytesList(size{x})"
        else:
            raise ICE()

    def in_list_help(self, node: Value, os: str) -> tuple[str, str]:
        if node.type_.type == TokenType.BOOL:
            return ("boolean", f"\t\treturn this._reader._getBoolList({os})")
        elif node.type_.type in typeMap:
            ti = typeMap[node.type_.type]
            return (ti.p, f"\t\treturn this._reader._get{ti.n}List({os})")
        elif node.struct:
            return (
                node.struct.name,
                f"\t\treturn this._reader._getStructList({os}, {node.struct.name})",
            )
        elif node.enum:
            return (
                node.enum.name + " | null",
                f"\t\treturn this._reader._getEnumList<{node.enum.name}>({os})",
            )
        elif node.table:
            if node.direct:
                return (
                    node.table.name + "In",
                    f"\t\treturn this._reader._getDirectTableList({os}, {node.table.name}In)",
                )
            return (
                node.table.name + "In | null",
                f"\t\treturn this._reader._getTableList({os}, {node.table.name}In)",
            )
        elif node.union:
            return (
                node.union.name + "In",
                f"\t\treturn this._reader._getUnionList({os}, {node.union.name}In)",
            )
        elif node.type_.type == TokenType.TEXT:
            return ("string | null", f"\t\treturn this._reader._getTextList({os})")
        elif node.type_.type == TokenType.BYTES:
            return (
                "ArrayBuffer | null",
                f"\t\treturn this._reader._getBytesList({os})",
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
        prefix: list[str] | None = None,
        suffix: list[str] | None = None,
    ):
        if suffix is None:
            suffix = []
        if prefix is None:
            prefix = []
        if not node.docstring and not suffix and not prefix:
            return
        self.o(f"{indent}/**")
        for line in prefix:
            self.o(f"{indent} * {line}")
        if prefix and (node.docstring or suffix):
            self.o(f"{indent} *")
        if node.docstring:
            for line in node.docstring:
                self.o(f"{indent} * {line}")
        if node.docstring and suffix:
            self.o(f"{indent} *")
        for line in suffix:
            self.o(f"{indent} * {line}")
        self.o(f"{indent} */")

    def generate_list_in(self, node: Value, lname: str) -> None:
        (tn, acc) = self.in_list_help(node, "o, s")

        self.output_doc(node, "\t")
        self.o(f"\tget {lname}() : scalgoproto.ListIn<{tn}> | null {{")
        magic = "DIRECT_LIST_MAGIC" if node.direct else "LIST_MAGIC"
        self.o(
            "\t\tconst [o, s] = this._getPtr%s(%d, scalgoproto.%s)"
            % ("Inplace" if node.inplace else "", node.offset, magic)
        )
        self.o("\t\tif (o === 0) return null;")
        self.o(acc)
        self.o("\t}")
        self.o()

    def generate_union_list_in(self, node: Value, lname: str) -> None:
        (tn, acc) = self.in_list_help(node, "o, s")
        self.output_doc(node, "\t")
        self.o(f"\tget {lname}() : scalgoproto.ListIn<{tn}> | null {{")
        self.o(f"\t\tif (!this.is{ucamel(lname)}) return null;")
        self.o("\t\tconst [o, s] = this._getPtr(scalgoproto.LIST_MAGIC)")
        self.o("\t\tif (o === 0) return null;")
        self.o(acc)
        self.o("\t}")
        self.o()

    def generate_list_out(self, node: Value, lname: str, size: int) -> None:
        it = "scalgoproto.ListIn<{}>".format(self.in_list_help(node, "")[0])
        ot = self.out_list_type(node)
        if not node.inplace:
            self.output_doc(node, "\t")
            self.o(f"\tset {lname}(value: {it} | {ot}) {{")
            self.o("\t\tif (value instanceof scalgoproto.ListIn) {")
            self.o(f"\t\t\tthis.add{ucamel(lname)}(value.length)._copy(value);")
            self.o("\t\t\treturn;")
            self.o("\t\t}")
            self.o("\t\tconsole.assert(value instanceof scalgoproto.ListOut);")
            self.o("\t\tthis._setList(%d, value);" % (node.offset))
            self.o("\t}")
            self.o()

            self.output_doc(node, "\t")
            self.o(
                f"\tadd{ucamel(lname)}(size:number) : {self.out_list_type(node)} {{"
            )
            self.o(f"\t\tconst res = this._writer.{self.out_list_constructor(node)};")
            self.o("\t\tthis._setList(%d, res);" % (node.offset))
            self.o("\t\treturn res;")
            self.o("\t}")
            self.o()
        else:
            self.output_doc(node, "\t")
            self.o(f"\tset {lname}(value: {it}) {{")
            self.o("\t\tconsole.assert(value instanceof scalgoproto.ListIn);")
            self.o(f"\t\tthis.add{ucamel(lname)}(value.length)._copy(value);")
            self.o("\t}")

            self.output_doc(node, "\t")
            self.o(
                f"\tadd{ucamel(lname)}(size: number) : {self.out_list_type(node)} {{"
            )
            self.o(
                f"\t\tconsole.assert(this._writer._size == this._offset + {size});"
            )
            self.o(
                f"\t\tconst l = this._writer.{self.out_list_constructor(node, True)};"
            )
            self.o("\t\tthis._setInplaceList(%d, size);" % (node.offset))
            self.o("\t\treturn l;")
            self.o("\t}")
            self.o()

    def generate_union_list_out(
        self, node: Value, lname: str, idx: int, inplace: bool
    ) -> None:
        it = "scalgoproto.ListIn<{}>".format(self.in_list_help(node, "")[0])
        ot = self.out_list_type(node)
        if not inplace:
            self.output_doc(node, "\t")
            self.o(f"\tset {lname}(value: {ot} |{it} ) {{")
            self.o("\t\tif (value instanceof scalgoproto.ListIn) {")
            self.o(f"\t\t\tthis.add{ucamel(lname)}(value.length)._copy(value)")
            self.o("\t\t\treturn;")
            self.o("\t\t}")
            self.o("\t\tconsole.assert(value instanceof scalgoproto.ListOut);")
            self.o("\t\tthis._set(%d, value._offset - 10);" % (idx,))
            self.o("\t}")
            self.o()

            self.output_doc(node, "\t")
            self.o(
                f"\tadd{ucamel(lname)}(size:number) : {self.out_list_type(node)} {{"
            )
            self.o(f"\t\tconst res = this._writer.{self.out_list_constructor(node)};")
            self.o("\t\tthis._set(%d, res._offset - 10);" % (idx,))
            self.o("\t\treturn res;")
            self.o("\t}")
            self.o()
        else:
            self.output_doc(node, "\t")
            self.o(f"\tset {lname}(value: {it}) {{")
            self.o("\t\tconsole.assert(value instanceof scalgoproto.ListIn);")
            self.o(f"\t\tthis.add{ucamel(lname)}(value.length)._copy(value);")
            self.o("\t}")
            self.o()
            self.output_doc(node, "\t")
            self.o(
                f"\tadd{ucamel(lname)}(size: number) : {self.out_list_type(node)} {{"
            )
            self.o("\t\tthis._set(%d, size);" % (idx,))
            self.o(
                f"\t\treturn this._writer.{self.out_list_constructor(node, True)};"
            )
            self.o("\t}")
            self.o()

    def generate_bool_in(self, node: Value, lname: str) -> None:
        if node.inplace:
            raise ICE()
        self.output_doc(node, "\t")
        self.o("\tget {}(): boolean{} {{".format(lname, " | null " if node.optional else ""))
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
        self.o(f"\tset {lname}(value: boolean) {{")
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
        self.o("\tget {}(): {}{} {{".format(lname, ti.p, " | null" if node.optional else ""))
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
        self.o(f"\tset {lname}(value: {ti.p}) {{")
        if node.optional and node.type_.type not in (TokenType.F32, TokenType.F64):
            self.o("\t\tthis._setBit(%d, %d);" % (node.has_offset, node.has_bit))
        self.o("\t\tthis._set%s(%d, value);" % (ti.n, node.offset))
        self.o("\t}")
        self.o()

    def generate_enum_in(self, node: Value, lname: str) -> None:
        if node.inplace:
            raise ICE()
        self.output_doc(node, "\t")
        self.o(f"\tget {lname}(): {node.enum.name} | null {{")
        self.o(
            "\t\tconst v = this._getUint8(%d, %s);" % (node.offset, node.parsed_value)
        )
        self.o(f"\t\treturn v == 255 ? null : v as {node.enum.name};")
        self.o("\t}")
        self.o()

    def generate_enum_out(self, node: Value, lname: str) -> None:
        if node.inplace:
            raise ICE()
        self.output_doc(node, "\t")
        self.o(f"\tset {lname}(value: {node.enum.name}) {{")
        self.o("\t\tthis._setUint8(%d, value as number)" % (node.offset))
        self.o("\t}")
        self.o()

    def generate_struct_in(self, node: Value, lname: str) -> None:
        if node.inplace:
            raise ICE()
        self.output_doc(node, "\t")
        self.o(
            "\tget {}(): {}{} {{".format(lname, node.struct.name, " | null " if node.optional else "")
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
        self.o(f"\tset {lname}(value: {node.struct.name}) {{")
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
            self.o(f"\tget {lname}() : {node.table.name}In | null {{")
            self.o(
                "\t\tconst [offset, size] = this._getPtr%s(%d, %sIn._MAGIC);"
                % ("Inplace" if node.inplace else "", node.offset, node.table.name)
            )
            self.o("\t\tif (offset === 0) return null;")
            self.o(
                f"\t\treturn new {node.table.name}In(this._reader, offset, size);"
            )
            self.o("\t}")
            self.o()

    def generate_union_table_in(self, node: Value, lname: str) -> None:
        if not node.table.empty:
            self.output_doc(node, "\t")
            self.o(f"\tget {lname}() : {node.table.name}In | null {{")
            self.o(f"\t\tif (!this.is{ucamel(lname)}) return null;")
            self.o(
                f"\t\tconst [offset, size] = this._getPtr({node.table.name}In._MAGIC);"
            )
            self.o("\t\tif (offset === 0) return null;")
            self.o(
                f"\t\treturn new {node.table.name}In(this._reader, offset, size);"
            )
            self.o("\t}")
            self.o()

    def generate_table_out(self, node: Value, lname: str, size: int) -> None:
        if not node.inplace:
            self.output_doc(node, "\t")
            self.o(
                f"\tset {lname}(value: {node.table.name}Out | {node.table.name}In) {{"
            )
            self.o(f"\t\tif (value instanceof {node.table.name}In) {{")
            self.o("\t\t\tconst v = value;")
            self.o(
                f"\t\t\tvalue = this._writer.constructTable({node.table.name}Out);"
            )
            self.o("\t\t\tvalue._copy(v);")
            self.o("\t\t}")
            self.o(f"\t\tconsole.assert(value instanceof {node.table.name}Out);")
            self.o("\t\tthis._setTable(%d, value);" % (node.offset))
            self.o("\t}")
            self.o()
            self.output_doc(node, "\t")
            self.o(f"\tadd{ucamel(lname)}() : {node.table.name}Out {{")
            self.o(
                f"\t\tconst res = this._writer.constructTable({node.table.name}Out);"
            )
            self.o("\t\tthis._setTable(%d, res);" % (node.offset,))
            self.o("\t\treturn res;")
            self.o("\t}")
            self.o()
        elif not node.table.empty:
            self.output_doc(node, "\t")
            self.o(f"\tset {lname}(value: {node.table.name}In) {{")
            self.o(f"\t\tconsole.assert(value instanceof {node.table.name}In);")
            self.o(f"\t\tthis.add{ucamel(lname)}()._copy(value);")
            self.o("\t}")
            self.o()
            self.output_doc(node, "\t")
            self.o(f"\tadd{ucamel(lname)}() : {node.table.name}Out {{")
            self.o(
                f"\t\tconsole.assert(this._writer._size == this._offset + {size});"
            )
            self.o(
                "\t\tthis._setUint48(%d, %d);" % (node.offset, len(node.table.default))
            )
            self.o(f"\t\treturn new {node.table.name}Out(this._writer, false);")
            self.o("\t}")
            self.o()
        else:
            self.output_doc(node, "\t")
            self.o(f"\tadd{ucamel(lname)}(self) {{")
            self.o("\t\tthis._setUint48(%d, %d);" % (node.offset, 0))
            self.o("\t}")
            self.o()

    def generate_union_table_out(
        self, node: Value, lname: str, idx: int, inplace: bool
    ) -> None:
        table = node.table
        if table.empty:
            self.output_doc(node, "\t")
            self.o(f"\tadd{ucamel(lname)}() {{")
            self.o("\t\tthis._set(%d, 0);" % (idx))
            self.o("\t}")
            self.o()
        elif not inplace:
            self.output_doc(node, "\t")
            self.o(f"\tset {lname}(value: {table.name}Out | {table.name}In) {{")
            self.o(f"\t\tif (value instanceof {node.table.name}In) {{")
            self.o("\t\t\tconst v = value;")
            self.o(
                f"\t\t\tvalue = this._writer.constructTable({node.table.name}Out);"
            )
            self.o("\t\t\tvalue._copy(v);")
            self.o("\t\t}")
            self.o(f"\t\tconsole.assert(value instanceof {node.table.name}Out);")
            self.o("\t\tthis._set(%d, value._offset - 10);" % (idx))
            self.o("\t}")
            self.o()
            self.output_doc(node, "\t")
            self.o(f"\tadd{ucamel(lname)}() : {table.name}Out {{")
            self.o(
                f"\t\tconst res = this._writer.constructTable({node.table.name}Out);"
            )
            self.o("\t\tthis._set(%d, res._offset - 10);" % (idx,))
            self.o("\t\treturn res;")
            self.o("\t}")
            self.o()
        else:
            self.output_doc(node, "\t")
            self.o(f"\tset {lname}(value: {node.table.name}In) {{")
            self.o(f"\t\tconsole.assert(value instanceof {node.table.name}In);")
            self.o(f"\t\tthis.add{ucamel(lname)}()._copy(value);")
            self.o("\t}")
            self.o()
            self.output_doc(node, "\t")
            self.o(f"\tadd{ucamel(lname)}() : {table.name}Out {{")
            self.o("\t\tconsole.assert(this._end == this._writer._size);")
            self.o("\t\tthis._set(%d, %d);" % (idx, table.bytes))
            self.o(f"\t\treturn new {table.name}Out(this._writer, false)")
            self.o("\t}")
            self.o()

    def generate_text_in(self, node: Value, lname: str) -> None:
        self.output_doc(node, "\t")
        self.o(f"\tget {lname}() : string | null {{")
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
        self.o(f"\tget {lname}() : string | null {{")
        self.o(f"\t\tif(!this.is{ucamel(lname)}) return null;")
        self.o("\t\tconst [o, s] = this._getPtr(scalgoproto.TEXT_MAGIC)")
        self.o("\t\tif (o === 0) return null;")
        self.o("\t\treturn this._reader._readText(o, s);")
        self.o("\t}")
        self.o()

    def generate_text_out(self, node: Value, lname: str, size: int) -> None:
        self.output_doc(node, "\t")
        if node.inplace:
            self.o(f"\tset {lname}(text: string) {{")
        else:
            self.o(f"\tset {lname}(t: scalgoproto.TextOut | string) {{")
        if node.inplace:
            self.o(
                f"\t\tconsole.assert(this._writer._size == this._offset + {size});"
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
            self.o(f"\tset {lname}(value: string) {{")
        else:
            self.o(f"\tset {lname}(value: scalgoproto.TextOut | string) {{")
        if inplace:
            self.o("\t\tthis._addInplaceText(%d, value);" % (idx))
        else:
            self.o("\t\tthis._setText(%d, value);" % (idx))
        self.o("}")
        self.o()

    def generate_bytes_in(self, node: Value, lname: str) -> None:
        self.output_doc(node, "\t")
        self.o(f"\tget {lname}() : ArrayBuffer | null {{")
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
        self.o(f"\tget {lname}() : ArrayBuffer | null {{")
        self.o(f"\t\tif (!this.is{ucamel(lname)}) return null;")
        self.o("\t\tconst [o, s] = this._getPtr(scalgoproto.BYTES_MAGIC)")
        self.o("\t\tif (o === 0) return null;")
        self.o("\t\tconst oo = (this._reader._data.byteOffset || 0) + o")
        self.o("\t\treturn this._reader._data.buffer.slice(oo, oo+s);")
        self.o("\t}")
        self.o()

    def generate_bytes_out(self, node: Value, lname: str, size: int) -> None:
        self.output_doc(node, "\t")
        if node.inplace:
            self.o(f"\tset {lname}(value: ArrayBuffer) {{")
        else:
            self.o(f"\tset {lname}(value: scalgoproto.BytesOut | ArrayBuffer) {{")
        if node.inplace:
            self.o(
                f"\t\tconsole.assert(this._writer._size == this._offset + {size});"
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
            self.o(f"\tset {lname}(value: ArrayBuffer) {{")
        else:
            self.o(f"\tset {lname}(value: scalgoproto.BytesOut | ArrayBuffer) {{")
        if inplace:
            self.o("\t\tthis._addInplaceBytes(%d, value);" % (idx))
        else:
            self.o("\t\tthis._setBytes(%d, value);" % (idx))
        self.o("\t}")
        self.o()

    def generate_union_in(self, node: Value, lname: str, table: Table) -> None:
        self.output_doc(node, "\t")
        self.o(f"\tget {lname}() : {node.union.name}In  {{")
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
            "\tget {}() : {}{}Out {{".format(lname, node.union.name, "Inplace" if node.inplace else "")
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
        self.o(f"\t_copy(i:{union.name}In) {{")
        self.o("\t\tswitch(i.type) {")
        for node in union.members:
            lname = self.value(node.identifier)
            self.o(f"\t\tcase {union.name}Type.{lname.upper()}:")
            if node.table and node.table.empty:
                self.o(f"\t\t\tthis.add{ucamel(lname)}();")
            else:
                self.o(f"\t\t\tthis.{lname} = i.{lname}!;")
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

        self.o(f"export enum {union.name}Type {{")
        self.o("\tNONE,")
        for member in union.members:
            if not isinstance(member, (Table, Value)):
                raise ICE()
            self.o(f"\t{self.value(member.identifier).upper()},")
        self.o("}")
        self.o()

        self.output_doc(union, "\t")
        self.o(f"export class {union.name}In extends scalgoproto.UnionIn {{")
        self.o(
            "\t/** Private constructor. Call factory methods on scalgoproto.Reader to construct instances */"
        )
        self.o(
            "\tconstructor(reader: scalgoproto.Reader, type: number, offset: number, size: number|null = null) {"
        )

        self.o("\t\tsuper(reader, type, offset, size);")
        self.o("\t}")
        self.o()

        self.o(f"\tget type() : {union.name}Type {{")
        self.output_doc(union, "    ")
        self.o(f"\t\treturn this._type as {union.name}Type;")
        self.o("\t}")
        self.o()
        for member in union.members:
            n = self.value(member.identifier)
            lname = lcamel(n)
            self.o(f"\tget is{ucamel(lname)}() : boolean {{")
            self.o(f"\t\treturn this.type == {union.name}Type.{n.upper()};")
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

        self.o(f"export class {union.name}Out extends scalgoproto.UnionOut {{")
        self.o(f"\tstatic readonly _IN = {union.name}In;")
        self.o(
            "\t/***Private constructor. Call factory methods on scalgoproto.Writer to construct instances*/"
        )
        self.o(
            "\tconstructor(writer: scalgoproto.Writer, offset: number, end: number = 0) {"
        )
        self.o("\t\tsuper(writer, offset, end);")
        self.o("\t}")
        self.o()
        for idx, member in enumerate(union.members, start=1):
            llname = lcamel(self.value(member.identifier))
            if member.type_.type == TokenType.REMOVED:
                continue
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
        self.generate_union_copy(union)
        self.o("}")
        self.o()

        self.o(f"export class {union.name}InplaceOut extends scalgoproto.UnionOut {{")
        self.o(
            "\t/** Private constructor. Call factory methods on scalgoproto.Writer to construct instances */"
        )
        self.o(
            "\tconstructor(writer: scalgoproto.Writer, offset: number, end: number = 0) {"
        )

        self.o("\t\tsuper(writer, offset, end);")
        self.o("\t}")
        self.o()
        for idx, member in enumerate(union.members, start=1):
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
        self.generate_union_copy(union)
        self.o("}")
        self.o()

    def generate_table_copy(self, table: Table) -> None:
        self.o(f"\t_copy(i:{table.name}In) {{")
        for ip in (True, False):
            for node in table.members:
                lname = lcamel(self.value(node.identifier))
                uname = ucamel(lname)
                if bool(node.inplace) != ip:
                    continue
                if node.list_:
                    self.o(
                        f"\t\tif (i.{lname} !== null) this.add{uname}(i.{lname}.length)._copy(i.{lname});"
                    )
                elif node.union:
                    if node.optional:
                        self.o(
                            f"\t\tif (i.{lname} !== null) this.{lname}._copy(i.{lname}!);"
                        )
                    else:
                        self.o(f"\t\tthis.{lname}._copy(i.{lname});")
                elif (
                    node.optional
                    or node.enum
                    or node.type_.type == TokenType.TEXT
                    or node.type_.type == TokenType.BYTES
                ):
                    self.o(
                        f"\t\tif (i.{lname} !== null) this.{lname} = i.{lname};"
                    )
                elif (
                    node.type_.type in typeMap
                    or node.type_.type == TokenType.BOOL
                    or node.enum
                    or node.struct
                ):
                    self.o(f"\t\tthis.{lname} = i.{lname};")
                elif node.table:
                    if node.table.empty:
                        self.o(f"\t\t if (i.{lname} !== null) this.add{uname}();")
                    else:
                        self.o(
                            f"\t\t if (i.{lname} !== null) this.add{uname}()._copy(i.{lname});"
                        )
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
        self.o(f"export class {table.name}In extends scalgoproto.TableIn {{")
        self.o(f"\tstatic readonly _MAGIC = 0x{table.magic:08X};")
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
        self.o(f"export class {table.name}Out extends scalgoproto.TableOut {{")
        self.o(f"\tstatic readonly _MAGIC = 0x{table.magic:08X};")
        self.o("\tstatic readonly _SIZE = %d;" % len(table.default))
        self.o(f"\tstatic readonly _IN = {table.name}In;")
        self.o()
        self.o(
            "\t/** Private constructor. Call factory methods on scalgoproto.Reader to construct instances */"
        )
        self.o("\tconstructor(writer: scalgoproto.Writer, withHeader: boolean) {")
        self.o(
            f'\t\tsuper(writer, withHeader, "{cescape(table.default)}", {table.name}Out._MAGIC);'
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
        self.o(f"export class {node.name} extends scalgoproto.StructType {{")
        ctor = []
        read = []
        write = []
        for v in node.members:
            n = lcamel(self.value(v.identifier))
            if v.type_.type in typeMap:
                ti = typeMap[v.type_.type]
                if v.type_.type in (TokenType.F32, TokenType.F64):
                    ctor.append(f"public {n}: {ti.p} = 0.0")
                elif v.type_.type == TokenType.BOOL:
                    ctor.append(f"public {n}: {ti.p} = false")
                else:
                    ctor.append(f"public {n}: {ti.p} = 0")

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
                ctor.append(f"public {n}: {v.enum.name} = 0")
                read.append(
                    "reader._data.getUint8(offset + %d) as %s" % (v.offset, v.enum.name)
                )
                write.append(
                    "writer._data.setUint8(offset + %d, +ins.%s)" % (v.offset, n)
                )
            elif v.struct:
                ctor.append(
                    f"public {n}: {v.struct.name} = new {v.struct.name}()"
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
        self.o("\tconstructor({}) {{super();}}".format(", ".join(ctor)))
        self.o()
        self.o(
            f"\tstatic _write(writer: scalgoproto.Writer, offset: number, ins: {node.name}) {{"
        )
        for line in write:
            self.o(f"\t\t{line};")
        self.o("\t}")
        self.o()
        self.o(
            f"\tstatic _read(reader: scalgoproto.Reader, offset: number) : {node.name} {{"
        )
        self.o(f"\t\treturn new {node.name}(")
        for line in read:
            self.o(f"\t\t\t{line},")
        self.o("\t\t);")
        self.o("\t}")
        self.o("}")
        self.o()

    def generate_enum(self, node: Enum) -> None:
        self.output_doc(node, "")
        self.o(f"export enum {node.name} {{")
        for ev in node.members:
            self.o(f"    {self.value(ev.identifier)},")
        self.o("}")
        self.o()

    def generate(self, ast: list[AstNode]) -> None:
        imports: dict[int, set[str]] = {}
        for node in ast:
            if node.document != 0:
                continue
            for u in node.uses:
                if u.document == 0:
                    continue
                if u.document not in imports:
                    imports[u.document] = set()
                i = imports[u.document]
                if isinstance(u, (Struct, Enum)):
                    i.add(u.name)
                elif isinstance(u, (Table, Union)):
                    i.add(f"{u.name}In")
                    i.add(f"{u.name}Out")
                else:
                    raise ICE()

        for d, imp in imports.items():
            doc = self.documents.by_id[d]
            self.o("import {{{}}} from '{}'".format(", ".join(imp), doc.name))

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
    out = open(os.path.join(args.output, f"{documents.root.name}.ts"), "w")
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
        print(file=out)

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
