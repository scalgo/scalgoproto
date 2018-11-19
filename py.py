# -*- mode: python; tab-width: 4; indent-tabs-mode: t; python-indent-offset: 4; coding: utf-8 -*-
"""
Generate python reader/wirter
"""
from parser import Parser, ParseError
from annotate import annotate
from parser import TokenType, NodeType, Token, Struct, AstNode, Value, Enum, Table, VLUnion, VLList, VLBytes, VLText
from typing import Set, Dict, List, TextIO, Tuple, Union, NamedTuple
from types import SimpleNamespace
import math
from util import cescape, getuname

TypeInfo = NamedTuple("TypeInfo", [("n",str), ("p",str),("s",str),("w",int)])

typeMap: Dict[TokenType, TypeInfo] = {
	TokenType.INT8: TypeInfo("Int8", "int", "b", 1),
	TokenType.INT16: TypeInfo("Int16", "int", "h", 2),
	TokenType.INT32: TypeInfo("Int32", "int", "i", 4),
	TokenType.INT64: TypeInfo("Int64", "int", "q", 8),
	TokenType.UINT8: TypeInfo("UInt8", "int", "B", 1),
	TokenType.UINT16: TypeInfo("UInt16", "int", "H", 2),
	TokenType.UINT32: TypeInfo("UInt32", "int", "I", 4),
	TokenType.UINT64: TypeInfo("UInt64", "int", "Q", 8),
	TokenType.FLOAT32: TypeInfo("Float32", "float", "f", 4),
	TokenType.FLOAT64: TypeInfo("Float64", "float", "d", 8),
	TokenType.BOOL: TypeInfo("Bool", "bool", "?", 1),
}

class Generator:
	out: TextIO = None
	def o(self, text=""):
		print(text, file=self.out)
	
	def __init__(self, data:str, out:TextIO) -> None:
		self.data = data
		self.out = out
		
	def value(self, t:Token) -> str:
		return self.data[t.index: t.index + t.length]

	def outputDoc(self, node: AstNode, indent:str="", prefix:List[str] = [], suffix:List[str] = []):
		if not node.docstring and not suffix and not prefix: return	
		self.o('%s"""'%indent)
		for line in prefix:
			self.o("%s%s"%(indent,line))
		if prefix and (node.docstring or suffix):
			self.o("%s"%indent)
		if node.docstring:
			for line in node.docstring:
				self.o("%s%s"%(indent, line))
		if node.docstring and suffix:
			self.o("%s"%indent)
		for line in suffix:
			self.o("%s%s"%(indent, line))
		self.o('%s"""'%indent)
	

	def generateValueOut(self, node:Value):
		n = self.value(node.identifier)
		uname = n[0].upper() + n[1:]
		if node.list:
			pass
		elif node.type.type == TokenType.BOOL:
			self.o("\tdef add%s(self, value:bool) -> None:"%(uname))
			self.outputDoc(node, "\t\t")
			if node.optional:
				self.o("\t\tself._setBit(%d, %d)"%(node.hasOffset, node.hasBit))
			self.o("\t\tif value: self._setBit(%d, %d)"%(node.offset, node.bit))
			self.o("\t\telse: self._unsetBit(%d, %d)"%(node.offset, node.bit))
			self.o("\t")
		elif node.type.type in typeMap:
			ti = typeMap[node.type.type]
			self.o("\tdef add%s(self, value: %s) -> None:"%(uname, ti.p))
			self.outputDoc(node, "\t\t")
			if node.optional and node.type.type not in (TokenType.FLOAT32, TokenType.FLOAT64):
				self.o("\t\tself._setBit(%d, %d)"%(node.hasOffset, node.hasBit))
			self.o("\t\tself._set%s(%d, value)"%(ti.n, node.offset))
			self.o("\t")
		elif node.type.type == TokenType.IDENTIFIER:
			typeName = self.value(node.type)
			if node.enum:
				self.o("\tdef add%s(self, value: %s) -> None:"%(uname, typeName))
				self.outputDoc(node, "\t\t")
				self.o("\t\tself._setUInt8(%d, int(value))"%(node.offset))
				self.o("\t")
			elif node.struct:
				self.o("\tdef add%s(self, value: %s) -> None:"%(uname, typeName))
				self.outputDoc(node, "\t\t")
				if node.optional:
					self.o("\t\tself._setBit(%d, %d)"%(node.hasOffset, node.hasBit))
				self.o("\t\t%s._write(self._writer, self._offset + %d, value)"%(typeName, node.offset))
				self.o("\t")
			elif node.table:
				pass
			else:
				assert False
		elif node.type.type == TokenType.TEXT:
			pass
		elif node.type.type == TokenType.BYTES:
			pass
		else:
			assert False

	def generateVLUnionOut(self, node:VLUnion):
		pass

	def generateVLBytesOut(self, node:VLBytes):
		pass

	def generateVLListOut(self, node:VLList):
		pass

	def generateVLTextOut(self, node:VLText):
		pass

	def generateTable(self, table:Table):
		# Recursivly generate contained VL tabels
		for node in table.values:
			if node.t == NodeType.VLUNION:
				assert isinstance(node, VLUnion)
				for member in node.members:
					if member.t == NodeType.TABLE:
						assert isinstance(member, Table)
						if member.values:
							self.generateTable(member)

		#Generate Table writer
		self.o("class %sOut(scalgoproto.TableOut):"%table.name)
		self.outputDoc(table, "\t")
		self.o("\t_MAGIC:typing.ClassVar[int]=0x%08x"%table.magic)
		self.o("\tdef __init__(self, writer: scalgoproto.Writer, withHeader: bool) -> None:")
		self.o('\t\t"""Private constructor. Call factory methods on scalgoproto.Reader to construct instances"""')
		self.o("\t\tsuper().__init__(writer, withHeader, b\"%s\")"%(cescape(table.default)))
		for node in table.values:
			if node.t == NodeType.VALUE:
				assert isinstance(node, Value)
				self.generateValueOut(node)
			elif node.t == NodeType.VLUNION:
				assert isinstance(node, VLUnion)
				self.generateVLUnionOut(node)
			elif node.t == NodeType.VLBYTES:
				assert isinstance(node, VLBytes)
				self.generateVLBytesOut(node)
			elif node.t == NodeType.VLLIST:
				assert isinstance(node, VLList)
				self.generateVLListOut(node)
			elif node.t == NodeType.VLTEXT:
				assert isinstance(node,VLText)
				self.generateVLTextOut(node)
			else:
				assert(False)
		self.o("")

	def generateStruct(self, node:Struct):
		name = self.value(node.identifier)
		self.o("class %s(scalgoproto.StructType):"%name)
		self.o("\t_WIDTH: typing.ClassVar[int] = %d"%node.bytes)
		things = []
		for v in node.values:
			assert isinstance(v, Value)
			thing = ('','', '', 0, 0, "")
			n = self.value(v.identifier)
			if v.type.type in typeMap:
				ti = typeMap[v.type.type]
				if v.type.type in (TokenType.FLOAT32 , TokenType.FLOAT64):
					d = "0.0"
				elif v.type.type == TokenType.BOOL:
					d = "False"
				else:
					d = "0"
				thing = (n, ti.p, ti.s, ti.w, v.offset, d)
			elif v.type.type == TokenType.IDENTIFIER: thing= (n,self.value(v.type), None, 0, v.offset, "%s()"%self.value(v.type))
			else: assert(False)
			things.append(thing)
		self.o("\tdef __init__(self, %s) -> None:"%(", ".join(map(lambda th: "%s: %s = %s"%(th[0],th[1], th[5]), things))))
		for (n,p,q,s,o,d) in things:
			self.o("\t\tself.%s = %s"%(n, n))
		self.o("\t@staticmethod")
		self.o("\tdef _write(writer: scalgoproto.Writer, offset:int, ins: '%s') -> None:"%name)
		for (n,p,q,s,o,d) in things:
			if q:
				self.o("\t\twriter._data[offset+%d:offset+%d] = struct.pack('<%s', ins.%s)"%(o, o+s, q, n))
			else:
				self.o("\t\t%s._write(writer, offset+%d, ins.%s)"%(p, o, n))
		self.o()

	def generateEnum(self, node:Enum) -> None:
		name = self.value(node.identifier)
		self.o("class %s(enum.IntEnum):"%name)
		self.outputDoc(node, "\t")
		index = 0
		for ev in node.values:
			self.o("\t%s = %d"%(self.value(ev), index))
			index += 1
		self.o()

	def generate(self, ast: List[AstNode]) -> None:
		for node in ast:
			if node.t == NodeType.STRUCT:
				assert isinstance(node, Struct)
				self.generateStruct(node)
			elif node.t == NodeType.ENUM:
				assert isinstance(node, Enum)
				self.generateEnum(node)
			elif node.t == NodeType.TABLE:
				assert isinstance(node, Table)
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
		print("# -*- mode: python; tab-width: 4; indent-tabs-mode: t; python-indent-offset: 4; coding: utf-8 -*-", file=out)
		print("# THIS FILE IS GENERATED DO NOT EDIT", file=out)
		print("import scalgoproto, enum, typing, struct, math", file=out)
		print("", file=out)
		g.generate(ast)
		return 0
	except ParseError as err:
		err.describe(data)
	return 1

def setup(subparsers) -> None:
	cmd = subparsers.add_parser('py', help='Generate python code')
	cmd.add_argument('schema', help='schema to generate things from')
	cmd.add_argument('output', help="where do we store the output")
	cmd.set_defaults(func=run)


