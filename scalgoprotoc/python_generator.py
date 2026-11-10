"""
Generate python reader/wirter
"""

import math
import os
from typing import NamedTuple, TextIO

from .annotate import annotate, has_jagged, owns_jagged
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
from .util import cescape, snake


class TypeInfo(NamedTuple):
    n: str
    p: str
    s: str
    w: int


typeMap: dict[TokenType, TypeInfo] = {
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
        self.out: TextIO = out
        if import_prefix and import_prefix[-1] != ".":
            import_prefix += "."
        self.import_prefix: str = import_prefix

    def out_list_type(self, node: Value) -> str:
        assert node.type_ is not None
        if node.type_.type == TokenType.BOOL:
            return "scalgoproto.BoolListOut"
        elif node.type_.type in typeMap:
            return f"scalgoproto.BasicListOut[{typeMap[node.type_.type].p}]"
        elif node.struct:
            return f"scalgoproto.StructListOut[{node.struct.name}]"
        elif node.enum:
            return f"scalgoproto.EnumListOut[{node.enum.name}]"
        elif node.table and node.direct:
            return f"scalgoproto.DirectTableListOut[{node.table.name}Out]"
        elif node.table:
            return f"scalgoproto.TableListOut[{node.table.name}Out]"
        elif node.union:
            return f"scalgoproto.UnionListOut[{node.union.name}Out]"
        elif node.type_.type == TokenType.TEXT:
            return "scalgoproto.TextListOut"
        elif node.type_.type == TokenType.BYTES:
            return "scalgoproto.BytesListOut"
        else:
            raise ICE()

    def out_list_constructor(self, node: Value) -> str:
        assert node.type_ is not None
        if node.type_.type == TokenType.BOOL:
            return "construct_bool_list(size)"
        elif node.type_.type in typeMap:
            return f"construct_{typeMap[node.type_.type].n}_list(size)"
        elif node.struct:
            return f"construct_struct_list({node.struct.name}, size)"
        elif node.enum:
            return f"construct_enum_list({node.enum.name}, size)"
        elif node.table and node.direct:
            return f"construct_direct_table_list({node.table.name}Out, size)"
        elif node.table:
            return f"construct_table_list({node.table.name}Out, size)"
        elif node.union:
            return f"construct_union_list({node.union.name}Out, size)"
        elif node.type_.type == TokenType.TEXT:
            return "construct_text_list(size)"
        elif node.type_.type == TokenType.BYTES:
            return "construct_bytes_list(size)"
        else:
            raise ICE()

    def in_list_help(self, node: Value, os: str) -> tuple[str, str]:
        assert node.type_ is not None
        if node.type_.type == TokenType.BOOL:
            return ("bool", f"        return self._reader._get_bool_list({os})")
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
            assert node.struct.name is not None
            return (
                node.struct.name,
                f"        return self._reader._get_struct_list({node.struct.name}, {os},)",
            )
        elif node.enum:
            assert node.enum.name is not None
            return (
                node.enum.name,
                f"        return self._reader._get_enum_list({node.enum.name}, {os})",
            )
        elif node.table:
            assert node.table.name is not None
            jagged = ", jagged=self._jagged()" if has_jagged(node.table) else ""
            return (
                node.table.name + "In",
                f"        return self._reader._get_table_list({node.table.name}In, {os}, direct={'True' if node.direct else 'False'}{jagged})",
            )
        elif node.union:
            assert node.union.name is not None
            return (
                node.union.name + "In",
                f"        return self._reader._get_union_list({node.union.name}In, {os})",
            )
        elif node.type_.type == TokenType.TEXT:
            return ("str", f"        return self._reader._get_text_list({os})")
        elif node.type_.type == TokenType.BYTES:
            return ("bytes", f"        return self._reader._get_bytes_list({os})")
        else:
            raise ICE()

    def o(self, text="") -> None:
        print(text, file=self.out)

    def struct_format_body(self, node: Struct) -> str:
        out: list[str] = []
        offset = 0

        for v in node.members:
            if v.offset > offset:
                out.append("%dx" % (v.offset - offset))
                offset = v.offset

            assert v.type_ is not None
            if v.type_.type in typeMap:
                ti = typeMap[v.type_.type]
                out.append(ti.s)
                offset += ti.w
            elif v.enum:
                out.append("B")
                offset += 1
            elif v.struct:
                out.append(self.struct_format_body(v.struct))
                offset += v.struct.bytes
            else:
                raise ICE()

        if node.bytes > offset:
            out.append("%dx" % (node.bytes - offset))

        return "".join(out)

    def value(self, t: Token) -> str:
        return self.documents.by_id[t.document].content[t.index : t.index + t.length]

    def output_doc(
        self,
        node: AstNode,
        indent: str = "",
        prefix: list[str] | None = None,
        suffix: list[str] | None = None,
    ) -> None:
        if suffix is None:
            suffix = []
        if prefix is None:
            prefix = []
        if not node.docstring and not suffix and not prefix:
            return
        self.o(f'{indent}"""')
        for line in prefix:
            self.o(f"{indent}{line}")
        if prefix and (node.docstring or suffix):
            self.o(f"{indent}")
        if node.docstring:
            for line in node.docstring:
                self.o(f"{indent}{line}")
        if node.docstring and suffix:
            self.o(f"{indent}")
        for line in suffix:
            self.o(f"{indent}{line}")
        self.o(f'{indent}"""')

    def generate_jagged_offset_in(self, node: Value, uname: str) -> None:
        self.o("    @property")
        self.o(f"    def {uname}_offset(self) -> int:")
        self.o(
            f'        """Index of the first of {uname} that this element owns in the list it names."""'
        )
        if node.bytes == 6:
            self.o("        return self._get_uint48(%d)" % node.offset)
        else:
            self.o(
                "        return self._get_uint%d(%d, 0)" % (node.bytes * 8, node.offset)
            )
        self.o()
        self.o("    @property")
        self.o(f"    def {uname}(self) -> scalgoproto.ListSlice[typing_.Any]:")
        self.output_doc(
            node,
            "        ",
            suffix=["Raises scalgoproto.OutOfBoundsError on invalid offsets."],
        )
        assert node.type_ is not None
        self.o(
            f'        return self._jagged_slice("{snake(self.value(node.type_))}", self.{uname}_offset, {node.offset}, {node.bytes})'
        )
        self.o()

    def generate_jagged_offset_out(self, node: Value, uname: str) -> None:
        self.o("    @scalgoproto.Adder")
        self.o(f"    def {uname}_offset(self, value: int) -> None:")
        self.output_doc(node, "        ")
        self.o("        if not 0 <= value < 2**%d:" % (node.bytes * 8))
        self.o(f'            raise ValueError("{uname}_offset out of range")')
        self.o("        self._set_uint%d(%d, value)" % (node.bytes * 8, node.offset))
        self.o()

    def generate_jagged_out(self, node: Value, uname: str) -> None:
        assert node.jagged_elements is not None and node.jagged_offset is not None
        list_name = snake(self.value(node.jagged_elements.identifier))
        offset = snake(self.value(node.jagged_offset.identifier)) + "_offset"
        self.o(
            f"    def add_jagged_{uname}(self, elements: {self.out_list_type(node.jagged_elements)}, total: int) -> scalgoproto.JaggedOut:"
        )
        self.o(
            f'        """Add {uname} with `total` children and return a view that gives each element of'
        )
        self.o(
            f"        `elements` (the list added by add_{list_name}) its range of them."
        )
        self.o()
        self.o(
            "        Claim ranges with add(element, k) in element order; Writer.finalize raises"
        )
        self.o('        ValueError unless all `total` children were claimed."""')
        self.o(f"        if total >= 2**{node.jagged_offset.bytes * 8}:")
        self.o(f'            raise ValueError("total does not fit in {offset}")')
        self.o(
            f'        return scalgoproto.JaggedOut(elements, self.add_{uname}(total), lambda e, v: setattr(e, "{offset}", v))'
        )
        self.o()

    def generate_list_in(self, node: Value, uname: str) -> None:
        (tn, acc) = self.in_list_help(
            node,
            f"*self._get_ptr{'_inplace' if node.inplace else ''}({node.offset}, scalgoproto.{'DIRECT_' if node.direct else ''}LIST_MAGIC)",
        )
        if node.optional:
            self.o("    @property")
            self.o(f"    def has_{uname}(self) -> bool:")
            self.o("        return self._get_uint48(%d) != 0" % (node.offset,))
            self.o()
            self.o("    @property")
            self.o(
                f"    def {uname}(self) -> typing_.Optional[scalgoproto.ListIn[{tn}]]:"
            )
            self.output_doc(node, "        ")
            self.o(f"        if not self.has_{uname}:")
            self.o("            return None")
            self.o(acc)
            self.o()
        else:
            self.o("    @property")
            self.o(f"    def {uname}(self) -> scalgoproto.ListIn[{tn}]:")
            self.output_doc(node, "        ")
            self.o(acc)
            self.o()

    def generate_union_list_in(self, node: Value, uname: str) -> None:
        (tn, acc) = self.in_list_help(
            node,
            f"*self._get_ptr(scalgoproto.{'DIRECT_' if node.direct else ''}LIST_MAGIC)",
        )
        self.o("    @property")
        self.o(f"    def {uname}(self) -> scalgoproto.ListIn[{tn}]:")
        self.output_doc(node, "        ")
        self.o(f"        assert self.is_{uname}")
        self.o(acc)
        self.o()

    def generate_inplace_list_constructor(self, node: Value) -> None:
        assert node.type_ is not None
        if node.type_.type == TokenType.BOOL:
            self.o("        l = scalgoproto.BoolListOut(self._writer, size, False)")
        elif node.type_.type in typeMap:
            ti = typeMap[node.type_.type]
            self.o(
                "        l = scalgoproto.BasicListOut[%s](self._writer, '%s', %d, size, False)"
                % (ti.p, ti.s, ti.w)
            )
        elif node.enum:
            self.o(
                f"        l = scalgoproto.EnumListOut[{node.enum.name}](self._writer, {node.enum.name}, size, False)"
            )
        elif node.struct:
            self.o(
                f"        l = scalgoproto.StructListOut[{node.struct.name}](self._writer, {node.struct.name}, size, False)"
            )
        elif node.table and node.direct:
            self.o(
                f"        l = scalgoproto.DirectTableListOut[{node.table.name}Out](self._writer, {node.table.name}Out, size, False)"
            )
        elif node.table:
            self.o(
                f"        l = scalgoproto.TableListOut[{node.table.name}Out](self._writer, {node.table.name}Out, size, False)"
            )
        elif node.type_.type == TokenType.TEXT:
            self.o("        l = scalgoproto.TextListOut(self._writer, size, False)")
        elif node.type_.type == TokenType.BYTES:
            self.o("        l = scalgoproto.BytesListOut(self._writer, size, False)")

    def generate_list_out(self, node: Value, uname: str) -> None:
        it = "scalgoproto.ListIn[{}]".format(self.in_list_help(node, "")[0])
        ot = self.out_list_type(node)
        if not node.inplace:
            self.o("    @scalgoproto.Adder")
            self.o(f"    def {uname}(self, value: typing_.Union[{it},{ot}]) -> None:")
            self.output_doc(node, "        ")
            self.o("        if isinstance(value, scalgoproto.ListIn):")
            self.o(f"            self.add_{uname}(len(value))._copy(value)")
            self.o("            return")
            self.o("        assert isinstance(value, scalgoproto.OutList)")
            self.o("        self._set_list(%d, value)" % (node.offset))
            self.o()

            self.o(
                f"    def add_{uname}(self, size:int) -> {self.out_list_type(node)}:"
            )
            self.output_doc(node, "        ")
            self.o(f"        res = self._writer.{self.out_list_constructor(node)}")
            self.o("        self._set_list(%d, res)" % (node.offset))
            self.o("        return res")
            self.o()
        else:
            self.o("    @scalgoproto.Adder")
            self.o(f"    def {uname}(self, value: {it}) -> None:")
            self.output_doc(node, "        ")
            self.o("        assert isinstance(value, scalgoproto.ListIn)")
            self.o(f"        self.add_{uname}(len(value))._copy(value)")
            self.o()

            self.o(
                f"    def add_{uname}(self, size: int) -> {self.out_list_type(node)}:"
            )
            self.output_doc(node, "        ")
            self.o(
                "        assert self._writer._used == self._offset + self._SIZE, 'No object may be created between table and its implace list'"
            )
            self.generate_inplace_list_constructor(node)
            self.o("        self._set_inplace_list(%d, size)" % (node.offset))
            self.o("        return l")
            self.o()

    def generate_union_list_out(
        self, node: Value, uname: str, idx: int, inplace: bool
    ) -> None:
        it = "scalgoproto.ListIn[{}]".format(self.in_list_help(node, "")[0])
        ot = self.out_list_type(node)
        if not inplace:
            self.o("    @scalgoproto.Adder")
            self.o(f"    def {uname}(self, value: typing_.Union[{ot},{it}]):")
            self.output_doc(node, "        ")
            self.o("        if isinstance(value, scalgoproto.ListIn):")
            self.o(f"            self.add_{uname}(len(value))._copy(value)")
            self.o("            return")
            self.o("        assert isinstance(value, scalgoproto.OutList)")
            self.o("        self._set(%d, value._offset - 10)" % (idx,))
            self.o()

            self.o(
                f"    def add_{uname}(self, size:int) -> {self.out_list_type(node)}:"
            )
            self.output_doc(node, "        ")
            self.o(f"        res = self._writer.{self.out_list_constructor(node)}")
            self.o("        self._set(%d, res._offset - 10)" % (idx,))
            self.o("        return res")
            self.o()
        else:
            self.o("    @scalgoproto.Adder")
            self.o(f"    def {uname}(self, value: {it}) -> None:")
            self.output_doc(node, "        ")
            self.o("        assert isinstance(value, scalgoproto.ListIn)")
            self.o(f"        self.add_{uname}(len(value))._copy(value)")
            self.o()
            self.o(
                f"    def add_{uname}(self, size: int) -> {self.out_list_type(node)}:"
            )
            self.output_doc(node, "        ")
            self.o(
                "        assert self._writer._used == self._end, 'No object may be created between table and its implace list'"
            )
            self.o("        self._set(%d, size)" % (idx,))
            self.generate_inplace_list_constructor(node)
            self.o("        return l")
            self.o()

    def generate_bool_in(self, node: Value, uname: str) -> None:
        if node.inplace:
            raise ICE()
        if node.optional:
            self.o("    @property")
            self.o(f"    def has_{uname}(self) -> bool:")
            self.o(
                "        return self._get_bit(%d, %s, False)"
                % (node.has_offset, node.has_bit)
            )
            self.o()
            self.o("    @property")
            self.o(f"    def {uname}(self) -> typing_.Optional[bool]:")
            self.output_doc(node, "        ")
            self.o(f"        if not self.has_{uname}:")
            self.o("            return None")
            self.o(
                "        return self._get_bit(%d, %s, False)" % (node.offset, node.bit)
            )
            self.o()
        else:
            self.o("    @property")
            self.o(f"    def {uname}(self) -> bool:")
            self.output_doc(node, "        ")
            self.o(
                "        return self._get_bit(%d, %s, False)" % (node.offset, node.bit)
            )
            self.o()

    def generate_bool_out(self, node: Value, uname: str) -> None:
        if node.inplace:
            raise ICE()
        self.o("    @scalgoproto.Adder")
        self.o(f"    def {uname}(self, value: bool) -> None:")
        self.output_doc(node, "        ")
        if node.optional:
            self.o("        self._set_bit(%d, %d)" % (node.has_offset, node.has_bit))
        self.o("        if value:")
        self.o("            self._set_bit(%d, %d)" % (node.offset, node.bit))
        self.o("        else:")
        self.o("            self._unset_bit(%d, %d)" % (node.offset, node.bit))
        self.o()

    def generate_basic_in(self, node: Value, uname: str) -> None:
        assert node.type_ is not None
        if node.inplace:
            raise ICE()
        ti = typeMap[node.type_.type]
        if node.optional:
            self.o("    @property")
            self.o(f"    def has_{uname}(self) -> bool:")
            if node.type_.type in (TokenType.F32, TokenType.F64):
                self.o(
                    "        return not math_.isnan(self._get_%s(%d, math_.nan))"
                    % (ti.n, node.offset)
                )
            else:
                self.o(
                    "        return self._get_bit(%d, %s, False)"
                    % (node.has_offset, node.has_bit)
                )
            self.o()
            self.o("    @property")
            self.o(f"    def {uname}(self) -> typing_.Optional[{ti.p}]:")
            self.output_doc(node, "        ")
            self.o(f"        if not self.has_{uname}:")
            self.o("            return None")
            self.o(
                "        return self._get_%s(%d, %s)"
                % (
                    ti.n,
                    node.offset,
                    node.parsed_value
                    if not math.isnan(node.parsed_value)
                    else "math_.nan",
                )
            )
            self.o()
        else:
            self.o("    @property")
            self.o(f"    def {uname}(self) -> {ti.p}:")
            self.output_doc(node, "        ")
            self.o(
                "        return self._get_%s(%d, %s)"
                % (
                    ti.n,
                    node.offset,
                    node.parsed_value
                    if not math.isnan(node.parsed_value)
                    else "math_.nan",
                )
            )
            self.o()

    def generate_basic_out(self, node: Value, uname: str) -> None:
        if node.inplace:
            raise ICE()
        assert node.type_ is not None
        ti = typeMap[node.type_.type]
        self.o("    @scalgoproto.Adder")
        self.o(f"    def {uname}(self, value: {ti.p}) -> None:")
        self.output_doc(node, "        ")
        if node.optional and node.type_.type not in (TokenType.F32, TokenType.F64):
            self.o("        self._set_bit(%d, %d)" % (node.has_offset, node.has_bit))
        self.o("        self._set_%s(%d, value)" % (ti.n, node.offset))
        self.o()

    def generate_enum_in(self, node: Value, uname: str) -> None:
        if node.inplace:
            raise ICE()
        assert node.enum is not None
        self.o("    @property")
        self.o(f"    def has_{uname}(self) -> bool:")
        self.o(
            "        return self._get_uint8(%d, %d) < %d"
            % (node.offset, node.parsed_value, len(node.enum.members))
        )
        self.o()
        self.o("    @property")
        self.o(f"    def {uname}(self) -> typing_.Optional[{node.enum.name}]:")
        self.output_doc(node, "        ")
        self.o(f"        if not self.has_{uname}:")
        self.o("            return None")
        self.o(
            "        return %s(self._get_uint8(%d, %s))"
            % (node.enum.name, node.offset, node.parsed_value)
        )
        self.o()

    def generate_enum_out(self, node: Value, uname: str) -> None:
        if node.inplace:
            raise ICE()
        assert node.enum is not None
        self.o("    @scalgoproto.Adder")
        self.o(f"    def {uname}(self, value: {node.enum.name}) -> None:")
        self.output_doc(node, "        ")
        self.o("        self._set_uint8(%d, int(value))" % (node.offset))
        self.o()

    def generate_struct_in(self, node: Value, uname: str) -> None:
        if node.inplace:
            raise ICE()
        assert node.struct is not None
        if node.optional:
            self.o("    @property")
            self.o(f"    def has_{uname}(self) -> bool:")
            self.o(
                "        return self._get_bit(%d, %s, False)"
                % (node.has_offset, node.has_bit)
            )
            self.o()
            self.o("    @property")
            self.o(f"    def {uname}(self) -> typing_.Optional[{node.struct.name}]:")
            self.output_doc(node, "        ")
            if node.optional:
                self.o(f"        if not self.has_{uname}:")
                self.o("            return None")
            self.o(
                "        return %s._read(self._reader, self._offset+%d) if %d < self._size else %s()"
                % (node.struct.name, node.offset, node.offset, node.struct.name)
            )
            self.o()
        else:
            self.o("    @property")
            self.o(f"    def {uname}(self) -> {node.struct.name}:")
            self.output_doc(node, "        ")
            self.o(
                "        return %s._read(self._reader, self._offset+%d) if %d < self._size else %s()"
                % (node.struct.name, node.offset, node.offset, node.struct.name)
            )
            self.o()

    def generate_struct_out(self, node: Value, uname: str) -> None:
        if node.inplace:
            raise ICE()
        assert node.struct is not None
        self.o("    @scalgoproto.Adder")
        self.o(f"    def {uname}(self, value: {node.struct.name}) -> None:")
        self.output_doc(node, "        ")
        if node.optional:
            self.o("        self._set_bit(%d, %d)" % (node.has_offset, node.has_bit))
        self.o(
            "        %s._write(self._writer, self._offset + %d, value)"
            % (node.struct.name, node.offset)
        )
        self.o()

    def generate_table_in(self, node: Value, uname: str) -> None:
        assert node.table is not None
        if node.optional:
            self.o("    @property")
            self.o(f"    def has_{uname}(self) -> bool:")
            self.o("        return self._get_uint48(%d) != 0" % (node.offset))
            self.o()
            if not node.table.empty:
                self.o("    @property")
                self.o(
                    f"    def {uname}(self) -> typing_.Optional[{node.table.name}In]:"
                )
                self.output_doc(node, "        ")
                self.o(f"        if not self.has_{uname}:")
                self.o("            return None")
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
        elif not node.table.empty:
            self.o("    @property")
            self.o(f"    def {uname}(self) -> {node.table.name}In:")
            self.output_doc(node, "        ")
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
        assert node.table is not None
        if not node.table.empty:
            self.o("    @property")
            self.o(f"    def {uname}(self) -> {node.table.name}In:")
            self.output_doc(node, "        ")
            self.o(f"        assert self.is_{uname}")
            self.o(
                f"        return {node.table.name}In(self._reader, *self._get_ptr({node.table.name}In._MAGIC))"
            )
            self.o()

    def generate_table_out(self, node: Value, uname: str) -> None:
        assert node.table is not None
        if not node.inplace:
            self.o("    @scalgoproto.Adder")
            self.o(
                f"    def {uname}(self, value: typing_.Union[{node.table.name}Out, {node.table.name}In]) -> None:"
            )
            self.output_doc(node, "        ")
            self.o(f"        if isinstance(value, {node.table.name}In):")
            self.o("            v = value")
            self.o(
                f"            value = self._writer.construct_table({node.table.name}Out)"
            )
            self.o("            value._copy(v)")
            self.o(f"        assert isinstance(value, {node.table.name}Out)")
            self.o("        self._set_table(%d, value)" % (node.offset))
            self.o()
            self.o(f"    def add_{uname}(self) -> {node.table.name}Out:")
            self.output_doc(node, "        ")
            self.o(f"        res = self._writer.construct_table({node.table.name}Out)")
            self.o("        self._set_table(%d, res)" % (node.offset,))
            self.o("        return res")
            self.o()

        elif not node.table.empty:
            assert node.table.default is not None
            self.o("    @scalgoproto.Adder")
            self.o(f"    def {uname}(self, value: {node.table.name}In) -> None:")
            self.output_doc(node, "        ")
            self.o(f"        assert isinstance(value, {node.table.name}In)")
            self.o(f"        self.add_{uname}()._copy(value)")
            self.o()
            self.o(f"    def add_{uname}(self) -> {node.table.name}Out:")
            self.output_doc(node, "        ")
            self.o(
                "        assert self._writer._used == self._offset + self._SIZE, 'No object may be created between table and its implace table'"
            )
            self.o(
                "        self._set_uint48(%d, %d)"
                % (node.offset, len(node.table.default))
            )
            self.o(f"        return {node.table.name}Out(self._writer, False)")
            self.o()
        else:
            self.o(f"    def add_{uname}(self) -> None:")
            self.output_doc(node, "        ")
            self.o("        self._set_uint48(%d, %d)" % (node.offset, 0))
            self.o()

    def generate_union_table_out(
        self, node: Value, uname: str, idx: int, inplace: bool
    ) -> None:
        assert node.table is not None
        table = node.table
        if table.empty:
            self.o(f"    def add_{uname}(self) -> None:")
            self.output_doc(node, "        ")
            self.o("        self._set(%d, 0)" % (idx))
            self.o()
        elif not inplace:
            self.o("    @scalgoproto.Adder")
            self.o(
                f"    def {uname}(self, value: typing_.Union[{table.name}Out,{table.name}In]) -> None:"
            )
            self.output_doc(node, "        ")
            self.o(f"        if isinstance(value, {node.table.name}In):")
            self.o("            v = value")
            self.o(
                f"            value = self._writer.construct_table({node.table.name}Out)"
            )
            self.o("            value._copy(v)")
            self.o(f"        assert isinstance(value, {node.table.name}Out)")
            self.o("        self._set(%d, value._offset - 10)" % (idx))
            self.o()
            self.o(f"    def add_{uname}(self) -> {table.name}Out:")
            self.output_doc(node, "        ")
            self.o(f"        res = self._writer.construct_table({node.table.name}Out)")
            self.o("        self._set(%d, res._offset - 10)" % (idx,))
            self.o("        return res")
            self.o()
        else:
            self.o("    @scalgoproto.Adder")
            self.o(f"    def {uname}(self, value: {node.table.name}In) -> None:")
            self.output_doc(node, "        ")
            self.o(f"        assert isinstance(value, {node.table.name}In)")
            self.o(f"        self.add_{uname}()._copy(value)")
            self.o()
            self.o(f"    def add_{uname}(self) -> {table.name}Out:")
            self.output_doc(node, "        ")
            self.o(
                "        assert self._end == self._writer._used, 'No object may be created between table and its implace table'"
            )
            self.o("        self._set(%d, %d)" % (idx, table.bytes))
            self.o(f"        return {table.name}Out(self._writer, False)")
            self.o()

    def generate_text_in(self, node: Value, uname: str) -> None:
        if node.optional:
            self.o("    @property")
            self.o(f"    def has_{uname}(self) -> bool:")
            self.o("        return self._get_uint48(%d) != 0" % (node.offset,))
            self.o()
            self.o("    @property")
            self.o(f"    def {uname}(self) -> typing_.Optional[str]:")
            self.output_doc(node, "        ")
            self.o(f"        if not self.has_{uname}:")
            self.o("            return None")
            self.o(
                "        (o, s) = self._get_ptr%s(%d, scalgoproto.TEXT_MAGIC)"
                % ("_inplace" if node.inplace else "", node.offset)
            )
            self.o('        return self._reader._data[o : o + s].decode("utf-8")')
            self.o()
        else:
            self.o("    @property")
            self.o(f"    def {uname}(self) -> str:")
            self.output_doc(node, "        ")
            self.o("        if self._get_uint48(%d) == 0:" % (node.offset,))
            self.o("            return ''")
            self.o(
                "        (o, s) = self._get_ptr%s(%d, scalgoproto.TEXT_MAGIC)"
                % ("_inplace" if node.inplace else "", node.offset)
            )
            self.o('        return self._reader._data[o : o + s].decode("utf-8")')
            self.o()

    def generate_union_text_in(self, node: Value, uname: str) -> None:
        self.o("    @property")
        self.o(f"    def {uname}(self) -> str:")
        self.output_doc(node, "        ")
        self.o(f"        assert self.is_{uname}")
        self.o("        (o, s) = self._get_ptr(scalgoproto.TEXT_MAGIC)")
        self.o('        return self._reader._data[o : o + s].decode("utf-8")')
        self.o()

    def generate_text_out(self, node: Value, uname: str) -> None:
        self.o("    @scalgoproto.Adder")
        if node.inplace:
            self.o(f"    def {uname}(self, text: str) -> None:")
        else:
            self.o(
                f"    def {uname}(self, t: typing_.Union[scalgoproto.TextOut, str]) -> None:"
            )
        self.output_doc(node, "        ")
        if node.inplace:
            self.o("        self._add_inplace_text(%d, text)" % (node.offset))
        else:
            self.o("        self._set_text(%d, t)" % (node.offset))
        self.o()

    def generate_union_text_out(
        self, node: Value, uname: str, idx: int, inplace: bool
    ) -> None:
        self.o("    @scalgoproto.Adder")
        if inplace:
            self.o(f"    def {uname}(self, value: str) -> None:")
        else:
            self.o(
                f"    def {uname}(self, value: typing_.Union[scalgoproto.TextOut, str]) -> None:"
            )
        self.output_doc(node, "        ")
        if inplace:
            self.o("        self._add_inplace_text(%d, value)" % (idx))
        else:
            self.o("        self._set_text(%d, value)" % (idx))
        self.o()

    def generate_bytes_in(self, node: Value, uname: str) -> None:
        if node.optional:
            self.o("    @property")
            self.o(f"    def has_{uname}(self) -> bool:")
            self.o("        return self._get_uint48(%d) != 0" % (node.offset,))
            self.o()
            self.o("    @property")
            self.o(f"    def {uname}(self) -> typing_.Optional[bytes]:")
            self.output_doc(node, "        ")
            self.o(f"        if not self.has_{uname}:")
            self.o("            return None")
            self.o(
                "        (o, s) = self._get_ptr%s(%d, scalgoproto.BYTES_MAGIC)"
                % ("_inplace" if node.inplace else "", node.offset)
            )
            self.o("        return self._reader._data[o : o + s]")
            self.o()
        else:
            self.o("    @property")
            self.o(f"    def {uname}(self) -> bytes:")
            self.output_doc(node, "        ")
            self.o("        if self._get_uint48(%d) == 0:" % (node.offset,))
            self.o("            return b''")
            self.o(
                "        (o, s) = self._get_ptr%s(%d, scalgoproto.BYTES_MAGIC)"
                % ("_inplace" if node.inplace else "", node.offset)
            )
            self.o("        return self._reader._data[o : o + s]")
            self.o()

    def generate_union_bytes_in(self, node: Value, uname: str) -> None:
        self.o("    @property")
        self.o(f"    def {uname}(self) -> bytes:")
        self.output_doc(node, "        ")
        self.o(f"        assert self.is_{uname}")
        self.o("        (o, s) = self._get_ptr(scalgoproto.BYTES_MAGIC)")
        self.o("        return self._reader._data[o : o + s]")
        self.o()

    def generate_bytes_out(self, node: Value, uname: str) -> None:
        self.o("    @scalgoproto.Adder")
        if node.inplace:
            self.o(f"    def {uname}(self, value: bytes) -> None:")
        else:
            self.o(
                f"    def {uname}(self, value: typing_.Union[scalgoproto.BytesOut, bytes]) -> None:"
            )
        self.output_doc(node, "        ")
        if node.inplace:
            self.o("        self._add_inplace_bytes(%d, value)" % (node.offset))
        else:
            self.o("        self._set_bytes(%d, value)" % (node.offset))
        self.o()

    def generate_union_bytes_out(
        self, node: Value, uname: str, idx: int, inplace: bool
    ) -> None:
        self.o("    @scalgoproto.Adder")
        if inplace:
            self.o(f"    def {uname}(self, value: bytes) -> None:")
        else:
            self.o(
                f"    def {uname}(self, value: typing_.Union[scalgoproto.BytesOut, bytes]) -> None:"
            )
        self.output_doc(node, "        ")
        if inplace:
            self.o("        self._add_inplace_bytes(%d, value)" % (idx))
        else:
            self.o("        self._set_bytes(%d, value)" % (idx))
        self.o()

    def generate_union_in(self, node: Value, uname: str, table: Table) -> None:
        assert node.union is not None
        if node.optional:
            self.o("    @property")
            self.o(f"    def has_{uname}(self) -> bool:")
            self.o("        return self._get_uint16(%d, 0) != 0" % (node.offset,))
            self.o()
            self.o("    @property")
            self.o(f"    def {uname}(self) -> typing_.Optional[{node.union.name}In]:")
            self.output_doc(node, "        ")
            self.o(f"        if not self.has_{uname}:")
            self.o("            return None")
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
        else:
            self.o("    @property")
            self.o(f"    def {uname}(self) -> {node.union.name}In:")
            self.output_doc(node, "        ")
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
        assert node.union is not None
        self.o("    @property")
        self.o(
            "    def {}(self) -> {}{}Out:".format(
                uname, node.union.name, "Inplace" if node.inplace else ""
            )
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
        assert node.type_ is not None
        uname = snake(self.value(node.identifier))
        if node.list_:
            self.generate_list_in(node, uname)
        elif node.jagged:
            self.generate_jagged_offset_in(node, uname)
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
        assert node.type_ is not None
        uname = snake(self.value(node.identifier))
        if node.list_:
            self.generate_list_out(node, uname)
            if node.jagged_elements is not None:
                self.generate_jagged_out(node, uname)
        elif node.jagged:
            self.generate_jagged_offset_out(node, uname)
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
        self.o(f"    def _copy(self, i:{union.name}In) -> None:")
        self.o("        if False:")
        self.o("            pass")
        for node in union.members:
            assert node.type_ is not None
            if node.type_.type == TokenType.REMOVED:
                continue
            uuname = snake(self.value(node.identifier))
            self.o(f"        elif i.is_{uuname}:")
            if node.list_:
                self.o(
                    f"            self.add_{uuname}(len(i.{uuname}))._copy(i.{uuname})"
                )
            elif (
                node.type_.type == TokenType.TEXT or node.type_.type == TokenType.BYTES
            ):
                self.o(f"            self.add_{uuname}(i.{uuname})")
            elif node.table:
                if node.table.empty:
                    self.o(f"            self.add_{uuname}()")
                else:
                    self.o(f"            self.add_{uuname}()._copy(i.{uuname})")
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

        self.o(f"class {union.name}In(scalgoproto.UnionIn):")
        self.output_doc(union, "    ")
        self.o("    __slots__: typing_.List[str] = []")
        self.o("    _MEMBERS = [")
        for node in union.members:
            self.o(f'        "{snake(self.value(node.identifier))}",')
        self.o("    ]")
        self.o()
        self.o(
            "    def __init__(self, reader: scalgoproto.Reader, type: int, offset: int, size: int | None = None) -> None:"
        )
        self.o(
            '        """Private constructor. Call factory methods on scalgoproto.Reader to construct instances"""'
        )
        self.o("        super().__init__(reader, type, offset, size)")
        self.o()
        self.o("    class Type(enum.IntEnum):")
        self.o("        NONE = 0")
        for idx, member in enumerate(union.members, start=1):
            assert member.type_ is not None
            if member.type_.type == TokenType.REMOVED:
                continue
            if not isinstance(member, (Table, Value)):
                raise ICE()
            self.o("        %s = %d" % (self.value(member.identifier).upper(), idx))
        self.o()
        self.o("    @property")
        self.o("    def type(self) -> Type:")
        self.output_doc(union, "    ")
        self.o(f"        return {union.name}In.Type(self._type)")
        self.o()
        for member in union.members:
            assert member.type_ is not None
            if member.type_.type == TokenType.REMOVED:
                continue
            n = self.value(member.identifier)
            uuname = snake(n)
            self.o("    @property")
            self.o(f"    def is_{uuname}(self) -> bool:")
            self.o(f"        return self.type == {union.name}In.Type.{n.upper()}")
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

        self.o(f"class {union.name}Out(scalgoproto.UnionOut):")
        self.o("    __slots__: typing_.List[str] = []")
        self.o()
        self.o(
            "    def __init__(self, writer: scalgoproto.Writer, offset: int, end: int = 0) -> None:"
        )
        self.o(
            '        """Private constructor. Call factory methods on scalgoproto.Writer to construct instances"""'
        )
        self.o("        super().__init__(writer, offset, end)")
        self.o()
        for idx, member in enumerate(union.members, start=1):
            assert member.type_ is not None
            if member.type_.type == TokenType.REMOVED:
                continue
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
        self.generate_union_copy(union)
        self.o()

        self.o(f"class {union.name}InplaceOut(scalgoproto.UnionOut):")
        self.o("    __slots__: typing_.List[str] = []")
        self.o()
        self.o(
            "    def __init__(self, writer: scalgoproto.Writer, offset: int, end: int = 0) -> None:"
        )
        self.o(
            '        """Private constructor. Call factory methods on scalgoproto.Writer to construct instances"""'
        )
        self.o("        super().__init__(writer, offset, end)")
        self.o()
        for idx, member in enumerate(union.members, start=1):
            assert member.type_ is not None
            if member.type_.type == TokenType.REMOVED:
                continue
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
        self.generate_union_copy(union)
        self.o()

    def generate_table_copy(self, table: Table) -> None:
        self.o(f"    def _copy(self, i:{table.name}In) -> None:")
        for ip in (True, False):
            for node in table.members:
                uname = snake(self.value(node.identifier))
                if bool(node.inplace) != ip:
                    continue
                assert node.type_ is not None
                if node.list_:
                    if node.optional:
                        self.o(f"        if i.{uname} is not None:")
                        self.o(
                            f"            self.add_{uname}(len(i.{uname}))._copy(i.{uname})"
                        )
                    else:
                        self.o(
                            f"        self.add_{uname}(len(i.{uname}))._copy(i.{uname})"
                        )
                elif node.jagged:
                    self.o(f"        self.{uname}_offset = i.{uname}_offset")
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
                        self.o(f"        if i.{uname} is not None:")
                        self.o(f"            self.{uname} = i.{uname}")
                    else:
                        self.o(f"        self.{uname} = i.{uname}")
                elif node.table:
                    if node.optional:
                        self.o(f"        if i.{uname} is not None:")
                        if node.table.empty:
                            self.o("            self.add_%s()")
                        else:
                            self.o(f"            self.add_{uname}()._copy(i.{uname})")
                    else:
                        if node.table.empty:
                            self.o("        self.add_%s()")
                        else:
                            self.o(f"        self.add_{uname}()._copy(i.{uname})")
                elif node.union:
                    self.o(f"        if i.{uname} is not None:")
                    self.o(f"            self.{uname}._copy(i.{uname})")
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
        slots = []
        if has_jagged(table):
            slots += ['"_jagged_ctx"', '"_jagged_next"']
        if owns_jagged(table):
            slots.append('"_jagged_lists"')
        self.o(f"class {table.name}In(scalgoproto.TableIn):")
        self.output_doc(table, "    ")
        self.o(f"    __slots__: typing_.List[str] = [{', '.join(slots)}]")
        self.o(
            f"    _MAGIC: typing_.ClassVar[int] = 0x{table.magic:08X} # type: ignore"
        )
        self.o("    _MEMBERS = [")
        for node in table.members:
            suffix = "_offset" if node.jagged else ""
            self.o(f'        "{snake(self.value(node.identifier))}{suffix}",')
        self.o("    ]")
        self.o()
        if has_jagged(table):
            self.o(
                "    def __init__(self, reader: scalgoproto.Reader, offset: int, size: int, jagged: scalgoproto.JaggedContext | None = None, next_: int | None = None) -> None:"
            )
            self.o(
                '        """Private constructor. `jagged` holds the lists that jagged members name, and `next_` is the offset of the next element in the list, if any"""'
            )
            self.o("        super().__init__(reader, offset, size)")
            self.o("        self._jagged_ctx = jagged")
            self.o("        self._jagged_next = next_")
            self.o()
        if owns_jagged(table):
            self.o("    def _jagged(self) -> scalgoproto.JaggedContext:")
            self.o("        try:")
            self.o("            return self._jagged_lists")
            self.o("        except AttributeError:")
            self.o("            self._jagged_lists = scalgoproto.JaggedContext(self)")
            self.o("            return self._jagged_lists")
            self.o()

        for node in table.members:
            self.generate_value_in(table, node)
        self.o()

        assert table.default is not None
        # Generate Table writer
        self.o(f"class {table.name}Out(scalgoproto.TableOut):")
        self.output_doc(table, "    ")
        self.o("    __slots__: typing_.List[str] = []")
        self.o(
            f"    _MAGIC: typing_.ClassVar[int] = 0x{table.magic:08X} # type: ignore"
        )
        self.o("    _SIZE: typing_.ClassVar[int] = %d" % len(table.default))
        self.o(f'    _DEFAULT: typing_.ClassVar[bytes] = b"{cescape(table.default)}"')
        self.o(f"    _IN = {table.name}In")
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

        self.o(f"class {node.name}(scalgoproto.StructType):")
        init = []
        copy = []
        write = []
        read = []
        slots = []
        for v in node.members:
            n = snake(self.value(v.identifier))
            copy.append(f"self.{n} = {n}")
            slots.append(f'"{n}"')
            assert v.type_ is not None
            if v.type_.type in typeMap:
                ti = typeMap[v.type_.type]
                if v.type_.type in (TokenType.F32, TokenType.F64):
                    init.append(f"{n}: {ti.p} = 0.0")
                elif v.type_.type == TokenType.BOOL:
                    init.append(f"{n}: {ti.p} = False")
                else:
                    init.append(f"{n}: {ti.p} = 0")
                write.append(
                    'writer._data[offset + %d : offset + %d] = struct.pack("<%s", ins.%s)'
                    % (v.offset, v.offset + ti.w, ti.s, n)
                )
                read.append(
                    'struct.unpack("<%s", reader._data[offset + %d : offset + %d])[0]'
                    % (ti.s, v.offset, v.offset + ti.w)
                )
            elif v.enum:
                init.append(f"{n}: {v.enum.name} = {v.enum.name}(0)")
                write.append("writer._data[offset + %d] = int(ins.%s)" % (v.offset, n))
                read.append("%s(reader._data[offset + %d])" % (v.enum.name, v.offset))
            elif v.struct:
                init.append(f"{n}: {v.struct.name} = {v.struct.name}()")
                write.append(
                    "%s._write(writer, offset + %d, ins.%s)"
                    % (v.struct.name, v.offset, n)
                )
                read.append("%s._read(reader, offset + %d)" % (v.struct.name, v.offset))
            else:
                raise ICE()
        self.o("    __slots__ = [{}]".format(", ".join(slots)))
        self.o("    _WIDTH: typing_.ClassVar[int] = %d" % node.bytes)
        fmt_body = self.struct_format_body(node)
        self.o(
            '    _STRUCT_STR: typing_.ClassVar[str] = "%s"'
            % ("<" + (fmt_body if fmt_body else "0x"))
        )
        self.o()
        self.o("    def __init__(self, {}) -> None:".format(", ".join(init)))
        for line in copy:
            self.o(f"        {line}")
        self.o()
        self.o("    @staticmethod")
        self.o(
            f'    def _write(writer: scalgoproto.Writer, offset: int, ins: "{node.name}") -> None:'
        )
        for line in write:
            self.o(f"        {line}")
        self.o()
        self.o("    @staticmethod")
        self.o(
            f'    def _read(reader: scalgoproto.Reader, offset: int) -> "{node.name}":'
        )
        self.o(f"        return {node.name}(")
        for line in read:
            self.o(f"            {line},")
        self.o("        )")
        self.o()
        self.o()

    def generate_enum(self, node: Enum) -> None:
        self.o(f"class {node.name}(enum.IntEnum):")
        self.output_doc(node, "   ")
        for index, ev in enumerate(node.members):
            self.o("    %s = %d" % (self.value(ev.identifier), index))
        self.o()
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
                    assert u.name is not None
                    i.add(u.name)
                elif isinstance(u, (Table, Union)):
                    i.add(f"{u.name}In")
                    i.add(f"{u.name}Out")
                else:
                    raise ICE()

        for d, imp in imports.items():
            doc = self.documents.by_id[d]
            self.o(
                "from {}{} import {}".format(
                    self.import_prefix, doc.name, ", ".join(imp)
                )
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
    out = open(os.path.join(args.output, f"{documents.root.name}.py"), "w")
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
