"""
Generate python reader/wirter
"""

import math
import os
from typing import NamedTuple, TextIO
from .documents import Documents

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


column_array: dict[TokenType, str] = {
    TokenType.I8: "Int8Array",
    TokenType.I16: "Int16Array",
    TokenType.I32: "Int32Array",
    TokenType.I64: "Float64Array",
    TokenType.U8: "Uint8Array",
    TokenType.U16: "Uint16Array",
    TokenType.UI32: "Uint32Array",
    TokenType.UI64: "Float64Array",
    TokenType.F32: "Float32Array",
    TokenType.F64: "Float64Array",
}


class Generator:
    def __init__(self, documents: Documents, out: TextIO, import_prefix: str) -> None:
        self.documents: Documents = documents
        self.out: TextIO = out
        if import_prefix and import_prefix[-1] != ".":
            import_prefix += "."
        self.import_prefix: str = import_prefix
        self.indent = ""

    def out_list_type(self, node: Value) -> str:
        """The class used to write the list node"""
        if node.type_.type == TokenType.BOOL:
            return "scalgoproto.BoolListOut"
        elif node.type_.type in typeMap:
            return "scalgoproto.%sListOut" % typeMap[node.type_.type].n
        elif node.struct:
            return "%s_ListOut" % node.struct.name
        elif node.enum:
            return "scalgoproto.EnumListOut<%s>" % node.enum.name
        elif node.table:
            if node.direct:
                return "%s_DirectListOut" % node.table.name
            return "%s_ListOut" % node.table.name
        elif node.union:
            return "%s_ListOut" % node.union.name
        elif node.type_.type == TokenType.TEXT:
            return "scalgoproto.TextListOut"
        elif node.type_.type == TokenType.BYTES:
            return "scalgoproto.BytesListOut"
        else:
            raise ICE()

    def in_list_help(self, node: Value) -> tuple[str, str]:
        """Return the element type and the list class used to read the list node"""
        if node.type_.type == TokenType.BOOL:
            return ("boolean", "scalgoproto.BoolListIn")
        elif node.type_.type in typeMap:
            ti = typeMap[node.type_.type]
            return (ti.p, "scalgoproto.%sListIn" % ti.n)
        elif node.struct:
            return (node.struct.name, "%s_ListIn" % node.struct.name)
        elif node.enum:
            return (
                node.enum.name + " | null",
                "scalgoproto.EnumListIn<%s>" % node.enum.name,
            )
        elif node.table:
            if node.direct:
                return (node.table.name + "In", "%s_DirectListIn" % node.table.name)
            return (node.table.name + "In | null", "%s_ListIn" % node.table.name)
        elif node.union:
            return (node.union.name + "In", "%s_ListIn" % node.union.name)
        elif node.type_.type == TokenType.TEXT:
            return ("string | null", "scalgoproto.TextListIn")
        elif node.type_.type == TokenType.BYTES:
            return ("globalThis.Uint8Array | null", "scalgoproto.BytesListIn")
        else:
            raise ICE()

    def default_value(self, node: Value) -> str:
        v = node.parsed_value
        if isinstance(v, float):
            if math.isnan(v):
                return "(0 / 0)"
            if math.isinf(v):
                return "(1 / 0)" if v > 0 else "(-1 / 0)"
            return repr(v)
        if isinstance(v, bool):
            return "true" if v else "false"
        return str(v)

    def table_ptr(self, offset: int, inplace: bool, magic: str) -> None:
        """Output code resolving a pointer member of a table.

        Afterwards r is the reader, o the offset of the content and s the size.
        Returns null if the member is absent"""
        self.o("\t\tif (%d >= this._size) return null;" % offset)
        if inplace:
            self.o("\t\tconst r = this._r, s = r._u48(this._off + %d);" % offset)
            self.o("\t\tif (s === 0) return null;")
            self.o("\t\tconst o = this._off + this._size;")
        else:
            self.o("\t\tconst r = this._r, p = r._u48(this._off + %d);" % offset)
            self.o("\t\tif (p === 0) return null;")
            self.o("\t\tconst o = p + 10, s = r._size(p, %s);" % magic)

    def union_ptr(self, lname: str, idx: int, magic: str) -> None:
        """Output code resolving the pointer of a union member.

        Afterwards r is the reader, o the offset of the content and s the size.
        Returns null if the member is not set"""
        self.o("\t\tif (this._type !== %d) return null;" % idx)
        self.o("\t\tconst r = this._r;")
        self.o("\t\tlet o = this._off, s = this._size;")
        self.o("\t\tif (s < 0) {")
        self.o("\t\t\tif (o === 0) return null;")
        self.o("\t\t\ts = r._size(o, %s);" % magic)
        self.o("\t\t\to += 10;")
        self.o("\t\t}")

    def o(self, text="") -> None:
        if text and self.indent:
            text = self.indent + text
        print(text, file=self.out)

    def value(self, t: Token) -> str:
        return self.documents.by_id[t.document].content[t.index : t.index + t.length]

    def output_doc(
        self,
        node: AstNode,
        indent: str = "",
        prefix: list[str] = [],
        suffix: list[str] = [],
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
        (tn, cls) = self.in_list_help(node)
        magic = "DIRECT_LIST_MAGIC" if node.direct else "LIST_MAGIC"
        self.output_doc(node, "\t")
        self.o("\tget %s(): %s | null {" % (lname, cls))
        self.table_ptr(node.offset, bool(node.inplace), "scalgoproto.%s" % magic)
        self.o("\t\treturn new %s(r, o, s);" % cls)
        self.o("\t}")
        self.o()

    def generate_union_list_in(self, node: Value, lname: str, idx: int) -> None:
        (tn, cls) = self.in_list_help(node)
        magic = "DIRECT_LIST_MAGIC" if node.direct else "LIST_MAGIC"
        self.output_doc(node, "\t")
        self.o("\tget %s(): %s | null {" % (lname, cls))
        self.union_ptr(lname, idx, "scalgoproto.%s" % magic)
        self.o("\t\treturn new %s(r, o, s);" % cls)
        self.o("\t}")
        self.o()

    def generate_list_out(self, node: Value, lname: str, size: int) -> None:
        store = "w._u48(this._off + %d, %%s)" % node.offset
        self.emit_list_setter(
            node, lname, store.replace("w._u48", "this._w._u48"), bool(node.inplace)
        )
        self.emit_list_adder(
            node, lname, store, bool(node.inplace), "this._off + %d" % size
        )

    def generate_union_list_out(
        self, node: Value, lname: str, idx: int, inplace: bool
    ) -> None:
        store = "this._set(%d, %%s)" % idx
        self.emit_list_setter(node, lname, store, inplace)
        self.emit_list_adder(node, lname, store, inplace, "this._end")

    def column_specs(
        self, members: list[Value], base: int, prefix: str, in_table: bool
    ) -> list[tuple]:
        """Describe the columns produced by toColumns for the given members.

        Each spec is one of
        ("num", name, offset, array type, read expression of {o}, default),
        ("bit", name, offset, bit),
        ("obj", name, ts type, getter name)"""
        specs: list[tuple] = []
        for v in members:
            if v.type_.type == TokenType.REMOVED:
                continue
            lname = lcamel(self.value(v.identifier))
            name = prefix + lname
            off = base + v.offset
            tt = v.type_.type
            is_float = tt in (TokenType.F32, TokenType.F64)
            if in_table and v.optional and not is_float and not v.list_:
                if tt in typeMap or v.struct:
                    specs.append(("bit", name + "_has", base + v.has_offset, v.has_bit))
            if v.list_ or tt in (TokenType.TEXT, TokenType.BYTES) or v.union:
                if in_table:
                    specs.append(("obj", name, self.getter_type(v), lname))
            elif v.table:
                if in_table and not v.table.empty:
                    specs.append(("obj", name, "%sIn | null" % v.table.name, lname))
            elif tt == TokenType.BOOL:
                if in_table:
                    specs.append(("bit", name, off, v.bit))
                else:
                    specs.append(
                        ("num", name, off, "Uint8Array", "dv.getUint8({o})", "0")
                    )
            elif tt in typeMap:
                array = column_array[tt]
                read = self.read_basic(tt, "{o}", "dv", "r")
                default = self.default_value(v) if in_table else "0"
                specs.append(("num", name, off, array, read, default))
            elif v.enum:
                default = self.default_value(v) if in_table else "0"
                specs.append(
                    ("num", name, off, "Uint8Array", "dv.getUint8({o})", default)
                )
            elif v.struct:
                specs.extend(
                    self.column_specs(v.struct.members, off, name + "_", False)
                )
            else:
                raise ICE()
        return specs

    def getter_type(self, v: Value) -> str:
        """Type returned by the reader getter of a pointer member"""
        if v.list_:
            return "%s | null" % self.in_list_help(v)[1]
        if v.type_.type == TokenType.TEXT:
            return "string | null"
        if v.type_.type == TokenType.BYTES:
            return "globalThis.Uint8Array | null"
        if v.union:
            return "%sIn" % v.union.name
        raise ICE()

    def columns_interface(self, name: str, specs: list[tuple], doc: str) -> None:
        self.o("/** %s */" % doc)
        self.o("export interface %s_Columns {" % name)
        for spec in specs:
            if spec[0] == "num":
                self.o("\t%s: globalThis.%s;" % (spec[1], spec[3]))
            elif spec[0] == "bit":
                self.o("\t%s: globalThis.Uint8Array;" % spec[1])
            else:
                self.o("\t%s: globalThis.Array<%s>;" % (spec[1], spec[2]))
        self.o("}")
        self.o()

    def to_columns(
        self, name: str, specs: list[tuple], width: str, size: int, cursor: bool
    ) -> None:
        """Output the toColumns method of a list class.

        width is an expression giving the size of each element, and size the size of an
        element in this version of the schema. Elements written with an older schema
        may be smaller; members beyond their end get their default"""
        self.o("\t/** Read the list into one array per field */")
        self.o("\ttoColumns(): %s_Columns {" % name)
        self.o("\t\tconst _n = this.length, _w = %s, _o = this._off;" % width)
        if any(sp[0] != "obj" for sp in specs):
            self.o("\t\tconst dv = this._dv;")
        if any(sp[0] == "num" and "r._" in sp[4] for sp in specs):
            self.o("\t\tconst r = this._r;")
        for spec in specs:
            if spec[0] == "num":
                self.o("\t\tconst c_%s = new globalThis.%s(_n);" % (spec[1], spec[3]))
            elif spec[0] == "bit":
                self.o("\t\tconst c_%s = new globalThis.Uint8Array(_n);" % spec[1])
            else:
                self.o(
                    "\t\tconst c_%s = new globalThis.Array<%s>(_n);"
                    % (spec[1], spec[2])
                )
        objs = [spec for spec in specs if spec[0] == "obj"]
        if cursor:
            self.o("\t\tconst c = this.cursor();")

        def row(i: str, o: str) -> None:
            for spec in specs:
                kind, col = spec[0], "c_" + spec[1]
                if kind == "num":
                    at = "%s + %d" % (o, spec[2]) if spec[2] else o
                    self.o("\t\t\t%s[%s] = %s;" % (col, i, spec[4].format(o=at)))
                elif kind == "bit":
                    at = "%s + %d" % (o, spec[2]) if spec[2] else o
                    self.o(
                        "\t\t\t%s[%s] = (dv.getUint8(%s) >> %d) & 1;"
                        % (col, i, at, spec[3])
                    )

        if not cursor:
            # Structs have a fixed size, so the elements are always whole
            self.o("\t\tfor (let i = 0, o = _o; i < _n; ++i, o += _w) {")
            row("i", "o")
            self.o("\t\t}")
            self.o(
                "\t\treturn {%s};"
                % ", ".join("%s: c_%s" % (sp[1], sp[1]) for sp in specs)
            )
            self.o("\t}")
            self.o()
            return

        # Common case: whole elements in a single pass, which is cache friendly
        self.o("\t\tif (_w >= %d) {" % size)
        self.o("\t\t\tfor (let i = 0, o = _o; i < _n; ++i, o += _w) {")
        self.indent = "\t"
        row("i", "o")
        if objs:
            self.o("\t\t\tc._off = o;")
            for spec in objs:
                self.o("\t\t\tc_%s[i] = c.%s;" % (spec[1], spec[3]))
        self.indent = ""
        self.o("\t\t\t}")
        self.o("\t\t} else {")
        # Elements from an older schema: check once per column whether it exists
        for spec in specs:
            kind, col = spec[0], "c_" + spec[1]
            if kind == "num":
                _, _, off, array, read, default = spec
                self.o("\t\t\tif (%d < _w)" % off)
                self.o(
                    "\t\t\t\tfor (let i = 0, o = _o + %d; i < _n; ++i, o += _w) %s[i] = %s;"
                    % (off, col, read.format(o="o"))
                )
                if default not in ("0", "0.0"):
                    self.o("\t\t\telse %s.fill(%s);" % (col, default))
            elif kind == "bit":
                _, _, off, bit = spec
                self.o("\t\t\tif (%d < _w)" % off)
                self.o(
                    "\t\t\t\tfor (let i = 0, o = _o + %d; i < _n; ++i, o += _w) %s[i] = (dv.getUint8(o) >> %d) & 1;"
                    % (off, col, bit)
                )
        if objs:
            self.o("\t\t\tfor (let i = 0, o = _o; i < _n; ++i, o += _w) {")
            self.o("\t\t\t\tc._off = o;")
            for spec in objs:
                self.o("\t\t\t\tc_%s[i] = c.%s;" % (spec[1], spec[3]))
            self.o("\t\t\t}")
        self.o("\t\t}")
        self.o(
            "\t\treturn {%s};" % ", ".join("%s: c_%s" % (sp[1], sp[1]) for sp in specs)
        )
        self.o("\t}")
        self.o()

    def list_helpers(self, t: str) -> None:
        """Output forEach and toArray for a generated list class with element type t.

        They are repeated in every list class so each copy gets its own type feedback,
        which keeps them fast when many kinds of lists are used"""
        self.o("\tforEach(fn: (value: %s, index: number) => void): void {" % t)
        self.o("\t\tconst n = this.length;")
        self.o("\t\tfor (let i = 0; i < n; ++i) fn(this.get(i), i);")
        self.o("\t}")
        self.o()
        self.o("\ttoArray(): globalThis.Array<%s> {" % t)
        self.o("\t\tconst n = this.length;")
        self.o("\t\tconst ans = new globalThis.Array<%s>(n);" % t)
        self.o("\t\tfor (let i = 0; i < n; ++i) ans[i] = this.get(i);")
        self.o("\t\treturn ans;")
        self.o("\t}")

    def has_expr(self, node: Value) -> str:
        return "(%d < this._size && (this._dv.getUint8(this._off + %d) & %d) !== 0)" % (
            node.has_offset,
            node.has_offset,
            1 << node.has_bit,
        )

    def generate_bool_in(self, node: Value, lname: str) -> None:
        if node.inplace:
            raise ICE()
        self.output_doc(node, "\t")
        self.o("\tget %s(): boolean%s {" % (lname, " | null" if node.optional else ""))
        if node.optional:
            self.o("\t\tif (!%s) return null;" % self.has_expr(node))
        self.o(
            "\t\treturn %d < this._size && (this._dv.getUint8(this._off + %d) & %d) !== 0;"
            % (node.offset, node.offset, 1 << node.bit)
        )
        self.o("\t}")
        self.o()

    def read_basic(self, tt: TokenType, o: str, dv: str, r: str) -> str:
        """Expression reading a basic type at offset o"""
        if tt == TokenType.I64:
            return "%s._i64(%s)" % (r, o)
        if tt == TokenType.UI64:
            return "%s._u64(%s)" % (r, o)
        if tt == TokenType.BOOL:
            return "%s.getUint8(%s) !== 0" % (dv, o)
        ti = typeMap[tt]
        if tt in (TokenType.I8, TokenType.U8):
            return "%s.get%s(%s)" % (dv, ti.n, o)
        return "%s.get%s(%s, true)" % (dv, ti.n, o)

    def generate_basic_in(self, node: Value, lname: str) -> None:
        if node.inplace:
            raise ICE()
        tt = node.type_.type
        ti = typeMap[tt]
        is_float = tt in (TokenType.F32, TokenType.F64)
        read = self.read_basic(
            tt, "this._off + %d" % node.offset, "this._dv", "this._r"
        )
        self.output_doc(node, "\t")
        self.o("\tget %s(): %s%s {" % (lname, ti.p, " | null" if node.optional else ""))
        if node.optional and is_float:
            self.o("\t\tif (%d >= this._size) return null;" % node.offset)
            self.o("\t\tconst v = %s;" % read)
            self.o("\t\treturn v !== v ? null : v;")
        else:
            if node.optional:
                self.o("\t\tif (!%s) return null;" % self.has_expr(node))
            self.o(
                "\t\treturn %d < this._size ? %s : %s;"
                % (node.offset, read, self.default_value(node))
            )
        self.o("\t}")
        self.o()
        if tt in (TokenType.I64, TokenType.UI64):
            self.output_doc(
                node, "\t", suffix=["Exact value of %s as a bigint" % lname]
            )
            self.o(
                "\tget %s_bigint(): bigint%s {"
                % (lname, " | null" if node.optional else "")
            )
            if node.optional:
                self.o("\t\tif (!%s) return null;" % self.has_expr(node))
            self.o(
                "\t\treturn %d < this._size ? this._dv.get%s(this._off + %d, true) : %dn;"
                % (
                    node.offset,
                    "BigInt64" if tt == TokenType.I64 else "BigUint64",
                    node.offset,
                    int(node.parsed_value),
                )
            )
            self.o("\t}")
            self.o()

    def generate_bool_out(self, node: Value, lname: str) -> None:
        self.output_doc(node, "\t")
        self.o("\tset %s(value: boolean) {" % (lname,))
        if node.optional:
            self.o("\t\t" + self.set_has(node))
        self.o(
            "\t\tthis._w._bit(this._off + %d, %d, value);"
            % (node.offset, 1 << node.bit)
        )
        self.o("\t}")
        self.o()

    def generate_basic_out(self, node: Value, lname: str) -> None:
        if node.inplace:
            raise ICE()
        tt = node.type_.type
        ti = typeMap[tt]
        has = node.optional and tt not in (TokenType.F32, TokenType.F64)
        self.output_doc(node, "\t")
        self.o("\tset %s(value: %s) {" % (lname, ti.p))
        if has:
            self.o("\t\t" + self.set_has(node))
        self.o(
            "\t\t%s;"
            % self.write_basic(
                tt, "this._off + %d" % node.offset, "value", "this._w._dv", "this._w"
            )
        )
        self.o("\t}")
        self.o()
        if tt in (TokenType.I64, TokenType.UI64):
            self.output_doc(node, "\t", suffix=["Set %s to an exact bigint" % lname])
            self.o("\tset %s_bigint(value: bigint) {" % lname)
            if has:
                self.o("\t\t" + self.set_has(node))
            self.o(
                "\t\tthis._w._dv.set%s(this._off + %d, value, true);"
                % ("BigInt64" if tt == TokenType.I64 else "BigUint64", node.offset)
            )
            self.o("\t}")
            self.o()

    def generate_enum_in(self, node: Value, lname: str) -> None:
        if node.inplace:
            raise ICE()
        self.output_doc(node, "\t")
        self.o("\tget %s(): %s | null {" % (lname, node.enum.name))
        self.o(
            "\t\tconst v = %d < this._size ? this._dv.getUint8(this._off + %d) : %s;"
            % (node.offset, node.offset, self.default_value(node))
        )
        self.o("\t\treturn v === 255 ? null : v as %s;" % (node.enum.name))
        self.o("\t}")
        self.o()

    def generate_enum_out(self, node: Value, lname: str) -> None:
        if node.inplace:
            raise ICE()
        self.output_doc(node, "\t")
        self.o("\tset %s(value: %s | null) {" % (lname, node.enum.name))
        self.o(
            "\t\tthis._w._dv.setUint8(this._off + %d, value === null ? 255 : value as number);"
            % node.offset
        )
        self.o("\t}")
        self.o()

    def generate_struct_in(self, node: Value, lname: str) -> None:
        if node.inplace:
            raise ICE()
        self.output_doc(node, "\t")
        self.o(
            "\tget %s(): %s%s {"
            % (lname, node.struct.name, " | null" if node.optional else "")
        )
        if node.optional:
            self.o("\t\tif (!%s) return null;" % self.has_expr(node))
        self.o(
            "\t\tif (%d >= this._size) return new %s();"
            % (node.offset, node.struct.name)
        )
        self.o(
            "\t\treturn %s._read(this._r, this._off + %d);"
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
            self.o("\t\t" + self.set_has(node))
        self.o(
            "\t\t%s._write(this._w, this._off + %d, value);"
            % (node.struct.name, node.offset)
        )
        self.o("\t}")
        self.o()

    def generate_table_in(self, node: Value, lname: str) -> None:
        if not node.table.empty:
            self.output_doc(node, "\t")
            self.o("\tget %s(): %sIn | null {" % (lname, node.table.name))
            self.table_ptr(
                node.offset, bool(node.inplace), "%sIn._MAGIC" % node.table.name
            )
            self.o("\t\treturn new %sIn(r, o, s);" % (node.table.name,))
            self.o("\t}")
            self.o()

    def generate_union_table_in(self, node: Value, lname: str, idx: int) -> None:
        if not node.table.empty:
            self.output_doc(node, "\t")
            self.o("\tget %s(): %sIn | null {" % (lname, node.table.name))
            self.union_ptr(lname, idx, "%sIn._MAGIC" % node.table.name)
            self.o("\t\treturn new %sIn(r, o, s);" % (node.table.name,))
            self.o("\t}")
            self.o()

    def generate_table_out(self, node: Value, lname: str, size: int) -> None:
        store = "this._w._u48(this._off + %d, %%s)" % node.offset
        self.output_doc(node, "\t")
        if node.table.empty:
            # Empty tables have no content, store their (zero) size
            self.o("\tadd%s(): void {" % ucamel(lname))
            self.o("\t\t" + store % "0" + ";")
            self.o("\t}")
            self.o()
        elif not node.inplace:
            self.emit_table_setter(node.table, lname, store)
            self.emit_table_adder(node.table, lname, store)
        else:
            self.emit_inplace_table_adder(
                node.table, lname, store, "this._off + %d" % size
            )

    def generate_union_table_out(
        self, node: Value, lname: str, idx: int, inplace: bool
    ) -> None:
        store = "this._set(%d, %%s)" % idx
        self.output_doc(node, "\t")
        if node.table.empty:
            self.o("\tadd%s(): void {" % ucamel(lname))
            self.o("\t\t" + store % "0" + ";")
            self.o("\t}")
            self.o()
        elif not inplace:
            self.emit_table_setter(node.table, lname, store)
            self.emit_table_adder(node.table, lname, store)
        else:
            self.emit_inplace_table_adder(node.table, lname, store, "this._end")

    def generate_text_in(self, node: Value, lname: str) -> None:
        self.output_doc(node, "\t")
        self.o("\tget %s(): string | null {" % (lname))
        self.table_ptr(node.offset, bool(node.inplace), "scalgoproto.TEXT_MAGIC")
        self.o("\t\treturn r._text(o, s);")
        self.o("\t}")
        self.o()

    def generate_union_text_in(self, node: Value, lname: str, idx: int) -> None:
        self.output_doc(node, "\t")
        self.o("\tget %s(): string | null {" % (lname))
        self.union_ptr(lname, idx, "scalgoproto.TEXT_MAGIC")
        self.o("\t\treturn r._text(o, s);")
        self.o("\t}")
        self.o()

    def generate_text_out(self, node: Value, lname: str, size: int) -> None:
        self.output_doc(node, "\t")
        self.emit_text_bytes_out(
            lname,
            True,
            "w._u48(this._off + %d, %%s)" % node.offset,
            bool(node.inplace),
            "this._off + %d" % size,
        )

    def generate_union_text_out(
        self, node: Value, lname: str, idx: int, inplace: bool
    ) -> None:
        self.output_doc(node, "\t")
        self.emit_text_bytes_out(
            lname, True, "this._set(%d, %%s)" % idx, inplace, "this._end"
        )

    def generate_bytes_in(self, node: Value, lname: str) -> None:
        self.output_doc(
            node, "\t", suffix=["The bytes are returned as a view of the message"]
        )
        self.o("\tget %s(): globalThis.Uint8Array | null {" % (lname))
        self.table_ptr(node.offset, bool(node.inplace), "scalgoproto.BYTES_MAGIC")
        self.o("\t\treturn r._bytes(o, s);")
        self.o("\t}")
        self.o()

    def generate_union_bytes_in(self, node: Value, lname: str, idx: int) -> None:
        self.output_doc(
            node, "\t", suffix=["The bytes are returned as a view of the message"]
        )
        self.o("\tget %s(): globalThis.Uint8Array | null {" % (lname))
        self.union_ptr(lname, idx, "scalgoproto.BYTES_MAGIC")
        self.o("\t\treturn r._bytes(o, s);")
        self.o("\t}")
        self.o()

    def generate_bytes_out(self, node: Value, lname: str, size: int) -> None:
        self.output_doc(node, "\t")
        self.emit_text_bytes_out(
            lname,
            False,
            "w._u48(this._off + %d, %%s)" % node.offset,
            bool(node.inplace),
            "this._off + %d" % size,
        )

    def generate_union_bytes_out(
        self, node: Value, lname: str, idx: int, inplace: bool
    ) -> None:
        self.output_doc(node, "\t")
        self.emit_text_bytes_out(
            lname, False, "this._set(%d, %%s)" % idx, inplace, "this._end"
        )

    def generate_union_in(self, node: Value, lname: str, table: Table) -> None:
        self.output_doc(node, "\t")
        self.o("\tget %s(): %sIn {" % (lname, node.union.name))
        self.o("\t\tconst o = this._off + %d;" % node.offset)
        self.o(
            "\t\tif (%d >= this._size) return new %sIn(this._r, 0, 0);"
            % (node.offset, node.union.name)
        )
        if node.inplace:
            self.o(
                "\t\treturn new %sIn(this._r, this._dv.getUint16(o, true), this._off + this._size, this._r._u48(o + 2));"
                % (node.union.name,)
            )
        else:
            self.o(
                "\t\treturn new %sIn(this._r, this._dv.getUint16(o, true), this._r._u48(o + 2));"
                % (node.union.name,)
            )
        self.o("\t}")
        self.o()

    def generate_union_out(self, node: Value, lname: str, table: Table) -> None:
        self.output_doc(node, "\t")
        if node.inplace:
            self.o("\tget %s(): %s_InplaceOut {" % (lname, node.union.name))
            self.o(
                "\t\treturn new %s_InplaceOut(this._w, this._off + %d, this._off + %d);"
                % (node.union.name, node.offset, len(table.default))
            )
        else:
            self.o("\tget %s(): %sOut {" % (lname, node.union.name))
            self.o(
                "\t\treturn new %sOut(this._w, this._off + %d);"
                % (node.union.name, node.offset)
            )
        self.o("\t}")
        self.o()

    def generate_value_in(self, table: Table, node: Value) -> None:
        if node.type_.type == TokenType.REMOVED:
            return
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
        if node.type_.type == TokenType.REMOVED:
            return
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

    def generate_union_copy(self, union: Union, inplace: bool) -> None:
        self.o("\t/** Set this union to a copy of a union read from another message */")
        self.o("\t_copy(i: %sIn): void {" % union.name)
        self.o("\t\tswitch (i.type) {")
        for idx, node in enumerate(union.members, start=1):
            if node.type_.type == TokenType.REMOVED:
                continue
            lname = lcamel(self.value(node.identifier))
            self.o("\t\tcase %d: {" % idx)
            if node.table and node.table.empty:
                self.o("\t\t\tthis.add%s();" % ucamel(lname))
            elif node.type_.type == TokenType.TEXT and not node.list_:
                # Copy the bytes of the text, without decoding and encoding it
                self.o("\t\t\tconst r = i._r;")
                self.o(
                    "\t\t\tconst b = i._size >= 0 ? r._bytes(i._off, i._size) : i._off === 0 ? null :"
                )
                self.o(
                    "\t\t\t\tr._bytes(i._off + 10, r._size(i._off, scalgoproto.TEXT_MAGIC));"
                )
                self.o("\t\t\tif (b === null) {")
                self.o("\t\t\t\tthis._set(%d, 0);" % idx)
                self.o("\t\t\t} else {")
                if inplace:
                    self.o("\t\t\t\tthis._w._checkInplace(this._end);")
                    self.o(
                        "\t\t\t\tthis._set(%d, this._w._inplaceTextFromBytes(b));" % idx
                    )
                else:
                    self.o("\t\t\t\tthis._set(%d, this._w._textFromBytes(b));" % idx)
                self.o("\t\t\t}")
            else:
                # The type may be set with no value
                self.o("\t\t\tconst v = i.%s;" % lname)
                self.o("\t\t\tif (v === null) this._set(%d, 0);" % idx)
                self.o("\t\t\telse this.%s = v;" % lname)
            self.o("\t\t\tbreak;")
            self.o("\t\t}")
        self.o("\t\tdefault:")
        self.o("\t\t\t// Not set, or a member unknown to this schema")
        self.o("\t\t\tthis._set(0, 0);")
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
        self.o("\tNONE = 0,")
        for idx, member in enumerate(union.members, start=1):
            if not isinstance(member, (Table, Value)):
                raise ICE()
            if member.type_.type == TokenType.REMOVED:
                continue
            self.o("\t%s = %d," % (self.value(member.identifier).upper(), idx))
        self.o("}")
        self.o()

        self.output_doc(union, "")
        self.o("export class %sIn {" % union.name)
        self.o("\tdeclare _r: scalgoproto.Reader;")
        self.o("\tdeclare _type: number;")
        self.o(
            "\t/** Offset of the content if inplace, otherwise offset of the magic */"
        )
        self.o("\tdeclare _off: number;")
        self.o("\t/** Size of the content if inplace, otherwise -1 */")
        self.o("\tdeclare _size: number;")
        self.o()
        self.o(
            "\t/** Private constructor. Use the accessors on tables and lists to get instances */"
        )
        self.o(
            "\tconstructor(reader: scalgoproto.Reader, type: number, offset: number, size: number | null = null) {"
        )
        self.o("\t\tthis._r = reader;")
        self.o("\t\tthis._type = type;")
        self.o("\t\tthis._off = offset;")
        self.o("\t\tthis._size = size === null ? -1 : size;")
        self.o("\t}")
        self.o()

        self.o("\tget type(): %sType {" % (union.name))
        self.o("\t\treturn this._type as %sType;" % (union.name))
        self.o("\t}")
        self.o()
        for idx, member in enumerate(union.members, start=1):
            if member.type_.type == TokenType.REMOVED:
                continue
            n = self.value(member.identifier)
            lname = lcamel(n)
            self.o("\tget is%s(): boolean {" % (ucamel(lname)))
            self.o("\t\treturn this._type === %d;" % idx)
            self.o("\t}")
            self.o()
            if member.list_:
                self.generate_union_list_in(member, lname, idx)
            elif member.table:
                self.generate_union_table_in(member, lname, idx)
            elif member.type_.type == TokenType.BYTES:
                self.generate_union_bytes_in(member, lname, idx)
            elif member.type_.type == TokenType.TEXT:
                self.generate_union_text_in(member, lname, idx)
            else:
                raise ICE()
        self.o("}")
        self.o()

        self.o(
            "export class %s_ListIn extends scalgoproto.UnionListIn<%sIn> {"
            % (union.name, union.name)
        )
        self.o("\tget(i: number): %sIn {" % union.name)
        self.o(
            "\t\tif (!((i >>> 0) === i && i < this.length)) scalgoproto._indexError(i, this.length);"
        )
        self.o("\t\tconst o = this._off + i * 8;")
        self.o(
            "\t\treturn new %sIn(this._r, this._dv.getUint16(o, true), this._r._u48(o + 2));"
            % union.name
        )
        self.o("\t}")
        self.o()
        self.list_helpers("%sIn" % union.name)
        self.o("}")
        self.o()

        self.generate_union_writers(union)

    def generate_table_copy(self, table: Table) -> None:
        self.o("\t/** Set this table to a copy of a table read from another message */")
        self.o("\t_copy(i: %sIn): void {" % table.name)
        # Inplace members must be written first, right after the table
        for ip in (True, False):
            for node in table.members:
                if node.type_.type == TokenType.REMOVED:
                    continue
                if bool(node.inplace) != ip:
                    continue
                lname = lcamel(self.value(node.identifier))
                uname = ucamel(lname)
                tt = node.type_.type
                f = node.offset
                # Each member is read only once
                if node.list_:
                    self.o(
                        "\t\t{ const v = i.%s; if (v !== null) this.add%s(v.length)._copy(v); }"
                        % (lname, uname)
                    )
                elif node.union:
                    self.o("\t\tthis.%s._copy(i.%s);" % (lname, lname))
                elif node.table:
                    if node.table.empty:
                        self.o("\t\tif (i.%s !== null) this.add%s();" % (lname, uname))
                    else:
                        self.o(
                            "\t\t{ const v = i.%s; if (v !== null) this.add%s()._copy(v); }"
                            % (lname, uname)
                        )
                elif tt == TokenType.TEXT and not node.inplace:
                    # Copy the bytes of the text, without decoding and encoding it
                    self.o("\t\tif (%d < i._size) {" % f)
                    self.o("\t\t\tconst p = i._r._u48(i._off + %d);" % f)
                    self.o(
                        "\t\t\tif (p !== 0) this._w._u48(this._off + %d, this._w._copyText(i._r, p));"
                        % f
                    )
                    self.o("\t\t}")
                elif tt == TokenType.TEXT:
                    # Inplace text: copy its bytes, without decoding and encoding it
                    self.o("\t\tif (%d < i._size) {" % f)
                    self.o("\t\t\tconst s = i._r._u48(i._off + %d);" % f)
                    self.o("\t\t\tif (s !== 0) {")
                    self.o(
                        "\t\t\t\tthis._w._checkInplace(this._off + %d);"
                        % len(table.default)
                    )
                    self.o(
                        "\t\t\t\tthis._w._u48(this._off + %d, this._w._inplaceTextFromBytes(i._r._bytes(i._off + i._size, s)));"
                        % f
                    )
                    self.o("\t\t\t}")
                    self.o("\t\t}")
                elif tt in (TokenType.I64, TokenType.UI64):
                    # Copy the 8 bytes, which is exact and needs no bigint
                    copy = "this._w._copy8(this._off + %d, i._dv, i._off + %d);" % (
                        f,
                        f,
                    )
                    if node.optional:
                        # A value outside the table reads as the default, which the
                        # new table already has
                        has = (
                            "%d < i._size && (i._dv.getUint8(i._off + %d) & %d) !== 0"
                            % (
                                node.has_offset,
                                node.has_offset,
                                1 << node.has_bit,
                            )
                        )
                        self.o(
                            "\t\tif (%s) { %s if (%d < i._size) %s }"
                            % (has, self.set_has(node), f, copy)
                        )
                    else:
                        self.o("\t\tif (%d < i._size) %s" % (f, copy))
                elif (
                    node.optional
                    or node.enum
                    or tt == TokenType.TEXT
                    or tt == TokenType.BYTES
                ):
                    self.o(
                        "\t\t{ const v = i.%s; if (v !== null) this.%s = v; }"
                        % (lname, lname)
                    )
                elif tt in typeMap or tt == TokenType.BOOL or node.struct:
                    self.o("\t\tthis.%s = i.%s;" % (lname, lname))
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
        self.o("export class %sIn {" % table.name)
        self.o("\tstatic readonly _MAGIC = 0x%08X;" % table.magic)
        self.o("\tdeclare _r: scalgoproto.Reader;")
        self.o("\tdeclare _dv: globalThis.DataView;")
        self.o("\t/** Offset of the table content in the message */")
        self.o("\tdeclare _off: number;")
        self.o("\t/** Size of the table content in the message */")
        self.o("\tdeclare _size: number;")
        self.o()
        self.o(
            "\t/** Private constructor. Use the accessors on tables, lists or Reader.root to get instances */"
        )
        self.o(
            "\tconstructor(reader: scalgoproto.Reader, offset: number, size: number) {"
        )
        self.o("\t\tthis._r = reader;")
        self.o("\t\tthis._dv = reader._dv;")
        self.o("\t\tthis._off = offset;")
        self.o("\t\tthis._size = size;")
        self.o("\t}")
        self.o()
        for node in table.members:
            self.generate_value_in(table, node)
        self.o("}")
        self.o()

        n = table.name
        self.o(
            "export class %s_ListIn extends scalgoproto.TableListIn<%sIn> {" % (n, n)
        )
        self.o("\tget(i: number): %sIn | null {" % n)
        self.o(
            "\t\tif (!((i >>> 0) === i && i < this.length)) scalgoproto._indexError(i, this.length);"
        )
        self.o("\t\tconst r = this._r, p = r._u48(this._off + i * 6);")
        self.o("\t\tif (p === 0) return null;")
        self.o("\t\treturn new %sIn(r, p + 10, r._size(p, %sIn._MAGIC));" % (n, n))
        self.o("\t}")
        self.o()
        self.list_helpers("%sIn | null" % n)
        self.o("}")
        self.o()

        self.o(
            "export class %s_DirectListIn extends scalgoproto.DirectTableListIn<%sIn> {"
            % (n, n)
        )
        self.o(
            "\tconstructor(reader: scalgoproto.Reader, offset: number, length: number) {"
        )
        self.o("\t\tsuper(reader, offset, length, %sIn._MAGIC);" % n)
        self.o("\t}")
        self.o()
        self.o("\tget(i: number): %sIn {" % n)
        self.o(
            "\t\tif (!((i >>> 0) === i && i < this.length)) scalgoproto._indexError(i, this.length);"
        )
        self.o(
            "\t\treturn new %sIn(this._r, this._off + i * this._itemSize, this._itemSize);"
            % n
        )
        self.o("\t}")
        self.o()
        self.o("\tcursor(): %sIn {" % n)
        self.o("\t\treturn new %sIn(this._r, this._off, this._itemSize);" % n)
        self.o("\t}")
        self.o()
        self.o("\tseek(c: %sIn, i: number): %sIn {" % (n, n))
        self.o(
            "\t\tif (!((i >>> 0) === i && i < this.length)) scalgoproto._indexError(i, this.length);"
        )
        self.o("\t\tc._off = this._off + i * this._itemSize;")
        self.o("\t\treturn c;")
        self.o("\t}")
        self.o()
        specs = self.column_specs(table.members, 0, "", True)
        self.to_columns(n, specs, "this._itemSize", len(table.default), True)
        self.list_helpers("%sIn" % n)
        self.o("}")
        self.o()
        self.columns_interface(
            n, specs, "Columns of a direct list of %s, see toColumns" % n
        )

        self.generate_table_writers(table)

    def generate_struct(self, node: Struct) -> None:
        # Recursively generate direct contained members
        for value in node.members:
            if value.direct_enum:
                self.generate_enum(value.direct_enum)
            if value.direct_struct:
                self.generate_struct(value.direct_struct)

        self.output_doc(node, "")
        self.o("export class %s {" % node.name)
        ctor = []
        read = []
        write = []
        for v in node.members:
            n = lcamel(self.value(v.identifier))
            if v.type_.type in typeMap:
                ti = typeMap[v.type_.type]
                if v.type_.type in (TokenType.F32, TokenType.F64):
                    ctor.append("%s: %s = 0.0" % (n, ti.p))
                elif v.type_.type == TokenType.BOOL:
                    ctor.append("%s: %s = false" % (n, ti.p))
                else:
                    ctor.append("%s: %s = 0" % (n, ti.p))

                if v.type_.type == TokenType.I8:
                    read.append(
                        self.read_basic(
                            v.type_.type, "offset + %d" % v.offset, "dv", "reader"
                        )
                    )
                    write.append(
                        self.write_basic(
                            v.type_.type,
                            "offset + %d" % v.offset,
                            "ins.%s" % n,
                            "dv",
                            "writer",
                        )
                    )
                elif v.type_.type == TokenType.I16:
                    read.append(
                        self.read_basic(
                            v.type_.type, "offset + %d" % v.offset, "dv", "reader"
                        )
                    )
                    write.append(
                        self.write_basic(
                            v.type_.type,
                            "offset + %d" % v.offset,
                            "ins.%s" % n,
                            "dv",
                            "writer",
                        )
                    )
                elif v.type_.type == TokenType.I32:
                    read.append(
                        self.read_basic(
                            v.type_.type, "offset + %d" % v.offset, "dv", "reader"
                        )
                    )
                    write.append(
                        self.write_basic(
                            v.type_.type,
                            "offset + %d" % v.offset,
                            "ins.%s" % n,
                            "dv",
                            "writer",
                        )
                    )
                elif v.type_.type == TokenType.I64:
                    read.append(
                        self.read_basic(
                            v.type_.type, "offset + %d" % v.offset, "dv", "reader"
                        )
                    )
                    write.append(
                        self.write_basic(
                            v.type_.type,
                            "offset + %d" % v.offset,
                            "ins.%s" % n,
                            "dv",
                            "writer",
                        )
                    )
                elif v.type_.type == TokenType.U8:
                    read.append(
                        self.read_basic(
                            v.type_.type, "offset + %d" % v.offset, "dv", "reader"
                        )
                    )
                    write.append(
                        self.write_basic(
                            v.type_.type,
                            "offset + %d" % v.offset,
                            "ins.%s" % n,
                            "dv",
                            "writer",
                        )
                    )
                elif v.type_.type == TokenType.U16:
                    read.append(
                        self.read_basic(
                            v.type_.type, "offset + %d" % v.offset, "dv", "reader"
                        )
                    )
                    write.append(
                        self.write_basic(
                            v.type_.type,
                            "offset + %d" % v.offset,
                            "ins.%s" % n,
                            "dv",
                            "writer",
                        )
                    )
                elif v.type_.type == TokenType.UI32:
                    read.append(
                        self.read_basic(
                            v.type_.type, "offset + %d" % v.offset, "dv", "reader"
                        )
                    )
                    write.append(
                        self.write_basic(
                            v.type_.type,
                            "offset + %d" % v.offset,
                            "ins.%s" % n,
                            "dv",
                            "writer",
                        )
                    )
                elif v.type_.type == TokenType.UI64:
                    read.append(
                        self.read_basic(
                            v.type_.type, "offset + %d" % v.offset, "dv", "reader"
                        )
                    )
                    write.append(
                        self.write_basic(
                            v.type_.type,
                            "offset + %d" % v.offset,
                            "ins.%s" % n,
                            "dv",
                            "writer",
                        )
                    )
                elif v.type_.type == TokenType.F32:
                    read.append(
                        self.read_basic(
                            v.type_.type, "offset + %d" % v.offset, "dv", "reader"
                        )
                    )
                    write.append(
                        self.write_basic(
                            v.type_.type,
                            "offset + %d" % v.offset,
                            "ins.%s" % n,
                            "dv",
                            "writer",
                        )
                    )
                elif v.type_.type == TokenType.F64:
                    read.append(
                        self.read_basic(
                            v.type_.type, "offset + %d" % v.offset, "dv", "reader"
                        )
                    )
                    write.append(
                        self.write_basic(
                            v.type_.type,
                            "offset + %d" % v.offset,
                            "ins.%s" % n,
                            "dv",
                            "writer",
                        )
                    )
                elif v.type_.type == TokenType.BOOL:
                    read.append(
                        self.read_basic(
                            v.type_.type, "offset + %d" % v.offset, "dv", "reader"
                        )
                    )
                    write.append(
                        self.write_basic(
                            v.type_.type,
                            "offset + %d" % v.offset,
                            "ins.%s" % n,
                            "dv",
                            "writer",
                        )
                    )
            elif v.enum:
                ctor.append("%s: %s = 0" % (n, v.enum.name))
                read.append("dv.getUint8(offset + %d) as %s" % (v.offset, v.enum.name))
                write.append("dv.setUint8(offset + %d, +ins.%s)" % (v.offset, n))
            elif v.struct:
                ctor.append("%s: %s = new %s()" % (n, v.struct.name, v.struct.name))
                write.append(
                    "%s._write(writer, offset + %d, ins.%s)"
                    % (v.struct.name, v.offset, n)
                )
                read.append("%s._read(reader, offset + %d)" % (v.struct.name, v.offset))
            else:
                raise ICE()
        self.o("\tstatic readonly _WIDTH = %d;" % node.bytes)
        for c in ctor:
            self.o("\tdeclare %s;" % c.split(" = ")[0])
        self.o()
        self.o("\tconstructor(%s) {" % (", ".join(ctor)))
        for c in ctor:
            n = c.split(":")[0]
            self.o("\t\tthis.%s = %s;" % (n, n))
        self.o("\t}")
        self.o()
        self.o(
            "\tstatic _write(writer: scalgoproto.Writer, offset: number, ins: %s) {"
            % node.name
        )
        if any(line.startswith("dv.") for line in write):
            self.o("\t\tconst dv = writer._dv;")
        for line in write:
            self.o("\t\t%s;" % line)
        self.o("\t}")
        self.o()
        self.o(
            "\tstatic _read(reader: scalgoproto.Reader, offset: number) : %s {"
            % node.name
        )
        self.o("\t\tconst dv = reader._dv;")
        self.o("\t\treturn new %s(" % node.name)
        for line in read:
            self.o("\t\t\t%s," % line)
        self.o("\t\t);")
        self.o("\t}")
        self.o("}")
        self.o()

        n = node.name
        self.o("export class %s_ListIn extends scalgoproto.StructListIn<%s> {" % (n, n))
        self.o("\tget _width(): number {")
        self.o("\t\treturn %d;" % node.bytes)
        self.o("\t}")
        self.o("\tget(i: number): %s {" % n)
        self.o(
            "\t\tif (!((i >>> 0) === i && i < this.length)) scalgoproto._indexError(i, this.length);"
        )
        self.o("\t\treturn %s._read(this._r, this._off + i * %d);" % (n, node.bytes))
        self.o("\t}")
        self.o()
        specs = self.column_specs(node.members, 0, "", False)
        self.to_columns(n, specs, str(node.bytes), node.bytes, False)
        self.list_helpers(n)
        self.o("}")
        self.o()
        self.columns_interface(n, specs, "Columns of a list of %s, see toColumns" % n)
        self.generate_struct_writers(node)
        self.o()

    def generate_enum(self, node: Enum) -> None:
        self.output_doc(node, "")
        self.o("export enum %s {" % node.name)
        for ev in node.members:
            self.o("    %s," % (self.value(ev.identifier)))
        self.o("}")
        self.o()

    def out_values_type(self, node: Value) -> str:
        """The type of the values that can be given when constructing the list node"""
        tt = node.type_.type
        if tt == TokenType.BOOL:
            return "globalThis.ArrayLike<boolean>"
        elif tt in typeMap:
            typed = {
                TokenType.I64: "BigInt64Array",
                TokenType.UI64: "BigUint64Array",
            }.get(tt, column_array.get(tt, ""))
            return "globalThis.ArrayLike<number> | globalThis.%s" % typed
        elif node.struct:
            return "globalThis.ArrayLike<%s>" % node.struct.name
        elif node.enum:
            return "globalThis.ArrayLike<%s | null>" % node.enum.name
        elif node.table:
            if node.direct:
                return "globalThis.ArrayLike<%sIn>" % node.table.name
            return "globalThis.ArrayLike<%sOut | %sIn | null>" % (
                node.table.name,
                node.table.name,
            )
        elif node.union:
            return "globalThis.ArrayLike<%sIn>" % node.union.name
        elif tt == TokenType.TEXT:
            return "globalThis.ArrayLike<string | scalgoproto.TextOut | null>"
        elif tt == TokenType.BYTES:
            return "globalThis.ArrayLike<scalgoproto.BytesLike | scalgoproto.BytesOut | null>"
        else:
            raise ICE()

    def list_header_size(self, node: Value) -> int:
        """Bytes between the start of a list with header and its first element"""
        return 18 if node.table and node.direct else 10

    def emit_list_adder(
        self, node: Value, lname: str, store: str, inplace: bool, check: str
    ) -> None:
        """Output an adder for a list member.

        store is a format string storing the value given as %s, check an expression
        whose value the writer size must have for inplace lists"""
        cls = self.out_list_type(node)
        self.output_doc(
            node,
            "\t",
            suffix=[
                "Add a list of the given length, or with the given values, and return it"
            ],
        )
        self.o(
            "\tadd%s(lengthOrValues: number | %s): %s {"
            % (ucamel(lname), self.out_values_type(node), cls)
        )
        self.o("\t\tconst w = this._w;")
        self.o(
            "\t\tconst n = typeof lengthOrValues === 'number' ? lengthOrValues : lengthOrValues.length;"
        )
        if inplace:
            self.o("\t\tw._checkInplace(%s);" % check)
            self.o("\t\t" + store % "n" + ";")
            self.o("\t\tconst l = new %s(w, n, false);" % cls)
        else:
            self.o("\t\tconst l = new %s(w, n, true);" % cls)
            self.o("\t\t" + store % ("l._off - %d" % self.list_header_size(node)) + ";")
        self.o("\t\tif (typeof lengthOrValues !== 'number') l.setAll(lengthOrValues);")
        self.o("\t\treturn l;")
        self.o("\t}")
        self.o()

    def emit_list_setter(
        self, node: Value, lname: str, store: str, inplace: bool
    ) -> None:
        """Output a setter for a list member taking a list writer or a read list"""
        cls = self.out_list_type(node)
        it = self.in_list_help(node)[1]
        self.output_doc(node, "\t")
        if inplace:
            self.o("\tset %s(value: %s) {" % (lname, it))
            self.o("\t\tthis.add%s(value.length)._copy(value);" % ucamel(lname))
        else:
            self.o("\tset %s(value: %s | %s) {" % (lname, cls, it))
            self.o("\t\tif (value instanceof scalgoproto.ListIn) {")
            self.o("\t\t\tthis.add%s(value.length)._copy(value);" % ucamel(lname))
            self.o("\t\t\treturn;")
            self.o("\t\t}")
            self.o(
                "\t\t"
                + store
                % ("this._w._own(value)._off - %d" % self.list_header_size(node))
                + ";"
            )
        self.o("\t}")
        self.o()

    def write_basic(self, tt: TokenType, o: str, v: str, dv: str, w: str) -> str:
        """Statement writing the basic type value v at offset o"""
        if tt == TokenType.I64:
            return "%s._i64(%s, %s)" % (w, o, v)
        if tt == TokenType.UI64:
            return "%s._u64(%s, %s)" % (w, o, v)
        if tt == TokenType.BOOL:
            return "%s.setUint8(%s, %s ? 1 : 0)" % (dv, o, v)
        ti = typeMap[tt]
        if tt in (TokenType.I8, TokenType.U8):
            return "%s.set%s(%s, %s)" % (dv, ti.n, o, v)
        return "%s.set%s(%s, %s, true)" % (dv, ti.n, o, v)

    def set_has(self, node: Value) -> str:
        return "this._w._setBits(this._off + %d, %d);" % (
            node.has_offset,
            1 << node.has_bit,
        )

    def emit_table_setter(self, table: Table, lname: str, store: str) -> None:
        n = table.name
        self.o("\tset %s(value: %sOut | %sIn) {" % (lname, n, n))
        self.o("\t\tif (value instanceof %sIn) {" % n)
        self.o("\t\t\tconst c = this._w.constructTable(%sOut);" % n)
        self.o("\t\t\tc._copy(value);")
        self.o("\t\t\tvalue = c;")
        self.o("\t\t}")
        self.o("\t\t" + store % "this._w._own(value)._off - 10" + ";")
        self.o("\t}")
        self.o()

    def emit_table_adder(self, table: Table, lname: str, store: str) -> None:
        n = table.name
        self.o("\tadd%s(): %sOut {" % (ucamel(lname), n))
        self.o("\t\tconst t = this._w.constructTable(%sOut);" % n)
        self.o("\t\t" + store % "t._off - 10" + ";")
        self.o("\t\treturn t;")
        self.o("\t}")
        self.o()

    def emit_inplace_table_adder(
        self, table: Table, lname: str, store: str, check: str
    ) -> None:
        n = table.name
        self.o("\tadd%s(): %sOut {" % (ucamel(lname), n))
        self.o("\t\tconst w = this._w;")
        self.o("\t\tw._checkInplace(%s);" % check)
        self.o("\t\t" + store % ("%sOut._SIZE" % n) + ";")
        self.o(
            "\t\treturn new %sOut(w, w._table(%sOut._MAGIC, %sOut._DEFAULT, %sOut._ZERO, false));"
            % (n, n, n, n)
        )
        self.o("\t}")
        self.o()
        self.o("\tset %s(value: %sIn) {" % (lname, n))
        self.o("\t\tthis.add%s()._copy(value);" % ucamel(lname))
        self.o("\t}")
        self.o()

    def emit_text_bytes_out(
        self, lname: str, text: bool, store: str, inplace: bool, check: str
    ) -> None:
        if inplace:
            self.o(
                "\tset %s(value: %s) {"
                % (lname, "string" if text else "scalgoproto.BytesLike")
            )
            self.o("\t\tconst w = this._w;")
            self.o("\t\tw._checkInplace(%s);" % check)
            self.o(
                "\t\tconst n = w.%s(value);" % ("_writeText" if text else "_writeBytes")
            )
            self.o("\t\t" + store % "n" + ";")
        else:
            t = (
                "string | scalgoproto.TextOut"
                if text
                else "scalgoproto.BytesLike | scalgoproto.BytesOut"
            )
            c = "TextOut" if text else "BytesOut"
            self.o("\tset %s(value: %s) {" % (lname, t))
            self.o("\t\tconst w = this._w;")
            self.o(
                "\t\tconst v = value instanceof scalgoproto.%s ? w._own(value) : w.construct%s(value);"
                % (c, "Text" if text else "Bytes")
            )
            self.o("\t\t" + store % "v._off" + ";")
        self.o("\t}")
        self.o()

    def generate_union_out_class(self, union: Union, inplace: bool) -> None:
        name = "%s_InplaceOut" % union.name if inplace else "%sOut" % union.name
        self.output_doc(union, "")
        self.o("export class %s {" % name)
        self.o("\tdeclare _w: scalgoproto.Writer;")
        self.o("\t/** Offset of the union in its table or list */")
        self.o("\tdeclare _off: number;")
        self.o("\t/** End of the table, where inplace content goes, or -1 */")
        self.o("\tdeclare _end: number;")
        self.o()
        self.o(
            "\t/** Private constructor. Use the accessors on tables and lists to get instances */"
        )
        self.o(
            "\tconstructor(writer: scalgoproto.Writer, offset: number, end: number = -1) {"
        )
        self.o("\t\tthis._w = writer;")
        self.o("\t\tthis._off = offset;")
        self.o("\t\tthis._end = end;")
        self.o("\t}")
        self.o()
        self.o("\t_set(type: number, value: number): void {")
        self.o("\t\tthis._w._dv.setUint16(this._off, type, true);")
        self.o("\t\tthis._w._u48(this._off + 2, value);")
        self.o("\t}")
        self.o()
        for idx, member in enumerate(union.members, start=1):
            if member.type_.type == TokenType.REMOVED:
                continue
            llname = lcamel(self.value(member.identifier))
            if member.list_:
                self.generate_union_list_out(member, llname, idx, inplace)
            elif member.table:
                self.generate_union_table_out(member, llname, idx, inplace)
            elif member.type_.type == TokenType.BYTES:
                self.generate_union_bytes_out(member, llname, idx, inplace)
            elif member.type_.type == TokenType.TEXT:
                self.generate_union_text_out(member, llname, idx, inplace)
            else:
                raise ICE()
        self.generate_union_copy(union, inplace)
        self.o("}")
        self.o()

    def generate_union_writers(self, union: Union) -> None:
        self.generate_union_out_class(union, False)
        self.generate_union_out_class(union, True)
        n = union.name
        self.o(
            "export class %s_ListOut extends scalgoproto.UnionListOut<%sOut, %sIn> {"
            % (n, n, n)
        )
        self.o(
            "\tconstructor(writer: scalgoproto.Writer, length: number, withHeader: boolean) {"
        )
        self.o(
            "\t\tsuper(writer, writer._list(length, length * 8, withHeader, 0), length);"
        )
        self.o("\t}")
        self.o()
        self.o("\tget(i: number): %sOut {" % n)
        self.o(
            "\t\tif (!((i >>> 0) === i && i < this.length)) scalgoproto._indexError(i, this.length);"
        )
        self.o("\t\treturn new %sOut(this._w, this._off + i * 8);" % n)
        self.o("\t}")
        self.o()
        self.o("\tset(i: number, value: %sIn): void {" % n)
        self.o("\t\tthis.get(i)._copy(value);")
        self.o("\t}")
        self.o("}")
        self.o()

    def generate_table_writers(self, table: Table) -> None:
        n = table.name
        self.output_doc(table, "")
        self.o("export class %sOut {" % n)
        self.o("\tstatic readonly _MAGIC = 0x%08X;" % table.magic)
        self.o("\tstatic readonly _SIZE = %d;" % len(table.default))
        self.o(
            '\tstatic readonly _DEFAULT = scalgoproto._defaultBytes("%s");'
            % cescape(table.default)
        )
        self.o(
            "\tstatic readonly _ZERO = %s;"
            % ("true" if not any(table.default) else "false")
        )
        self.o("\tdeclare _w: scalgoproto.Writer;")
        self.o("\t/** Offset of the table content in the message */")
        self.o("\tdeclare _off: number;")
        self.o()
        self.o(
            "\t/** Private constructor. Use Writer.constructTable or the adders of tables and lists */"
        )
        self.o("\tconstructor(writer: scalgoproto.Writer, offset: number) {")
        self.o("\t\tthis._w = writer;")
        self.o("\t\tthis._off = offset;")
        self.o("\t}")
        self.o()
        for node in table.members:
            self.generate_value_out(table, node)
        self.generate_table_copy(table)
        self.o("}")
        self.o()

        self.o(
            "export class %s_ListOut extends scalgoproto.TableListOut<%sOut, %sIn> {"
            % (n, n, n)
        )
        self.o(
            "\tconstructor(writer: scalgoproto.Writer, length: number, withHeader: boolean) {"
        )
        self.o(
            "\t\tsuper(writer, writer._list(length, length * 6, withHeader, 0), length);"
        )
        self.o("\t}")
        self.o()
        self.o("\tset(i: number, value: %sOut | %sIn | null): void {" % (n, n))
        self.o(
            "\t\tif (!((i >>> 0) === i && i < this.length)) scalgoproto._indexError(i, this.length);"
        )
        self.o("\t\tif (value === null) {")
        self.o("\t\t\tthis._w._u48(this._off + i * 6, 0);")
        self.o("\t\t\treturn;")
        self.o("\t\t}")
        self.o("\t\tif (value instanceof %sIn) {" % n)
        self.o("\t\t\tconst c = this._w.constructTable(%sOut);" % n)
        self.o("\t\t\tc._copy(value);")
        self.o("\t\t\tvalue = c;")
        self.o("\t\t}")
        self.o("\t\tthis._w._u48(this._off + i * 6, this._w._own(value)._off - 10);")
        self.o("\t}")
        self.o()
        self.o("\tadd(i: number): %sOut {" % n)
        self.o(
            "\t\tif (!((i >>> 0) === i && i < this.length)) scalgoproto._indexError(i, this.length);"
        )
        self.o("\t\tconst t = this._w.constructTable(%sOut);" % n)
        self.o("\t\tthis._w._u48(this._off + i * 6, t._off - 10);")
        self.o("\t\treturn t;")
        self.o("\t}")
        self.o("}")
        self.o()

        self.o(
            "export class %s_DirectListOut extends scalgoproto.DirectTableListOut<%sOut, %sIn> {"
            % (n, n, n)
        )
        self.o(
            "\tconstructor(writer: scalgoproto.Writer, length: number, withHeader: boolean) {"
        )
        self.o(
            "\t\tsuper(writer, writer._directList(length, %sOut._MAGIC, %sOut._DEFAULT, %sOut._ZERO, withHeader), length);"
            % (n, n, n)
        )
        self.o("\t}")
        self.o()
        self.o("\tget(i: number): %sOut {" % n)
        self.o(
            "\t\tif (!((i >>> 0) === i && i < this.length)) scalgoproto._indexError(i, this.length);"
        )
        self.o("\t\treturn new %sOut(this._w, this._off + i * %sOut._SIZE);" % (n, n))
        self.o("\t}")
        self.o()
        self.o("\tset(i: number, value: %sIn): void {" % n)
        self.o("\t\tconst t = this.get(i);")
        self.o(
            "\t\t// Restore the defaults, as the copy skips members that are not set"
        )
        self.o("\t\tthis._w._u8.set(%sOut._DEFAULT, t._off);" % n)
        self.o("\t\tt._copy(value);")
        self.o("\t}")
        self.o("}")
        self.o()

    def generate_struct_writers(self, node: Struct) -> None:
        n = node.name
        self.o(
            "export class %s_ListOut extends scalgoproto.StructListOut<%s> {" % (n, n)
        )
        self.o("\tget _width(): number {")
        self.o("\t\treturn %d;" % node.bytes)
        self.o("\t}")
        self.o()
        self.o(
            "\tconstructor(writer: scalgoproto.Writer, length: number, withHeader: boolean) {"
        )
        self.o(
            "\t\tsuper(writer, writer._list(length, length * %d, withHeader, 0), length);"
            % node.bytes
        )
        self.o("\t}")
        self.o()
        self.o("\tset(i: number, value: %s): void {" % n)
        self.o(
            "\t\tif (!((i >>> 0) === i && i < this.length)) scalgoproto._indexError(i, this.length);"
        )
        self.o("\t\t%s._write(this._w, this._off + i * %d, value);" % (n, node.bytes))
        self.o("\t}")
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
                if isinstance(u, Struct):
                    i.add(u.name)
                    i.add("%s_ListIn" % u.name)
                    i.add("%s_ListOut" % u.name)
                elif isinstance(u, Enum):
                    i.add(u.name)
                elif isinstance(u, Table):
                    if not u.empty:
                        i.add("%sOut" % u.name)
                        i.add("%sIn" % u.name)
                        i.add("%s_ListIn" % u.name)
                        i.add("%s_DirectListIn" % u.name)
                        i.add("%s_ListOut" % u.name)
                        i.add("%s_DirectListOut" % u.name)
                elif isinstance(u, Union):
                    i.add("%sIn" % u.name)
                    i.add("%sOut" % u.name)
                    i.add("%s_InplaceOut" % u.name)
                    i.add("%s_ListIn" % u.name)
                    i.add("%s_ListOut" % u.name)
                else:
                    raise ICE()

        for d, imp in imports.items():
            doc = self.documents.by_id[d]
            self.o("import {%s} from '%s'" % (", ".join(sorted(imp)), doc.name))

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
