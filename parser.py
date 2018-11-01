# -*- mode: python; tab-width: 4; indent-tabs-mode: t; python-indent-offset: 4; coding: utf-8 -*-
"""
Parse a protocol description and generate an ast
"""
from enum import Enum
from collections import namedtuple 

class TokenType(Enum):
	BAD = 0
	BOOL = 1
	BYTES = 2
	COLON = 3
	COMMA = 4
	ENUM = 5
	EOF = 6
	EQUAL = 7
	FALSE = 8
	INT16 = 9
	INT32 = 10
	INT64 = 11
	INT8 = 12
	LBRACE = 13
	LIST = 14
	NUMBER = 15
	OPTIONAL = 17
	RBRACE = 18
	SEMICOLON = 20
	STRING = 21
	STRUCT = 22
	TABLE = 23
	TEXT = 24
	TRUE = 25
	UINT16 = 26
	UINT32 = 27
	UINT64 = 28
	UINT8 = 29
	UNION = 30
	IDENTIFIER = 31
	FLOAT32 = 32
	FLOAT64 = 64
	ID = 65
	NAMESPACE = 66
	COLONCOLON = 67
	
Token = namedtuple('Token', ['type', 'index', 'length'])

def tokenize(data):
	cur = 0
	ops = {
		':': TokenType.COLON,
		';': TokenType.SEMICOLON,
		',': TokenType.COMMA,
		'=': TokenType.EQUAL,
		'{': TokenType.LBRACE,
		'}': TokenType.RBRACE,
		}

	keywords = {
		'Bool': TokenType.BOOL,
		'Bytes': TokenType.BYTES,
		'Float32': TokenType.FLOAT32,
		'Float64': TokenType.FLOAT64, 
		'Int16': TokenType.INT16,
		'Int32': TokenType.INT32,
		'Int64': TokenType.INT64,
		'Int8': TokenType.INT8,
		'List': TokenType.LIST,
		'Optional': TokenType.OPTIONAL,
		'Text': TokenType.TEXT,
		'UInt16': TokenType.UINT16,
		'UInt32': TokenType.UINT32,
		'UInt64': TokenType.UINT64,
		'UInt8': TokenType.UINT8,
		'enum': TokenType.ENUM,
		'false': TokenType.FALSE,
		'struct': TokenType.STRUCT,
		'table': TokenType.TABLE,
		'true': TokenType.TRUE,
		'union': TokenType.UNION,
		'namespace': TokenType.NAMESPACE,
	}

	while cur < len(data):
		if data[cur:cur+2] == '::':
			yield Token(TokenType.COLONCOLON, cur, 2)
			cur += 2
			continue

		if data[cur] in " \t\n\r":
			cur += 1
			continue
		if data[cur] in ops:
			yield Token(ops[data[cur]], cur, 1)
			cur += 1
			continue
		if data[cur] == '#' or data[cur:cur+2] == '//':
			while cur < len(data) and data[cur] != '\n':
				cur += 1
			continue
		if data[cur:cur+2] == '/*':
			cnt = 1
			cur += 2
			while cnt !=0 and cur < len(data):
				if data[cur:cur+2] == '/*':
					cnt += 1
					cur += 2
				elif data[cur:cur+2] == '*/':
					cnt -= 1
					cur += 2
				else:
					cur += 1
			continue

		if data[cur].isalpha() or data[cur] == '_':
			end = cur+1
			while end < len(data) and (data[end] == '_' or data[end].isalnum()):
				end += 1
			type = TokenType.IDENTIFIER
			if data[cur:end] in keywords: type = keywords[data[cur:end]]
			yield Token(type, cur, end-cur)
			cur = end;
			continue

		if data[cur] == '@':
			end = cur+1
			while end < len(data) and data[end] in "0123456789ABCDEFG":
				end += 1
			yield Token(TokenType.ID, cur, end-cur)
			cur = end
			continue
									   
		if data[cur] == '-' or data[cur] == '.' or data[cur] in "0123456789":		  
			end = cur
			if end < len(data) and data[end] == '-':
				end += 1
			while end < len(data) and data[end] in "0123456789":
				end += 1
			if end < len(data) and data[end] == '.':
				end += 1
				while end < len(data) and data[end] in "0123456789":
					end += 1
			if end < len(data) and data[end] in "eE":
				end += 1
				if end < len(data) and data[end] in "+-":
					end += 1
				while end < len(data) and data[end] in "0123456789":
					end += 1
			yield Token(TokenType.NUMBER, cur, end-cur)
			cur = end;
			continue
		
		yield Token(TokenType.BAD, cur, 1)
		cur += 1
	yield Token(TokenType.EOF, cur, 0)


class NodeType(Enum):
	STRUCT = 1
	ENUM = 2
	TABLE = 3
	VALUE = 4
	NAMESPACE = 5
	VLBYTES = 6
	VLLIST = 7
	VLTEXT = 8
	VLUNION = 9
	
class Namespace:
	def __init__(self, token, namespace):
		self.t = NodeType.NAMESPACE
		self.token = token
		self.namespace = namespace
		
class Struct:
	def __init__(self, token, identifier, values):
		self.t = NodeType.STRUCT
		self.token = token
		self.identifier = identifier
		self.values = values
		
class Enum:
	def __init__(self, token, identifier, values):
		self.t = NodeType.ENUM
		self.token = token
		self.identifier = identifier
		self.values = values

class Table:
	def __init__(self, token, identifier, id, values):
		self.t = NodeType.TABLE
		self.token = token
		self.identifier = identifier
		self.id = id
		self.values = values
	
class Value:
	def __init__(self, token, identifier, value, type, optional, list):
		self.t = NodeType.VALUE
		self.token = token
		self.identifier = identifier
		self.value = value
		self.type = type
		self.optional = optional
		self.list = list


class VLUnion:
	def __init__(self, token, members):
		self.t = NodeType.VLUNION
		self.token = token
		self.members = members

class VLBytes:
	def __init__(self, token):
		self.t = NodeType.VLBYTES
		self.token = token

class VLText:
	def __init__(self, token):
		self.t = NodeType.VLTEXT
		self.token = token

class VLList:
	def __init__(self, token, type):
		self.t = NodeType.VLLIST
		self.token = token
		self.type = type


class ParseError(Exception):
	def __init__(self, token, message):
		self.token = token
		self.message = message

	def describe(self, data):
		cnt = 1
		idx = 0
		start = 0
		t = 0
		while idx < self.token.index:
			if data[idx] == '\n':
				cnt += 1
				start = idx + 1
				t = 0
			if data[idx] == '\t':
				t += 1
			idx += 1
		print("Parse error on line %d: %s"%(cnt, self.message))
		end = start
		while end < len(data) and data[end] != '\n':
			end += 1
		print(data[start:end])
		print("%s%s%s"%('\t'*t, ' '*(self.token.index - start -t), '^'*(self.token.length)))
		
class Parser:
	def __init__(self, data):
		self.data = data
		self.tokenizer = tokenize(data)
		self.token = None
		self.nextToken()

	def checkToken(self, t, types):
		if not t.type in types:
			raise ParseError(t, "Expected one of %s got %s"%(", ".join(map(str, types)), t.type))
		
	def consumeToken(self, types):
		t = self.token
		self.checkToken(t, types)
		self.nextToken()
		return t
	
	def nextToken(self):
		self.token = next(self.tokenizer)

	def parseType(self):
		return self.consumeToken([TokenType.BOOL, TokenType.TEXT, TokenType.IDENTIFIER, 
								  TokenType.INT8, TokenType.INT16, TokenType.INT32, TokenType.INT64,
								  TokenType.UINT8, TokenType.UINT16, TokenType.UINT32, TokenType.UINT64,
								  TokenType.FLOAT32, TokenType.FLOAT64])
			
	def parseContent(self):
		ans = []
		self.consumeToken([TokenType.LBRACE])
		while True:
			t = self.consumeToken([
					TokenType.RBRACE,
					TokenType.IDENTIFIER,
					TokenType.UNION,
					TokenType.LIST,
					TokenType.TEXT,
					TokenType.BYTES])
			if t.type == TokenType.RBRACE:
				break
			elif t.type == TokenType.IDENTIFIER:
				colon = self.consumeToken([TokenType.COLON])
				optional = None
				list_ = None
				if self.token.type == TokenType.OPTIONAL:
					optional = self.consumeToken([TokenType.OPTIONAL])
				elif self.token.type == TokenType.LIST:
					list_ = self.consumeToken([TokenType.LIST])					
				type_ = self.parseType()
				value = None
				if self.token.type == TokenType.EQUAL:
					self.consumeToken([TokenType.EQUAL])
					value = self.consumeToken([TokenType.TRUE, TokenType.FALSE, TokenType.NUMBER, TokenType.STRING])
				ans.append(Value(colon, t, value, type_, optional, list_))
			elif t.type == TokenType.UNION:
				self.consumeToken([TokenType.LBRACE])
				members = []
				while True:
					t2 = self.consumeToken([TokenType.RBRACE, TokenType.IDENTIFIER])
					if t2.type == TokenType.RBRACE:
						break
					elif t2.type == TokenType.IDENTIFIER:
						self.checkToken(self.token, [TokenType.LBRACE, TokenType.COLON])
						if self.token.type == TokenType.COLON:
							self.consumeToken([TokenType.COLON])
							type_ = self.consumeToken([TokenType.IDENTIFIER])
							members.append(Value(self.token, t2, None, type_, None, None))
						else:
							members.append(Table(t, t2, None, self.parseContent()))
					else:
						assert(False)
					if self.token.type in [TokenType.COMMA, TokenType.SEMICOLON]:
						self.nextToken()
				ans.append(VLUnion(t, members))
			elif t.type == TokenType.LIST:
				ans.append(VLList(t, self.parseType()));
			elif t.type == TokenType.BYTES:
				ans.append(VLBytes(t))
			elif t.type == TokenType.TEXT:
				ans.append(VLText(t))
			else:
				assert(False)
			if self.token.type in [TokenType.COMMA, TokenType.SEMICOLON]:
				self.nextToken()
		return ans
		
	def parseDocument(self):
		ans = []
		while self.token.type != TokenType.EOF:
			t = self.consumeToken([TokenType.STRUCT, TokenType.ENUM, TokenType.TABLE, TokenType.NAMESPACE])
			if t.type == TokenType.NAMESPACE:
				namespace = ""
				while True:
					i = self.consumeToken([TokenType.IDENTIFIER])
					namespace += self.data[i.index: i.index + i.length]
					tt = self.consumeToken([TokenType.COLONCOLON, TokenType.SEMICOLON])
					if tt.type != TokenType.COLONCOLON: break
					namespace += "::"
				ans.append(Namespace(t, namespace))
			elif t.type == TokenType.STRUCT:
				i = self.consumeToken([TokenType.IDENTIFIER])
				ans.append(Struct(t, i, self.parseContent()))
			elif t.type == TokenType.TABLE:
				i = self.consumeToken([TokenType.IDENTIFIER])
				id = self.consumeToken([TokenType.ID])
				ans.append(Table(t, i, id, self.parseContent()))
			elif t.type == TokenType.ENUM:
				i = self.consumeToken([TokenType.IDENTIFIER])
				self.consumeToken([TokenType.LBRACE])
				values = []
				while True:
					self.checkToken(self.token, [TokenType.RBRACE, TokenType.IDENTIFIER])
					if self.token.type == TokenType.RBRACE:
						break
					elif self.token.type == TokenType.IDENTIFIER:
						values.append(self.consumeToken([TokenType.IDENTIFIER]))
						if self.token.type in [TokenType.COMMA, TokenType.SEMICOLON]:
							self.nextToken()
				self.consumeToken([TokenType.RBRACE])
				ans.append(Enum(t, i, values))
			if self.token.type in [TokenType.COMMA, TokenType.SEMICOLON]:
				self.nextToken()
		return ans


