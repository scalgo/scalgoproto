"""
Validate a schema
"""

import io
import math
import os
import sys

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

typeMap = {
    TokenType.I8: "std::int8_t",
    TokenType.I16: "std::int16_t",
    TokenType.I32: "std::int32_t",
    TokenType.I64: "std::int64_t",
    TokenType.U8: "std::uint8_t",
    TokenType.U16: "std::uint16_t",
    TokenType.UI32: "std::uint32_t",
    TokenType.UI64: "std::uint64_t",
    TokenType.F32: "float",
    TokenType.F64: "double",
}


def bs(v: Token | None) -> str:
    return "true" if v else "false"


class Generator:
    out: io.StringIO | None = None

    def __init__(self, documents: Documents) -> None:
        self.documents = documents
        self.current_namespace: str | None = None
        self.current_file: str | None = None

    def in_list_types(self, node: Value) -> tuple[str, str | None]:
        typeName: str | None = None
        rawType: str | None = None
        assert node.type_ is not None
        if node.type_.type in typeMap:
            typeName = typeMap[node.type_.type]
            rawType = typeName
        elif node.type_.type == TokenType.BOOL:
            typeName = "bool"
            rawType = "char"
        elif node.enum:
            typeName = rawType = self.qualify(node.enum)
        elif node.struct:
            typeName = rawType = self.qualify(node.struct)
        elif node.table:
            typeName = f"{self.qualify(node.table)}In"
        elif node.union:
            typeName = f"{self.qualify(node.union)}In<false>"
        elif node.type_.type == TokenType.TEXT:
            typeName = "std::string_view"
        elif node.type_.type == TokenType.BYTES:
            typeName = "scalgoproto::Bytes"
        else:
            raise ICE()
        assert typeName is not None
        return (typeName, rawType)

    def out_list_type(self, node: Value) -> str:
        typeName: str
        assert node.type_ is not None
        if node.type_.type in typeMap:
            typeName = typeMap[node.type_.type]
        elif node.type_.type == TokenType.BOOL:
            typeName = "bool"
        elif node.enum:
            typeName = self.qualify(node.enum)
        elif node.struct:
            typeName = self.qualify(node.struct)
        elif node.table:
            typeName = f"{self.qualify(node.table)}Out"
        elif node.union:
            typeName = f"{self.qualify(node.union)}Out"
        elif node.type_.type == TokenType.TEXT:
            typeName = "scalgoproto::TextOut"
        elif node.type_.type == TokenType.BYTES:
            typeName = "scalgoproto::BytesOut"
        else:
            raise ICE()
        return typeName

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

    def generate_list_in(self, node: Value, uname: str) -> None:
        lname = lcamel(uname)
        typeName, rawType = self.in_list_types(node)
        direct = "Direct" if node.direct else ""
        mult = f", scalgoproto::ListAccess<{typeName}>::mult" if not node.direct else ""

        if node.optional:
            self.o(f"\tbool has{uname}() const noexcept {{")
            self.o(f"\t\treturn get48_<{node.offset}>() != 0;")
            self.o("\t}")
            self.o("\t")

        self.output_doc(node, "\t")
        self.o(f"\tscalgoproto::{direct}ListIn<{typeName}> {lname}() const {{")
        if node.optional:
            self.o(f"\t\tassert (has{uname}());")
        self.o(
            f"\t\treturn getObject_<scalgoproto::{direct}ListIn<{typeName}> >(reader_, getPtr_<{bs(node.inplace)}, scalgoproto::{direct.upper()}LISTMAGIC, {node.offset}{mult}>());"
        )
        self.o("\t}")
        if rawType:
            self.o("\t")
            self.output_doc(
                node, "\t", [], ["\\note accessing this is undefined behaivour"]
            )
            self.o(f"\tstd::pair<const {rawType} *, size_t> {lname}Raw() const {{")
            if node.optional:
                self.o(f"\t\tassert(has{uname}());")
            self.o(
                f"\t\treturn getListRaw_<{rawType}>(getPtr_<{bs(node.inplace)}, scalgoproto::LISTMAGIC, {node.offset}{mult}>());"
            )
            self.o("\t}")

    def generate_union_list_in(self, node: Value, uname: str) -> None:
        lname = lcamel(uname)
        typeName, rawType = self.in_list_types(node)
        direct = "Direct" if node.direct else ""
        mult = f", scalgoproto::ListAccess<{typeName}>::mult" if not node.direct else ""
        self.o(f"\tscalgoproto::{direct}ListIn<{typeName}> {lname}() const {{")
        self.o(f"\t\tassert(is{uname}());")
        self.o(
            f"\t\treturn scalgoproto::In::getObject_<scalgoproto::{direct}ListIn<{typeName}>>(this->reader_, this->template getPtr_<scalgoproto::{direct.upper()}LISTMAGIC{mult}>());"
        )
        self.o("\t}")
        if rawType:
            self.o("\t")
            self.output_doc(
                node, "\t", [], ["\\note accessing this is undefined behavior"]
            )
            self.o(f"\tstd::pair<const {rawType} *, size_t> {lname}Raw() const {{")
            self.o(f"\t\tassert(is{uname}());")
            self.o(
                f"\t\treturn scalgoproto::In::getListRaw_<{rawType}>(this->reader_, this->template getPtr_<scalgoproto::LISTMAGIC, scalgoproto::ListAccess<{typeName}>::mult>());"
            )
            self.o("\t}")

    def generate_list_out(self, node: Value, uname: str, outer: str) -> None:
        assert node.type_ is not None
        typeName = self.out_list_type(node)
        direct = "Direct" if node.direct else ""
        header_size = 18 if node.direct else 10
        if node.inplace:
            self.o(
                f"\tscalgoproto::{direct}ListOut<{typeName}> add{uname}(size_t size) noexcept {{"
            )
            self.o(f"\t\tset48_<{node.offset}>(size);")
            self.o(
                f"\t\treturn addInplace{direct}List_<{typeName}>(writer_, offset_ + SIZE, size);"
            )
        else:
            self.o(
                f"\t{outer} & set{uname}(scalgoproto::{direct}ListOut<{typeName}> value) noexcept {{"
            )
            self.o(f"\t\tset48_<{node.offset}>(getOffset_(value)-{header_size});")
            self.o("\t\treturn * this;")
            self.o("\t}")
            self.o(
                f"\tscalgoproto::{direct}ListOut<{typeName}> add{uname}(size_t size) noexcept {{"
            )
            self.o(f"\t\tauto res = writer_.construct{direct}List<{typeName}>(size);")
            self.o(f"\t\tset48_<{node.offset}>(getOffset_(res)-{header_size});")
            self.o("\t\treturn res;")
        self.o("\t}")
        self.o(
            f"\tscalgoproto::{direct}ListOut<{typeName}> add{uname}(scalgoproto::{direct}ListIn<{self.in_list_types(node)[0]}> in) noexcept {{"
        )
        self.o(f"\t\treturn add{uname}(in.size()).copy_(in);")
        self.o("\t}")

        if node.type_.type in typeMap or node.struct or node.enum:
            self.o(
                f"\tscalgoproto::ListOut<{typeName}> add{uname}(const {typeName} * data, size_t size) noexcept {{"
            )
            self.o(f"\t\tauto v = add{uname}(size);")
            self.o("\t\tfor (size_t i = 0; i < size; ++i) {")
            self.o("\t\t\tv[i] = data[i];")
            self.o("\t\t}")
            self.o("\t\treturn v;")
            self.o("\t}")

    def generate_union_list_out(
        self, node: Value, uname: str, inplace: bool, idx: int
    ) -> None:
        typeName = self.out_list_type(node)
        direct = "Direct" if node.direct else ""
        if inplace:
            self.o(
                f"\tscalgoproto::{direct}ListOut<{typeName}> add{uname}(size_t size) noexcept {{"
            )
            self.o(f"\t\tsetType_({idx});")
            self.o("\t\tsetSize_(size);")
            self.o(
                f"\t\treturn addInplace{direct}List_<{typeName}>(writer_, next_, size);"
            )
        else:
            self.o(
                f"\tvoid set{uname}(scalgoproto::{direct}ListOut<{typeName}> value) noexcept {{"
            )
            self.o(f"\t\tsetType_({idx});")
            self.o(f"\t\tsetObject_(getOffset_(value)-{18 if node.direct else 10});")
            self.o("\t}")
            self.o(
                f"\tscalgoproto::{direct}ListOut<{typeName}> add{uname}(size_t size) noexcept {{"
            )
            self.o(f"\t\tauto res = writer_.constructList<{typeName}>(size);")
            self.o(f"\t\tset{uname}(res);")
            self.o("\t\treturn res;")
        self.o("\t}")
        self.o(
            f"\tscalgoproto::{direct}ListOut<{typeName}> add{uname}(scalgoproto::{direct}ListIn<{self.in_list_types(node)[0]}> in) noexcept {{"
        )
        self.o(f"\t\treturn add{uname}(in.size()).copy_(in);")
        self.o("\t}")

    def generate_bool_in(self, node: Value, uname: str) -> None:
        if node.inplace:
            raise ICE()
        if node.optional:
            self.o(f"\tbool has{uname}() const noexcept {{")
            self.o("\t\treturn getBit_<%d, %s, 0>();" % (node.has_offset, node.has_bit))
            self.o("\t}")
        self.o("\t")
        self.output_doc(node, "\t")
        self.o(f"\tbool {lcamel(uname)}() const noexcept {{")
        if node.optional:
            self.o(f"\t\tassert(has{uname}());")
        self.o("\t\treturn getBit_<%d, %s, 0>();" % (node.offset, node.bit))
        self.o("\t}")

    def generate_bool_out(self, node: Value, uname: str, outer: str) -> None:
        if node.inplace:
            raise ICE()
        self.o(f"\t{outer} & set{uname}(bool value) noexcept {{")
        if node.optional:
            self.o("\t\tsetBit_<%d, %d>();" % (node.has_offset, node.has_bit))
        self.o(
            f"\t\tif(value) setBit_<{node.offset}, {node.bit}>(); else unsetBit_<{node.offset}, {node.bit}>();"
        )
        self.o("\t\treturn *this;")
        self.o("\t}")
        self.generate_bool_in(node, uname)

    def generate_basic_in(self, node: Value, uname: str) -> None:
        if node.inplace:
            raise ICE()
        assert node.type_ is not None
        typeName = typeMap[node.type_.type]
        if node.optional:
            self.o(f"\tbool has{uname}() const noexcept {{")
            if node.type_.type in (TokenType.F32, TokenType.F64):
                self.o(
                    f"\t\treturn !std::isnan(getInner_<{typeName}, {node.offset}>(std::numeric_limits<{typeName}>::quiet_NaN()));"
                )
            else:
                self.o(
                    "\t\treturn getBit_<%d, %s, 0>();" % (node.has_offset, node.has_bit)
                )
            self.o("\t}")
        self.o("\t")
        self.output_doc(node, "\t")
        self.o(f"\t{typeName} {lcamel(uname)}() const noexcept {{")
        if node.optional:
            self.o(f"\t\tassert(has{uname}());")
        self.o(
            "\t\treturn getInner_<%s, %d>(%s);"
            % (
                typeName,
                node.offset,
                node.parsed_value if not math.isnan(node.parsed_value) else "NAN",
            )
        )
        self.o("\t}")

    def generate_basic_out(self, node: Value, uname: str, outer: str) -> None:
        if node.inplace:
            raise ICE()
        assert node.type_ is not None
        typeName = typeMap[node.type_.type]
        self.o(f"\t{outer} & set{uname}({typeName} value) noexcept {{")
        if node.optional and node.type_.type not in (TokenType.F32, TokenType.F64):
            self.o("\t\tsetBit_<%d, %d>();" % (node.has_offset, node.has_bit))
        self.o("\t\tsetInner_<%s, %d>(value);" % (typeName, node.offset))
        self.o("\t\treturn *this;")
        self.o("\t}")
        self.generate_basic_in(node, uname)

    def generate_enum_in(self, node: Value, uname: str) -> None:
        if node.inplace:
            raise ICE()
        assert node.enum is not None
        self.o(f"\tbool has{uname}() const noexcept {{")
        self.o(
            "\t\treturn getInner_<std::uint8_t, %d>(%d) < %d;"
            % (node.offset, node.parsed_value, len(node.enum.members))
        )
        self.o("\t}")
        self.o("\t")
        self.output_doc(node, "\t")
        self.o(f"\t{self.qualify(node.enum)} {lcamel(uname)}() const noexcept {{")
        self.o(f"\t\tassert(has{uname}());")
        self.o(
            "\t\treturn (%s)getInner_<std::uint8_t, %d>(%s);"
            % (self.qualify(node.enum), node.offset, node.parsed_value)
        )
        self.o("\t}")

    def generate_enum_out(self, node: Value, uname: str, outer: str) -> None:
        if node.inplace:
            raise ICE()
        assert node.enum is not None
        self.o(
            f"\t{outer} & set{uname}({self.qualify(node.enum)} value) noexcept {{"
        )
        self.o("\t\tsetInner_<%s, %d>(value);" % (self.qualify(node.enum), node.offset))
        self.o("\t\treturn *this;")
        self.o("\t}")
        self.generate_enum_in(node, uname)

    def generate_struct_in(self, node: Value, uname: str) -> None:
        if node.inplace:
            raise ICE()
        assert node.struct is not None
        if node.optional:
            self.o(f"\tbool has{uname}() const noexcept {{")
            self.o("\t\treturn getBit_<%d, %s, 0>();" % (node.has_offset, node.has_bit))
            self.o("\t}")
        self.o("\t")
        self.output_doc(node, "\t")
        self.o(
            f"\t{self.qualify(node.struct)} {lcamel(uname)}() const noexcept {{"
        )
        if node.optional:
            self.o(f"\t\tassert(has{uname}());")
        self.o(
            "\t\treturn getInner_<%s, %d>();" % (self.qualify(node.struct), node.offset)
        )
        self.o("\t}")

    def generate_struct_out(self, node: Value, uname: str, outer: str) -> None:
        if node.inplace:
            raise ICE()
        assert node.struct is not None
        self.o(
            f"\t{outer}& set{uname}(const {self.qualify(node.struct)} & value) noexcept {{"
        )
        if node.optional:
            self.o("\t\tsetBit_<%d, %d>();" % (node.has_offset, node.has_bit))
        self.o(
            "\t\tsetInner_<%s, %d>(value);" % (self.qualify(node.struct), node.offset)
        )
        self.o("\t\treturn *this;")
        self.o("\t}")
        self.generate_struct_in(node, uname)

    def generate_table_in(self, node: Value, uname: str) -> None:
        if node.optional:
            self.o(f"\tbool has{uname}() const noexcept {{")
            self.o("\t\treturn get48_<%d>() != 0;" % (node.offset))
            self.o("\t}")
            self.o("\t")
        assert node.table is not None
        if not node.table.empty:
            self.output_doc(node, "\t")
            self.o(f"\t{self.qualify(node.table)}In {lcamel(uname)}() const {{")
            if node.optional:
                self.o(f"\t\tassert(has{uname}());")
            self.o(
                "\t\treturn getObject_<%sIn>(reader_, getPtr_<%s, %sIn::MAGIC, %d>());"
                % (
                    self.qualify(node.table),
                    bs(node.inplace),
                    node.table.name,
                    node.offset,
                )
            )
        self.o("\t}")

    def generate_union_table_in(self, node: Value, uname: str) -> None:
        assert node.table is not None
        if not node.table.empty:
            self.output_doc(node, "\t")
            self.o(f"\t{self.qualify(node.table)}In {lcamel(uname)}() const {{")
            self.o(f"\t\tassert(is{uname}());")
            self.o(
                f"\t\treturn scalgoproto::In::getObject_<{self.qualify(node.table)}In>(this->reader_, this->template getPtr_<{node.table.name}In::MAGIC>());"
            )
            self.o("\t}")

    def generate_table_out(self, node: Value, uname: str, outer: str) -> None:
        assert node.table is not None
        self.o(
            "\tbool has%s() const noexcept {return get48_<%d>() != 0;}"
            % (uname, node.offset)
        )
        self.o("")
        if not node.inplace:
            self.o(
                f"\t{outer} & set{uname}({self.qualify(node.table)}Out value) noexcept {{"
            )
            self.o(f"\t\tassert(!has{uname}());")
            self.o("\t\tset48_<%d>(getOffset_(value)-10);" % (node.offset))
            self.o("\t\treturn *this;")
            self.o("\t}")
            self.o(f"\t{self.qualify(node.table)}Out add{uname}() noexcept {{")
            self.o(f"\t\tassert(!has{uname}());")
            self.o(
                f"\t\tauto res = writer_.construct<{self.qualify(node.table)}Out>();"
            )
            self.o("\t\tset48_<%d>(getOffset_(res)-10);" % (node.offset))
            self.o("\t\treturn res;")
            self.o("\t}")
            self.o(
                f"\t{self.qualify(node.table)}Out add{uname}({self.qualify(node.table)}In in) noexcept {{"
            )
            self.o(f"\t\treturn add{uname}().copy_(in);")
            self.o("\t}")
        elif not node.table.empty:
            self.o(f"\t{self.qualify(node.table)}Out add{uname}() noexcept {{")
            self.o(f"\t\tassert(!has{uname}());")
            self.o(
                "\t\tset48_<%d>(%sOut::SIZE);" % (node.offset, self.qualify(node.table))
            )
            self.o(
                f"\t\treturn addInplaceTable_<{self.qualify(node.table)}Out>(writer_, offset_+SIZE);"
            )
            self.o("\t}")
            self.o(
                f"\t{self.qualify(node.table)}Out add{uname}({self.qualify(node.table)}In in) noexcept {{"
            )
            self.o(f"\t\treturn add{uname}().copy_(in);")
            self.o("\t}")
        else:
            self.o(f"\t{uname} & set{outer}() noexcept {{")
            self.o(f"\t\tassert(!has{uname}());")
            self.o("\t\tset48_<%d>(0);" % (node.offset))
            self.o("\t\treturn *this;")
            self.o("\t}")

    def generate_union_table_out(
        self, node: Value, uname: str, inplace: bool, idx: int
    ) -> None:
        assert node.table is not None
        self.output_doc(node, "\t")
        if node.table.empty:
            self.o(f"\tvoid set{uname}() noexcept {{")
            self.o("\t\tsetType_(%d);" % (idx))
            self.o("\t}")
        elif not inplace:
            self.o(
                f"\tvoid set{uname}({self.qualify(node.table)}Out value) noexcept {{"
            )
            self.o("\t\tsetType_(%d);" % (idx))
            self.o("\t\tsetObject_(getOffset_(value)-10);")
            self.o("\t}")
            self.o(f"\t{self.qualify(node.table)}Out add{uname}() noexcept {{")
            self.o(
                f"\t\tauto res = writer_.construct<{self.qualify(node.table)}Out>();"
            )
            self.o(f"\t\tset{uname}(res);")
            self.o("\t\treturn res;")
            self.o("\t}")
            self.o(
                f"\t{self.qualify(node.table)}Out add{uname}({self.qualify(node.table)}In in) noexcept {{"
            )
            self.o(f"\t\treturn add{uname}().copy_(in);")
            self.o("\t}")
        else:
            self.o(f"\t{self.qualify(node.table)}Out add{uname}() noexcept {{")
            self.o("\t\tsetType_(%d);" % (idx))
            self.o(f"\t\tsetSize_({self.qualify(node.table)}Out::SIZE);")
            self.o(
                f"\t\treturn addInplaceTable_<{self.qualify(node.table)}Out>(writer_, next_);"
            )
            self.o("\t}")
            self.o(
                f"\t{self.qualify(node.table)}Out add{uname}({self.qualify(node.table)}In in) noexcept {{"
            )
            self.o(f"\t\treturn add{uname}().copy_(in);")
            self.o("\t}")

    def generate_text_in(self, node: Value, uname: str) -> None:
        if node.optional:
            self.o(f"\tbool has{uname}() const noexcept {{")
            self.o("\t\treturn get48_<%d>() != 0;" % (node.offset))
            self.o("\t}")
        self.o("\t")
        self.output_doc(node, "\t")
        self.o(f"\tstd::string_view {lcamel(uname)}() const {{")
        if node.optional:
            self.o(f"\t\tassert(has{uname}());")
        self.o(
            "\t\treturn getText_(reader_, getPtr_<%s, scalgoproto::TEXTMAGIC, %d,  1, 1>());"
            % (bs(node.inplace), node.offset)
        )
        self.o("\t}")

    def generate_union_text_in(self, node: Value, uname: str) -> None:
        self.output_doc(node, "\t")
        self.o(f"\tstd::string_view {lcamel(uname)}() {{")
        self.o(
            "\t\treturn scalgoproto::In::getText_(this->reader_, this->template getPtr_<scalgoproto::TEXTMAGIC, 1, 1>());"
        )
        self.o("\t}")

    def generate_text_out(self, node: Value, uname: str, outer: str) -> None:
        self.o(
            "\tbool has%s() const noexcept {return get48_<%d>() != 0;}"
            % (uname, node.offset)
        )
        if node.inplace:
            self.o(f"\tvoid add{uname}(std::string_view text) noexcept {{")
            self.o("\t\tset48_<%d>(text.size());" % (node.offset))
            self.o("\t\taddInplaceText_(writer_, offset_+SIZE, text);")
        else:
            self.o(f"\t{outer} set{uname}(scalgoproto::TextOut t) noexcept {{")
            self.o("\t\tset48_<%d>(getOffset_(t));" % (node.offset))
            self.o("\t\treturn *this;")
            self.o("\t}")
            self.o(
                f"\tscalgoproto::TextOut add{uname}(std::string_view t) noexcept {{"
            )
            self.o("\t\tauto res = writer_.constructText(t);")
            self.o("\t\tset48_<%d>(getOffset_(res));" % (node.offset))
            self.o("\t\treturn res;")
        self.o("\t}")

    def generate_union_text_out(
        self, node: Value, uname: str, inplace: bool, idx: int
    ) -> None:
        if inplace:
            self.o(f"\tvoid add{uname}(std::string_view text) noexcept {{")
            self.o("\t\tsetType_(%d);" % (idx))
            self.o("\t\tsetSize_(text.size());")
            self.o("\t\taddInplaceText_(writer_, next_, text);")
        else:
            self.o(f"\tvoid set{uname}(scalgoproto::TextOut t) noexcept {{")
            self.o("\t\tsetType_(%d);" % (idx))
            self.o("\t\tsetObject_(getOffset_(t));")
            self.o("\t}")
            self.o(
                f"\tscalgoproto::TextOut add{uname}(std::string_view t) noexcept {{"
            )
            self.o("\t\tauto res = writer_.constructText(t);")
            self.o(f"\t\tset{uname}(res);")
            self.o("\t\treturn res;")
        self.o("\t}")

    def generate_bytes_in(self, node: Value, uname: str) -> None:
        if node.optional:
            self.o(f"\tbool has{uname}() const noexcept {{")
            self.o("\t\treturn get48_<%d>() != 0;" % (node.offset))
            self.o("\t}")
            self.o("\t")
        self.output_doc(node, "\t")
        self.o(f"\tscalgoproto::Bytes {lcamel(uname)}() const {{")
        if node.optional:
            self.o(f"\t\tassert(has{uname}());")
        self.o(
            "\t\treturn getBytes_(getPtr_<%s, scalgoproto::BYTESMAGIC, %d>());"
            % (bs(node.inplace), node.offset)
        )
        self.o("\t}")

    def generate_union_bytes_in(self, node: Value, uname: str) -> None:
        self.output_doc(node, "\t")
        self.o(f"\tscalgoproto::Bytes {lcamel(uname)}() const {{")
        self.o(
            "\t\treturn scalgoproto::In::getBytes_(this->template getPtr_<scalgoproto::BYTESMAGIC>());"
        )
        self.o("\t}")

    def generate_bytes_out(self, node: Value, uname: str, outer: str) -> None:
        self.o(
            "\tbool has%s() const noexcept {return get48_<%d>() != 0;}"
            % (uname, node.offset)
        )
        if node.inplace:
            self.o(f"\tvoid add{uname}(const char * data, size_t size) noexcept {{")
            self.o("\t\tset48_<%d>(size);" % (node.offset,))
            self.o("\t\taddInplaceBytes_(writer_, offset_+SIZE, data, size);")
            self.o("\t}")
            self.o(f"\tvoid add{uname}(scalgoproto::Bytes bytes) noexcept {{")
            self.o(f"\t\tadd{uname}(bytes.first, bytes.second);")
            self.o("\t}")
            self.o(f"\tchar * add{uname}(size_t size) noexcept {{")
            self.o("\t\treturn addInplaceBytes_(writer_, offset_+SIZE, size);")
        else:
            self.o(f"\t{outer} & set{uname}(scalgoproto::BytesOut b) noexcept {{")
            self.o("\t\tset48_<%d>(getOffset_(b));" % (node.offset,))
            self.o("\t\treturn *this;")
            self.o("\t}")
            self.o(
                f"\tscalgoproto::BytesOut add{uname}(const char * data, size_t size) noexcept {{"
            )
            self.o("\t\tauto res = writer_.constructBytes(data, size);")
            self.o("\t\tset48_<%d>(getOffset_(res));" % (node.offset,))
            self.o("\t\treturn res;")
            self.o("\t}")
            self.o(
                f"\tscalgoproto::BytesOut add{uname}(scalgoproto::Bytes bytes) noexcept {{"
            )
            self.o(f"\t\treturn add{uname}(bytes.first, bytes.second);")
        self.o("\t}")

    def generate_union_bytes_out(
        self, node: Value, uname: str, inplace: bool, idx: int
    ) -> None:
        if inplace:
            self.o(f"\tvoid add{uname}(const char * data, size_t size) noexcept {{")
            self.o("\t\tsetType_(%d);" % (idx,))
            self.o("\t\tsetSize_(size);")
            self.o("\t\taddInplaceBytes_(writer_, next_, data, size);")
            self.o("\t}")
            self.o(f"\tvoid add{uname}(scalgoproto::Bytes bytes) noexcept {{")
            self.o(f"\t\tadd{uname}(bytes.first, bytes.second);")
        else:
            self.o(f"\tvoid set{uname}(scalgoproto::BytesOut b) noexcept {{")
            self.o("\t\tsetType_(%d);" % (idx,))
            self.o("\t\tsetObject_(getOffset_(b));")
            self.o("\t}")
            self.o(
                f"\tscalgoproto::BytesOut add{uname}(const char * data, size_t size) noexcept {{"
            )
            self.o("\t\tauto res = writer_.constructBytes(data, size);")
            self.o(f"\t\tset{uname}(res);")
            self.o("\t\treturn res;")
            self.o("\t}")
            self.o(
                f"\tscalgoproto::BytesOut add{uname}(scalgoproto::Bytes bytes) noexcept {{"
            )
            self.o(f"\t\treturn add{uname}(bytes.first, bytes.second);")
        self.o("\t}")

    def generate_union_in(self, node: Value, uname: str) -> None:
        assert node.union is not None
        if node.optional:
            self.o(
                "\tbool has%s() const noexcept {return getInner_<std::uint16_t, %d>() != 0;}"
                % (uname, node.offset)
            )
        self.output_doc(node, "\t")
        self.o(
            f"\t{self.qualify(node.union)}In<{bs(node.inplace)}> {lcamel(uname)}() const {{"
        )
        if node.optional:
            self.o(f"\t\tassert(has{uname}());")
        if node.inplace:
            self.o(
                "\t\treturn getObject_<%sIn<true>>(reader_, getInner_<std::uint16_t, %d>(), start_ + size_, get48_<%d>());"
                % (self.qualify(node.union), node.offset, node.offset + 2)
            )
        else:
            self.o(
                "\t\treturn getObject_<%sIn<false>>(reader_, getInner_<std::uint16_t, %d>(), get48_<%d>());"
                % (self.qualify(node.union), node.offset, node.offset + 2)
            )
        self.o("\t}")

    def generate_union_out(self, node: Value, uname: str) -> None:
        assert node.union is not None
        self.o(
            "\tbool has%s() const noexcept {return getInner_<std::uint16_t, %d>() != 0;}"
            % (uname, node.offset)
        )
        if node.inplace:
            self.o(
                f"\t{self.qualify(node.union)}InplaceOut {lcamel(uname)}() const noexcept {{"
            )
            self.o(
                "\t\treturn construct_<%sInplaceOut>(writer_, offset_ + %d, offset_ + SIZE);"
                % (self.qualify(node.union), node.offset)
            )
            self.o("\t}")
        else:
            self.o(
                f"\t{self.qualify(node.union)}Out {lcamel(uname)}() const noexcept {{"
            )
            self.o(
                "\t\treturn construct_<%sOut>(writer_, offset_ + %d);"
                % (self.qualify(node.union), node.offset)
            )
            self.o("\t}")
        self.o("\t")

    def generate_value_in(self, node: Value) -> None:
        assert node.type_ is not None
        n = self.value(node.identifier)
        uname = ucamel(n)
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
            self.generate_union_in(node, uname)
        elif node.type_.type == TokenType.TEXT:
            self.generate_text_in(node, uname)
        elif node.type_.type == TokenType.BYTES:
            self.generate_bytes_in(node, uname)
        else:
            raise ICE()

    def generate_value_out(self, node: Value, outer: str) -> None:
        assert node.type_ is not None
        uname = ucamel(self.value(node.identifier))
        self.output_doc(node, "\t")
        if node.list_:
            self.generate_list_out(node, uname, outer)
        elif node.type_.type == TokenType.BOOL:
            self.generate_bool_out(node, uname, outer)
        elif node.type_.type in typeMap:
            self.generate_basic_out(node, uname, outer)
        elif node.enum:
            self.generate_enum_out(node, uname, outer)
        elif node.struct:
            self.generate_struct_out(node, uname, outer)
        elif node.table:
            self.generate_table_out(node, uname, outer)
        elif node.union:
            self.generate_union_out(node, uname)
        elif node.type_.type == TokenType.TEXT:
            self.generate_text_out(node, uname, outer)
        elif node.type_.type == TokenType.BYTES:
            self.generate_bytes_out(node, uname, outer)
        else:
            raise ICE()

    def output_metamagic(self, mm: str) -> None:
        self.switch_namespace("scalgoproto")
        self.o(mm)

    def generate_union_copy(self, union: Union, inplace: bool) -> None:
        self.o(
            "\tvoid copy_({}In<{}> i) {{".format(union.name, "true" if inplace else "false")
        )
        self.o("\t\tswitch (i.type()) {")
        for node in union.members:
            assert node.type_ is not None
            if node.type_.type == TokenType.REMOVED:
                continue
            lname = lcamel(self.value(node.identifier))
            uname = ucamel(lname)
            c = f"{union.name}Type::{lname}"
            if node.list_:
                self.o(
                    f"\t\tcase {c}: add{uname}(i.{lname}().size()).copy_(i.{lname}()); break;"
                )
            elif node.type_.type == TokenType.TEXT:
                self.o(f"\t\tcase {c}: add{uname}(i.{lname}()); break;")
            elif node.type_.type == TokenType.BYTES:
                self.o(
                    f"\t\tcase {c}: add{uname}((const char *)i.{lname}().first, i.{lname}().second); break;"
                )
            elif node.table:
                if node.table.empty:
                    self.o(f"\t\tcase {c}: set{uname}(); break;")
                else:
                    self.o(f"\t\tcase {c}: add{uname}().copy_(i.{lname}()); break;")
            else:
                raise ICE()
        self.o("\t\tdefault: break;")
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
        self.switch_namespace(union.namespace)
        self.output_doc(union)
        self.o(f"enum class {union.name}Type : std::uint16_t {{")
        self.o("\tnone,")
        for member in union.members:
            if not isinstance(member, (Table, Value)):
                raise ICE()
            self.o(f"\t{self.value(member.identifier)},")
        self.o("};")
        self.o("")
        self.output_doc(union)
        self.o("template <bool inplace>")
        self.o(f"class {union.name}In: public scalgoproto::UnionIn<inplace> {{")
        self.o("protected:")
        self.o("\tusing scalgoproto::UnionIn<inplace>::UnionIn;")
        self.o("public:")
        self.o(f"\tusing IN={union.name}In;")
        self.o(f"\tusing Type = {union.name}Type;")
        self.o("\tType type() const noexcept {return (Type)this->type_;}")
        for member in union.members:
            assert member.type_ is not None
            if member.type_.type == TokenType.REMOVED:
                continue
            n = self.value(member.identifier)
            uname = ucamel(n)
            self.o(
                f"\tbool is{uname}() const noexcept {{return type() == Type::{n};}}"
            )
            if member.list_:
                self.generate_union_list_in(member, uname)
            elif member.table:
                self.generate_union_table_in(member, uname)
            elif member.type_.type == TokenType.BYTES:
                self.generate_union_bytes_in(member, uname)
            elif member.type_.type == TokenType.TEXT:
                self.generate_union_text_in(member, uname)
            else:
                raise ICE()
        self.o("};")
        self.output_metamagic(
            f"template <bool inplace> struct MetaMagic<{self.qualify(union, True)}In<inplace>> {{using t=UnionTag;}};"
        )
        self.o("")
        for inplace, prefix in ((False, ""), (True, "Inplace")):
            self.switch_namespace(union.namespace)
            self.o(
                f"class {union.name}{prefix}Out: public scalgoproto::{prefix}UnionOut {{"
            )
            self.o("\tfriend class Out;")
            self.o("protected:")
            self.o(f"\tusing scalgoproto::{prefix}UnionOut::{prefix}UnionOut;")
            self.o("public:")
            self.o(f"\tusing Type = {union.name}Type;")
            self.o(
                "\tusing IN={}In<{}>;".format(union.name, "true" if inplace else "false")
            )
            self.o("\tType type() const noexcept {return (Type)this->getType_();}")
            for idx, member in enumerate(union.members, start=1):
                assert member.type_ is not None
                if member.type_.type == TokenType.REMOVED:
                    continue
                n = self.value(member.identifier)
                uname = ucamel(n)
                if member.list_:
                    self.generate_union_list_out(member, uname, inplace, idx)
                elif member.table:
                    self.generate_union_table_out(member, uname, inplace, idx)
                elif member.type_.type == TokenType.BYTES:
                    self.generate_union_bytes_out(member, uname, inplace, idx)
                elif member.type_.type == TokenType.TEXT:
                    self.generate_union_text_out(member, uname, inplace, idx)
                else:
                    raise ICE()
            self.generate_union_copy(union, inplace)
            self.o("};")
            self.output_metamagic(
                f"template <> struct MetaMagic<{self.qualify(union, True)}{prefix}Out> {{using t=UnionTag;}};"
            )
            self.o("")

    def generate_table_copy(self, table: Table) -> None:
        self.o(f"\t{table.name}Out & copy_({table.name}In i) {{")
        for ip in (True, False):
            for node in table.members:
                lname = lcamel(self.value(node.identifier))
                uname = ucamel(lname)
                if bool(node.inplace) != ip:
                    continue
                assert node.type_ is not None
                if node.list_:
                    self.o(
                        f"\t\tif (i.{lname}().size()) add{uname}(i.{lname}().size()).copy_(i.{lname}());"
                    )
                elif (
                    node.type_.type in typeMap
                    or node.type_.type == TokenType.BOOL
                    or node.enum
                    or node.struct
                ):
                    if node.optional:
                        self.o(
                            f"\t\tif (i.has{uname}()) set{uname}(i.{lname}());"
                        )
                    else:
                        self.o(f"\t\tset{uname}(i.{lname}());")
                elif node.table:
                    if node.table.empty:
                        self.o(f"\t\tif (i.has{uname}()) add{uname}();")
                    elif node.optional:
                        self.o(
                            f"\t\tif (i.has{uname}()) add{uname}().copy_(i.{lname}());"
                        )
                    else:
                        self.o(f"\t\tadd{uname}().copy_(i.{lname}());")
                elif node.union and node.optional:
                    self.o(
                        f"\t\tif (i.has{uname}()) {lname}().copy_(i.{lname}());"
                    )
                elif node.union:
                    self.o(f"\t\t{lname}().copy_(i.{lname}());")
                elif node.type_.type == TokenType.TEXT and node.optional:
                    self.o(f"\t\tif (i.has{uname}()) add{uname}(i.{lname}());")
                elif node.type_.type == TokenType.TEXT:
                    self.o(
                        f"\t\tif (!i.{lname}().empty()) add{uname}(i.{lname}());"
                    )
                elif node.type_.type == TokenType.BYTES and node.optional:
                    self.o(
                        f"\t\tif (i.has{uname}()) add{uname}((const char*)i.{lname}().first, i.{lname}().second);"
                    )
                elif node.type_.type == TokenType.BYTES:
                    self.o(
                        f"\t\tif (i.{lname}().second) add{uname}((const char*)i.{lname}().first, i.{lname}().second);"
                    )
                else:
                    raise ICE()
        self.o("\t\treturn *this;")
        self.o("\t}")

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
        self.switch_namespace(table.namespace)
        self.output_doc(table)
        self.o(f"class {table.name}In: public scalgoproto::TableIn {{")
        self.o("\tfriend class scalgoproto::In;")
        self.o("\tfriend class scalgoproto::TableIn;")
        self.o("\tfriend class scalgoproto::Reader;")
        self.o(
            "\ttemplate <typename, typename> friend class scalgoproto::ListAccessHelp;"
        )
        self.o("protected:")
        self.o(
            f"\t{table.name}In(const scalgoproto::Reader * reader, scalgoproto::Ptr p): scalgoproto::TableIn(reader, p) {{}}"
        )
        self.o("public:")
        self.o(f"\tstatic constexpr std::uint32_t MAGIC = 0x{table.magic:08X};")
        self.o(f"\tusing IN={table.name}In;")
        for node in table.members:
            self.generate_value_in(node)
        self.o("};")
        self.output_metamagic(
            f"template <> struct MetaMagic<{self.qualify(table, True)}In> {{using t=TableTag;}};"
        )
        self.o("")
        assert table.default is not None
        self.switch_namespace(table.namespace)
        self.output_doc(table)
        self.o(f"class {table.name}Out: public scalgoproto::TableOut {{")
        self.o("\tfriend class scalgoproto::Out;")
        self.o("\tfriend class scalgoproto::Writer;")
        self.o("public:")
        self.o("\tstatic constexpr std::uint64_t SIZE = %d;" % (len(table.default)))
        self.o(f"\tstatic constexpr std::uint32_t MAGIC = 0x{table.magic:08X};")
        self.o(f"\tusing IN={table.name}In;")
        self.o("protected:")
        self.o(
            f'\t{table.name}Out(scalgoproto::Writer & writer, bool withHeader): scalgoproto::TableOut(writer, withHeader, MAGIC, "{cescape(table.default)}", SIZE) {{}}'
        )
        self.o(
            f"\t{table.name}Out(scalgoproto::Writer & writer, std::uint64_t offset): scalgoproto::TableOut(writer, offset) {{}}"
        )
        self.o("public:")
        for node in table.members:
            self.generate_value_out(node, f"{table.name}Out")
        self.generate_table_copy(table)
        self.o("};")
        self.output_metamagic(
            f"template <> struct MetaMagic<{self.qualify(table, True)}Out> {{using t=TableTag;}};"
        )
        self.o("")

    def generate_struct(self, node: Struct) -> None:
        # Recursively generate direct contained members
        for value in node.members:
            if value.direct_enum:
                self.generate_enum(value.direct_enum)
            if value.direct_struct:
                self.generate_struct(value.direct_struct)

        self.switch_namespace(node.namespace)
        self.o("#pragma pack(push, 1)")
        self.o(f"struct {node.name} {{")
        for v in node.members:
            if not isinstance(v, Value):
                raise ICE()
            if v.type_ is None:
                raise ICE()
            typeName = ""
            if v.type_.type == TokenType.U8:
                typeName = "std::uint8_t"
            elif v.type_.type == TokenType.U16:
                typeName = "std::uint16_t"
            elif v.type_.type == TokenType.UI32:
                typeName = "std::uint32_t"
            elif v.type_.type == TokenType.UI64:
                typeName = "std::uint64_t"
            elif v.type_.type == TokenType.I8:
                typeName = "std::int8_t"
            elif v.type_.type == TokenType.I16:
                typeName = "std::int16_t"
            elif v.type_.type == TokenType.I32:
                typeName = "std::int32_t"
            elif v.type_.type == TokenType.I64:
                typeName = "std::int64_t"
            elif v.type_.type == TokenType.F32:
                typeName = "float"
            elif v.type_.type == TokenType.F64:
                typeName = "double"
            elif v.type_.type == TokenType.BOOL:
                typeName = "bool"
            elif v.struct:
                if v.struct.name is None:
                    raise ICE()
                typeName = v.struct.name
            elif v.enum:
                if v.enum.name is None:
                    raise ICE()
                typeName = v.enum.name
            else:
                raise ICE()
            self.o(f"\t{typeName} {self.value(v.identifier)};")
        self.o("};")
        self.o("#pragma pack(pop)")
        self.output_metamagic(
            f"template <> struct MetaMagic<{self.qualify(node, True)}> {{using t=PodTag;}};"
        )
        self.o()

    def generate_enum(self, node: Enum) -> None:
        self.switch_namespace(node.namespace)
        self.o(f"enum class {node.name}: std::uint8_t {{")
        for idx, ev in enumerate(node.members):
            if ev.token is None:
                raise ICE()
            self.output_doc(ev, "\t")
            self.o("\t%s = %d," % (self.value(ev.token), idx))
        self.o("};")
        self.output_metamagic(
            """template <> struct MetaMagic<%s> {using t=EnumTag;};
template <> struct EnumSize<%s> {static constexpr size_t size() noexcept {return %d;}};"""
            % (self.qualify(node, True), self.qualify(node, True), len(node.members))
        )
        self.o()

    def switch_namespace(self, namespace: str | None) -> None:
        if namespace == self.current_namespace:
            return
        if self.current_namespace:
            self.o(f"}} //namespace {self.current_namespace}")
        if namespace:
            self.o(f"namespace {namespace} {{")
        self.current_namespace = namespace

    def qualify(self, node: Union | Table | Struct | Enum, full: bool = False) -> str:
        if node.namespace and (full or node.namespace != self.current_namespace):
            return f"{node.namespace}::{node.name}"
        else:
            if node.name is None:
                raise ICE()
            return node.name

    def switch_file(self, name: str | None, output: str):
        if self.current_file:
            assert self.out is not None
            self.switch_namespace(None)
            self.o(f"#endif //__SCALGOPROTO_{self.current_file}__")
            po = os.path.join(output, f"{self.current_file}.hh")
            if not os.path.exists(po) or open(po).read() != self.out.getvalue():
                open(po, "w").write(self.out.getvalue())
        if name:
            guard_name = name.replace("/", "_")
            self.out = io.StringIO()
            self.o("//THIS FILE IS GENERATED DO NOT EDIT")
            self.o(f"#ifndef __SCALGOPROTO_{guard_name}__")
            self.o(f"#define __SCALGOPROTO_{guard_name}__")
            self.o("#include <scalgoproto.hh>")
            self.current_file = name

    def generate(
        self,
        ast: list[AstNode],
        output: str,
        single: bool,
        expected: list[str],
        expected_only: bool,
        schema: str,
        *,
        dir_strip: int | None = None,
    ) -> None:
        if single:
            if dir_strip is not None:
                raise Exception("--single and --dir-strip cannot be specified together")
            self.switch_file(self.documents.root.name, output)

            imports = set()
            for node in ast:
                if node.document != 0:
                    continue
                for u in node.uses:
                    if u.document == 0:
                        continue
                    imports.add(self.documents.by_id[u.document].name)

            for i in sorted(imports):
                self.o(f'#include "{i}.hh"')

        def node_path(node: Struct | Enum | Table | Union) -> str:
            name = node.name
            assert name is not None
            if dir_strip is None:
                return name
            assert node.namespace is not None
            ns = node.namespace.split("::")[dir_strip:]
            assert ".." not in ns
            return "/".join(ns + [name])

        err = False
        found = set()
        for node in ast:
            if node.document != 0:
                continue

            if not single and (
                isinstance(node, (Struct, Enum, Table, Union))
            ):
                name = node_path(node)
                short_name = name.split("/")[-1]
                found.add(short_name)
                if expected_only and short_name not in expected:
                    ParseError(
                        node.identifier, f"Unexpected output {short_name}", schema
                    ).describe(self.documents)
                    err = True
                self.switch_file(name, output)
                for use in sorted(node.uses, key=lambda u: u.name):
                    n = node_path(use)
                    lcp = os.path.commonprefix([name, os.path.dirname(n) + "/"])
                    dirs = name[len(lcp) :].count("/")
                    relpath = "../" * dirs + n[len(lcp) :]
                    self.o(f'#include "{relpath}.hh"')

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
        self.switch_file(None, output)
        for name in expected:
            if name not in found:
                print(
                    f"Missing output {name} in {schema}",
                    file=sys.stderr,
                )
                err = True
        if err:
            sys.exit(1)


def run(args) -> int:
    documents = Documents()
    documents.read_root(args.schema)
    p = Parser(documents)
    try:
        ast = p.parse_document()
        if not annotate(documents, ast):
            print("Invalid schema is valid")
            return 1
        g = Generator(documents)
        os.makedirs(args.output, exist_ok=True)
        g.generate(
            ast,
            args.output,
            args.single,
            dir_strip=args.dir_strip,
            expected=args.expected,
            expected_only=args.expected_only,
            schema=args.schema,
        )
        return 0
    except ParseError as err:
        err.describe(documents)
    return 1


def setup(subparsers) -> None:
    cmd = subparsers.add_parser("cpp", help="Generate cpp code for windows")
    cmd.add_argument("schema", help="schema to generate things from")
    cmd.add_argument("output", help="where do we store the output")
    cmd.add_argument("--single", action="store_true")
    cmd.add_argument(
        "--dir-strip",
        type=int,
        metavar="N",
        help="output in subdir formed by removing first N components of namespace",
    )
    cmd.add_argument(
        "--expect",
        action="append",
        help="Check that this table is defined",
        dest="expected",
        default=[],
    )
    cmd.add_argument(
        "--expected-only",
        action="store_true",
        help="Check that only --expect tables exist",
    )
    cmd.set_defaults(func=run)
