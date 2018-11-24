# -*- mode: python; tab-width: 4; indent-tabs-mode: t; python-indent-offset: 4; coding: utf-8 -*-
"""
Validate a schema
"""
from parser import Parser, ParseError
from annotate import annotate
from tokenize import TokenType, Token
from parser import Struct, AstNode, Value, Enum, Table, Union, Namespace
from typing import Set, Dict, List, TextIO, Tuple
from types import SimpleNamespace
import math
from util import ucamel, cescape, lcamel

class Generator:
	out: TextIO = None
	typeMap = {
		TokenType.INT8: "std::int8_t",
		TokenType.INT16: "std::int16_t",
		TokenType.INT32: "std::int32_t",
		TokenType.INT64: "std::int64_t",
		TokenType.UINT8: "std::uint8_t",
		TokenType.UINT16: "std::uint16_t",
		TokenType.UINT32: "std::uint32_t",
		TokenType.UINT64: "std::uint64_t",
		TokenType.FLOAT32: "float",
		TokenType.FLOAT64: "double",
	}


	def o(self, text=""):
		print(text, file=self.out)
	
	def __init__(self, data:str, out:TextIO) -> None:
		self.data = data
		self.out = out
		
	def value(self, t:Token) -> str:
		return self.data[t.index: t.index + t.length]


	def in_list_types(self, node: Value) -> Tuple[str,str]:
		typeName:str = None
		rawType:str = None
		if node.type_.type in self.typeMap:
			typeName = self.typeMap[node.type_.type]
			rawType = typeName
		elif node.type_.type == TokenType.BOOL:
			typeName = "bool"
			rawType = "char"
		elif node.type_.type == TokenType.IDENTIFIER:
			typeName = self.value(node.type_)
			if node.enum or node.struct:
				rawType = typeName
			if node.table:
				typeName = "%sIn"%typeName
		elif node.type_.type == TokenType.TEXT:
			typeName = "std::string_view"
		elif node.type_.type == TokenType.BYTES:
			typeName = "std::pair<const void *, size_t>"
		else:
			assert False
		return (typeName, rawType)

	def out_list_type(self, node: Value) -> str:
		typeName:str = None
		if node.type_.type in self.typeMap:
			typeName = self.typeMap[node.type_.type]
		elif node.type_.type == TokenType.BOOL:
			typeName = "bool"
		elif node.type_.type == TokenType.IDENTIFIER:
			typeName = self.value(node.type_)
			if node.table:
				typeName = "%sOut"%typeName
		elif node.type_.type == TokenType.TEXT:
			typeName = "scalgoproto::TextOut"
		elif node.type_.type == TokenType.BYTES:
			typeName = "scalgoproto::BytesOut"
		return typeName

	def output_doc(self, node: AstNode, indent:str="", prefix:List[str] = [], suffix:List[str] = []):
		if not node.docstring and not suffix and not prefix: return
		self.o("%s/**"%indent)
		for line in prefix:
			self.o("%s * %s"%(indent, line))
		if prefix and (node.docstring or suffix):
			self.o("%s *"%indent)
		if node.docstring:
			for line in node.docstring:
				self.o("%s * %s"%(indent, line))
		if node.docstring and suffix:
			self.o("%s *"%indent)
		for line in suffix:
			self.o("%s * %s"%(indent, line))
		self.o("%s */"%indent)
	
	def generate_value_in(self, node:Value) -> None:
		n = self.value(node.identifier)
		uname = ucamel(n)
		typeName = self.value(node.type_)
		if node.list_:
			typeName, rawType = self.in_list_types(node)
			self.o("\tbool has%s() const noexcept {"%(uname))
			self.o("\t\treturn getInner_<std::uint32_t, %d>(0) != 0;"%(node.offset))
			self.o("\t}")
			self.o("\t")
			self.output_doc(node, "\t")
			self.o("\tscalgoproto::ListIn<%s> get%s() const {"%(typeName, uname))
			self.o("\t\tassert(has%s());"%uname)
			if node.inplace: self.o("\t\treturn getVLList_<%s, %d>();"%(typeName, node.offset))
			else: self.o("\t\treturn getList_<%s, %d>();"%(typeName, node.offset))
			self.o("\t}")
			if rawType:
				self.o("\t")
				self.output_doc(node, "\t", [], ["\\note accessing this is undefined behaivour"])
				self.o("\tstd::pair<const %s *, size_t> get%sRaw() const {"%(rawType, uname))
				self.o("\t\tassert(has%s());"%uname)
				if node.inplace: self.o("\t\treturn getVLListRaw_<%s, %d>();"%(rawType, node.offset))
				else: self.o("\t\treturn getListRaw_<%s, %d>();"%(rawType, node.offset))
				self.o("\t}")
		elif node.type_.type in self.typeMap:
			assert not node.inplace
			typeName = self.typeMap[node.type_.type]
			if node.optional:
				self.o("\tbool has%s() const noexcept {"%( uname))
				if node.type_.type in (TokenType.FLOAT32, TokenType.FLOAT64):
					self.o("\t\treturn !std::isnan(getInner_<%s, %s>(std::numeric_limits<%s>::quiet_NaN()));"%(typeName, node.offset, typeName))
				else:
					self.o("\t\treturn getBit_<%d, %s, 0>();"%(node.has_offset, node.has_bit))
				self.o("\t}")
			self.o("\t")
			self.output_doc(node, "\t")
			self.o("\t%s get%s() const noexcept {"%(typeName, uname))
			if node.optional:
				self.o("\t\tassert(has%s());"%uname)
			self.o("\t\treturn getInner_<%s, %d>(%s);"%(typeName, node.offset, node.parsed_value if not math.isnan(node.parsed_value) else "NAN"))
			self.o("\t}")
		elif node.type_.type == TokenType.BOOL:
			assert not node.inplace
			if node.optional:
				self.o("\tbool has%s() const noexcept {"%( uname))
				self.o("\t\treturn getBit_<%d, %s, 0>();"%(node.has_offset, node.has_bit))
				self.o("\t}")
			self.o("\t")
			self.output_doc(node, "\t")
			self.o("\tbool get%s() const noexcept {"%(uname))
			if node.optional:
				self.o("\t\tassert(has%s());"%uname)
			self.o("\t\treturn getBit_<%d, %s, 0>();"%(node.offset, node.bit))
			self.o("\t}")
		elif node.enum:
			assert not node.inplace
			self.o("\tbool has%s() const noexcept {"%(uname))
			self.o("\t\treturn getInner_<std::uint8_t, %d>(%d) != 255;"%(node.offset, node.parsed_value))
			self.o("\t}")
			self.o("\t")
			self.output_doc(node, "\t")
			self.o("\t%s get%s() const noexcept {"%(typeName, uname))
			self.o("\t\tassert(has%s());"%uname)
			self.o("\t\treturn (%s)getInner_<std::uint8_t, %d>(%s);"%(typeName, node.offset, node.parsed_value))
			self.o("\t}")
		elif node.struct:
			assert not node.inplace
			if node.optional:
				self.o("\tbool has%s() const noexcept {"%(uname))
				self.o("\t\treturn getBit_<%d, %s, 0>();"%(node.has_offset, node.has_bit))
				self.o("\t}")
			self.o("\t")
			self.output_doc(node, "\t")
			self.o("\t%s get%s() const noexcept {"%(typeName, uname))
			if node.optional:
				self.o("\t\tassert(has%s());"%uname)
			self.o("\t\treturn getInner_<%s, %d>();"%( typeName, node.offset))
			self.o("\t}")
		elif node.table:
			assert not node.inplace
			self.o("\tbool has%s() const noexcept {"%(uname))
			self.o("\t\treturn getInner_<std::uint32_t, %d>(0) != 0;"%(node.offset))
			self.o("\t}")
			self.o("\t")
			self.output_doc(node, "\t")
			self.o("\t%sIn get%s() const {"%(typeName, uname))
			self.o("\t\tassert(has%s());"%uname)
			self.o("\t\treturn getTable_<%sIn, %d>();"%(typeName, node.offset))
			self.o("\t}")
		elif node.union:
			assert node.inplace
			self.o("\tenum Type {")
			self.o("\t\tNONE,")
			for member in node.union.members:
				assert isinstance(member, (Table, Value))
				self.o("\t\t%s,"%self.value(member.identifier).upper())
			self.o("\t};")
			self.o("\t")
			self.output_doc(node, "\t")
			self.o("\tType getType() const noexcept {")
			self.o("\t\treturn (Type)getInner_<std::uint16_t, %d>();"%node.offset)
			self.o("\t}")
			self.o("\tbool hasType() const noexcept {return getType() != NONE;}")
			for member in node.union.members:
				assert isinstance(member, (Table, Value))
				n = self.value(member.identifier)
				uname = n[0].upper() + n[1:]
				tbl = member.table
				self.o("\tbool is%s() const noexcept {return getType() == %s;}"%(uname, n.upper()))
				if tbl.members:
					self.o("\t")
					self.output_doc(node, "\t")
					self.o("\t%sIn get%s() const noexcept {"%(tbl.name, uname))
					self.o("\t\tassert(is%s());"%(uname))
					self.o("\t\treturn getVLTable_<%sIn, %d>();"%(tbl.name, node.offset+2))
					self.o("\t}")
		elif node.type_.type == TokenType.TEXT:
			self.o("\tbool has%s() const noexcept {"%(uname))
			self.o("\t\treturn getInner_<std::uint32_t, %d>(0) != 0;"%(node.offset))
			self.o("\t}")
			self.o("\t")
			self.output_doc(node, "\t")
			self.o("\tstd::string_view get%s() {"%(uname))
			if node.inplace: self.o("\t\treturn getVLText_<%d>();"%(node.offset))
			else: self.o("\t\treturn getText_<%d>();"%(node.offset))
			self.o("\t}")
		elif node.type_.type == TokenType.BYTES:
			self.o("\tbool has%s() const noexcept {"%(uname))
			self.o("\t\treturn getInner_<std::uint32_t, %d>(0) != 0;"%(node.offset))
			self.o("\t}")
			self.o("\t")
			self.output_doc(node, "\t")
			self.o("\tstd::pair<const void*, size_t> get%s()  {"%(uname))
			if node.inplace: self.o("\t\treturn getVLBytes_<%d>();"%(node.offset))
			else: self.o("\t\treturn getBytes_<%d>();"%(node.offset))
			self.o("\t}")
		else:
			assert False

	def generate_value_out(self, node:Value) -> None:
		n = self.value(node.identifier)
		uname = ucamel(n)
		self.output_doc(node, "\t")
		typeName = self.value(node.type_)
		if node.list_:
			typeName = self.out_list_type(node)
			if node.inplace:
				self.o("\tscalgoproto::ListOut<%s> add%s(size_t size) noexcept {"%(typeName, uname))
				self.o("\t\treturn addVLList_<%d, %s>(size);"%(node.offset, typeName))
			else:
				self.o("\tvoid add%s(scalgoproto::ListOut<%s> value) noexcept {"%(uname, typeName))
				self.o("\t\tsetList_<%s, %d>(value);"%(typeName, node.offset))
			self.o("\t}")
		elif node.type_.type in self.typeMap:
			assert not node.inplace
			typeName = self.typeMap[node.type_.type]
			self.o("\tvoid add%s(%s value) noexcept {"%(uname, typeName))
			if node.optional and node.type_.type not in (TokenType.FLOAT32, TokenType.FLOAT64):
				self.o("\t\tsetBit_<%d, %d>();"%(node.has_offset, node.has_bit))
			self.o("\t\tsetInner_<%s, %d>(value);"%(typeName, node.offset))
			self.o("\t}")
		elif node.type_.type == TokenType.BOOL:
			assert not node.inplace
			self.o("\tvoid add%s(bool value) noexcept {"%(uname))
			if node.optional:
				self.o("\t\tsetBit_<%d, %d>();"%(node.has_offset, node.has_bit))
			self.o("\t\tif(value) setBit_<%d, %d>(); else unsetBit_<%d, %d>();"%(node.offset, node.bit, node.offset, node.bit))
			self.o("\t}")
		elif node.enum:
			assert not node.inplace
			self.o("\tvoid add%s(%s value) noexcept {"%(uname, typeName))
			self.o("\t\tsetInner_<%s, %d>(value);"%(typeName, node.offset))
			self.o("\t}")
		elif node.struct:
			assert not node.inplace
			self.o("\tvoid add%s(const %s & value) noexcept {"%(uname, typeName))
			if node.optional:
				self.o("\t\tsetBit_<%d, %d>();"%(node.has_offset, node.has_bit))
			self.o("\t\tsetInner_<%s, %d>(value);"%(typeName, node.offset))
			self.o("\t}")
		elif node.table:
			assert not node.inplace
			self.o("\tvoid add%s(%sOut value) noexcept {"%(uname, typeName))
			self.o("\t\tsetTable_<%sOut, %d>(value);"%(typeName, node.offset))
			self.o("\t}")
		elif node.union:
			self.o("\tbool has%s() const noexcept {"%(uname))
			self.o("\t\treturn getInner_<std::uint16_t, %d>() != 0;"%(node.offset))
			self.o("\t}")
			idx = 1
			for member in node.union.members:
				n = self.value(member.identifier)
				uuname = n[0].upper() + n[1:]
				tbl = member.table
				self.output_doc(member, "\t")
				if tbl.members:
					self.o("\t%sOut %sAdd%s() noexcept {"%(tbl.name, lcamel(uname), uuname))
					self.o("\t\tassert(!has%s());"%(uname))
					self.o("\t\tsetInner_<std::uint16_t, %d>(%d);"%(node.offset, idx))
					self.o("\t\tsetInner_<std::uint32_t, %d>(%d);"%(node.offset+2, len(tbl.default)))
					self.o("\t\treturn constructUnionMember_<%sOut>();"%tbl.name)
					self.o("\t}")
				else:
					self.o("\tvoid %sAdd%s() noexcept {"%(lcamel(uname), uuname))
					self.o("\t\tassert(!has%s());"%(uname))
					self.o("\t\tsetInner_<std::uint16_t, %d>(%d);"%(node.offset, idx))
					self.o("\t\tsetInner_<std::uint32_t, %d>(%d);"%(node.offset+2, 0))
					self.o("\t}")
				idx += 1
		elif node.type_.type == TokenType.TEXT:
			if node.inplace:
				self.o("\tvoid add%s(std::string_view text) noexcept {"%(uname))
				self.o("\t\taddVLText_<%d>(text);"%(node.offset))
			else:
				self.o("\tvoid add%s(scalgoproto::TextOut t) noexcept {"%(uname))
				self.o("\tsetText_<%d>(t);"%(node.offset))
			self.o("\t}")
		elif node.type_.type == TokenType.BYTES:
			if node.inplace:
				self.o("\tvoid add%s(const char * data, size_t size) noexcept {"%(uname))
				self.o("\t\taddVLBytes_<%d>(data, size);"%(node.offset))
			else:
				self.o("\tvoid add%s(scalgoproto::BytesOut b) noexcept {"%(uname))
				self.o("\tsetBytes_<%d>(b);"%(node.offset))
			self.o("\t}")
		else:
			assert False

	def visit_union(self, union:Union) -> None:
		for value in union.members:
			if value.direct_table:
				self.generate_table(value.direct_table)
			if value.direct_union:
				self.visit_union(value.direct_union)

	def generate_table(self, table:Table) -> None:
		# Recursively generate direct contained members
		for value in table.members:
			if value.direct_table:
				self.generate_table(value.direct_table)
			if value.direct_union:
				self.visit_union(value.direct_union)

		self.output_doc(table)
		self.o("class %sIn: public scalgoproto::In {"%table.name)
		self.o("\tfriend class scalgoproto::In;")
		self.o("\tfriend class scalgoproto::Reader;")
		self.o("\ttemplate <typename, typename> friend class scalgoproto::ListAccessHelp;")
		self.o("protected:")
		self.o("\t%sIn(const scalgoproto::Reader & reader, const char * start, std::uint32_t size): scalgoproto::In(reader, start, size) {}"%table.name)
		self.o("\tstatic uint32_t readSize_(const scalgoproto::Reader & reader, std::uint32_t offset) { return In::readObjectSize_<0x%08X>(reader, offset); }"%(table.magic))
		self.o("public:")
		for node in table.members:
			self.generate_value_in(node)
		self.o("};")
		self.o("namespace scalgoproto {template <> struct MetaMagic<%sIn> {using t=TableTag;};}"%table.name)
		self.o("")
		self.output_doc(table)
		self.o("class %sOut: public scalgoproto::Out {"%table.name)
		self.o("\tfriend class scalgoproto::Out;")
		self.o("\tfriend class scalgoproto::Writer;")
		self.o("protected:")
		self.o("\t%sOut(scalgoproto::Writer & writer, bool withHeader): scalgoproto::Out(writer, withHeader, 0x%08X, \"%s\", %d) {}"%(table.name, table.magic, cescape(table.default), len(table.default)))
		self.o("public:")
		for node in table.members:
			self.generate_value_out(node)
		self.o("};")
		self.o("namespace scalgoproto {template <> struct MetaMagic<%sOut> {using t=TableTag;};}"%table.name)
		self.o("")
	
	def generate(self, ast: List[AstNode]) -> None:
		for node in ast:
			if isinstance(node, Struct):
				name = self.value(node.identifier)
				self.o("#pragma pack(push, 1)")
				self.o("struct %s {"%name)
				for v in node.members:
					assert isinstance(v, Value)
					typeName = ""
					if v.type_.type == TokenType.UINT8: typeName = "std::uint8_t"
					elif v.type_.type == TokenType.UINT16: typeName = "std::uint16_t"
					elif v.type_.type == TokenType.UINT32: typeName = "std::uint32_t"
					elif v.type_.type == TokenType.UINT64: typeName = "std::uint64_t"
					elif v.type_.type == TokenType.INT8: typeName = "std::int8_t"
					elif v.type_.type == TokenType.INT16: typeName = "std::int16_t"
					elif v.type_.type == TokenType.INT32: typeName = "std::int32_t"
					elif v.type_.type == TokenType.INT64: typeName = "std::int64_t"
					elif v.type_.type == TokenType.FLOAT32: typeName = "float"
					elif v.type_.type == TokenType.FLOAT64: typeName = "double"
					elif v.type_.type == TokenType.BOOL: typeName = "bool"
					elif v.type_.type == TokenType.IDENTIFIER: typeName = self.value(v.type_)
					else: assert(False)
					self.o("\t%s %s;"%(typeName, self.value(v.identifier)))
				self.o("};")
				self.o("#pragma pack(pop)")
				self.o("namespace scalgoproto {template <> struct MetaMagic<%s> {using t=PodTag;};}"%name)
				self.o()
			elif isinstance(node, Enum):
				name = self.value(node.identifier)
				self.o("enum class %s: std::uint8_t {"%name)
				index = 0
				for ev in node.members:
					self.output_doc(ev, "\t")
					self.o("\t%s = %d,"%(self.value(ev.token), index))
					index += 1
				self.o("};")
				self.o("namespace scalgoproto {template <> struct MetaMagic<%s> {using t=EnumTag;};}"%name)
				self.o()
			elif isinstance(node, Table):
				name = self.value(node.identifier)
				self.generate_table(node)
			elif isinstance(node, Union):
				self.visit_union(node)
			elif isinstance(node, Namespace):
				# TODO handle namespace
				pass
			else:
				assert False

def run(args) -> int:
	data = open(args.schema, "r").read()
	p = Parser(data)
	out = open(args.output, "w")
	try:
		ast = p.parseDocument()
		if not annotate(data, ast):
			print("Invalid schema is valid")
			return 1
		g = Generator(data, out)
		print("#include \"scalgoproto.hh\"", file=out)
		g.generate(ast)
		return 0
	except ParseError as err:
		err.describe(data)
	return 1

def setup(subparsers) -> None:
	cmd = subparsers.add_parser('cpp', help='Generate cpp code for windows')
	cmd.add_argument('schema', help='schema to generate things from')
	cmd.add_argument('output', help="where do we store the output")
	cmd.set_defaults(func=run)


