# -*- mode: python; tab-width: 4; indent-tabs-mode: t; python-indent-offset: 4; coding: utf-8 -*-
"""
Parse a protocol description and generate an ast
"""
import enum
import typing as ty
from error import error
from tokenize import TokenType, tokenize, Token

class AstNode(object):
	__slots__ = ['token', 'docccomment', 'bytes', 'offset', 'docstring']
	def __init__(self, token: Token, doccomment: Token = None) -> None:
		self.token = token
		self.docccomment = doccomment
		self.bytes = 0
		self.offset = 0
		docstring: ty.List[str] = None
		self.docstring = docstring

class Namespace(AstNode):
	__slots__ = ['namespace']
	def __init__(self, token: Token, namespace:str) -> None:
		super().__init__(token)
		self.namespace = namespace
		
class Struct(AstNode):
	__slots__ = ['identifier', 'members']
	def __init__(self, token: Token, identifier: Token, members: ty.List['Value'], doccomment: Token) -> None:
		super().__init__(token, doccomment)
		self.identifier = identifier
		self.members = members
		
class Enum(AstNode):
	__slots__ = ['identifier', 'members', 'annotatedValues']
	
	def __init__(self, token: Token, identifier: Token, members: ty.List['Value'], doccomment: Token) -> None:
		super().__init__(token, doccomment)
		self.identifier = identifier
		self.members = members
		annotatedValues: ty.Dict[str, int] = None
		self.annotatedValues = annotatedValues

class Table(AstNode):
	__slots__ = ['identifier', 'id_', 'members', 'default', 'magic', 'name']
	
	def __init__(self, token: Token, identifier: Token, id_: Token, members: ty.List['Value'],  doccomment: Token) -> None:
		super().__init__(token, doccomment)
		self.identifier = identifier
		self.id_ = id_
		self.members = members
		default: bytes = None
		name: str = None
		self.default = default
		self.magic: int = 0
		self.name = name

class Union(AstNode):
	__slots__ = ['members', 'identifier', 'name']
	def __init__(self, token: Token, identifier: Token, members: ty.List['Value'], docccomment: Token) -> None:
		super().__init__(token, docccomment)
		self.members = members
		self.identifier = identifier
		name: str = None
		self.name = name

class Value(AstNode):
	__slots__ = ['identifier', 'value', 'type_', 'optional', 'list_', 'inplace', 'direct_table', 'direct_union', 'has_offset', 'has_bit', 'bit', 'table',
		'enum', 'struct', 'union', 'parsed_value']
	
	def __init__(self, token: Token, identifier: Token, value: Token, type_: Token, optional: Token, 
		list_: Token, inplace: Token, direct_table: Table, direct_union: Union,  doccomment: Token) -> None:
		super().__init__(token, doccomment)
		self.identifier = identifier
		self.value = value
		self.type_ = type_
		self.optional = optional
		self.list_ = list_
		self.inplace = inplace
		self.direct_table = direct_table
		self.direct_union = direct_union
		self.has_offset = 0
		self.has_bit = 0
		self.bit = 0
		table: Table = None
		enum: Enum = None
		struct: Struct = None
		union: Union = None
		parsed_value: ty.Union[int, float] = 0
		self.table = table
		self.enum = enum
		self.struct = struct
		self.union = union
		self.parsed_value = parsed_value
		self.direct_table = direct_table
		self.direct_union = direct_union

class ParseError(Exception):
	def __init__(self, token: Token, message: str, context: str) -> None:
		self.token = token
		self.message = message
		self.context = context

	def describe(self, data: str) -> None:
		error(data, self.context, self.token, self.message, "Parse error")
		
class Parser:
	token: Token = None

	def __init__(self, data:str) -> None:
		self.data = data
		self.tokenizer = tokenize(data)
		self.token = None
		self.next_token()
		self.context = ""

	def check_token(self, t: Token, types: ty.List[TokenType]) -> None:
		if not t.type in types:
			raise ParseError(t, "Expected one of %s got %s"%(", ".join(map(str, types)), t.type), self.context)
		
	def consume_token(self, types: ty.List[TokenType]) -> Token:
		t = self.token
		self.check_token(t, types)
		self.next_token()
		return t
	
	def next_token(self) -> None:
		self.token = next(self.tokenizer)

	def parse_content(self) -> ty.List[Value]:
		self.consume_token([TokenType.LBRACE])
		members: ty.List[Value] = []
		doccomment: Token = None
		while True:
			t = self.consume_token([
					TokenType.RBRACE,
					TokenType.IDENTIFIER,
					TokenType.DOCCOMMENT
					])
			if t.type == TokenType.DOCCOMMENT:
				doccomment = t
			elif t.type == TokenType.RBRACE:
				break
			elif t.type == TokenType.IDENTIFIER:
				self.check_token(self.token, [TokenType.COLON, TokenType.LBRACE])
				colon: Token = self.consume_token([TokenType.COLON]) if self.token.type == TokenType.COLON else None
				optional: Token = None
				list_: Token = None
				inplace: Token = None
				value: Token = None
				direct_table: Table = None
				direct_union: Union = None
				while self.token.type in [TokenType.OPTIONAL, TokenType.LIST, TokenType.INPLACE]:
					if self.token.type == TokenType.OPTIONAL:
						optional = self.consume_token([TokenType.OPTIONAL])
					elif self.token.type == TokenType.LIST:
						list_ = self.consume_token([TokenType.LIST])		
					elif self.token.type == TokenType.INPLACE:
						inplace = self.consume_token([TokenType.INPLACE])	
				type_ = self.token
				self.check_token(self.token,[
					TokenType.BOOL, TokenType.TEXT, TokenType.IDENTIFIER, TokenType.BYTES,
					TokenType.INT8, TokenType.INT16, TokenType.INT32, TokenType.INT64,
					TokenType.UINT8, TokenType.UINT16, TokenType.UINT32, TokenType.UINT64,
					TokenType.FLOAT32, TokenType.FLOAT64, TokenType.UNION, TokenType.TABLE,
					TokenType.LBRACE])
				if type_.type == TokenType.LBRACE:
					direct_table = Table(type_, None, None, self.parse_content(), doccomment)
				else:
					self.next_token()
					if type_.type == TokenType.UNION:
						direct_union = Union(type_, None, self.parse_content(), doccomment)
					elif type_.type == TokenType.TABLE:
						id_ = self.consume_token([TokenType.ID]) if self.token.type == TokenType.ID else None
						direct_table = Table(type_, None, id_, self.parse_content(), doccomment)
					if self.token.type == TokenType.EQUAL:
						self.consume_token([TokenType.EQUAL])
						value = self.consume_token([TokenType.TRUE, TokenType.FALSE, TokenType.NUMBER, TokenType.IDENTIFIER])
				members.append(Value(colon, t, value, type_, optional, list_, inplace, direct_table, direct_union, doccomment))
				doccomment = None
			else:
				assert(False)
			if self.token.type in [TokenType.COMMA, TokenType.SEMICOLON]:
				self.next_token()
		return members


	def value(self, t:Token) -> str:
		return self.data[t.index: t.index + t.length]	

	def parseDocument(self) -> ty.List[AstNode]:
		ans: ty.List[AstNode] = []
		doccomment: Token = None
		while self.token.type != TokenType.EOF:
			self.context = "message"
			t = self.consume_token([TokenType.STRUCT, TokenType.ENUM, TokenType.TABLE, TokenType.NAMESPACE, TokenType.UNION, TokenType.DOCCOMMENT])
			if t.type == TokenType.DOCCOMMENT:
				doccomment = t
			elif t.type == TokenType.NAMESPACE:
				namespace = ""
				while True:
					i = self.consume_token([TokenType.IDENTIFIER])
					namespace += self.data[i.index: i.index + i.length]
					tt = self.consume_token([TokenType.COLONCOLON, TokenType.SEMICOLON])
					if tt.type != TokenType.COLONCOLON: break
					namespace += "::"
				ans.append(Namespace(t, namespace))
				doccomment = None
			elif t.type == TokenType.STRUCT:
				i = self.consume_token([TokenType.IDENTIFIER])
				self.context = "struct %s"%self.value(i)
				ans.append(Struct(t, i, self.parse_content(), doccomment))
				doccomment = None
			elif t.type == TokenType.TABLE:
				i = self.consume_token([TokenType.IDENTIFIER])
				self.context = "table %s"%self.value(i)
				id_ = self.consume_token([TokenType.ID]) if self.token.type == TokenType.ID else None
				ans.append(Table(t, i, id_, self.parse_content(), doccomment))
				doccomment = None
			elif t.type == TokenType.ENUM:
				i = self.consume_token([TokenType.IDENTIFIER])
				self.context = "enum %s"%self.value(i)
				self.consume_token([TokenType.LBRACE])
				values = []
				doccomment2 = None
				while True:
					self.check_token(self.token, [TokenType.RBRACE, TokenType.IDENTIFIER, TokenType.DOCCOMMENT])
					if self.token.type == TokenType.RBRACE:
						break
					elif self.token.type == TokenType.DOCCOMMENT:
						doccomment2 = self.token
					elif self.token.type == TokenType.IDENTIFIER:
						ident = self.consume_token([TokenType.IDENTIFIER])
						values.append(Value(ident, ident, None, None, None, None, None, None, None, doccomment2))
						doccomment2 = None
						if self.token.type in [TokenType.COMMA, TokenType.SEMICOLON]:
							self.next_token()
				self.consume_token([TokenType.RBRACE])
				ans.append(Enum(t, i, values, doccomment))
				doccomment = None
			elif t.type == TokenType.UNION:
				self.context = "union %s"%self.value(i)
				self.consume_token([TokenType.IDENTIFIER])
				ans.append(Union(t, i, self.parse_content(), doccomment))
				doccomment = None
			if self.token.type in [TokenType.COMMA, TokenType.SEMICOLON]:
				self.next_token()
		return ans

