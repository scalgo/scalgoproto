# -*- mode: python; tab-width: 4; indent-tabs-mode: t; python-indent-offset: 4; coding: utf-8 -*-
"""
Validate a schema
"""
from parser import Parser, ParseError
from annotate import annotate

from parser import TokenType, NodeType, Token, Struct, AstNode, Value, Enum, Table, VLUnion, VLList
from typing import Set, Dict, List
from types import SimpleNamespace

class Generator:
	enums: Dict[str, Enum] = {}
	structs: Dict[str, Struct] = {}
	tabels: Dict[str, Table] = {}

	def __init__(self, data:str) -> None:
		self.data = data

	def value(self, t:Token) -> str:
		return self.data[t.index: t.index + t.length]

	def generateTable(self, name, values: List[AstNode]) -> None:
		for node in values:
			if node.t == NodeType.VLUNION:
				assert isinstance(node, VLUnion)
				for member in node.members:
					if member.t == NodeType.TABLE:
						assert isinstance(member, Table)
						if member.values:
							self.generateTable("%s__%s"%(name, self.value(member.identifier)), member.values)
		print("class %sIn: public scalgoproto::In {"%name)
		print("\tfriend class scalgoproto::In;")
		print("\tfriend class scalgoproto::Reader;")
		print("protected:")
		print("\t%sIn(const char * data, std::uint32_t offset, std::uint32_t size): scalgoproto::In(data, offset, size) {}"%name)
		print("\tstatic uint32_t readSize_(const char * data, std::uint32_t offset) { return scalgoproto::In::readSize_(data, offset, 0x%08X); }"%(1234))
		print("public:")
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
		for node in values:
			if node.t == NodeType.VALUE:
				assert isinstance(node, Value)
				name = self.value(node.identifier)
				uname = name[0].upper() + name[1:]
				if node.type.type in typeMap:
					typeName = typeMap[node.type.type]
					if node.optional:
						print("\tbool has%s() const noexcept {"%( uname))
						if node.type.type in (TokenType.FLOAT32, TokenType.FLOAT64):
							print("\t\treturn std::isnan(getInner_<%s, %s>(std::numeric_limits<%s>::quiet_NaN()));"%(typeName, node.offset, typeName))
						else: 
							print("\t\treturn getBit_<%d, %s, 0>();"%(node.hasOffset, node.hasBit))
						print("\t}")
						
					print("\t%s get%s() const noexcept {"%(typeName, uname))
					if node.optional:
						print("\t\tassert(has%s());"%uname)
					print("\t\treturn getInner_<%s, %d>(0);"%( typeName, node.offset))
					print("\t}")
				elif node.type.type == TokenType.BOOL:
					if node.optional:
						print("\tbool has%s() const noexcept {"%( uname))
						print("\t\treturn getBit_<%d, %s, 0>();"%(node.hasOffset, node.hasBit))
						print("\t}")
					print("\tbool get%s() const noexcept {"%(uname))
					if node.optional:
						print("\t\tassert(has%s());"%uname)
					print("\t\treturn getBit_<%d, %s, 0>();"%(node.offset, node.bit))
					print("\t}")
				elif node.type.type == TokenType.IDENTIFIER:
					typeName = self.value(node.type)
					if typeName in self.enums:
						if node.optional:
							print("\tbool has%s() const noexcept {"%(uname))
							print("\t\treturn getInner_<std::uint8_t, %d>(255) == 255;"%(node.offset))
							print("\t}")
						print("\t%s get%s() const noexcept {"%(typeName, uname))
						if node.optional:
							print("\t\tassert(has%s());"%uname)
						print("\t\treturn (%s)getInner_<std::uint8_t, %d>(0);"%(typeName, node.offset))
						print("\t}")
					elif typeName in self.structs:
						if node.optional:
							print("\tbool has%s() const noexcept {"%(uname))
							print("\t\treturn getBit_<%d, %s, 0>();"%(node.hasOffset, node.hasBit))
							print("\t}")
						print("\t%s get%s() const noexcept {"%(typeName, uname))
						if node.optional:
							print("\t\tassert(has%s());"%uname)
						print("\t\treturn getInner_<%s, %d>();"%( typeName, node.offset))
						print("\t}")
					elif typeName in self.tabels:
						if node.optional:
							print("\tbool has%s() const noexcept {"%(uname))
							print("\t\treturn getInner_<std::uint32_t, %d>(0) == 0;"%(node.offset))
							print("\t}")
						print("\t%sIn get%s() const noexcept {"%(typeName, uname))
						if node.optional:
							print("\t\tassert(has%s());"%uname)
						print("\t\treturn getTable_<%sIn, %d>();"%(typeName, node.offset))
						print("\t}")
					else:
						assert False
		print("};")
		print("")
	
	def generate(self, ast: List[AstNode]) -> None:
		for node in ast:
			if node.t == NodeType.STRUCT:
				assert isinstance(node, Struct)
				name = self.value(node.identifier)
				print("#pragma pack(push, 1)")
				print("struct %s {"%name)
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
					print("\t%s %s;"%(typeName, self.value(v.identifier)))
				print("};")
				print("#pragma pack(pop)")
				print()
				self.structs[name] = node
			elif node.t == NodeType.ENUM:
				assert isinstance(node, Enum)
				name = self.value(node.identifier)
				print("enum class %s: std::uint8_t {"%name)
				index = 0
				for ev in node.values:
					print("\t%s = %d,"%(self.value(ev), index))
					index += 1
				print("};")
				print()
				self.enums[name] = node
			elif node.t == NodeType.TABLE:
				assert isinstance(node, Table)
				name = self.value(node.identifier)
				self.generateTable(name, node.values)
				self.tabels[name] = node

def run(args) -> int:
	data = open(args.schema).read()
	p = Parser(data)
	try:
		ast = p.parseDocument()
		if not annotate(data, ast):
			print("Invalid schema is valid")
			return 1
		g = Generator(data)
		print("#include \"scalgoproto.hh\"")
		g.generate(ast)
	except ParseError as err:
		err.describe(data)
	return 1

def setup(subparsers) -> None:
	cmd = subparsers.add_parser('cpp', help='Generate cpp code for windows')
	cmd.add_argument('schema', help='schema to generate things from')
	cmd.set_defaults(func=run)

class A:
	pass

