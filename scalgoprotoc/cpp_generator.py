# -*- mode: python; tab-width: 4; indent-tabs-mode: nil; python-indent-offset: 4; coding: utf-8 -*-
"""
Validate a schema
"""
import math, io, os, sys
from typing import List, Tuple, Optional
import typing
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
from .util import cescape, lcamel, ucamel, snake
from .documents import Documents, Document

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


def bs(v: Optional[Token]) -> str:
    return "true" if v else "false"


class Generator:
    out: Optional[io.StringIO] = None

    def __init__(self, documents: Documents) -> None:
        self.documents = documents
        self.current_namespace: Optional[str] = None
        self.current_file: Optional[str] = None

    def in_list_types(self, node: Value) -> Tuple[str, Optional[str]]:
        typeName: Optional[str] = None
        rawType: Optional[str] = None
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
            typeName = "%sIn" % self.qualify(node.table)
        elif node.union:
            typeName = "%sIn<false>" % self.qualify(node.union)
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
            typeName = "%sOut" % self.qualify(node.table)
        elif node.union:
            typeName = "%sOut" % self.qualify(node.union)
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
            self.o("\tbool has%s() const noexcept {" % (uname))
            self.o("\t\treturn getBit_<%d, %s, 0>();" % (node.has_offset, node.has_bit))
            self.o("\t}")
        self.o("\t")
        self.output_doc(node, "\t")
        self.o("\tbool %s() const noexcept {" % (lcamel(uname)))
        if node.optional:
            self.o("\t\tassert(has%s());" % uname)
        self.o("\t\treturn getBit_<%d, %s, 0>();" % (node.offset, node.bit))
        self.o("\t}")

    def generate_bool_out(self, node: Value, uname: str, outer: str) -> None:
        if node.inplace:
            raise ICE()
        self.o("\t%s & set%s(bool value) noexcept {" % (outer, uname))
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
            self.o("\tbool has%s() const noexcept {" % (uname))
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
        self.o("\t%s %s() const noexcept {" % (typeName, lcamel(uname)))
        if node.optional:
            self.o("\t\tassert(has%s());" % uname)
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
        self.o("\t%s & set%s(%s value) noexcept {" % (outer, uname, typeName))
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
        self.o("\tbool has%s() const noexcept {" % (uname))
        self.o(
            "\t\treturn getInner_<std::uint8_t, %d>(%d) < %d;"
            % (node.offset, node.parsed_value, len(node.enum.members))
        )
        self.o("\t}")
        self.o("\t")
        self.output_doc(node, "\t")
        self.o("\t%s %s() const noexcept {" % (self.qualify(node.enum), lcamel(uname)))
        self.o("\t\tassert(has%s());" % uname)
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
            "\t%s & set%s(%s value) noexcept {"
            % (outer, uname, self.qualify(node.enum))
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
            self.o("\tbool has%s() const noexcept {" % (uname))
            self.o("\t\treturn getBit_<%d, %s, 0>();" % (node.has_offset, node.has_bit))
            self.o("\t}")
        self.o("\t")
        self.output_doc(node, "\t")
        self.o(
            "\t%s %s() const noexcept {" % (self.qualify(node.struct), lcamel(uname))
        )
        if node.optional:
            self.o("\t\tassert(has%s());" % uname)
        self.o(
            "\t\treturn getInner_<%s, %d>();" % (self.qualify(node.struct), node.offset)
        )
        self.o("\t}")

    def generate_struct_out(self, node: Value, uname: str, outer: str) -> None:
        if node.inplace:
            raise ICE()
        assert node.struct is not None
        self.o(
            "\t%s& set%s(const %s & value) noexcept {"
            % (outer, uname, self.qualify(node.struct))
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
            self.o("\tbool has%s() const noexcept {" % (uname))
            self.o("\t\treturn get48_<%d>() != 0;" % (node.offset))
            self.o("\t}")
            self.o("\t")
        assert node.table is not None
        if not node.table.empty:
            self.output_doc(node, "\t")
            self.o("\t%sIn %s() const {" % (self.qualify(node.table), lcamel(uname)))
            if node.optional:
                self.o("\t\tassert(has%s());" % uname)
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
            self.o(
                "\t%sIn %s() const noexcept {"
                % (self.qualify(node.table), lcamel(uname))
            )
            self.o("\t\tassert(is%s());" % (uname))
            self.o(
                "\t\treturn scalgoproto::In::getObject_<%sIn>(this->reader_, this->template getPtr_<%sIn::MAGIC>());"
                % (self.qualify(node.table), node.table.name)
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
                "\t%s & set%s(%sOut value) noexcept {"
                % (outer, uname, self.qualify(node.table))
            )
            self.o("\t\tassert(!has%s());" % (uname))
            self.o("\t\tset48_<%d>(getOffset_(value)-10);" % (node.offset))
            self.o("\t\treturn *this;")
            self.o("\t}")
            self.o("\t%sOut add%s() noexcept {" % (self.qualify(node.table), uname))
            self.o("\t\tassert(!has%s());" % (uname))
            self.o(
                "\t\tauto res = writer_.construct<%sOut>();"
                % (self.qualify(node.table),)
            )
            self.o("\t\tset48_<%d>(getOffset_(res)-10);" % (node.offset))
            self.o("\t\treturn res;")
            self.o("\t}")
            self.o(
                "\t%sOut add%s(%sIn in) noexcept {"
                % (self.qualify(node.table), uname, self.qualify(node.table))
            )
            self.o("\t\treturn add%s().copy_(in);" % (uname))
            self.o("\t}")
        elif not node.table.empty:
            self.o("\t%sOut add%s() noexcept {" % (self.qualify(node.table), uname))
            self.o("\t\tassert(!has%s());" % (uname))
            self.o(
                "\t\tset48_<%d>(%sOut::SIZE);" % (node.offset, self.qualify(node.table))
            )
            self.o(
                "\t\treturn addInplaceTable_<%sOut>(writer_, offset_+SIZE);"
                % self.qualify(node.table)
            )
            self.o("\t}")
            self.o(
                "\t%sOut add%s(%sIn in) noexcept {"
                % (self.qualify(node.table), uname, self.qualify(node.table))
            )
            self.o("\t\treturn add%s().copy_(in);" % (uname))
            self.o("\t}")
        else:
            self.o("\t%s & set%s() noexcept {" % (uname, outer))
            self.o("\t\tassert(!has%s());" % (uname))
            self.o("\t\tset48_<%d>(0);" % (node.offset))
            self.o("\t\treturn *this;")
            self.o("\t}")

    def generate_union_table_out(
        self, node: Value, uname: str, inplace: bool, idx: int
    ) -> None:
        assert node.table is not None
        self.output_doc(node, "\t")
        if node.table.empty:
            self.o("\tvoid set%s() noexcept {" % (uname))
            self.o("\t\tsetType_(%d);" % (idx))
            self.o("\t}")
        elif not inplace:
            self.o(
                "\tvoid set%s(%sOut value) noexcept {"
                % (uname, self.qualify(node.table))
            )
            self.o("\t\tsetType_(%d);" % (idx))
            self.o("\t\tsetObject_(getOffset_(value)-10);")
            self.o("\t}")
            self.o("\t%sOut add%s() noexcept {" % (self.qualify(node.table), uname))
            self.o(
                "\t\tauto res = writer_.construct<%sOut>();" % self.qualify(node.table)
            )
            self.o("\t\tset%s(res);" % (uname,))
            self.o("\t\treturn res;")
            self.o("\t}")
            self.o(
                "\t%sOut add%s(%sIn in) noexcept {"
                % (self.qualify(node.table), uname, self.qualify(node.table))
            )
            self.o("\t\treturn add%s().copy_(in);" % (uname))
            self.o("\t}")
        else:
            self.o("\t%sOut add%s() noexcept {" % (self.qualify(node.table), uname))
            self.o("\t\tsetType_(%d);" % (idx))
            self.o("\t\tsetSize_(%sOut::SIZE);" % (self.qualify(node.table)))
            self.o(
                "\t\treturn addInplaceTable_<%sOut>(writer_, next_);"
                % (self.qualify(node.table))
            )
            self.o("\t}")
            self.o(
                "\t%sOut add%s(%sIn in) noexcept {"
                % (self.qualify(node.table), uname, self.qualify(node.table))
            )
            self.o("\t\treturn add%s().copy_(in);" % (uname))
            self.o("\t}")

    def generate_text_in(self, node: Value, uname: str) -> None:
        if node.optional:
            self.o("\tbool has%s() const noexcept {" % (uname))
            self.o("\t\treturn get48_<%d>() != 0;" % (node.offset))
            self.o("\t}")
        self.o("\t")
        self.output_doc(node, "\t")
        self.o("\tstd::string_view %s() const {" % (lcamel(uname)))
        if node.optional:
            self.o("\t\tassert(has%s());" % (uname))
        self.o(
            "\t\treturn getText_(reader_, getPtr_<%s, scalgoproto::TEXTMAGIC, %d,  1, 1>());"
            % (bs(node.inplace), node.offset)
        )
        self.o("\t}")

    def generate_union_text_in(self, node: Value, uname: str) -> None:
        self.output_doc(node, "\t")
        self.o("\tstd::string_view %s() {" % (lcamel(uname)))
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
            self.o("\tvoid add%s(std::string_view text) noexcept {" % (uname))
            self.o("\t\tset48_<%d>(text.size());" % (node.offset))
            self.o("\t\taddInplaceText_(writer_, offset_+SIZE, text);")
        else:
            self.o("\t%s set%s(scalgoproto::TextOut t) noexcept {" % (outer, uname))
            self.o("\t\tset48_<%d>(getOffset_(t));" % (node.offset))
            self.o("\t\treturn *this;")
            self.o("\t}")
            self.o(
                "\tscalgoproto::TextOut add%s(std::string_view t) noexcept {" % (uname)
            )
            self.o("\t\tauto res = writer_.constructText(t);")
            self.o("\t\tset48_<%d>(getOffset_(res));" % (node.offset))
            self.o("\t\treturn res;")
        self.o("\t}")

    def generate_union_text_out(
        self, node: Value, uname: str, inplace: bool, idx: int
    ) -> None:
        if inplace:
            self.o("\tvoid add%s(std::string_view text) noexcept {" % (uname))
            self.o("\t\tsetType_(%d);" % (idx))
            self.o("\t\tsetSize_(text.size());")
            self.o("\t\taddInplaceText_(writer_, next_, text);")
        else:
            self.o("\tvoid set%s(scalgoproto::TextOut t) noexcept {" % (uname))
            self.o("\t\tsetType_(%d);" % (idx))
            self.o("\t\tsetObject_(getOffset_(t));")
            self.o("\t}")
            self.o(
                "\tscalgoproto::TextOut add%s(std::string_view t) noexcept {" % (uname)
            )
            self.o("\t\tauto res = writer_.constructText(t);")
            self.o("\t\tset%s(res);" % uname)
            self.o("\t\treturn res;")
        self.o("\t}")

    def generate_bytes_in(self, node: Value, uname: str) -> None:
        if node.optional:
            self.o("\tbool has%s() const noexcept {" % (uname))
            self.o("\t\treturn get48_<%d>() != 0;" % (node.offset))
            self.o("\t}")
            self.o("\t")
        self.output_doc(node, "\t")
        self.o("\tscalgoproto::Bytes %s() const {" % (lcamel(uname)))
        if node.optional:
            self.o("\t\tassert(has%s());" % (uname))
        self.o(
            "\t\treturn getBytes_(getPtr_<%s, scalgoproto::BYTESMAGIC, %d>());"
            % (bs(node.inplace), node.offset)
        )
        self.o("\t}")

    def generate_union_bytes_in(self, node: Value, uname: str) -> None:
        self.output_doc(node, "\t")
        self.o("\tscalgoproto::Bytes %s() const {" % (lcamel(uname)))
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
            self.o("\tvoid add%s(const char * data, size_t size) noexcept {" % (uname,))
            self.o("\t\tset48_<%d>(size);" % (node.offset,))
            self.o("\t\taddInplaceBytes_(writer_, offset_+SIZE, data, size);")
            self.o("\t}")
            self.o("\tvoid add%s(scalgoproto::Bytes bytes) noexcept {" % (uname,))
            self.o("\t\tadd%s(bytes.first, bytes.second);" % (uname,))
            self.o("\t}")
            self.o("\tchar * add%s(size_t size) noexcept {" % (uname,))
            self.o("\t\treturn addInplaceBytes_(writer_, offset_+SIZE, size);")
        else:
            self.o("\t%s & set%s(scalgoproto::BytesOut b) noexcept {" % (outer, uname))
            self.o("\t\tset48_<%d>(getOffset_(b));" % (node.offset,))
            self.o("\t\treturn *this;")
            self.o("\t}")
            self.o(
                "\tscalgoproto::BytesOut add%s(const char * data, size_t size) noexcept {"
                % (uname,)
            )
            self.o("\t\tauto res = writer_.constructBytes(data, size);")
            self.o("\t\tset48_<%d>(getOffset_(res));" % (node.offset,))
            self.o("\t\treturn res;")
            self.o("\t}")
            self.o(
                "\tscalgoproto::BytesOut add%s(scalgoproto::Bytes bytes) noexcept {"
                % (uname,)
            )
            self.o("\t\treturn add%s(bytes.first, bytes.second);" % (uname,))
        self.o("\t}")

    def generate_union_bytes_out(
        self, node: Value, uname: str, inplace: bool, idx: int
    ) -> None:
        if inplace:
            self.o("\tvoid add%s(const char * data, size_t size) noexcept {" % (uname,))
            self.o("\t\tsetType_(%d);" % (idx,))
            self.o("\t\tsetSize_(size);")
            self.o("\t\taddInplaceBytes_(writer_, next_, data, size);")
            self.o("\t}")
            self.o("\tvoid add%s(scalgoproto::Bytes bytes) noexcept {" % (uname,))
            self.o("\t\tadd%s(bytes.first, bytes.second);" % (uname,))
        else:
            self.o("\tvoid set%s(scalgoproto::BytesOut b) noexcept {" % (uname,))
            self.o("\t\tsetType_(%d);" % (idx,))
            self.o("\t\tsetObject_(getOffset_(b));")
            self.o("\t}")
            self.o(
                "\tscalgoproto::BytesOut add%s(const char * data, size_t size) noexcept {"
                % (uname,)
            )
            self.o("\t\tauto res = writer_.constructBytes(data, size);")
            self.o("\t\tset%s(res);" % (uname,))
            self.o("\t\treturn res;")
            self.o("\t}")
            self.o(
                "\tscalgoproto::BytesOut add%s(scalgoproto::Bytes bytes) noexcept {"
                % (uname,)
            )
            self.o("\t\treturn add%s(bytes.first, bytes.second);" % (uname,))
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
            "\t%sIn<%s> %s() const {"
            % (self.qualify(node.union), bs(node.inplace), lcamel(uname))
        )
        if node.optional:
            self.o("\t\tassert(has%s());" % (uname))
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
                "\t%sInplaceOut %s() const noexcept {"
                % (self.qualify(node.union), lcamel(uname))
            )
            self.o(
                "\t\treturn construct_<%sInplaceOut>(writer_, offset_ + %d, offset_ + SIZE);"
                % (self.qualify(node.union), node.offset)
            )
            self.o("\t}")
        else:
            self.o(
                "\t%sOut %s() const noexcept {"
                % (self.qualify(node.union), lcamel(uname))
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
        typeName = self.value(node.type_)
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
            "\tvoid copy_(%sIn<%s> i) {" % (union.name, "true" if inplace else "false")
        )
        self.o("\t\tswitch (i.type()) {")
        for node in union.members:
            assert node.type_ is not None
            if node.type_.type == TokenType.REMOVED:
                continue
            lname = lcamel(self.value(node.identifier))
            uname = ucamel(lname)
            c = "%sType::%s" % (union.name, lname)
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
                    self.o("\t\tcase %s: set%s(); break;" % (c, uname))
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
        self.o("enum class %sType : std::uint16_t {" % union.name)
        self.o("\tnone,")
        for member in union.members:
            if not isinstance(member, (Table, Value)):
                raise ICE()
            self.o("\t%s," % (self.value(member.identifier)))
        self.o("};")
        self.o("")
        self.output_doc(union)
        self.o("template <bool inplace>")
        self.o("class %sIn: public scalgoproto::UnionIn<inplace> {" % union.name)
        self.o("protected:")
        self.o("\tusing scalgoproto::UnionIn<inplace>::UnionIn;")
        self.o("public:")
        self.o("\tusing IN=%sIn;" % union.name)
        self.o("\tusing Type = %sType;" % union.name)
        self.o("\tType type() const noexcept {return (Type)this->type_;}")
        for member in union.members:
            assert member.type_ is not None
            if member.type_.type == TokenType.REMOVED:
                continue
            n = self.value(member.identifier)
            uname = ucamel(n)
            self.o(
                "\tbool is%s() const noexcept {return type() == Type::%s;}" % (uname, n)
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
            "template <bool inplace> struct MetaMagic<%sIn<inplace>> {using t=UnionTag;};"
            % self.qualify(union, True)
        )
        self.o("")
        for inplace, prefix in ((False, ""), (True, "Inplace")):
            self.switch_namespace(union.namespace)
            self.o(
                "class %s%sOut: public scalgoproto::%sUnionOut {"
                % (union.name, prefix, prefix)
            )
            self.o("\tfriend class Out;")
            self.o("protected:")
            self.o("\tusing scalgoproto::%sUnionOut::%sUnionOut;" % (prefix, prefix))
            self.o("public:")
            self.o("\tusing Type = %sType;" % union.name)
            self.o(
                "\tusing IN=%sIn<%s>;" % (union.name, "true" if inplace else "false")
            )
            self.o("\tType type() const noexcept {return (Type)this->getType_();}")
            for idx, member in enumerate(union.members):
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
                "template <> struct MetaMagic<%s%sOut> {using t=UnionTag;};"
                % (self.qualify(union, True), prefix)
            )
            self.o("")

    def generate_table_copy(self, table: Table) -> None:
        self.o("\t%sOut & copy_(%sIn i) {" % (table.name, table.name))
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
                            "\t\tif (i.has%s()) set%s(i.%s());" % (uname, uname, lname)
                        )
                    else:
                        self.o("\t\tset%s(i.%s());" % (uname, lname))
                elif node.table:
                    if node.table.empty:
                        self.o("\t\tif (i.has%s()) add%s();" % (uname, uname))
                    elif node.optional:
                        self.o(
                            "\t\tif (i.has%s()) add%s().copy_(i.%s());"
                            % (uname, uname, lname)
                        )
                    else:
                        self.o("\t\tadd%s().copy_(i.%s());" % (uname, lname))
                elif node.union and node.optional:
                    self.o(
                        "\t\tif (i.has%s()) %s().copy_(i.%s());" % (uname, lname, lname)
                    )
                elif node.union:
                    self.o("\t\t%s().copy_(i.%s());" % (lname, lname))
                elif node.type_.type == TokenType.TEXT and node.optional:
                    self.o("\t\tif (i.has%s()) add%s(i.%s());" % (uname, uname, lname))
                elif node.type_.type == TokenType.TEXT:
                    self.o(
                        "\t\tif (!i.%s().empty()) add%s(i.%s());"
                        % (lname, uname, lname)
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
        self.o("class %sIn: public scalgoproto::TableIn {" % table.name)
        self.o("\tfriend class scalgoproto::In;")
        self.o("\tfriend class scalgoproto::TableIn;")
        self.o("\tfriend class scalgoproto::Reader;")
        self.o(
            "\ttemplate <typename, typename> friend class scalgoproto::ListAccessHelp;"
        )
        self.o("protected:")
        self.o(
            "\t%sIn(const scalgoproto::Reader * reader, scalgoproto::Ptr p): scalgoproto::TableIn(reader, p) {}"
            % table.name
        )
        self.o("public:")
        self.o("\tstatic constexpr std::uint32_t MAGIC = 0x%08X;" % (table.magic))
        self.o("\tusing IN=%sIn;" % table.name)
        for node in table.members:
            self.generate_value_in(node)
        self.o("};")
        self.output_metamagic(
            "template <> struct MetaMagic<%sIn> {using t=TableTag;};"
            % self.qualify(table, True)
        )
        self.o("")
        assert table.default is not None
        self.switch_namespace(table.namespace)
        self.output_doc(table)
        self.o("class %sOut: public scalgoproto::TableOut {" % table.name)
        self.o("\tfriend class scalgoproto::Out;")
        self.o("\tfriend class scalgoproto::Writer;")
        self.o("public:")
        self.o("\tstatic constexpr std::uint64_t SIZE = %d;" % (len(table.default)))
        self.o("\tstatic constexpr std::uint32_t MAGIC = 0x%08X;" % (table.magic))
        self.o("\tusing IN=%sIn;" % (table.name))
        self.o("protected:")
        self.o(
            '\t%sOut(scalgoproto::Writer & writer, bool withHeader): scalgoproto::TableOut(writer, withHeader, MAGIC, "%s", SIZE) {}'
            % (table.name, cescape(table.default))
        )
        self.o(
            "\t%sOut(scalgoproto::Writer & writer, std::uint64_t offset): scalgoproto::TableOut(writer, offset) {}"
            % (table.name,)
        )
        self.o("public:")
        for node in table.members:
            self.generate_value_out(node, "%sOut" % table.name)
        self.generate_table_copy(table)
        self.o("};")
        self.output_metamagic(
            "template <> struct MetaMagic<%sOut> {using t=TableTag;};"
            % self.qualify(table, True)
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
        self.o("struct %s {" % node.name)
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
            self.o("\t%s %s;" % (typeName, self.value(v.identifier)))
        self.o("};")
        self.o("#pragma pack(pop)")
        self.output_metamagic(
            "template <> struct MetaMagic<%s> {using t=PodTag;};"
            % (self.qualify(node, True))
        )
        self.o()

    def generate_enum(self, node: Enum) -> None:
        self.switch_namespace(node.namespace)
        self.o("enum class %s: std::uint8_t {" % node.name)
        index = 0
        for ev in node.members:
            if ev.token is None:
                raise ICE()
            self.output_doc(ev, "\t")
            self.o("\t%s = %d," % (self.value(ev.token), index))
            index += 1
        self.o("};")
        self.output_metamagic(
            """template <> struct MetaMagic<%s> {using t=EnumTag;};
template <> struct EnumSize<%s> {static constexpr size_t size() noexcept {return %d;}};"""
            % (self.qualify(node, True), self.qualify(node, True), len(node.members))
        )
        self.o()

    def switch_namespace(self, namespace: Optional[str]) -> None:
        if namespace == self.current_namespace:
            return
        if self.current_namespace:
            self.o("} //namespace %s" % self.current_namespace)
        if namespace:
            self.o("namespace %s {" % namespace)
        self.current_namespace = namespace

    def qualify(
        self, node: typing.Union[Union, Table, Struct, Enum], full: bool = False
    ) -> str:
        if node.namespace and (full or node.namespace != self.current_namespace):
            return "%s::%s" % (node.namespace, node.name)
        else:
            if node.name is None:
                raise ICE()
            return node.name

    def switch_file(self, name: Optional[str], output: str):
        if self.current_file:
            assert self.out is not None
            self.switch_namespace(None)
            self.o("#endif //__SCALGOPROTO_%s__" % self.current_file)
            po = os.path.join(output, "%s.hh" % self.current_file)
            if not os.path.exists(po) or open(po, "r").read() != self.out.getvalue():
                open(po, "w").write(self.out.getvalue())
        if name:
            guard_name = name.replace("/", "_")
            self.out = io.StringIO()
            self.o("//THIS FILE IS GENERATED DO NOT EDIT")
            self.o("#ifndef __SCALGOPROTO_%s__" % guard_name)
            self.o("#define __SCALGOPROTO_%s__" % guard_name)
            self.o("#include <scalgoproto.hh>")
            self.current_file = name

    def generate(
        self, ast: List[AstNode], output: str, single: bool,
        expected: List[str],
        expected_only: bool,
        schema: str,
        *, dir_strip: int = None,
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

            for i in sorted(list(imports)):
                self.o('#include "%s.hh"' % i)

        def node_path(node: typing.Union[Struct, Enum, Table, Union]) -> str:
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

            if not single:
                if (
                    isinstance(node, Struct)
                    or isinstance(node, Enum)
                    or isinstance(node, Table)
                    or isinstance(node, Union)
                ):
                    name = node_path(node)
                    short_name = name.split("/")[-1]
                    found.add(short_name)
                    if expected_only and short_name not in expected:
                        ParseError(node.identifier, f"Unexpected output {short_name}", schema).describe(self.documents)
                        err = True
                    self.switch_file(name, output)
                    for use in sorted(node.uses, key=lambda u: u.name):
                        n = node_path(use)
                        lcp = os.path.commonprefix([name, os.path.dirname(n) + "/"])
                        dirs = name[len(lcp) :].count("/")
                        relpath = "../" * dirs + n[len(lcp) :]
                        self.o('#include "%s.hh"' % relpath)

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
            exit(1)

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
        g.generate(ast, args.output, args.single, dir_strip=args.dir_strip,
                expected=args.expected, expected_only=args.expected_only, schema=args.schema)
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
        action='append',
        help="Check that this table is defined",
        dest="expected",
        default=[],
    )
    cmd.add_argument(
        "--expected-only",
        action='store_true',
        help="Check that only --expect tables exist",
    )
    cmd.set_defaults(func=run)
