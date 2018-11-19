# -*- mode: python; tab-width: 4; indent-tabs-mode: t; python-indent-offset: 4; coding: utf-8 -*-
"""
Validate a schema
"""
from parser import Parser, ParseError
from annotate import annotate

from parser import TokenType, NodeType, Token, Struct, AstNode, Value, Enum, Table, VLUnion, VLList, VLBytes, VLText
from typing import Set, Dict, List, TextIO, Tuple, Union
from types import SimpleNamespace
import math

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


	def listTypes(self, node: Union[Value, VLList]) -> Tuple[str,str]:
		typeName:str = None
		rawType:str = None
		if node.type.type in self.typeMap:
			typeName = self.typeMap[node.type.type]
			rawType = typeName
		elif node.type.type == TokenType.BOOL:
			typeName = "bool"
			rawType = "char"
		elif node.type.type == TokenType.IDENTIFIER:
			typeName = self.value(node.type)
			if node.enum or node.struct:
				rawType = typeName
			if node.table:
				typeName = "%sIn"%typeName
		elif node.type.type == TokenType.TEXT:
			typeName = "std::string_view"
		elif node.type.type == TokenType.BYTES:
			typeName = "std::pair<const void *, size_t>"
		else:
			assert False
		return (typeName, rawType)

	def outListType(self, node: Union[Value, VLList]) -> str:
		typeName:str = None
		if node.type.type in self.typeMap:
			typeName = self.typeMap[node.type.type]
		elif node.type.type == TokenType.BOOL:
			typeName = "bool"
		elif node.type.type == TokenType.IDENTIFIER:
			typeName = self.value(node.type)
			if node.table:
				typeName = "%sOut"%typeName
		elif node.type.type == TokenType.TEXT:
			typeName = "scalgoproto::TextOut"
		elif node.type.type == TokenType.BYTES:
			typeName = "scalgoproto::BytesOut"
		return typeName

	def outputDoc(self, node: AstNode, indent:str="", prefix:List[str] = [], suffix:List[str] = []):
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
	
	def generateTable(self, table:Table ) -> None:
		for node in table.values:
			if node.t == NodeType.VLUNION:
				assert isinstance(node, VLUnion)
				for member in node.members:
					if member.t == NodeType.TABLE:
						assert isinstance(member, Table)
						if member.values:
							self.generateTable(member)
		self.outputDoc(table)
		self.o("class %sIn: public scalgoproto::In {"%table.name)
		self.o("\tfriend class scalgoproto::In;")
		self.o("\tfriend class scalgoproto::Reader;")
		self.o("\ttemplate <typename, typename> friend class scalgoproto::ListAccessHelp;")
		self.o("protected:")
		self.o("\t%sIn(const scalgoproto::Reader & reader, const char * start, std::uint32_t size): scalgoproto::In(reader, start, size) {}"%table.name)
		self.o("\tstatic uint32_t readSize_(const scalgoproto::Reader & reader, std::uint32_t offset) { return In::readObjectSize_<0x%08X>(reader, offset); }"%(table.magic))
		self.o("public:")
		for node in table.values:
			if node.t == NodeType.VALUE:
				assert isinstance(node, Value)
				n = self.value(node.identifier)
				uname = n[0].upper() + n[1:]
				if node.list:
					typeName, rawType = self.listTypes(node)
					self.o("\tbool has%s() const noexcept {"%(uname))
					self.o("\t\treturn getInner_<std::uint32_t, %d>(0) != 0;"%(node.offset))
					self.o("\t}")
					self.o("\t")
					self.outputDoc(node, "\t")
					self.o("\tscalgoproto::ListIn<%s> get%s() const {"%(typeName, uname))
					self.o("\t\tassert(has%s());"%uname)
					self.o("\t\treturn getList_<%s, %d>();"%(typeName, node.offset))
					self.o("\t}")
					if rawType:
						self.o("\t")
						self.outputDoc(node, "\t", [], ["\\note accessing this is undefined behaivour"])
						self.o("\tstd::pair<const %s *, size_t> get%sRaw() const {"%(rawType, uname))
						self.o("\t\tassert(has%s());"%uname)
						self.o("\t\treturn getListRaw_<%s, %d>();"%(rawType, node.offset))
						self.o("\t}")
				elif node.type.type in self.typeMap:
					typeName = self.typeMap[node.type.type]
					if node.optional:
						self.o("\tbool has%s() const noexcept {"%( uname))
						if node.type.type in (TokenType.FLOAT32, TokenType.FLOAT64):
							self.o("\t\treturn !std::isnan(getInner_<%s, %s>(std::numeric_limits<%s>::quiet_NaN()));"%(typeName, node.offset, typeName))
						else: 
							self.o("\t\treturn getBit_<%d, %s, 0>();"%(node.hasOffset, node.hasBit))
						self.o("\t}")
					self.o("\t")
					self.outputDoc(node, "\t")
					self.o("\t%s get%s() const noexcept {"%(typeName, uname))
					if node.optional:
						self.o("\t\tassert(has%s());"%uname)
					self.o("\t\treturn getInner_<%s, %d>(%s);"%(typeName, node.offset, node.parsedValue if not math.isnan(node.parsedValue) else "NAN"))
					self.o("\t}")
				elif node.type.type == TokenType.BOOL:
					if node.optional:
						self.o("\tbool has%s() const noexcept {"%( uname))
						self.o("\t\treturn getBit_<%d, %s, 0>();"%(node.hasOffset, node.hasBit))
						self.o("\t}")
					self.o("\t")
					self.outputDoc(node, "\t")
					self.o("\tbool get%s() const noexcept {"%(uname))
					if node.optional:
						self.o("\t\tassert(has%s());"%uname)
					self.o("\t\treturn getBit_<%d, %s, 0>();"%(node.offset, node.bit))
					self.o("\t}")
				elif node.type.type == TokenType.IDENTIFIER:
					typeName = self.value(node.type)
					if node.enum:
						self.o("\tbool has%s() const noexcept {"%(uname))
						self.o("\t\treturn getInner_<std::uint8_t, %d>(%d) != 255;"%(node.offset, node.parsedValue))
						self.o("\t}")
						self.o("\t")
						self.outputDoc(node, "\t")
						self.o("\t%s get%s() const noexcept {"%(typeName, uname))
						self.o("\t\tassert(has%s());"%uname)
						self.o("\t\treturn (%s)getInner_<std::uint8_t, %d>(%s);"%(typeName, node.offset, node.parsedValue))
						self.o("\t}")
					elif node.struct:
						if node.optional:
							self.o("\tbool has%s() const noexcept {"%(uname))
							self.o("\t\treturn getBit_<%d, %s, 0>();"%(node.hasOffset, node.hasBit))
							self.o("\t}")
						self.o("\t")
						self.outputDoc(node, "\t")
						self.o("\t%s get%s() const noexcept {"%(typeName, uname))
						if node.optional:
							self.o("\t\tassert(has%s());"%uname)
						self.o("\t\treturn getInner_<%s, %d>();"%( typeName, node.offset))
						self.o("\t}")
					elif node.table:
						self.o("\tbool has%s() const noexcept {"%(uname))
						self.o("\t\treturn getInner_<std::uint32_t, %d>(0) != 0;"%(node.offset))
						self.o("\t}")
						self.o("\t")
						self.outputDoc(node, "\t")
						self.o("\t%sIn get%s() const {"%(typeName, uname))
						self.o("\t\tassert(has%s());"%uname)
						self.o("\t\treturn getTable_<%sIn, %d>();"%(typeName, node.offset))
						self.o("\t}")
					else:
						assert False
				elif node.type.type == TokenType.TEXT:
					self.o("\tbool has%s() const noexcept {"%(uname))
					self.o("\t\treturn getInner_<std::uint32_t, %d>(0) != 0;"%(node.offset))
					self.o("\t}")
					self.o("\t")
					self.outputDoc(node, "\t")
					self.o("\tstd::string_view get%s() {"%(uname))
					self.o("\t\treturn getText_<%d>();"%(node.offset))
					self.o("\t}")
				elif node.type.type == TokenType.BYTES:
					self.o("\tbool has%s() const noexcept {"%(uname))
					self.o("\t\treturn getInner_<std::uint32_t, %d>(0) != 0;"%(node.offset))
					self.o("\t}")
					self.o("\t")
					self.outputDoc(node, "\t")
					self.o("\tstd::pair<const void*, size_t> get%s()  {"%(uname))
					self.o("\t\treturn getBytes_<%d>();"%(node.offset))
					self.o("\t}")
				else:
					assert False
			elif node.t == NodeType.VLUNION:
				assert isinstance(node, VLUnion)
				self.o("\tenum Type {")
				self.o("\t\tNONE,")
				for member in node.members:
					assert isinstance(member, (Table, Value))
					self.o("\t\t%s,"%self.value(member.identifier).upper())
				self.o("\t};")
				self.o("\t")
				self.outputDoc(node, "\t")
				self.o("\tType getType() const noexcept {")
				self.o("\t\treturn (Type)getInner_<std::uint16_t, %d>();"%node.offset)
				self.o("\t}")
				self.o("\tbool hasType() const noexcept {return getType() != NONE;}")
				for member in node.members:
					assert isinstance(member, (Table, Value))
					n = self.value(member.identifier)
					uname = n[0].upper() + n[1:]
					tbl = member.table if isinstance(member, Value) else member
					self.o("\tbool is%s() const noexcept {return getType() == %s;}"%(uname, n.upper()))
					if tbl.values:
						self.o("\t")
						self.outputDoc(node, "\t")
						self.o("\t%sIn get%s() const noexcept {"%(tbl.name, uname))
						self.o("\t\tassert(is%s());"%(uname))
						self.o("\t\treturn getVLTable_<%sIn, %d>();"%(tbl.name, node.offset+2))
						self.o("\t}")
			elif node.t == NodeType.VLBYTES:
				assert isinstance(node, VLBytes)
				self.o("\tbool hasBytes() const noexcept {")
				self.o("\t\treturn getInner_<std::uint32_t, %d>() != 0;"%(node.offset))
				self.o("\t}")
				self.o("\t")
				self.outputDoc(node, "\t")
				self.o("\tstd::pair<const void *, size_t> getBytes() const noexcept {")
				self.o("\t\tassert(hasBytes());")
				self.o("\t\treturn getVLBytes_<%d>();"%(node.offset))
				self.o("\t}")
			elif node.t == NodeType.VLLIST:
				assert isinstance(node, VLList)
				typeName, rawType = self.listTypes(node)
				self.o("\tbool hasList() const noexcept {")
				self.o("\t\treturn getInner_<std::uint32_t, %d>() != 0;"%(node.offset))
				self.o("\t}")
				self.o("\t")
				self.outputDoc(node, "\t")
				self.o("\tscalgoproto::ListIn<%s> getList() const {"%(typeName))
				self.o("\t\treturn getVLList_<%s, %d>();"%(typeName, node.offset))
				self.o("\t}")
				if rawType:
					self.o("\t")
					self.outputDoc(node, "\t", [], ["\\note accessing this is undefined behaivour"])
					self.o("\tstd::pair<const %s *, size_t> getListRaw() const {"%(rawType))
					self.o("\t\tassert(hasList());")
					self.o("\t\treturn getVLListRaw_<%s, %d>();"%(rawType, node.offset))
					self.o("\t}")
			elif node.t == NodeType.VLTEXT:
				assert isinstance(node,VLText)
				self.o("\tbool hasText() const noexcept {")
				self.o("\t\treturn getInner_<std::uint32_t, %d>() != 0;"%(node.offset))
				self.o("\t}")
				self.o("\t")
				self.outputDoc(node, "\t")
				self.o("\tstd::string_view getText() const noexcept {")
				self.o("\t\tassert(hasText());")
				self.o("\t\treturn getVLText_<%d>();"%(node.offset))
				self.o("\t}")
			else:
				assert(False)
		self.o("};")
		self.o("namespace scalgoproto {template <> struct MetaMagic<%sIn> {using t=TableTag;};}"%table.name)
		self.o("")
		self.outputDoc(table)
		self.o("class %sOut: public scalgoproto::Out {"%table.name)
		self.o("\tfriend class scalgoproto::Out;")
		self.o("\tfriend class scalgoproto::Writer;")
		self.o("protected:")
		default = []
		cmap = {
			0: "\\0",
			34: "\"",
			9: "\\t",
			10: "\\n",
			13: "\\r"
		}
		for c in table.default:
			if c in cmap:
				default.append(cmap[c])
			elif 32 <= c <= 125:
				default.append(chr(c))
			else:
				default.append("\\x%02x"%c)
				
		self.o("\t%sOut(scalgoproto::Writer & writer, bool withHeader): scalgoproto::Out(writer, withHeader, 0x%08X, \"%s\", %d) {}"%(table.name, table.magic, "".join(default), len(table.default)))
		self.o("public:")
		for node in table.values:
			if node.t == NodeType.VALUE:
				assert isinstance(node, Value)
				n = self.value(node.identifier)
				uname = n[0].upper() + n[1:]
				self.outputDoc(node, "\t")
				if node.list:
					typeName = self.outListType(node)
					self.o("\tvoid add%s(scalgoproto::ListOut<%s> value) noexcept {"%(uname, typeName))
					self.o("\t\tsetList_<%s, %d>(value);"%(typeName, node.offset))
					self.o("\t}")
				elif node.type.type in self.typeMap:
					typeName = self.typeMap[node.type.type]
					self.o("\tvoid add%s(%s value) noexcept {"%(uname, typeName))
					if node.optional and node.type.type not in (TokenType.FLOAT32, TokenType.FLOAT64):
						self.o("\t\tsetBit_<%d, %d>();"%(node.hasOffset, node.hasBit))
					self.o("\t\tsetInner_<%s, %d>(value);"%(typeName, node.offset))
					self.o("\t}")
				elif node.type.type == TokenType.BOOL:
					self.o("\tvoid add%s(bool value) noexcept {"%(uname))
					if node.optional:
						self.o("\t\tsetBit_<%d, %d>();"%(node.hasOffset, node.hasBit))
					self.o("\t\tif(value) setBit_<%d, %d>(); else unsetBit_<%d, %d>();"%(node.offset, node.bit, node.offset, node.bit))
					self.o("\t}")
				elif node.type.type == TokenType.IDENTIFIER:
					typeName = self.value(node.type)
					if node.enum:
						self.o("\tvoid add%s(%s value) noexcept {"%(uname, typeName))
						self.o("\t\tsetInner_<%s, %d>(value);"%(typeName, node.offset))
						self.o("\t}")
					elif node.struct:
						self.o("\tvoid add%s(const %s & value) noexcept {"%(uname, typeName))
						if node.optional:
							self.o("\t\tsetBit_<%d, %d>();"%(node.hasOffset, node.hasBit))
						self.o("\t\tsetInner_<%s, %d>(value);"%(typeName, node.offset))
						self.o("\t}")
					elif node.table:
						self.o("\tvoid add%s(%sOut value) noexcept {"%(uname, typeName))
						self.o("\t\tsetTable_<%sOut, %d>(value);"%(typeName, node.offset))
						self.o("\t}")
						pass
					else:
						assert False
				elif node.type.type == TokenType.TEXT:
					self.o("\tvoid add%s(scalgoproto::TextOut t) noexcept {"%(uname))
					self.o("\tsetText_<%d>(t);"%(node.offset))
					self.o("\t}")
				elif node.type.type == TokenType.BYTES:
					self.o("\tvoid add%s(scalgoproto::BytesOut b) noexcept {"%(uname))
					self.o("\tsetBytes_<%d>(b);"%(node.offset))
					self.o("\t}")
				else:
					assert False
			elif node.t == NodeType.VLUNION:
				assert isinstance(node, VLUnion)
				self.outputDoc(node, "\t")
				self.o("\tbool hasType() const noexcept {")
				self.o("\t\treturn getInner_<std::uint16_t, %d>() != 0;"%(node.offset))
				self.o("\t}")
				idx = 1
				for member in node.members:
					assert isinstance(member, (Table, Value))
					n = self.value(member.identifier)
					uname = n[0].upper() + n[1:]
					tbl = member.table if isinstance(member, Value) else member
					self.outputDoc(member, "\t")
					if tbl.values:
						self.o("\t%sOut add%s() noexcept {"%(tbl.name, uname))
						self.o("\t\tassert(!hasType());")
						self.o("\t\tsetInner_<std::uint16_t, %d>(%d);"%(node.offset, idx))
						self.o("\t\tsetInner_<std::uint32_t, %d>(%d);"%(node.offset+2, len(tbl.default)))
						self.o("\t\treturn constructUnionMember_<%sOut>();"%tbl.name)
						self.o("\t}")
					else:
						self.o("\tvoid add%s() noexcept {"%(uname))
						self.o("\t\tassert(!hasType());")
						self.o("\t\tsetInner_<std::uint16_t, %d>(%d);"%(node.offset, idx))
						self.o("\t\tsetInner_<std::uint32_t, %d>(%d);"%(node.offset+2, 0))
						self.o("\t}")
					idx += 1
			elif node.t == NodeType.VLBYTES:
				assert isinstance(node, VLBytes)
				self.outputDoc(node, "\t")
				self.o("\tvoid addBytes(const char * data, size_t size) noexcept {")
				self.o("\t\taddVLBytes_<%d>(data, size);"%(node.offset))
				self.o("\t}")
			elif node.t == NodeType.VLLIST:
				assert isinstance(node, VLList)
				typeName = self.outListType(node)
				self.outputDoc(node, "\t")
				self.o("\tscalgoproto::ListOut<%s> addList(size_t size) noexcept {"%(typeName))
				self.o("\t\treturn addVLList_<%d, %s>(size);"%(node.offset, typeName))
				self.o("\t}")
			elif node.t == NodeType.VLTEXT:
				assert isinstance(node,VLText)
				self.outputDoc(node, "\t")
				self.o("\tvoid addText(std::string_view text) noexcept {")
				self.o("\t\taddVLText_<%d>(text);"%(node.offset))
				self.o("\t}")
			else:
				assert(False)
		self.o("};")
		self.o("namespace scalgoproto {template <> struct MetaMagic<%sOut> {using t=TableTag;};}"%table.name)
		self.o("")
	
	def generate(self, ast: List[AstNode]) -> None:
		for node in ast:
			if node.t == NodeType.STRUCT:
				assert isinstance(node, Struct)
				name = self.value(node.identifier)
				self.o("#pragma pack(push, 1)")
				self.o("struct %s {"%name)
				for v in node.values:
					assert isinstance(v, Value)
					typeName = ""
					if v.type.type == TokenType.UINT8: typeName = "std::uint8_t"
					elif v.type.type == TokenType.UINT16: typeName = "std::uint16_t"
					elif v.type.type == TokenType.UINT32: typeName = "std::uint32_t"
					elif v.type.type == TokenType.UINT64: typeName = "std::uint64_t"
					elif v.type.type == TokenType.INT8: typeName = "std::int8_t"
					elif v.type.type == TokenType.INT16: typeName = "std::int16_t"
					elif v.type.type == TokenType.INT32: typeName = "std::int32_t"
					elif v.type.type == TokenType.INT64: typeName = "std::int64_t"
					elif v.type.type == TokenType.FLOAT32: typeName = "float"
					elif v.type.type == TokenType.FLOAT64: typeName = "double"
					elif v.type.type == TokenType.BOOL: typeName = "bool"
					elif v.type.type == TokenType.IDENTIFIER: typeName = self.value(v.identifier)
					else: assert(False)
					self.o("\t%s %s;"%(typeName, self.value(v.identifier)))
				self.o("};")
				self.o("#pragma pack(pop)")
				self.o("namespace scalgoproto {template <> struct MetaMagic<%s> {using t=PodTag;};}"%name)
				self.o()
			elif node.t == NodeType.ENUM:
				assert isinstance(node, Enum)
				name = self.value(node.identifier)
				self.o("enum class %s: std::uint8_t {"%name)
				index = 0
				for ev in node.values:
					self.o("\t%s = %d,"%(self.value(ev), index))
					index += 1
				self.o("};")
				self.o("namespace scalgoproto {template <> struct MetaMagic<%s> {using t=EnumTag;};}"%name)
				self.o()
			elif node.t == NodeType.TABLE:
				assert isinstance(node, Table)
				name = self.value(node.identifier)
				self.generateTable(node)

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


