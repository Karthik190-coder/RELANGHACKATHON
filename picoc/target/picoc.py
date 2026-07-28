#!/usr/bin/env python3
"""A C interpreter ported from picoc."""
import sys
import struct
import math
import os

# ============================================================
# TYPE SYSTEM
# ============================================================

class BaseType:
    VOID = 0
    INT = 1
    SHORT = 2
    CHAR = 3
    LONG = 4
    UNSIGNED_INT = 5
    UNSIGNED_SHORT = 6
    UNSIGNED_CHAR = 7
    UNSIGNED_LONG = 8
    FP = 9
    FUNCTION = 10
    MACRO = 11
    POINTER = 12
    ARRAY = 13
    STRUCT = 14
    UNION = 15
    ENUM = 16
    GOTO_LABEL = 17
    TYPE_TYPE = 18

class ValueType:
    def __init__(self, base, sizeof=0, align=1, from_type=None, array_size=0, identifier=None):
        self.base = base
        self.sizeof = sizeof
        self.align = align
        self.from_type = from_type
        self.array_size = array_size
        self.identifier = identifier
        self.members = {}
        self.member_order = []
        self.static = False
        self.is_typedef = False
        self.func_def = None
        self.enum_values = {}

    def is_integer(self):
        return self.base >= BaseType.INT and self.base <= BaseType.UNSIGNED_LONG

    def is_signed(self):
        return self.base in (BaseType.INT, BaseType.SHORT, BaseType.CHAR, BaseType.LONG)

    def is_unsigned(self):
        return self.base in (BaseType.UNSIGNED_INT, BaseType.UNSIGNED_SHORT, BaseType.UNSIGNED_CHAR, BaseType.UNSIGNED_LONG)

    def is_fp(self):
        return self.base == BaseType.FP

    def is_numeric(self):
        return self.is_integer() or self.is_fp()

    def is_pointer(self):
        return self.base == BaseType.POINTER

    def is_array(self):
        return self.base == BaseType.ARRAY

    def is_struct(self):
        return self.base == BaseType.STRUCT

    def is_union(self):
        return self.base == BaseType.UNION

    def is_void(self):
        return self.base == BaseType.VOID

    def is_function(self):
        return self.base == BaseType.FUNCTION

    def is_enum(self):
        return self.base == BaseType.ENUM

def type_size(typ, array_size=-1):
    if array_size < 0:
        array_size = typ.array_size
    if typ.is_array():
        if array_size == 0:
            return 0
        return type_size(typ.from_type) * array_size
    return typ.sizeof

def type_alignof(typ):
    if typ.is_array():
        return type_alignof(typ.from_type)
    return typ.align

def compute_struct_size(members, is_union):
    if is_union:
        max_size = 0
        max_align = 1
        for name, mtype, offset in members:
            sz = type_size(mtype)
            al = type_alignof(mtype)
            if sz > max_size:
                max_size = sz
            if al > max_align:
                max_align = al
        total = max_size
        if max_align > 0:
            total = (total + max_align - 1) // max_align * max_align
        return total, max_align
    else:
        offset = 0
        max_align = 1
        for name, mtype, _ in members:
            al = type_alignof(mtype)
            sz = type_size(mtype)
            if al > 0:
                offset = (offset + al - 1) // al * al
            if al > max_align:
                max_align = al
            offset += sz
        if max_align > 0:
            offset = (offset + max_align - 1) // max_align * max_align
        return offset, max_align

# ============================================================
# MEMORY MODEL
# ============================================================

class Memory:
    def __init__(self, size=2 * 1024 * 1024):
        self.data = bytearray(size)
        self.stack_top = 0
        self.heap_start = size // 2
        self.heap_top = self.heap_start
        self.size = size

    def alloc_stack(self, size):
        self.stack_top = (self.stack_top + 7) & ~7
        offset = self.stack_top
        self.stack_top += max(size, 1)
        return offset

    def push_stack_frame(self):
        return self.stack_top

    def pop_stack_frame(self, old_top):
        self.stack_top = old_top

    def alloc_heap(self, size):
        if size <= 0:
            size = 1
        self.heap_top = (self.heap_top + 7) & ~7
        offset = self.heap_top
        self.heap_top += size
        if self.heap_top >= self.size:
            return 0
        return offset

    def free_heap(self, offset):
        pass

    def read_signed(self, offset, size):
        return int.from_bytes(self.data[offset:offset + size], 'little', signed=True)

    def read_unsigned(self, offset, size):
        return int.from_bytes(self.data[offset:offset + size], 'little', signed=False)

    def read_double(self, offset):
        return struct.unpack('<d', bytes(self.data[offset:offset + 8]))[0]

    def read_ptr(self, offset):
        return int.from_bytes(self.data[offset:offset + 8], 'little', signed=False)

    def read_bytes(self, offset, length):
        return bytes(self.data[offset:offset + length])

    def write_int(self, offset, value, size):
        mask = (1 << (size * 8)) - 1
        value = value & mask
        self.data[offset:offset + size] = value.to_bytes(size, 'little')

    def write_double(self, offset, value):
        self.data[offset:offset + 8] = struct.pack('<d', value)

    def write_ptr(self, offset, value):
        self.data[offset:offset + 8] = (value & 0xFFFFFFFFFFFFFFFF).to_bytes(8, 'little')

    def write_bytes(self, offset, data):
        self.data[offset:offset + len(data)] = data

    def read_cstring(self, offset):
        end = offset
        while end < len(self.data) and self.data[end] != 0:
            end += 1
        return bytes(self.data[offset:end]).decode('latin-1')

# ============================================================
# VALUES
# ============================================================

class Value:
    __slots__ = ['typ', 'offset', 'is_lvalue', 'rvalue_val', 'mem']

    def __init__(self, typ, offset=0, is_lvalue=False, mem=None, rvalue_val=None):
        self.typ = typ
        self.offset = offset
        self.is_lvalue = is_lvalue
        self.rvalue_val = rvalue_val
        self.mem = mem

    def read_int(self):
        if self.rvalue_val is not None:
            if self.rvalue_val[0] == 'int':
                return self.rvalue_val[1]
            elif self.rvalue_val[0] == 'fp':
                return int(self.rvalue_val[1])
            elif self.rvalue_val[0] == 'ptr':
                return self.rvalue_val[1]
        if self.typ.is_fp():
            return int(self.read_fp())
        sz = self.typ.sizeof
        if self.typ.is_signed():
            return self.mem.read_signed(self.offset, sz)
        else:
            return self.mem.read_unsigned(self.offset, sz)

    def read_uint(self):
        if self.rvalue_val is not None:
            if self.rvalue_val[0] == 'int':
                return self.rvalue_val[1] & 0xFFFFFFFF
            elif self.rvalue_val[0] == 'fp':
                return int(self.rvalue_val[1]) & 0xFFFFFFFF
            elif self.rvalue_val[0] == 'ptr':
                return self.rvalue_val[1] & 0xFFFFFFFF
        if self.typ.is_fp():
            return int(self.read_fp()) & 0xFFFFFFFF
        sz = self.typ.sizeof
        return self.mem.read_unsigned(self.offset, sz)

    def read_long(self):
        if self.rvalue_val is not None:
            if self.rvalue_val[0] == 'int':
                return self.rvalue_val[1]
            elif self.rvalue_val[0] == 'fp':
                return int(self.rvalue_val[1])
            elif self.rvalue_val[0] == 'ptr':
                return self.rvalue_val[1]
        if self.typ.is_fp():
            return int(self.read_fp())
        sz = self.typ.sizeof
        if self.typ.is_signed():
            return self.mem.read_signed(self.offset, sz)
        else:
            return self.mem.read_unsigned(self.offset, sz)

    def read_ulong(self):
        if self.rvalue_val is not None:
            if self.rvalue_val[0] == 'int':
                return self.rvalue_val[1] & 0xFFFFFFFFFFFFFFFF
            elif self.rvalue_val[0] == 'fp':
                return int(self.rvalue_val[1]) & 0xFFFFFFFFFFFFFFFF
            elif self.rvalue_val[0] == 'ptr':
                return self.rvalue_val[1] & 0xFFFFFFFFFFFFFFFF
        if self.typ.is_fp():
            return int(self.read_fp()) & 0xFFFFFFFFFFFFFFFF
        sz = self.typ.sizeof
        return self.mem.read_unsigned(self.offset, sz)

    def read_fp(self):
        if self.rvalue_val is not None:
            if self.rvalue_val[0] == 'fp':
                return self.rvalue_val[1]
            elif self.rvalue_val[0] == 'int':
                return float(self.rvalue_val[1])
            elif self.rvalue_val[0] == 'ptr':
                return float(self.rvalue_val[1])
        if self.typ.is_fp():
            return self.mem.read_double(self.offset)
        sz = self.typ.sizeof
        if self.typ.is_signed():
            return float(self.mem.read_signed(self.offset, sz))
        else:
            return float(self.mem.read_unsigned(self.offset, sz))

    def read_ptr(self):
        if self.rvalue_val is not None:
            if self.rvalue_val[0] == 'ptr':
                return self.rvalue_val[1]
            elif self.rvalue_val[0] == 'int':
                return self.rvalue_val[1]
        if self.typ.is_array():
            return self.offset
        if self.typ.is_pointer():
            return self.mem.read_ptr(self.offset)
        return self.offset

    def write_int(self, value):
        if self.is_lvalue and self.rvalue_val is None:
            sz = self.typ.sizeof
            self.mem.write_int(self.offset, value, sz)
        else:
            self.rvalue_val = ('int', value)

    def write_fp(self, value):
        if self.is_lvalue and self.rvalue_val is None:
            self.mem.write_double(self.offset, value)
        else:
            self.rvalue_val = ('fp', value)

    def write_ptr(self, value):
        if self.is_lvalue and self.rvalue_val is None:
            self.mem.write_ptr(self.offset, value)
        else:
            self.rvalue_val = ('ptr', value)

    def write_value(self, src_val):
        if self.typ.is_fp():
            self.write_fp(src_val.read_fp())
        elif self.typ.is_signed():
            self.write_int(src_val.read_int())
        elif self.typ.is_unsigned():
            if self.typ.sizeof == 8:
                self._write_ulong(src_val.read_ulong())
            else:
                self.write_int(src_val.read_int())
        elif self.typ.is_pointer():
            self.write_ptr(src_val.read_ptr())
        elif self.typ.is_array():
            sz = type_size(self.typ)
            if src_val.is_lvalue and src_val.rvalue_val is None:
                src_data = src_val.mem.read_bytes(src_val.offset, sz)
            else:
                src_data = bytes(sz)
            self.mem.write_bytes(self.offset, src_data)
        else:
            sz = type_size(self.typ)
            if src_val.is_lvalue and src_val.rvalue_val is None:
                src_data = src_val.mem.read_bytes(src_val.offset, sz)
            else:
                src_data = bytes(sz)
            self.mem.write_bytes(self.offset, src_data)

    def _write_ulong(self, value):
        if self.is_lvalue and self.rvalue_val is None:
            self.mem.write_int(self.offset, value, 8)
        else:
            self.rvalue_val = ('int', value)

_pointer_type_cache = {}

def get_pointer_type(base_type):
    key = id(base_type)
    if key not in _pointer_type_cache:
        _pointer_type_cache[key] = ValueType(BaseType.POINTER, sizeof=8, align=8, from_type=base_type)
    return _pointer_type_cache[key]

def get_array_type(base_type, array_size):
    sz = type_size(base_type) * array_size if array_size > 0 else 0
    return ValueType(BaseType.ARRAY, sizeof=sz, align=base_type.align, from_type=base_type, array_size=array_size)

_base_types = {}

def get_base_type(base):
    if base not in _base_types:
        if base == BaseType.VOID:
            _base_types[base] = ValueType(base, sizeof=0, align=1)
        elif base == BaseType.INT:
            _base_types[base] = ValueType(base, sizeof=4, align=4)
        elif base == BaseType.SHORT:
            _base_types[base] = ValueType(base, sizeof=2, align=2)
        elif base == BaseType.CHAR:
            _base_types[base] = ValueType(base, sizeof=1, align=1)
        elif base == BaseType.LONG:
            _base_types[base] = ValueType(base, sizeof=8, align=8)
        elif base == BaseType.UNSIGNED_INT:
            _base_types[base] = ValueType(base, sizeof=4, align=4)
        elif base == BaseType.UNSIGNED_SHORT:
            _base_types[base] = ValueType(base, sizeof=2, align=2)
        elif base == BaseType.UNSIGNED_CHAR:
            _base_types[base] = ValueType(base, sizeof=1, align=1)
        elif base == BaseType.UNSIGNED_LONG:
            _base_types[base] = ValueType(base, sizeof=8, align=8)
        elif base == BaseType.FP:
            _base_types[base] = ValueType(base, sizeof=8, align=8)
    return _base_types[base]

# ============================================================
# FUNCTION DEFINITION
# ============================================================

class FuncDef:
    def __init__(self, return_type, params, var_args=False, body=None, intrinsic=None):
        self.return_type = return_type
        self.params = params
        self.var_args = var_args
        self.body = body
        self.intrinsic = intrinsic

# ============================================================
# AST NODES
# ============================================================

class Node:
    pass

class NumberNode(Node):
    def __init__(self, value, is_fp=False):
        self.value = value
        self.is_fp = is_fp

class StringNode(Node):
    def __init__(self, value):
        self.value = value

class CharNode(Node):
    def __init__(self, value):
        self.value = value

class IdentifierNode(Node):
    def __init__(self, name):
        self.name = name

class BinaryOpNode(Node):
    def __init__(self, op, left, right):
        self.op = op
        self.left = left
        self.right = right

class UnaryOpNode(Node):
    def __init__(self, op, operand, prefix=True):
        self.op = op
        self.operand = operand
        self.prefix = prefix

class AssignmentNode(Node):
    def __init__(self, op, target, value):
        self.op = op
        self.target = target
        self.value = value

class ConditionalNode(Node):
    def __init__(self, cond, then_expr, else_expr):
        self.cond = cond
        self.then_expr = then_expr
        self.else_expr = else_expr

class CallNode(Node):
    def __init__(self, func, args):
        self.func = func
        self.args = args

class MemberAccessNode(Node):
    def __init__(self, obj, member, is_arrow=False):
        self.obj = obj
        self.member = member
        self.is_arrow = is_arrow

class IndexNode(Node):
    def __init__(self, array, index):
        self.array = array
        self.index = index

class CastNode(Node):
    def __init__(self, target_type, expr):
        self.target_type = target_type
        self.expr = expr

class SizeofNode(Node):
    def __init__(self, target_type=None, expr=None):
        self.target_type = target_type
        self.expr = expr

class VarDeclNode(Node):
    def __init__(self, var_type, name, init=None, is_static=False, array_sizes=None):
        self.var_type = var_type
        self.name = name
        self.init = init
        self.is_static = is_static
        self.array_sizes = array_sizes

class ArrayInitNode(Node):
    def __init__(self, elements):
        self.elements = elements

class FuncDefNode(Node):
    def __init__(self, return_type, name, params, body, var_args=False):
        self.return_type = return_type
        self.name = name
        self.params = params
        self.body = body
        self.var_args = var_args

class IfNode(Node):
    def __init__(self, cond, then_stmt, else_stmt=None):
        self.cond = cond
        self.then_stmt = then_stmt
        self.else_stmt = else_stmt

class ForNode(Node):
    def __init__(self, init, cond, update, body):
        self.init = init
        self.cond = cond
        self.update = update
        self.body = body

class WhileNode(Node):
    def __init__(self, cond, body):
        self.cond = cond
        self.body = body

class DoWhileNode(Node):
    def __init__(self, body, cond):
        self.body = body
        self.cond = cond

class SwitchNode(Node):
    def __init__(self, expr, body):
        self.expr = expr
        self.body = body

class BreakNode(Node):
    pass

class ContinueNode(Node):
    pass

class ReturnNode(Node):
    def __init__(self, value=None):
        self.value = value

class GotoNode(Node):
    def __init__(self, label):
        self.label = label

class LabelNode(Node):
    def __init__(self, name, stmt=None):
        self.name = name
        self.stmt = stmt

class BlockNode(Node):
    def __init__(self, statements):
        self.statements = statements

class ExprStmtNode(Node):
    def __init__(self, expr):
        self.expr = expr

class EmptyNode(Node):
    pass

class TypedefNode(Node):
    def __init__(self, name, target_type):
        self.name = name
        self.target_type = target_type

class StructDeclNode(Node):
    def __init__(self, name, is_union, struct_type=None):
        self.name = name
        self.is_union = is_union
        self.struct_type = struct_type

class EnumDeclNode(Node):
    def __init__(self, name, values):
        self.name = name
        self.values = values

# ============================================================
# EXCEPTIONS FOR CONTROL FLOW
# ============================================================

class BreakException(Exception):
    pass

class ContinueException(Exception):
    pass

class ReturnException(Exception):
    def __init__(self, value):
        self.value = value

class GotoException(Exception):
    def __init__(self, label):
        self.label = label

class ProgramError(Exception):
    pass

# ============================================================
# TOKENS
# ============================================================

class Token:
    __slots__ = ['type', 'value', 'pos', 'line', 'col']

    def __init__(self, type, value=None, pos=0, line=1, col=0):
        self.type = type
        self.value = value
        self.pos = pos
        self.line = line
        self.col = col

    def __repr__(self):
        return f"Token({self.type}, {self.value!r})"

BUILTIN_MACROS = set()

# ============================================================
# LEXER
# ============================================================

class Lexer:
    T_NONE = 0
    T_COMMA = 1
    T_ASSIGN = 2
    T_ADD_ASSIGN = 3
    T_SUB_ASSIGN = 4
    T_MUL_ASSIGN = 5
    T_DIV_ASSIGN = 6
    T_MOD_ASSIGN = 7
    T_SHL_ASSIGN = 8
    T_SHR_ASSIGN = 9
    T_AND_ASSIGN = 10
    T_OR_ASSIGN = 11
    T_XOR_ASSIGN = 12
    T_QUESTION = 13
    T_COLON = 14
    T_LOGICAL_OR = 15
    T_LOGICAL_AND = 16
    T_BITWISE_OR = 17
    T_BITWISE_XOR = 18
    T_AMPERSAND = 19
    T_EQUAL = 20
    T_NOT_EQUAL = 21
    T_LESS_THAN = 22
    T_GREATER_THAN = 23
    T_LESS_EQUAL = 24
    T_GREATER_EQUAL = 25
    T_SHIFT_LEFT = 26
    T_SHIFT_RIGHT = 27
    T_PLUS = 28
    T_MINUS = 29
    T_ASTERISK = 30
    T_SLASH = 31
    T_MODULUS = 32
    T_INCREMENT = 33
    T_DECREMENT = 34
    T_UNARY_NOT = 35
    T_TILDE = 36
    T_SIZEOF = 37
    T_LBRACKET = 38
    T_RBRACKET = 39
    T_DOT = 40
    T_ARROW = 41
    T_LPAREN = 42
    T_RPAREN = 43
    T_IDENTIFIER = 44
    T_INT_CONST = 45
    T_FP_CONST = 46
    T_STRING_CONST = 47
    T_CHAR_CONST = 48
    T_SEMICOLON = 49
    T_ELLIPSIS = 50
    T_LBRACE = 51
    T_RBRACE = 52
    T_INT_TYPE = 53
    T_CHAR_TYPE = 54
    T_FLOAT_TYPE = 55
    T_DOUBLE_TYPE = 56
    T_VOID_TYPE = 57
    T_ENUM_TYPE = 58
    T_LONG_TYPE = 59
    T_SIGNED_TYPE = 60
    T_SHORT_TYPE = 61
    T_STATIC_TYPE = 62
    T_AUTO_TYPE = 63
    T_REGISTER_TYPE = 64
    T_EXTERN_TYPE = 65
    T_STRUCT_TYPE = 66
    T_UNION_TYPE = 67
    T_UNSIGNED_TYPE = 68
    T_TYPEDEF = 69
    T_CONTINUE = 70
    T_DO = 71
    T_ELSE = 72
    T_FOR = 73
    T_GOTO = 74
    T_IF = 75
    T_WHILE = 76
    T_BREAK = 77
    T_SWITCH = 78
    T_CASE = 79
    T_DEFAULT = 80
    T_RETURN = 81
    T_EOF = 82

    RESERVED_WORDS = {
        'auto': T_AUTO_TYPE, 'break': T_BREAK, 'case': T_CASE,
        'char': T_CHAR_TYPE, 'continue': T_CONTINUE, 'default': T_DEFAULT,
        'do': T_DO, 'double': T_DOUBLE_TYPE, 'else': T_ELSE,
        'enum': T_ENUM_TYPE, 'extern': T_EXTERN_TYPE, 'float': T_FLOAT_TYPE,
        'for': T_FOR, 'goto': T_GOTO, 'if': T_IF, 'int': T_INT_TYPE,
        'long': T_LONG_TYPE, 'register': T_REGISTER_TYPE, 'return': T_RETURN,
        'short': T_SHORT_TYPE, 'signed': T_SIGNED_TYPE, 'sizeof': T_SIZEOF,
        'static': T_STATIC_TYPE, 'struct': T_STRUCT_TYPE, 'switch': T_SWITCH,
        'typedef': T_TYPEDEF, 'union': T_UNION_TYPE, 'unsigned': T_UNSIGNED_TYPE,
        'void': T_VOID_TYPE, 'while': T_WHILE,
    }

    def __init__(self, source):
        self.source = source
        self.pos = 0
        self.line = 1
        self.col = 0
        self.tokens = []
        self.macros = {}

    def error(self, msg):
        raise ProgramError(f"Lexer error at line {self.line}: {msg}")

    def peek(self, offset=0):
        p = self.pos + offset
        if p < len(self.source):
            return self.source[p]
        return ''

    def advance(self):
        ch = self.source[self.pos]
        self.pos += 1
        if ch == '\n':
            self.line += 1
            self.col = 0
        else:
            self.col += 1
        return ch

    def is_ident_start(self, ch):
        return ch.isalpha() or ch == '_'

    def is_ident(self, ch):
        return ch.isalnum() or ch == '_'

    def is_hex_digit(self, ch):
        return ch in '0123456789abcdefABCDEF'

    def is_digit(self, ch, base=10):
        if base <= 10:
            return ch.isdigit() and int(ch) < base if ch.isdigit() else False
        return ch.isdigit() or (ch.lower() in 'abcdef')

    def get_digit(self, ch):
        if ch <= '9':
            return ord(ch) - ord('0')
        elif ch <= 'F':
            return ord(ch) - ord('A') + 10
        else:
            return ord(ch) - ord('a') + 10

    def skip_whitespace_and_comments(self):
        while self.pos < len(self.source):
            ch = self.peek()
            if ch in ' \t\r\n':
                self.advance()
            elif ch == '/' and self.peek(1) == '/':
                while self.pos < len(self.source) and self.peek() != '\n':
                    self.advance()
            elif ch == '/' and self.peek(1) == '*':
                self.advance(); self.advance()
                while self.pos < len(self.source):
                    if self.peek() == '*' and self.peek(1) == '/':
                        self.advance(); self.advance()
                        break
                    self.advance()
            elif ch == '\\' and self.peek(1) == '\n':
                self.advance(); self.advance()
            else:
                break

    def read_number(self):
        result = 0
        base = 10
        is_fp = False
        fp_result = 0.0

        if self.peek() == '0':
            self.advance()
            if self.pos < len(self.source):
                ch = self.peek()
                if ch in 'xX':
                    base = 16; self.advance()
                elif ch in 'bB':
                    base = 2; self.advance()
                elif ch != '.' and ch not in 'eE':
                    base = 8

        while self.pos < len(self.source) and self.is_digit(self.peek(), base):
            result = result * base + self.get_digit(self.advance())

        if self.peek() in 'uU':
            self.advance()
        if self.peek() in 'lL':
            self.advance()

        if self.pos >= len(self.source) or (self.peek() != '.' and self.peek() not in 'eE'):
            self.tokens.append(Token(self.T_INT_CONST, ('int', result), self.pos, self.line, self.col))
            return

        is_fp = True
        fp_result = float(result)

        if self.peek() == '.':
            self.advance()
            fp_div = 1.0 / base
            while self.pos < len(self.source) and self.is_digit(self.peek(), base):
                fp_result += self.get_digit(self.advance()) * fp_div
                fp_div /= base

        if self.pos < len(self.source) and self.peek() in 'eE':
            self.advance()
            exp_sign = 1
            if self.peek() == '-':
                exp_sign = -1; self.advance()
            elif self.peek() == '+':
                self.advance()
            exp_val = 0
            while self.pos < len(self.source) and self.is_digit(self.peek(), base):
                exp_val = exp_val * base + self.get_digit(self.advance())
            fp_result *= base ** (exp_val * exp_sign)

        if self.peek() in 'fF':
            self.advance()

        self.tokens.append(Token(self.T_FP_CONST, ('fp', fp_result), self.pos, self.line, self.col))

    def read_identifier(self):
        start = self.pos
        while self.pos < len(self.source) and self.is_ident(self.peek()):
            self.advance()
        return self.source[start:self.pos]

    def unescape_char(self, ch):
        escapes = {'n': 10, 't': 9, 'r': 13, '\\': 92, "'": 39, '"': 34,
                   '0': 0, 'a': 7, 'b': 8, 'f': 12, 'v': 11, '?': 63}
        if ch in escapes:
            return escapes[ch]
        return ord(ch)

    def read_string(self, end_char):
        result = []
        while self.pos < len(self.source) and self.peek() != end_char:
            ch = self.advance()
            if ch == '\\':
                ch = self.advance()
                if ch == 'n': result.append('\n')
                elif ch == 't': result.append('\t')
                elif ch == 'r': result.append('\r')
                elif ch == '\\': result.append('\\')
                elif ch == "'": result.append("'")
                elif ch == '"': result.append('"')
                elif ch == '0': result.append('\0')
                elif ch == 'a': result.append('\a')
                elif ch == 'b': result.append('\b')
                elif ch == 'f': result.append('\f')
                elif ch == 'v': result.append('\v')
                elif ch == '\n': pass
                elif ch in '01234567':
                    oct_val = self.get_digit(ch)
                    count = 0
                    while count < 2 and self.pos < len(self.source) and self.peek() in '01234567':
                        oct_val = oct_val * 8 + self.get_digit(self.advance())
                        count += 1
                    result.append(chr(oct_val))
                elif ch == 'x':
                    hex_val = 0
                    count = 0
                    while count < 2 and self.pos < len(self.source) and self.is_hex_digit(self.peek()):
                        hex_val = hex_val * 16 + self.get_digit(self.advance())
                        count += 1
                    result.append(chr(hex_val))
                else:
                    result.append(ch)
            else:
                result.append(ch)
        if self.pos < len(self.source) and self.peek() == end_char:
            self.advance()
        return ''.join(result)

    def read_char_constant(self):
        self.advance()  # skip opening '
        ch = self.peek()
        val = 0
        if ch == '\\':
            self.advance()
            ch = self.advance()
            if ch in '01234567':
                val = self.get_digit(ch)
                count = 0
                while count < 2 and self.pos < len(self.source) and self.peek() in '01234567':
                    val = val * 8 + self.get_digit(self.advance())
                    count += 1
            elif ch == 'x':
                val = 0
                count = 0
                while count < 2 and self.pos < len(self.source) and self.is_hex_digit(self.peek()):
                    val = val * 16 + self.get_digit(self.advance())
                    count += 1
            else:
                val = self.unescape_char(ch)
        else:
            val = ord(self.advance())
        if self.peek() == '\'':
            self.advance()
        self.tokens.append(Token(self.T_CHAR_CONST, val, self.pos, self.line, self.col))

    def tokenize(self):
        while self.pos < len(self.source):
            self.skip_whitespace_and_comments()
            if self.pos >= len(self.source):
                break
            ch = self.peek()
            sl, sc = self.line, self.col

            if ch == '#':
                self.handle_preprocessor()
                continue

            if ch.isdigit():
                self.read_number()
                continue

            if ch == '_' or ch.isalpha():
                name = self.read_identifier()
                kw = self.RESERVED_WORDS.get(name)
                if kw is not None:
                    self.tokens.append(Token(kw, name, self.pos, sl, sc))
                else:
                    self.tokens.append(Token(self.T_IDENTIFIER, name, self.pos, sl, sc))
                continue

            if ch == '"':
                self.advance()
                s = self.read_string('"')
                self.tokens.append(Token(self.T_STRING_CONST, s, self.pos, sl, sc))
                continue

            if ch == '\'':
                self.read_char_constant()
                continue

            ch2 = self.peek(1)
            ch3 = self.peek(2)

            # Multi-char operators
            if ch == '.' and ch2 == '.' and ch3 == '.':
                self.advance(); self.advance(); self.advance()
                self.tokens.append(Token(self.T_ELLIPSIS, None, self.pos, sl, sc)); continue
            if ch == '+':
                if ch2 == '+': self.advance(); self.advance(); self.tokens.append(Token(self.T_INCREMENT, None, self.pos, sl, sc))
                elif ch2 == '=': self.advance(); self.advance(); self.tokens.append(Token(self.T_ADD_ASSIGN, None, self.pos, sl, sc))
                else: self.advance(); self.tokens.append(Token(self.T_PLUS, None, self.pos, sl, sc))
                continue
            if ch == '-':
                if ch2 == '-': self.advance(); self.advance(); self.tokens.append(Token(self.T_DECREMENT, None, self.pos, sl, sc))
                elif ch2 == '=': self.advance(); self.advance(); self.tokens.append(Token(self.T_SUB_ASSIGN, None, self.pos, sl, sc))
                elif ch2 == '>': self.advance(); self.advance(); self.tokens.append(Token(self.T_ARROW, None, self.pos, sl, sc))
                else: self.advance(); self.tokens.append(Token(self.T_MINUS, None, self.pos, sl, sc))
                continue
            if ch == '*':
                if ch2 == '=': self.advance(); self.advance(); self.tokens.append(Token(self.T_MUL_ASSIGN, None, self.pos, sl, sc))
                else: self.advance(); self.tokens.append(Token(self.T_ASTERISK, None, self.pos, sl, sc))
                continue
            if ch == '/':
                if ch2 == '=': self.advance(); self.advance(); self.tokens.append(Token(self.T_DIV_ASSIGN, None, self.pos, sl, sc))
                else: self.advance(); self.tokens.append(Token(self.T_SLASH, None, self.pos, sl, sc))
                continue
            if ch == '%':
                if ch2 == '=': self.advance(); self.advance(); self.tokens.append(Token(self.T_MOD_ASSIGN, None, self.pos, sl, sc))
                else: self.advance(); self.tokens.append(Token(self.T_MODULUS, None, self.pos, sl, sc))
                continue
            if ch == '=':
                if ch2 == '=': self.advance(); self.advance(); self.tokens.append(Token(self.T_EQUAL, None, self.pos, sl, sc))
                else: self.advance(); self.tokens.append(Token(self.T_ASSIGN, None, self.pos, sl, sc))
                continue
            if ch == '!':
                if ch2 == '=': self.advance(); self.advance(); self.tokens.append(Token(self.T_NOT_EQUAL, None, self.pos, sl, sc))
                else: self.advance(); self.tokens.append(Token(self.T_UNARY_NOT, None, self.pos, sl, sc))
                continue
            if ch == '<':
                if ch2 == '<' and ch3 == '=': self.advance(); self.advance(); self.advance(); self.tokens.append(Token(self.T_SHL_ASSIGN, None, self.pos, sl, sc))
                elif ch2 == '<': self.advance(); self.advance(); self.tokens.append(Token(self.T_SHIFT_LEFT, None, self.pos, sl, sc))
                elif ch2 == '=': self.advance(); self.advance(); self.tokens.append(Token(self.T_LESS_EQUAL, None, self.pos, sl, sc))
                else: self.advance(); self.tokens.append(Token(self.T_LESS_THAN, None, self.pos, sl, sc))
                continue
            if ch == '>':
                if ch2 == '>' and ch3 == '=': self.advance(); self.advance(); self.advance(); self.tokens.append(Token(self.T_SHR_ASSIGN, None, self.pos, sl, sc))
                elif ch2 == '>': self.advance(); self.advance(); self.tokens.append(Token(self.T_SHIFT_RIGHT, None, self.pos, sl, sc))
                elif ch2 == '=': self.advance(); self.advance(); self.tokens.append(Token(self.T_GREATER_EQUAL, None, self.pos, sl, sc))
                else: self.advance(); self.tokens.append(Token(self.T_GREATER_THAN, None, self.pos, sl, sc))
                continue
            if ch == '&':
                if ch2 == '&': self.advance(); self.advance(); self.tokens.append(Token(self.T_LOGICAL_AND, None, self.pos, sl, sc))
                elif ch2 == '=': self.advance(); self.advance(); self.tokens.append(Token(self.T_AND_ASSIGN, None, self.pos, sl, sc))
                else: self.advance(); self.tokens.append(Token(self.T_AMPERSAND, None, self.pos, sl, sc))
                continue
            if ch == '|':
                if ch2 == '|': self.advance(); self.advance(); self.tokens.append(Token(self.T_LOGICAL_OR, None, self.pos, sl, sc))
                elif ch2 == '=': self.advance(); self.advance(); self.tokens.append(Token(self.T_OR_ASSIGN, None, self.pos, sl, sc))
                else: self.advance(); self.tokens.append(Token(self.T_BITWISE_OR, None, self.pos, sl, sc))
                continue
            if ch == '^':
                if ch2 == '=': self.advance(); self.advance(); self.tokens.append(Token(self.T_XOR_ASSIGN, None, self.pos, sl, sc))
                else: self.advance(); self.tokens.append(Token(self.T_BITWISE_XOR, None, self.pos, sl, sc))
                continue
            if ch == '?': self.advance(); self.tokens.append(Token(self.T_QUESTION, None, self.pos, sl, sc)); continue
            if ch == ':': self.advance(); self.tokens.append(Token(self.T_COLON, None, self.pos, sl, sc)); continue
            if ch == ';': self.advance(); self.tokens.append(Token(self.T_SEMICOLON, None, self.pos, sl, sc)); continue
            if ch == ',': self.advance(); self.tokens.append(Token(self.T_COMMA, None, self.pos, sl, sc)); continue
            if ch == '(': self.advance(); self.tokens.append(Token(self.T_LPAREN, None, self.pos, sl, sc)); continue
            if ch == ')': self.advance(); self.tokens.append(Token(self.T_RPAREN, None, self.pos, sl, sc)); continue
            if ch == '{': self.advance(); self.tokens.append(Token(self.T_LBRACE, None, self.pos, sl, sc)); continue
            if ch == '}': self.advance(); self.tokens.append(Token(self.T_RBRACE, None, self.pos, sl, sc)); continue
            if ch == '[': self.advance(); self.tokens.append(Token(self.T_LBRACKET, None, self.pos, sl, sc)); continue
            if ch == ']': self.advance(); self.tokens.append(Token(self.T_RBRACKET, None, self.pos, sl, sc)); continue
            if ch == '~': self.advance(); self.tokens.append(Token(self.T_TILDE, None, self.pos, sl, sc)); continue
            if ch == '.': self.advance(); self.tokens.append(Token(self.T_DOT, None, self.pos, sl, sc)); continue

            self.error(f"unexpected character: {ch!r}")

        self.tokens.append(Token(self.T_EOF, None, self.pos, self.line, self.col))

    def handle_preprocessor(self):
        self.advance()  # skip '#'
        while self.pos < len(self.source) and self.peek() in ' \t':
            self.advance()
        start = self.pos
        while self.pos < len(self.source) and (self.peek().isalpha() or self.peek() == '_'):
            self.advance()
        directive = self.source[start:self.pos]

        if directive == 'define':
            self.handle_define()
        elif directive == 'include':
            self.handle_include()
        elif directive in ('if', 'ifdef', 'ifndef', 'else', 'endif', 'elif'):
            self.handle_conditional(directive)
        elif directive == 'undef':
            self.handle_undef()
        else:
            while self.pos < len(self.source) and self.peek() != '\n':
                self.advance()

    def handle_define(self):
        while self.pos < len(self.source) and self.peek() in ' \t':
            self.advance()
        start = self.pos
        while self.pos < len(self.source) and (self.peek().isalnum() or self.peek() == '_'):
            self.advance()
        name = self.source[start:self.pos]

        params = None
        if self.pos < len(self.source) and self.peek() == '(':
            self.advance()
            params = []
            while self.pos < len(self.source) and self.peek() != ')':
                while self.pos < len(self.source) and self.peek() in ' \t':
                    self.advance()
                if self.peek() == ')':
                    break
                if self.peek() == '.' and self.peek(1) == '.' and self.peek(2) == '.':
                    self.advance(); self.advance(); self.advance()
                    params.append('...')
                    while self.pos < len(self.source) and self.peek() != ')':
                        self.advance()
                    break
                pstart = self.pos
                while self.pos < len(self.source) and (self.peek().isalnum() or self.peek() == '_'):
                    self.advance()
                params.append(self.source[pstart:self.pos])
                while self.pos < len(self.source) and self.peek() in ' \t':
                    self.advance()
                if self.peek() == ',':
                    self.advance()
            if self.peek() == ')':
                self.advance()

        while self.pos < len(self.source) and self.peek() in ' \t':
            self.advance()
        body = []
        while self.pos < len(self.source):
            ch = self.peek()
            if ch == '\n':
                if body and body[-1] == '\\':
                    body.pop()
                    self.advance()
                    continue
                break
            body.append(self.advance())
        body_str = ''.join(body).strip()
        self.macros[name] = (params, body_str)

    def handle_include(self):
        while self.pos < len(self.source) and self.peek() in ' \t':
            self.advance()
        while self.pos < len(self.source) and self.peek() != '\n':
            self.advance()

    def handle_conditional(self, directive):
        if directive == 'ifdef':
            while self.pos < len(self.source) and self.peek() in ' \t':
                self.advance()
            start = self.pos
            while self.pos < len(self.source) and (self.peek().isalnum() or self.peek() == '_'):
                self.advance()
            name = self.source[start:self.pos]
            defined = name in self.macros or name in BUILTIN_MACROS
            while self.pos < len(self.source) and self.peek() != '\n':
                self.advance()
            if not defined:
                self.skip_conditional_block()
        elif directive == 'ifndef':
            while self.pos < len(self.source) and self.peek() in ' \t':
                self.advance()
            start = self.pos
            while self.pos < len(self.source) and (self.peek().isalnum() or self.peek() == '_'):
                self.advance()
            name = self.source[start:self.pos]
            defined = name in self.macros or name in BUILTIN_MACROS
            while self.pos < len(self.source) and self.peek() != '\n':
                self.advance()
            if defined:
                self.skip_conditional_block()
        elif directive == 'if':
            cond_start = self.pos
            while self.pos < len(self.source) and self.peek() != '\n':
                self.advance()
            cond_str = self.source[cond_start:self.pos].strip()
            result = self.eval_preprocessor_expr(cond_str)
            if not result:
                self.skip_conditional_block()
        elif directive == 'else':
            self.skip_conditional_block()
        elif directive == 'elif':
            self.skip_conditional_block()
        elif directive == 'endif':
            while self.pos < len(self.source) and self.peek() != '\n':
                self.advance()

    def skip_conditional_block(self):
        depth = 1
        while self.pos < len(self.source) and depth > 0:
            while self.pos < len(self.source) and self.peek() in ' \t\r\n':
                self.advance()
            if self.pos >= len(self.source):
                break
            if self.peek() == '/' and self.peek(1) == '/':
                while self.pos < len(self.source) and self.peek() != '\n':
                    self.advance()
                continue
            if self.peek() == '/' and self.peek(1) == '*':
                self.advance(); self.advance()
                while self.pos < len(self.source):
                    if self.peek() == '*' and self.peek(1) == '/':
                        self.advance(); self.advance(); break
                    self.advance()
                continue
            if self.peek() == '#':
                self.advance()
                while self.pos < len(self.source) and self.peek() in ' \t':
                    self.advance()
                start = self.pos
                while self.pos < len(self.source) and (self.peek().isalpha() or self.peek() == '_'):
                    self.advance()
                directive = self.source[start:self.pos]
                if directive in ('if', 'ifdef', 'ifndef'):
                    depth += 1
                elif directive == 'endif':
                    depth -= 1
                elif directive == 'else' and depth == 1:
                    break
                while self.pos < len(self.source) and self.peek() != '\n':
                    self.advance()
            else:
                self.advance()

    def handle_undef(self):
        while self.pos < len(self.source) and self.peek() in ' \t':
            self.advance()
        start = self.pos
        while self.pos < len(self.source) and (self.peek().isalnum() or self.peek() == '_'):
            self.advance()
        name = self.source[start:self.pos]
        if name in self.macros:
            del self.macros[name]
        while self.pos < len(self.source) and self.peek() != '\n':
            self.advance()

    def eval_preprocessor_expr(self, expr_str):
        expr_str = self.expand_macros_in_expr(expr_str)
        expr_str = re.sub(r'defined\s*\(\s*(\w+)\s*\)', lambda m: '1' if m.group(1) in self.macros or m.group(1) in BUILTIN_MACROS else '0', expr_str)
        expr_str = re.sub(r'defined\s+(\w+)', lambda m: '1' if m.group(1) in self.macros or m.group(1) in BUILTIN_MACROS else '0', expr_str)
        expr_str = re.sub(r'[a-zA-Z_]\w*', '0', expr_str)
        try:
            return int(eval(expr_str, {'__builtins__': {}}, {})) != 0
        except:
            return False

    def expand_macros_in_expr(self, expr_str):
        result = expr_str
        for name, (params, body) in self.macros.items():
            if params is None:
                result = result.replace(name, body)
        return result

    def get_macro_value(self, name):
        if name in self.macros:
            params, body = self.macros[name]
            if params is None:
                return body
        return None

    def expand_macros_in_token_list(self, tokens):
        result = []
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            if tok.type == self.T_IDENTIFIER and tok.value in self.macros:
                params, body = self.macros[tok.value]
                if params is None:
                    sub = Lexer(body)
                    sub.macros = self.macros
                    sub.tokenize()
                    result.extend(sub.tokens[:-1])
                    i += 1
                    continue
                elif params is not None and i + 1 < len(tokens) and tokens[i + 1].type == self.T_LPAREN:
                    j = i + 2
                    args = []
                    current = []
                    depth = 1
                    while j < len(tokens) and depth > 0:
                        if tokens[j].type == self.T_LPAREN:
                            depth += 1; current.append(tokens[j])
                        elif tokens[j].type == self.T_RPAREN:
                            depth -= 1
                            if depth > 0:
                                current.append(tokens[j])
                            else:
                                args.append(current); break
                        elif tokens[j].type == self.T_COMMA and depth == 1:
                            args.append(current); current = []
                        else:
                            current.append(tokens[j])
                        j += 1
                    i = j + 1
                    body_lex = Lexer(body)
                    body_lex.macros = self.macros
                    body_lex.tokenize()
                    body_tokens = body_lex.tokens[:-1]
                    expanded = []
                    for bt in body_tokens:
                        if bt.type == self.T_IDENTIFIER and bt.value in params:
                            pidx = params.index(bt.value)
                            if pidx < len(args):
                                expanded.extend(args[pidx])
                        else:
                            expanded.append(bt)
                    result.extend(expanded)
                    continue
            result.append(tok)
            i += 1
        return result

import re

# ============================================================
# PARSER
# ============================================================

class Parser:
    def __init__(self, tokens, lexer):
        self.tokens = tokens
        self.pos = 0
        self.lexer = lexer

    def error(self, msg):
        tok = self.peek()
        raise ProgramError(f"Parse error at line {tok.line}: {msg} (got {tok.type}: {tok.value!r})")

    def peek(self, offset=0):
        idx = self.pos + offset
        if idx < len(self.tokens):
            return self.tokens[idx]
        return self.tokens[-1]

    def advance(self):
        tok = self.tokens[self.pos]
        if self.pos < len(self.tokens) - 1:
            self.pos += 1
        return tok

    def check(self, type):
        return self.peek().type == type

    def match(self, type):
        if self.peek().type == type:
            return self.advance()
        return None

    def expect(self, type):
        if self.peek().type == type:
            return self.advance()
        self.error(f"expected token type {type}")

    def is_type_start(self, tok):
        return tok.type in (Lexer.T_INT_TYPE, Lexer.T_CHAR_TYPE, Lexer.T_FLOAT_TYPE,
                           Lexer.T_DOUBLE_TYPE, Lexer.T_VOID_TYPE, Lexer.T_ENUM_TYPE,
                           Lexer.T_LONG_TYPE, Lexer.T_SIGNED_TYPE, Lexer.T_SHORT_TYPE,
                           Lexer.T_STATIC_TYPE, Lexer.T_AUTO_TYPE, Lexer.T_REGISTER_TYPE,
                           Lexer.T_EXTERN_TYPE, Lexer.T_STRUCT_TYPE, Lexer.T_UNION_TYPE,
                           Lexer.T_UNSIGNED_TYPE, Lexer.T_TYPEDEF)

    def parse(self):
        declarations = []
        while not self.check(Lexer.T_EOF):
            decl = self.parse_toplevel()
            if decl is not None:
                declarations.append(decl)
        return declarations

    def parse_type_modifiers(self):
        is_static = False; is_extern = False; is_typedef = False
        is_unsigned = False; is_signed = False; is_short = False; is_long = False
        while True:
            tok = self.peek()
            if tok.type == Lexer.T_STATIC_TYPE: is_static = True; self.advance()
            elif tok.type == Lexer.T_EXTERN_TYPE: is_extern = True; self.advance()
            elif tok.type == Lexer.T_TYPEDEF: is_typedef = True; self.advance()
            elif tok.type == Lexer.T_UNSIGNED_TYPE: is_unsigned = True; self.advance()
            elif tok.type == Lexer.T_SIGNED_TYPE: is_signed = True; self.advance()
            elif tok.type == Lexer.T_SHORT_TYPE: is_short = True; self.advance()
            elif tok.type == Lexer.T_LONG_TYPE: is_long = True; self.advance()
            elif tok.type == Lexer.T_REGISTER_TYPE: self.advance()
            elif tok.type == Lexer.T_AUTO_TYPE: self.advance()
            else: break
        return (is_static, is_extern, is_typedef, is_unsigned, is_signed, is_short, is_long)

    def resolve_base_type(self, is_unsigned, is_short, is_long, base_type):
        if base_type is None:
            if is_unsigned:
                if is_short: return BaseType.UNSIGNED_SHORT
                elif is_long: return BaseType.UNSIGNED_LONG
                else: return BaseType.UNSIGNED_INT
            elif is_short: return BaseType.SHORT
            elif is_long: return BaseType.LONG
            else: return BaseType.INT
        return base_type

    def parse_struct_or_union(self):
        is_union = self.peek().type == Lexer.T_UNION_TYPE
        self.advance()
        name = None
        if self.check(Lexer.T_IDENTIFIER):
            name = self.advance().value
        members = []
        has_body = self.check(Lexer.T_LBRACE)
        if has_body:
            self.advance()
            while not self.check(Lexer.T_RBRACE):
                members.extend(self.parse_struct_member_decls())
            self.advance()
            members_with_offsets = self.compute_struct_offsets(members, is_union)
            total_size, total_align = compute_struct_size(
                [(n, t, o) for n, t, o in members_with_offsets], is_union)
            st = ValueType(BaseType.UNION if is_union else BaseType.STRUCT,
                           sizeof=total_size, align=total_align, identifier=name)
            for mn, mt, mo in members_with_offsets:
                st.members[mn] = (mt, mo)
                st.member_order.append((mn, mt, mo))
            return st
        else:
            return ('struct_ref', name, is_union)

    def parse_enum(self):
        self.advance()  # skip 'enum'
        name = None
        if self.check(Lexer.T_IDENTIFIER):
            name = self.advance().value
        enum_values = []
        if self.check(Lexer.T_LBRACE):
            self.advance()
            next_val = 0
            while not self.check(Lexer.T_RBRACE):
                if self.check(Lexer.T_IDENTIFIER):
                    vname = self.advance().value
                    if self.match(Lexer.T_ASSIGN):
                        vexpr = self.parse_expression()
                        next_val = self._eval_const_expr(vexpr)
                    enum_values.append((vname, next_val))
                    next_val += 1
                if not self.match(Lexer.T_COMMA):
                    break
            self.advance()
        vt = ValueType(BaseType.ENUM, sizeof=4, align=4)
        for n, v in enum_values:
            vt.enum_values[n] = v
        return vt, name, enum_values

    def parse_toplevel(self):
        while self.match(Lexer.T_SEMICOLON):
            pass
        if self.check(Lexer.T_EOF):
            return None

        is_static, is_extern, is_typedef, is_unsigned, is_signed, is_short, is_long = self.parse_type_modifiers()

        base_type = None
        struct_type = None
        is_struct = False
        enum_vt = None
        enum_name = None
        enum_values = []

        tok = self.peek()
        if tok.type == Lexer.T_INT_TYPE:
            base_type = BaseType.UNSIGNED_INT if is_unsigned else BaseType.INT; self.advance()
        elif tok.type == Lexer.T_CHAR_TYPE:
            base_type = BaseType.UNSIGNED_CHAR if is_unsigned else BaseType.CHAR; self.advance()
        elif tok.type == Lexer.T_FLOAT_TYPE:
            base_type = BaseType.FP; self.advance()
        elif tok.type == Lexer.T_DOUBLE_TYPE:
            base_type = BaseType.FP; self.advance()
        elif tok.type == Lexer.T_VOID_TYPE:
            base_type = BaseType.VOID; self.advance()
        elif tok.type == Lexer.T_STRUCT_TYPE or tok.type == Lexer.T_UNION_TYPE:
            struct_type = self.parse_struct_or_union()
            is_struct = True
        elif tok.type == Lexer.T_ENUM_TYPE:
            enum_vt, enum_name, enum_values = self.parse_enum()
            base_type = BaseType.ENUM
        else:
            pass

        base = self.resolve_base_type(is_unsigned, is_short, is_long, base_type)

        if is_struct:
            base_vt = struct_type
        elif base_type == BaseType.ENUM:
            base_vt = enum_vt
        else:
            base_vt = get_base_type(base)

        if is_typedef:
            vt = base_vt
            while self.match(Lexer.T_ASTERISK):
                vt = get_pointer_type(vt) if isinstance(vt, ValueType) else ('pointer', vt)
            if self.check(Lexer.T_IDENTIFIER):
                typedef_name = self.advance().value
                self.expect(Lexer.T_SEMICOLON)
                return TypedefNode(typedef_name, vt)
            self.error("expected typedef name")

        vt = base_vt
        while self.match(Lexer.T_ASTERISK):
            vt = get_pointer_type(vt) if isinstance(vt, ValueType) else ('pointer', vt)

        if not self.check(Lexer.T_IDENTIFIER):
            if self.check(Lexer.T_SEMICOLON):
                self.advance()
                if isinstance(struct_type, ValueType):
                    return StructDeclNode(struct_type.identifier, struct_type.is_union(), struct_type)
                elif isinstance(struct_type, tuple) and struct_type[0] == "struct_ref":
                    return StructDeclNode(struct_type[1], struct_type[2], None)
                return None
            self.error("expected identifier")

        name = self.advance().value

        if self.check(Lexer.T_LPAREN):
            self.advance()
            params = []
            var_args = False
            if not self.check(Lexer.T_RPAREN):
                while True:
                    if self.check(Lexer.T_ELLIPSIS):
                        self.advance(); var_args = True; break
                    param = self.parse_param()
                    params.append(param)
                    if not self.match(Lexer.T_COMMA):
                        break
            self.expect(Lexer.T_RPAREN)
            if self.check(Lexer.T_LBRACE):
                body = self.parse_block()
                return FuncDefNode(vt, name, params, body, var_args)
            else:
                self.match(Lexer.T_SEMICOLON)
                return FuncDefNode(vt, name, params, None, var_args)

        decls = [self.parse_var_decl_rest(vt, name, is_static)]
        while self.match(Lexer.T_COMMA):
            t2 = base_vt
            while self.match(Lexer.T_ASTERISK):
                t2 = get_pointer_type(t2) if isinstance(t2, ValueType) else ('pointer', t2)
            name2 = self.advance().value
            decls.append(self.parse_var_decl_rest(t2, name2, is_static))
        self.expect(Lexer.T_SEMICOLON)
        return BlockNode(decls)

    def parse_param(self):
        is_unsigned, is_signed, is_short, is_long = False, False, False, False
        base_type = None
        struct_type = None
        is_struct = False

        while True:
            tok = self.peek()
            if tok.type == Lexer.T_UNSIGNED_TYPE: is_unsigned = True; self.advance()
            elif tok.type == Lexer.T_SIGNED_TYPE: self.advance()
            elif tok.type == Lexer.T_SHORT_TYPE: is_short = True; self.advance()
            elif tok.type == Lexer.T_LONG_TYPE: is_long = True; self.advance()
            elif tok.type == Lexer.T_INT_TYPE: base_type = BaseType.UNSIGNED_INT if is_unsigned else BaseType.INT; self.advance()
            elif tok.type == Lexer.T_CHAR_TYPE: base_type = BaseType.UNSIGNED_CHAR if is_unsigned else BaseType.CHAR; self.advance()
            elif tok.type == Lexer.T_FLOAT_TYPE: base_type = BaseType.FP; self.advance()
            elif tok.type == Lexer.T_DOUBLE_TYPE: base_type = BaseType.FP; self.advance()
            elif tok.type == Lexer.T_VOID_TYPE: base_type = BaseType.VOID; self.advance()
            elif tok.type == Lexer.T_STRUCT_TYPE or tok.type == Lexer.T_UNION_TYPE:
                struct_type = self.parse_struct_or_union()
                is_struct = True; base_type = BaseType.STRUCT; break
            elif tok.type == Lexer.T_ENUM_TYPE:
                struct_type, _, _ = self.parse_enum()
                base_type = BaseType.ENUM; break
            else: break

        if base_type is None:
            if is_unsigned:
                if is_short: base_type = BaseType.UNSIGNED_SHORT
                elif is_long: base_type = BaseType.UNSIGNED_LONG
                else: base_type = BaseType.UNSIGNED_INT
            elif is_short: base_type = BaseType.SHORT
            elif is_long: base_type = BaseType.LONG
            else: base_type = BaseType.INT

        if is_struct:
            vt = struct_type
        elif base_type == BaseType.ENUM:
            vt = struct_type
        else:
            vt = get_base_type(base_type)

        while self.match(Lexer.T_ASTERISK):
            vt = get_pointer_type(vt) if isinstance(vt, ValueType) else ('pointer', vt)

        if self.check(Lexer.T_LBRACKET):
            self.advance()
            if self.check(Lexer.T_RBRACKET):
                self.advance()
            else:
                self.parse_expression()
                self.expect(Lexer.T_RBRACKET)
            if isinstance(vt, ValueType):
                vt = get_pointer_type(vt.from_type if vt.is_array() else vt)

        pname = None
        if self.check(Lexer.T_IDENTIFIER):
            pname = self.advance().value
        return (pname, vt)

    def parse_var_decl_rest(self, vt, name, is_static):
        array_dims = []
        while self.check(Lexer.T_LBRACKET):
            self.advance()
            if self.check(Lexer.T_RBRACKET):
                array_dims.append(None); self.advance()
            else:
                array_dims.append(self.parse_expression())
                self.expect(Lexer.T_RBRACKET)
        init = None
        if self.match(Lexer.T_ASSIGN):
            if self.check(Lexer.T_LBRACE):
                init = self.parse_array_initializer()
            else:
                init = self.parse_assignment_expr()
        return VarDeclNode(vt, name, init, is_static, array_dims)

    def parse_array_initializer(self):
        self.expect(Lexer.T_LBRACE)
        elements = []
        if not self.check(Lexer.T_RBRACE):
            while True:
                if self.check(Lexer.T_LBRACE):
                    elements.append(self.parse_array_initializer())
                else:
                    elements.append(self.parse_assignment_expr())
                if not self.match(Lexer.T_COMMA):
                    break
                if self.check(Lexer.T_RBRACE):
                    break
        self.expect(Lexer.T_RBRACE)
        return ArrayInitNode(elements)

    def parse_struct_member_decls(self):
        is_unsigned = is_signed = is_short = is_long = False
        base_type = None
        struct_type = None
        is_struct = False

        while True:
            tok = self.peek()
            if tok.type == Lexer.T_UNSIGNED_TYPE: is_unsigned = True; self.advance()
            elif tok.type == Lexer.T_SIGNED_TYPE: self.advance()
            elif tok.type == Lexer.T_SHORT_TYPE: is_short = True; self.advance()
            elif tok.type == Lexer.T_LONG_TYPE: is_long = True; self.advance()
            elif tok.type == Lexer.T_INT_TYPE: base_type = BaseType.UNSIGNED_INT if is_unsigned else BaseType.INT; self.advance()
            elif tok.type == Lexer.T_CHAR_TYPE: base_type = BaseType.UNSIGNED_CHAR if is_unsigned else BaseType.CHAR; self.advance()
            elif tok.type == Lexer.T_FLOAT_TYPE: base_type = BaseType.FP; self.advance()
            elif tok.type == Lexer.T_DOUBLE_TYPE: base_type = BaseType.FP; self.advance()
            elif tok.type == Lexer.T_VOID_TYPE: base_type = BaseType.VOID; self.advance()
            elif tok.type == Lexer.T_STRUCT_TYPE or tok.type == Lexer.T_UNION_TYPE:
                struct_type = self.parse_struct_or_union()
                is_struct = True; base_type = BaseType.STRUCT; break
            else: break

        if base_type is None:
            if is_unsigned:
                if is_short: base_type = BaseType.UNSIGNED_SHORT
                elif is_long: base_type = BaseType.UNSIGNED_LONG
                else: base_type = BaseType.UNSIGNED_INT
            elif is_short: base_type = BaseType.SHORT
            elif is_long: base_type = BaseType.LONG
            else: base_type = BaseType.INT

        base_vt = struct_type if is_struct else get_base_type(base_type)
        members = []
        while True:
            vt = base_vt
            while self.match(Lexer.T_ASTERISK):
                vt = get_pointer_type(vt) if isinstance(vt, ValueType) else ('pointer', vt)
            mname = None
            if self.check(Lexer.T_IDENTIFIER):
                mname = self.advance().value
            array_dims = []
            while self.check(Lexer.T_LBRACKET):
                self.advance()
                if self.check(Lexer.T_RBRACKET):
                    array_dims.append(None); self.advance()
                else:
                    array_dims.append(self.parse_expression())
                    self.expect(Lexer.T_RBRACKET)
            actual_vt = vt
            for dim in reversed(array_dims):
                dim_size = self._eval_const_expr(dim) if dim is not None else 0
                if isinstance(actual_vt, ValueType):
                    actual_vt = get_array_type(actual_vt, dim_size)
                else:
                    actual_vt = ('array', actual_vt, dim_size)
            init = None
            if self.match(Lexer.T_ASSIGN):
                if self.check(Lexer.T_LBRACE):
                    init = self.parse_array_initializer()
                else:
                    init = self.parse_assignment_expr()
            members.append((actual_vt, mname, init))
            if not self.match(Lexer.T_COMMA):
                break
        self.expect(Lexer.T_SEMICOLON)
        return members

    def compute_struct_offsets(self, members, is_union):
        result = []
        if is_union:
            for vt, name, init in members:
                result.append((name, vt, 0))
        else:
            offset = 0
            for vt, name, init in members:
                al = type_alignof(vt) if isinstance(vt, ValueType) else 4
                sz = type_size(vt) if isinstance(vt, ValueType) else 4
                if al > 0:
                    offset = (offset + al - 1) // al * al
                result.append((name, vt, offset))
                offset += sz
        return result

    def _eval_const_expr(self, expr):
        if isinstance(expr, NumberNode): return expr.value
        elif isinstance(expr, CharNode): return expr.value
        elif isinstance(expr, BinaryOpNode):
            l = self._eval_const_expr(expr.left)
            r = self._eval_const_expr(expr.right)
            if expr.op == '+': return l + r
            if expr.op == '-': return l - r
            if expr.op == '*': return l * r
            if expr.op == '/': return l // r
        elif isinstance(expr, IdentifierNode):
            val = self.lexer.get_macro_value(expr.name)
            if val is not None:
                try: return int(val)
                except: pass
        return 0

    def parse_block(self):
        self.expect(Lexer.T_LBRACE)
        statements = []
        while not self.check(Lexer.T_RBRACE) and not self.check(Lexer.T_EOF):
            stmt = self.parse_statement()
            if stmt is not None:
                statements.append(stmt)
        self.expect(Lexer.T_RBRACE)
        return BlockNode(statements)

    def parse_statement(self):
        tok = self.peek()
        if tok.type == Lexer.T_SEMICOLON: self.advance(); return EmptyNode()
        if tok.type == Lexer.T_LBRACE: return self.parse_block()
        if self.is_type_start(tok): return self.parse_local_decl()
        if tok.type == Lexer.T_IF: return self.parse_if()
        if tok.type == Lexer.T_WHILE: return self.parse_while()
        if tok.type == Lexer.T_DO: return self.parse_do_while()
        if tok.type == Lexer.T_FOR: return self.parse_for()
        if tok.type == Lexer.T_SWITCH: return self.parse_switch()
        if tok.type == Lexer.T_BREAK: self.advance(); self.expect(Lexer.T_SEMICOLON); return BreakNode()
        if tok.type == Lexer.T_CONTINUE: self.advance(); self.expect(Lexer.T_SEMICOLON); return ContinueNode()
        if tok.type == Lexer.T_RETURN:
            self.advance()
            if self.check(Lexer.T_SEMICOLON): self.advance(); return ReturnNode(None)
            expr = self.parse_expression(); self.expect(Lexer.T_SEMICOLON); return ReturnNode(expr)
        if tok.type == Lexer.T_GOTO:
            self.advance()
            if self.check(Lexer.T_IDENTIFIER):
                label = self.advance().value; self.expect(Lexer.T_SEMICOLON); return GotoNode(label)
            self.error("expected label after goto")
        if tok.type == Lexer.T_IDENTIFIER and self.peek(1).type == Lexer.T_COLON:
            label = self.advance().value; self.advance()
            stmt = self.parse_statement()
            return LabelNode(label, stmt)
        expr = self.parse_expression(); self.expect(Lexer.T_SEMICOLON); return ExprStmtNode(expr)

    def parse_local_decl(self):
        is_static, is_extern, is_typedef, is_unsigned, is_signed, is_short, is_long = self.parse_type_modifiers()
        base_type = None; struct_type = None; is_struct = False; enum_vt = None; enum_values = []

        tok = self.peek()
        if tok.type == Lexer.T_INT_TYPE: base_type = BaseType.UNSIGNED_INT if is_unsigned else BaseType.INT; self.advance()
        elif tok.type == Lexer.T_CHAR_TYPE: base_type = BaseType.UNSIGNED_CHAR if is_unsigned else BaseType.CHAR; self.advance()
        elif tok.type == Lexer.T_FLOAT_TYPE: base_type = BaseType.FP; self.advance()
        elif tok.type == Lexer.T_DOUBLE_TYPE: base_type = BaseType.FP; self.advance()
        elif tok.type == Lexer.T_VOID_TYPE: base_type = BaseType.VOID; self.advance()
        elif tok.type == Lexer.T_STRUCT_TYPE or tok.type == Lexer.T_UNION_TYPE:
            struct_type = self.parse_struct_or_union(); is_struct = True
        elif tok.type == Lexer.T_ENUM_TYPE:
            enum_vt, _, enum_values = self.parse_enum(); base_type = BaseType.ENUM

        base = self.resolve_base_type(is_unsigned, is_short, is_long, base_type)
        if is_struct: base_vt = struct_type
        elif base_type == BaseType.ENUM: base_vt = enum_vt
        else: base_vt = get_base_type(base)

        if is_typedef:
            vt = base_vt
            while self.match(Lexer.T_ASTERISK):
                vt = get_pointer_type(vt) if isinstance(vt, ValueType) else ('pointer', vt)
            if self.check(Lexer.T_IDENTIFIER):
                tn = self.advance().value; self.expect(Lexer.T_SEMICOLON)
                return TypedefNode(tn, vt)

        decls = []
        while True:
            vt = base_vt
            while self.match(Lexer.T_ASTERISK):
                vt = get_pointer_type(vt) if isinstance(vt, ValueType) else ('pointer', vt)
            name = None
            if self.check(Lexer.T_IDENTIFIER):
                name = self.advance().value
            array_dims = []
            while self.check(Lexer.T_LBRACKET):
                self.advance()
                if self.check(Lexer.T_RBRACKET): array_dims.append(None); self.advance()
                else: array_dims.append(self.parse_expression()); self.expect(Lexer.T_RBRACKET)
            init = None
            if self.match(Lexer.T_ASSIGN):
                if self.check(Lexer.T_LBRACE): init = self.parse_array_initializer()
                else: init = self.parse_assignment_expr()
            decls.append(VarDeclNode(vt, name, init, is_static, array_dims))
            if not self.match(Lexer.T_COMMA): break
        self.expect(Lexer.T_SEMICOLON)
        return BlockNode(decls)

    def parse_if(self):
        self.advance(); self.expect(Lexer.T_LPAREN)
        cond = self.parse_expression(); self.expect(Lexer.T_RPAREN)
        then_stmt = self.parse_statement()
        else_stmt = None
        if self.match(Lexer.T_ELSE):
            else_stmt = self.parse_statement()
        return IfNode(cond, then_stmt, else_stmt)

    def parse_while(self):
        self.advance(); self.expect(Lexer.T_LPAREN)
        cond = self.parse_expression(); self.expect(Lexer.T_RPAREN)
        body = self.parse_statement()
        return WhileNode(cond, body)

    def parse_do_while(self):
        self.advance(); body = self.parse_statement()
        self.expect(Lexer.T_WHILE); self.expect(Lexer.T_LPAREN)
        cond = self.parse_expression(); self.expect(Lexer.T_RPAREN); self.expect(Lexer.T_SEMICOLON)
        return DoWhileNode(body, cond)

    def parse_for(self):
        self.advance(); self.expect(Lexer.T_LPAREN)
        if self.check(Lexer.T_SEMICOLON): init = None; self.advance()
        elif self.is_type_start(self.peek()): init = self.parse_local_decl()
        else: init = ExprStmtNode(self.parse_expression()); self.expect(Lexer.T_SEMICOLON)
        cond = None
        if not self.check(Lexer.T_SEMICOLON): cond = self.parse_expression()
        self.expect(Lexer.T_SEMICOLON)
        update = None
        if not self.check(Lexer.T_RPAREN): update = self.parse_expression()
        self.expect(Lexer.T_RPAREN)
        body = self.parse_statement()
        return ForNode(init, cond, update, body)

    def parse_switch(self):
        self.advance(); self.expect(Lexer.T_LPAREN)
        expr = self.parse_expression(); self.expect(Lexer.T_RPAREN)
        self.expect(Lexer.T_LBRACE)
        statements = []
        while not self.check(Lexer.T_RBRACE):
            if self.check(Lexer.T_CASE):
                self.advance(); case_expr = self.parse_expression(); self.expect(Lexer.T_COLON)
                statements.append(('case', case_expr))
            elif self.check(Lexer.T_DEFAULT):
                self.advance(); self.expect(Lexer.T_COLON)
                statements.append(('default',))
            elif self.check(Lexer.T_IDENTIFIER) and self.peek(1).type == Lexer.T_COLON:
                label = self.advance().value; self.advance()
                statements.append(('label', label))
            else:
                stmt = self.parse_statement()
                if stmt is not None: statements.append(('stmt', stmt))
        self.expect(Lexer.T_RBRACE)
        return SwitchNode(expr, statements)

    def parse_expression(self):
        expr = self.parse_assignment_expr()
        while self.match(Lexer.T_COMMA):
            right = self.parse_assignment_expr()
            expr = BinaryOpNode(',', expr, right)
        return expr

    def parse_assignment_expr(self):
        expr = self.parse_conditional()
        tok = self.peek()
        assign_map = {
            Lexer.T_ASSIGN: '=', Lexer.T_ADD_ASSIGN: '+=', Lexer.T_SUB_ASSIGN: '-=',
            Lexer.T_MUL_ASSIGN: '*=', Lexer.T_DIV_ASSIGN: '/=', Lexer.T_MOD_ASSIGN: '%=',
            Lexer.T_SHL_ASSIGN: '<<=', Lexer.T_SHR_ASSIGN: '>>=',
            Lexer.T_AND_ASSIGN: '&=', Lexer.T_OR_ASSIGN: '|=', Lexer.T_XOR_ASSIGN: '^='
        }
        if tok.type in assign_map:
            self.advance()
            value = self.parse_assignment_expr()
            return AssignmentNode(assign_map[tok.type], expr, value)
        return expr

    def parse_conditional(self):
        cond = self.parse_logical_or()
        if self.match(Lexer.T_QUESTION):
            then_expr = self.parse_expression()
            self.expect(Lexer.T_COLON)
            else_expr = self.parse_conditional()
            return ConditionalNode(cond, then_expr, else_expr)
        return cond

    def parse_logical_or(self):
        left = self.parse_logical_and()
        while self.check(Lexer.T_LOGICAL_OR):
            self.advance(); right = self.parse_logical_and()
            left = BinaryOpNode('||', left, right)
        return left

    def parse_logical_and(self):
        left = self.parse_bitwise_or()
        while self.check(Lexer.T_LOGICAL_AND):
            self.advance(); right = self.parse_bitwise_or()
            left = BinaryOpNode('&&', left, right)
        return left

    def parse_bitwise_or(self):
        left = self.parse_bitwise_xor()
        while self.check(Lexer.T_BITWISE_OR):
            self.advance(); right = self.parse_bitwise_xor()
            left = BinaryOpNode('|', left, right)
        return left

    def parse_bitwise_xor(self):
        left = self.parse_bitwise_and()
        while self.check(Lexer.T_BITWISE_XOR):
            self.advance(); right = self.parse_bitwise_and()
            left = BinaryOpNode('^', left, right)
        return left

    def parse_bitwise_and(self):
        left = self.parse_equality()
        while self.check(Lexer.T_AMPERSAND):
            self.advance(); right = self.parse_equality()
            left = BinaryOpNode('&', left, right)
        return left

    def parse_equality(self):
        left = self.parse_relational()
        while self.peek().type in (Lexer.T_EQUAL, Lexer.T_NOT_EQUAL):
            op = '==' if self.peek().type == Lexer.T_EQUAL else '!='
            self.advance(); right = self.parse_relational()
            left = BinaryOpNode(op, left, right)
        return left

    def parse_relational(self):
        left = self.parse_shift()
        while self.peek().type in (Lexer.T_LESS_THAN, Lexer.T_GREATER_THAN, Lexer.T_LESS_EQUAL, Lexer.T_GREATER_EQUAL):
            op_map = {Lexer.T_LESS_THAN: '<', Lexer.T_GREATER_THAN: '>', Lexer.T_LESS_EQUAL: '<=', Lexer.T_GREATER_EQUAL: '>='}
            op = op_map[self.peek().type]; self.advance()
            right = self.parse_shift()
            left = BinaryOpNode(op, left, right)
        return left

    def parse_shift(self):
        left = self.parse_additive()
        while self.peek().type in (Lexer.T_SHIFT_LEFT, Lexer.T_SHIFT_RIGHT):
            op = '<<' if self.peek().type == Lexer.T_SHIFT_LEFT else '>>'
            self.advance(); right = self.parse_additive()
            left = BinaryOpNode(op, left, right)
        return left

    def parse_additive(self):
        left = self.parse_multiplicative()
        while self.peek().type in (Lexer.T_PLUS, Lexer.T_MINUS):
            op = '+' if self.peek().type == Lexer.T_PLUS else '-'
            self.advance(); right = self.parse_multiplicative()
            left = BinaryOpNode(op, left, right)
        return left

    def parse_multiplicative(self):
        left = self.parse_cast()
        while self.peek().type in (Lexer.T_ASTERISK, Lexer.T_SLASH, Lexer.T_MODULUS):
            op_map = {Lexer.T_ASTERISK: '*', Lexer.T_SLASH: '/', Lexer.T_MODULUS: '%'}
            op = op_map[self.peek().type]; self.advance()
            right = self.parse_cast()
            left = BinaryOpNode(op, left, right)
        return left

    def parse_cast(self):
        if self.check(Lexer.T_SIZEOF):
            self.advance()
            if self.match(Lexer.T_LPAREN):
                if self.is_type_start(self.peek()):
                    target_type = self.parse_type_spec()
                    self.expect(Lexer.T_RPAREN)
                    return SizeofNode(target_type=target_type)
                else:
                    expr = self.parse_expression()
                    self.expect(Lexer.T_RPAREN)
                    return SizeofNode(expr=expr)
            else:
                expr = self.parse_unary()
                return SizeofNode(expr=expr)

        if self.check(Lexer.T_LPAREN) and self.is_type_start(self.peek(1)):
            saved = self.pos
            self.advance()
            target_type = self.parse_type_spec()
            self.expect(Lexer.T_RPAREN)
            if self.peek().type in (Lexer.T_IDENTIFIER, Lexer.T_INT_CONST, Lexer.T_FP_CONST,
                                   Lexer.T_STRING_CONST, Lexer.T_CHAR_CONST, Lexer.T_LPAREN,
                                   Lexer.T_MINUS, Lexer.T_PLUS, Lexer.T_UNARY_NOT,
                                   Lexer.T_INCREMENT, Lexer.T_DECREMENT, Lexer.T_ASTERISK,
                                   Lexer.T_AMPERSAND, Lexer.T_SIZEOF, Lexer.T_TILDE):
                expr = self.parse_cast()
                return CastNode(target_type, expr)
            else:
                self.pos = saved

        return self.parse_unary()

    def parse_type_spec(self):
        is_unsigned = is_signed = is_short = is_long = False
        base_type = None; struct_type = None; is_struct = False

        while True:
            tok = self.peek()
            if tok.type == Lexer.T_UNSIGNED_TYPE: is_unsigned = True; self.advance()
            elif tok.type == Lexer.T_SIGNED_TYPE: self.advance()
            elif tok.type == Lexer.T_SHORT_TYPE: is_short = True; self.advance()
            elif tok.type == Lexer.T_LONG_TYPE: is_long = True; self.advance()
            elif tok.type == Lexer.T_INT_TYPE: base_type = BaseType.UNSIGNED_INT if is_unsigned else BaseType.INT; self.advance()
            elif tok.type == Lexer.T_CHAR_TYPE: base_type = BaseType.UNSIGNED_CHAR if is_unsigned else BaseType.CHAR; self.advance()
            elif tok.type == Lexer.T_FLOAT_TYPE: base_type = BaseType.FP; self.advance()
            elif tok.type == Lexer.T_DOUBLE_TYPE: base_type = BaseType.FP; self.advance()
            elif tok.type == Lexer.T_VOID_TYPE: base_type = BaseType.VOID; self.advance()
            elif tok.type == Lexer.T_STRUCT_TYPE or tok.type == Lexer.T_UNION_TYPE:
                struct_type = self.parse_struct_or_union(); is_struct = True; break
            elif tok.type == Lexer.T_ENUM_TYPE:
                struct_type, _, _ = self.parse_enum(); base_type = BaseType.ENUM; break
            else: break

        if base_type is None:
            if is_unsigned:
                if is_short: base_type = BaseType.UNSIGNED_SHORT
                elif is_long: base_type = BaseType.UNSIGNED_LONG
                else: base_type = BaseType.UNSIGNED_INT
            elif is_short: base_type = BaseType.SHORT
            elif is_long: base_type = BaseType.LONG
            else: base_type = BaseType.INT

        vt = struct_type if is_struct else (get_base_type(base_type) if base_type != BaseType.ENUM else struct_type)
        while self.match(Lexer.T_ASTERISK):
            vt = get_pointer_type(vt) if isinstance(vt, ValueType) else ('pointer', vt)
        return vt

    def parse_unary(self):
        tok = self.peek()
        if tok.type == Lexer.T_INCREMENT: self.advance(); return UnaryOpNode('++', self.parse_unary(), prefix=True)
        if tok.type == Lexer.T_DECREMENT: self.advance(); return UnaryOpNode('--', self.parse_unary(), prefix=True)
        if tok.type == Lexer.T_PLUS: self.advance(); return self.parse_unary()
        if tok.type == Lexer.T_MINUS: self.advance(); return UnaryOpNode('-', self.parse_unary(), prefix=True)
        if tok.type == Lexer.T_UNARY_NOT: self.advance(); return UnaryOpNode('!', self.parse_unary(), prefix=True)
        if tok.type == Lexer.T_TILDE: self.advance(); return UnaryOpNode('~', self.parse_unary(), prefix=True)
        if tok.type == Lexer.T_AMPERSAND: self.advance(); return UnaryOpNode('&', self.parse_unary(), prefix=True)
        if tok.type == Lexer.T_ASTERISK: self.advance(); return UnaryOpNode('*', self.parse_unary(), prefix=True)
        return self.parse_postfix()

    def parse_postfix(self):
        expr = self.parse_primary()
        while True:
            tok = self.peek()
            if tok.type == Lexer.T_LPAREN:
                self.advance()
                args = []
                if not self.check(Lexer.T_RPAREN):
                    while True:
                        args.append(self.parse_assignment_expr())
                        if not self.match(Lexer.T_COMMA): break
                self.expect(Lexer.T_RPAREN)
                expr = CallNode(expr, args)
            elif tok.type == Lexer.T_LBRACKET:
                self.advance(); index = self.parse_expression(); self.expect(Lexer.T_RBRACKET)
                expr = IndexNode(expr, index)
            elif tok.type == Lexer.T_DOT:
                self.advance(); member = self.advance().value
                expr = MemberAccessNode(expr, member, is_arrow=False)
            elif tok.type == Lexer.T_ARROW:
                self.advance(); member = self.advance().value
                expr = MemberAccessNode(expr, member, is_arrow=True)
            elif tok.type == Lexer.T_INCREMENT:
                self.advance(); expr = UnaryOpNode('++', expr, prefix=False)
            elif tok.type == Lexer.T_DECREMENT:
                self.advance(); expr = UnaryOpNode('--', expr, prefix=False)
            else: break
        return expr

    def parse_primary(self):
        tok = self.peek()
        if tok.type == Lexer.T_INT_CONST: self.advance(); return NumberNode(tok.value[1], is_fp=False)
        if tok.type == Lexer.T_FP_CONST: self.advance(); return NumberNode(tok.value[1], is_fp=True)
        if tok.type == Lexer.T_STRING_CONST: self.advance(); return StringNode(tok.value)
        if tok.type == Lexer.T_CHAR_CONST: self.advance(); return CharNode(tok.value)
        if tok.type == Lexer.T_IDENTIFIER: self.advance(); return IdentifierNode(tok.value)
        if tok.type == Lexer.T_LPAREN:
            self.advance(); expr = self.parse_expression(); self.expect(Lexer.T_RPAREN); return expr
        self.error(f"unexpected token in expression")

# ============================================================
# INTERPRETER
# ============================================================

class Interpreter:
    def __init__(self):
        self.mem = Memory()
        self.global_scope = {}
        self.functions = {}
        self.typedefs = {}
        self.struct_types = {}
        self.enum_constants = {}
        self.static_vars = {}
        self.string_literals = {}
        self.string_literal_next = 1024 * 768
        self.output = []
        self.exit_value = 0

    def resolve_type(self, vt):
        if isinstance(vt, ValueType):
            return vt
        if isinstance(vt, tuple):
            if vt[0] == 'struct_ref':
                _, sname, is_union = vt
                key = ('union' if is_union else 'struct', sname)
                if key in self.struct_types:
                    return self.struct_types[key]
                return ValueType(BaseType.STRUCT if not is_union else BaseType.UNION, sizeof=0, align=1, identifier=sname)
            elif vt[0] == 'pointer':
                return get_pointer_type(self.resolve_type(vt[1]))
            elif vt[0] == 'array':
                return get_array_type(self.resolve_type(vt[1]), vt[2])
        return vt

    def run(self, source):
        lexer = Lexer(source)
        lexer.tokenize()
        tokens = lexer.expand_macros_in_token_list(lexer.tokens)
        parser = Parser(tokens, lexer)
        declarations = parser.parse()

        for decl in declarations:
            self.exec_toplevel(decl)

        if 'main' not in self.functions:
            return
        main_func = self.functions['main']
        if main_func.body is None:
            return
        try:
            result = self.call_function(main_func, [])
            if result is not None:
                self.exit_value = result.read_int() & 0xFF
        except ReturnException:
            pass
        except SystemExit:
            pass

    def exec_toplevel(self, decl):
        if isinstance(decl, FuncDefNode):
            self.functions[decl.name] = decl
        elif isinstance(decl, TypedefNode):
            self.typedefs[decl.name] = self.resolve_type(decl.target_type)
        elif isinstance(decl, BlockNode):
            for stmt in decl.statements:
                self.exec_toplevel(stmt)
        elif isinstance(decl, VarDeclNode):
            self.exec_global_var_decl(decl)
        elif isinstance(decl, StructDeclNode):
            if decl.struct_type is not None:
                key = ('union' if decl.is_union else 'struct', decl.name)
                self.struct_types[key] = decl.struct_type

    def exec_global_var_decl(self, decl):
        vt = self.resolve_type(decl.var_type)
        if decl.array_sizes:
            for dim in reversed(decl.array_sizes):
                dim_size = self._eval_dim(dim) if dim is not None else 0
                vt = get_array_type(vt, dim_size)
        offset = self.mem.alloc_stack(type_size(vt))
        val = Value(vt, offset, is_lvalue=True, mem=self.mem)
        if decl.init is not None:
            self.init_variable(val, decl.init, vt, self.global_scope)
        else:
            self.mem.write_bytes(offset, bytes(type_size(vt)))
        self.global_scope[decl.name] = val

    def _eval_dim(self, dim):
        if isinstance(dim, int): return dim
        return self.eval_const(dim)

    def init_variable(self, val, init_expr, vt, scope=None):
        if isinstance(init_expr, ArrayInitNode):
            self.init_array(val, init_expr, vt, scope)
        else:
            init_val = self.eval_expr(init_expr, scope)
            if val.typ.is_fp(): val.write_fp(init_val.read_fp())
            elif val.typ.is_signed() or val.typ.is_unsigned(): val.write_int(init_val.read_int())
            elif val.typ.is_pointer(): val.write_ptr(init_val.read_ptr())
            else: val.write_value(init_val)

    def init_array(self, val, init_expr, vt, scope=None):
        if not vt.is_array():
            return
        elem_type = vt.from_type
        elem_size = type_size(elem_type)
        total_size = type_size(vt)
        self.mem.write_bytes(val.offset, bytes(total_size))
        offset = val.offset
        for elem in init_expr.elements:
            if isinstance(elem, ArrayInitNode):
                sub_val = Value(elem_type, offset, is_lvalue=True, mem=self.mem)
                self.init_array(sub_val, elem, elem_type)
            elif elem_type.is_array():
                sub_val = Value(elem_type, offset, is_lvalue=True, mem=self.mem)
                if isinstance(elem, ArrayInitNode):
                    self.init_array(sub_val, elem, elem_type)
            else:
                elem_val = self.eval_expr(elem, scope)
                if elem_type.is_fp(): self.mem.write_double(offset, elem_val.read_fp())
                elif elem_type.is_signed():
                    v = elem_val.read_int()
                    bits = elem_type.sizeof * 8
                    v = v & ((1 << bits) - 1)
                    self.mem.write_int(offset, v, elem_type.sizeof)
                elif elem_type.is_unsigned():
                    self.mem.write_int(offset, elem_val.read_uint(), elem_type.sizeof)
                elif elem_type.is_pointer():
                    self.mem.write_ptr(offset, elem_val.read_ptr())
                else:
                    self.mem.write_int(offset, elem_val.read_int(), elem_type.sizeof)
            offset += elem_size

    def eval_const(self, expr):
        if isinstance(expr, NumberNode): return expr.value
        if isinstance(expr, CharNode): return expr.value
        if isinstance(expr, BinaryOpNode):
            l = self.eval_const(expr.left); r = self.eval_const(expr.right)
            ops = {'+': l+r, '-': l-r, '*': l*r, '/': l//r, '%': l%r}
            return ops.get(expr.op, 0)
        if isinstance(expr, IdentifierNode):
            if expr.name in self.enum_constants:
                return self.enum_constants[expr.name]
        return 0

    def get_string_literal(self, s):
        if s in self.string_literals:
            return self.string_literals[s]
        data = s.encode('latin-1') + b'\0'
        offset = self.string_literal_next
        self.string_literal_next += len(data)
        self.string_literal_next = (self.string_literal_next + 7) & ~7
        self.mem.write_bytes(offset, data)
        self.string_literals[s] = offset
        return offset

    def call_function(self, func_def_node, arg_values):
        old_stack_top = self.mem.stack_top
        local_scope = {}
        params = func_def_node.params
        for i, (pname, ptype) in enumerate(params):
            vt = self.resolve_type(ptype)
            if i < len(arg_values):
                arg_val = arg_values[i]
                sz = type_size(vt)
                offset = self.mem.alloc_stack(sz)
                param_val = Value(vt, offset, is_lvalue=True, mem=self.mem)
                if vt.is_fp(): param_val.write_fp(arg_val.read_fp())
                elif vt.is_signed() or vt.is_unsigned():
                    if vt.sizeof == 8: param_val._write_ulong(arg_val.read_long())
                    else: param_val.write_int(arg_val.read_int())
                elif vt.is_pointer(): param_val.write_ptr(arg_val.read_ptr())
                elif vt.is_struct() or vt.is_union():
                    src_sz = type_size(arg_val.typ)
                    if arg_val.is_lvalue and arg_val.rvalue_val is None:
                        data = arg_val.mem.read_bytes(arg_val.offset, src_sz)
                    else: data = bytes(src_sz)
                    self.mem.write_bytes(offset, data)
                else: param_val.write_int(arg_val.read_int())
                if pname: local_scope[pname] = param_val

        labels = {}
        if func_def_node.body:
            self.scan_labels(func_def_node.body, labels)

        goto_label = None
        while True:
            try:
                if goto_label is not None:
                    body_statements = func_def_node.body.statements
                    start_idx = None
                    for i, stmt in enumerate(body_statements):
                        if isinstance(stmt, LabelNode) and stmt.name == goto_label:
                            start_idx = i
                            break
                    if start_idx is None:
                        raise ProgramError(f"goto to unknown label '{goto_label}'")
                    for j in range(start_idx, len(body_statements)):
                        self.exec_stmt(body_statements[j], local_scope, labels)
                else:
                    self.exec_block(func_def_node.body, local_scope, labels)
                break
            except GotoException as e:
                goto_label = e.label
                continue
            except ReturnException as e:
                self.mem.stack_top = old_stack_top
                if e.value is not None and e.value.is_lvalue and e.value.rvalue_val is None:
                    v = e.value
                    if v.typ.is_fp():
                        return Value(v.typ, rvalue_val=("fp", v.read_fp()))
                    elif v.typ.is_pointer():
                        return Value(v.typ, rvalue_val=("ptr", v.read_ptr()))
                    else:
                        return Value(v.typ, rvalue_val=("int", v.read_int()))
                return e.value
        self.mem.stack_top = old_stack_top
        return None

    def scan_labels(self, node, labels):
        if isinstance(node, BlockNode):
            for stmt in node.statements:
                self.scan_labels(stmt, labels)
        elif isinstance(node, LabelNode):
            labels[node.name] = node

    def exec_block(self, block, scope, labels=None):
        if isinstance(block, BlockNode):
            for stmt in block.statements:
                self.exec_stmt(stmt, scope, labels)
        else:
            self.exec_stmt(block, scope, labels)

    def exec_stmt(self, stmt, scope, labels=None):
        if stmt is None or isinstance(stmt, EmptyNode): return

        if isinstance(stmt, BlockNode):
            for s in stmt.statements:
                self.exec_stmt(s, scope, labels)
        elif isinstance(stmt, VarDeclNode):
            self.exec_var_decl(stmt, scope)
        elif isinstance(stmt, ExprStmtNode):
            self.eval_expr(stmt.expr, scope)
        elif isinstance(stmt, IfNode):
            cond_val = self.eval_expr(stmt.cond, scope)
            if cond_val.read_int() != 0:
                self.exec_stmt(stmt.then_stmt, scope, labels)
            elif stmt.else_stmt is not None:
                self.exec_stmt(stmt.else_stmt, scope, labels)
        elif isinstance(stmt, WhileNode):
            while True:
                cond_val = self.eval_expr(stmt.cond, scope)
                if cond_val.read_int() == 0: break
                try: self.exec_stmt(stmt.body, scope, labels)
                except BreakException: break
                except ContinueException: continue
        elif isinstance(stmt, DoWhileNode):
            while True:
                try: self.exec_stmt(stmt.body, scope, labels)
                except BreakException: break
                except ContinueException: pass
                cond_val = self.eval_expr(stmt.cond, scope)
                if cond_val.read_int() == 0: break
        elif isinstance(stmt, ForNode):
            for_scope = scope
            if stmt.init is not None:
                if isinstance(stmt.init, BlockNode):
                    for s in stmt.init.statements: self.exec_stmt(s, for_scope, labels)
                elif isinstance(stmt.init, ExprStmtNode):
                    self.eval_expr(stmt.init.expr, for_scope)
                else:
                    self.exec_stmt(stmt.init, for_scope, labels)
            while True:
                if stmt.cond is not None:
                    cond_val = self.eval_expr(stmt.cond, for_scope)
                    if cond_val.read_int() == 0: break
                try: self.exec_stmt(stmt.body, for_scope, labels)
                except BreakException: break
                except ContinueException: pass
                if stmt.update is not None:
                    self.eval_expr(stmt.update, for_scope)
        elif isinstance(stmt, BreakNode): raise BreakException()
        elif isinstance(stmt, ContinueNode): raise ContinueException()
        elif isinstance(stmt, ReturnNode):
            if stmt.value is not None:
                raise ReturnException(self.eval_expr(stmt.value, scope))
            raise ReturnException(None)
        elif isinstance(stmt, GotoNode): raise GotoException(stmt.label)
        elif isinstance(stmt, LabelNode):
            if stmt.stmt is not None:
                self.exec_stmt(stmt.stmt, scope, labels)
        elif isinstance(stmt, SwitchNode):
            self.exec_switch(stmt, scope, labels)
        elif isinstance(stmt, TypedefNode):
            self.typedefs[stmt.name] = self.resolve_type(stmt.target_type)
        elif isinstance(stmt, FuncDefNode):
            self.functions[stmt.name] = stmt
        else:
            self.eval_expr(stmt, scope)

    def exec_switch(self, stmt, scope, labels):
        switch_val = self.eval_expr(stmt.expr, scope)
        switch_int = switch_val.read_int()
        matched = False; default_idx = None; start_idx = None
        for i, item in enumerate(stmt.body):
            if item[0] == 'case':
                case_val = self.eval_expr(item[1], scope)
                if case_val.read_int() == switch_int:
                    start_idx = i; matched = True; break
            elif item[0] == 'default':
                default_idx = i
        if not matched and default_idx is not None:
            start_idx = default_idx
        if start_idx is None: return
        try:
            for i in range(start_idx, len(stmt.body)):
                item = stmt.body[i]
                if item[0] in ('case', 'default', 'label'): continue
                elif item[0] == 'stmt': self.exec_stmt(item[1], scope, labels)
        except BreakException: pass

    def exec_var_decl(self, decl, scope):
        vt = self.resolve_type(decl.var_type)
        if decl.array_sizes:
            for dim in reversed(decl.array_sizes):
                if dim is not None:
                    dim_size = self.eval_expr(dim, scope).read_int() if not isinstance(dim, int) else dim
                else:
                    dim_size = len(decl.init.elements) if decl.init is not None and isinstance(decl.init, ArrayInitNode) else 0
                vt = get_array_type(vt, dim_size)

        if decl.is_static:
            if decl.name in self.static_vars:
                scope[decl.name] = self.static_vars[decl.name]
                return
            offset = self.mem.alloc_stack(type_size(vt))
            val = Value(vt, offset, is_lvalue=True, mem=self.mem)
            if decl.init is not None: self.init_variable(val, decl.init, vt, self.global_scope)
            else: self.mem.write_bytes(offset, bytes(type_size(vt)))
            self.static_vars[decl.name] = val
            scope[decl.name] = val
            return

        offset = self.mem.alloc_stack(type_size(vt))
        val = Value(vt, offset, is_lvalue=True, mem=self.mem)
        if decl.init is not None: self.init_variable(val, decl.init, vt, scope)
        else:
            sz = type_size(vt)
            if sz > 0: self.mem.write_bytes(offset, bytes(sz))
        scope[decl.name] = val

    def eval_expr(self, expr, scope=None):
        if scope is None: scope = self.global_scope

        if isinstance(expr, NumberNode):
            if expr.is_fp: return Value(get_base_type(BaseType.FP), rvalue_val=('fp', expr.value))
            else: return Value(get_base_type(BaseType.INT), rvalue_val=('int', expr.value))
        if isinstance(expr, StringNode):
            offset = self.get_string_literal(expr.value)
            return Value(get_pointer_type(get_base_type(BaseType.CHAR)), rvalue_val=('ptr', offset))
        if isinstance(expr, CharNode):
            return Value(get_base_type(BaseType.CHAR), rvalue_val=('int', expr.value))
        if isinstance(expr, IdentifierNode):
            return self.lookup_identifier(expr.name, scope)
        if isinstance(expr, BinaryOpNode):
            return self.eval_binary_op(expr, scope)
        if isinstance(expr, UnaryOpNode):
            return self.eval_unary_op(expr, scope)
        if isinstance(expr, AssignmentNode):
            return self.eval_assignment(expr, scope)
        if isinstance(expr, ConditionalNode):
            cond_val = self.eval_expr(expr.cond, scope)
            if cond_val.read_int() != 0: return self.eval_expr(expr.then_expr, scope)
            else: return self.eval_expr(expr.else_expr, scope)
        if isinstance(expr, CallNode):
            return self.eval_call(expr, scope)
        if isinstance(expr, MemberAccessNode):
            return self.eval_member_access(expr, scope)
        if isinstance(expr, IndexNode):
            return self.eval_index(expr, scope)
        if isinstance(expr, CastNode):
            return self.eval_cast(expr, scope)
        if isinstance(expr, SizeofNode):
            return self.eval_sizeof(expr, scope)
        raise ProgramError(f"Cannot evaluate: {type(expr).__name__}")

    def lookup_identifier(self, name, scope):
        if name in scope: return scope[name]
        if name in self.global_scope: return self.global_scope[name]
        if name in self.functions:
            func_vt = ValueType(BaseType.FUNCTION, sizeof=4, align=4)
            return Value(func_vt, rvalue_val=('func', name))
        if name in self.enum_constants:
            return Value(get_base_type(BaseType.INT), rvalue_val=('int', self.enum_constants[name]))
        if name in self.typedefs:
            return Value(get_base_type(BaseType.TYPE_TYPE), rvalue_val=('type', self.typedefs[name]))
        return Value(get_base_type(BaseType.INT), rvalue_val=('int', 0))

    def eval_binary_op(self, expr, scope):
        op = expr.op
        if op == ',':
            self.eval_expr(expr.left, scope)
            return self.eval_expr(expr.right, scope)
        if op == '&&':
            left_val = self.eval_expr(expr.left, scope)
            if left_val.read_int() == 0:
                return Value(get_base_type(BaseType.INT), rvalue_val=('int', 0))
            right_val = self.eval_expr(expr.right, scope)
            return Value(get_base_type(BaseType.INT), rvalue_val=('int', 1 if right_val.read_int() != 0 else 0))
        if op == '||':
            left_val = self.eval_expr(expr.left, scope)
            if left_val.read_int() != 0:
                return Value(get_base_type(BaseType.INT), rvalue_val=('int', 1))
            right_val = self.eval_expr(expr.right, scope)
            return Value(get_base_type(BaseType.INT), rvalue_val=('int', 1 if right_val.read_int() != 0 else 0))

        left_val = self.eval_expr(expr.left, scope)
        right_val = self.eval_expr(expr.right, scope)

        if op in ('+', '-', '*', '/', '%', '<<', '>>', '&', '|', '^'):
            return self.eval_arithmetic(op, left_val, right_val)
        if op in ('==', '!=', '<', '>', '<=', '>='):
            return self.eval_comparison(op, left_val, right_val)
        raise ProgramError(f"Unknown binary op: {op}")

    def eval_arithmetic(self, op, left_val, right_val):
        lt, rt = left_val.typ, right_val.typ

        if lt.is_pointer() and op in ('+', '-') and not rt.is_pointer():
            ptr = left_val.read_ptr()
            offset_val = right_val.read_int()
            if op == '+': return Value(lt, rvalue_val=('ptr', ptr + offset_val * lt.from_type.sizeof))
            else: return Value(lt, rvalue_val=('ptr', ptr - offset_val * lt.from_type.sizeof))
        if rt.is_pointer() and op == '+' and not lt.is_pointer():
            ptr = right_val.read_ptr()
            return Value(rt, rvalue_val=('ptr', ptr + left_val.read_int() * rt.from_type.sizeof))
        if lt.is_pointer() and rt.is_pointer() and op == '-':
            return Value(get_base_type(BaseType.INT), rvalue_val=('int', (left_val.read_ptr() - right_val.read_ptr()) // lt.from_type.sizeof))

        if lt.is_fp() or rt.is_fp():
            l, r = left_val.read_fp(), right_val.read_fp()
            if op == '+': result = l + r
            elif op == '-': result = l - r
            elif op == '*': result = l * r
            elif op == '/': result = l / r
            elif op == '%': result = math.fmod(l, r)
            else: raise ProgramError(f"invalid op {op} on float")
            return Value(get_base_type(BaseType.FP), rvalue_val=('fp', result))

        result_type = self.promote_types(lt, rt)
        if result_type.sizeof == 8:
            l, r = left_val.read_long(), right_val.read_long()
        else:
            l, r = left_val.read_int(), right_val.read_int()

        if op == '+': result = l + r
        elif op == '-': result = l - r
        elif op == '*': result = l * r
        elif op == '/':
            if r == 0: raise ProgramError("division by zero")
            result = int(l / r) if result_type.is_signed() else l // r
        elif op == '%':
            if r == 0: raise ProgramError("modulo by zero")
            result = int(math.fmod(l, r)) if result_type.is_signed() else l % r
        elif op == '<<': result = l << (r & 63)
        elif op == '>>':
            if result_type.is_signed(): result = l >> (r & 63)
            else: result = (l & 0xFFFFFFFFFFFFFFFF) >> (r & 63)
        elif op == '&': result = l & r
        elif op == '|': result = l | r
        elif op == '^': result = l ^ r
        else: raise ProgramError(f"unknown arithmetic op: {op}")

        bits = result_type.sizeof * 8
        result = result & ((1 << bits) - 1)
        if result_type.is_signed() and result >= (1 << (bits - 1)):
            result -= (1 << bits)
        return Value(result_type, rvalue_val=('int', result))

    def promote_types(self, lt, rt):
        if lt.is_fp() or rt.is_fp(): return get_base_type(BaseType.FP)
        if lt.base == BaseType.UNSIGNED_LONG or rt.base == BaseType.UNSIGNED_LONG:
            return get_base_type(BaseType.UNSIGNED_LONG)
        if lt.base == BaseType.LONG or rt.base == BaseType.LONG:
            return get_base_type(BaseType.LONG)
        if lt.base == BaseType.UNSIGNED_INT or rt.base == BaseType.UNSIGNED_INT:
            return get_base_type(BaseType.UNSIGNED_INT)
        return get_base_type(BaseType.INT)

    def eval_comparison(self, op, left_val, right_val):
        lt, rt = left_val.typ, right_val.typ
        if lt.is_fp() or rt.is_fp():
            l, r = left_val.read_fp(), right_val.read_fp()
        elif lt.is_pointer() or rt.is_pointer():
            l, r = left_val.read_ptr(), right_val.read_ptr()
        else:
            l, r = left_val.read_int(), right_val.read_int()
        if op == '==': result = 1 if l == r else 0
        elif op == '!=': result = 1 if l != r else 0
        elif op == '<': result = 1 if l < r else 0
        elif op == '>': result = 1 if l > r else 0
        elif op == '<=': result = 1 if l <= r else 0
        elif op == '>=': result = 1 if l >= r else 0
        else: result = 0
        return Value(get_base_type(BaseType.INT), rvalue_val=('int', result))

    def eval_unary_op(self, expr, scope):
        op = expr.op
        if op == '&':
            operand = self.eval_expr(expr.operand, scope)
            if operand.is_lvalue or operand.typ.is_array():
                target_type = operand.typ.from_type if operand.typ.is_array() else operand.typ
                return Value(get_pointer_type(target_type), rvalue_val=('ptr', operand.offset if operand.rvalue_val is None else 0))
            raise ProgramError("cannot take address of rvalue")
        if op == '*':
            operand = self.eval_expr(expr.operand, scope)
            ptr = operand.read_ptr()
            target_type = operand.typ.from_type if operand.typ.is_pointer() else get_base_type(BaseType.INT)
            return Value(target_type, ptr, is_lvalue=True, mem=self.mem)
        if op == '-':
            operand = self.eval_expr(expr.operand, scope)
            if operand.typ.is_fp():
                return Value(operand.typ, rvalue_val=('fp', -operand.read_fp()))
            result_type = operand.typ if operand.typ.sizeof >= 4 else get_base_type(BaseType.INT)
            return Value(result_type, rvalue_val=('int', -operand.read_int()))
        if op == '!':
            operand = self.eval_expr(expr.operand, scope)
            return Value(get_base_type(BaseType.INT), rvalue_val=('int', 1 if operand.read_int() == 0 else 0))
        if op == '~':
            operand = self.eval_expr(expr.operand, scope)
            result_type = operand.typ if operand.typ.sizeof >= 4 else get_base_type(BaseType.INT)
            v = operand.read_int()
            bits = result_type.sizeof * 8
            mask = (1 << bits) - 1
            result = (~v) & mask
            if result_type.is_signed() and result >= (1 << (bits - 1)):
                result -= (1 << bits)
            return Value(result_type, rvalue_val=('int', result))
        if op in ('++', '--'):
            operand = self.eval_expr(expr.operand, scope)
            if not operand.is_lvalue: raise ProgramError(f"cannot {op} rvalue")
            if operand.typ.is_fp():
                old = operand.read_fp()
                new = old + (1 if op == '++' else -1)
                operand.write_fp(new)
                return Value(operand.typ, rvalue_val=('fp', old if not expr.prefix else new))
            old = operand.read_int()
            new = old + (1 if op == '++' else -1)
            bits = operand.typ.sizeof * 8
            new = new & ((1 << bits) - 1)
            if operand.typ.is_signed() and new >= (1 << (bits - 1)):
                new -= (1 << bits)
            operand.write_int(new)
            return Value(operand.typ, rvalue_val=('int', old if not expr.prefix else new))
        raise ProgramError(f"Unknown unary op: {op}")

    def eval_assignment(self, expr, scope):
        target = self.eval_expr(expr.target, scope)
        if not target.is_lvalue: raise ProgramError("assignment to non-lvalue")
        if expr.op == '=':
            src_val = self.eval_expr(expr.value, scope)
            self.assign_value(target, src_val)
            return target
        src_val = self.eval_expr(expr.value, scope)
        op = expr.op[:-1]
        if target.typ.is_fp() or src_val.typ.is_fp():
            old = target.read_fp(); new = src_val.read_fp()
            if op == '+': result = old + new
            elif op == '-': result = old - new
            elif op == '*': result = old * new
            elif op == '/': result = old / new
            elif op == '%': result = math.fmod(old, new)
            else: raise ProgramError(f"invalid compound {op}= on float")
            target.write_fp(result)
            return target
        if target.typ.is_pointer():
            old_ptr = target.read_ptr(); offset = src_val.read_int()
            if op == '+': target.write_ptr(old_ptr + offset * target.typ.from_type.sizeof)
            elif op == '-': target.write_ptr(old_ptr - offset * target.typ.from_type.sizeof)
            else: raise ProgramError(f"invalid compound {op}= on pointer")
            return target
        old = target.read_int(); new = src_val.read_int()
        if op == '+': result = old + new
        elif op == '-': result = old - new
        elif op == '*': result = old * new
        elif op == '/':
            if new == 0: raise ProgramError("division by zero")
            result = int(old / new)
        elif op == '%':
            if new == 0: raise ProgramError("modulo by zero")
            result = int(math.fmod(old, new))
        elif op == '<<': result = old << (new & 63)
        elif op == '>>': result = old >> (new & 63)
        elif op == '&': result = old & new
        elif op == '|': result = old | new
        elif op == '^': result = old ^ new
        else: raise ProgramError(f"unknown compound: {op}=")
        bits = target.typ.sizeof * 8
        result = result & ((1 << bits) - 1)
        if target.typ.is_signed() and result >= (1 << (bits - 1)):
            result -= (1 << bits)
        target.write_int(result)
        return target

    def assign_value(self, target, src_val):
        if target.typ.is_fp(): target.write_fp(src_val.read_fp())
        elif target.typ.is_pointer():
            if src_val.typ.is_pointer() or src_val.typ.is_array():
                target.write_ptr(src_val.read_ptr())
            elif src_val.typ.is_numeric():
                target.write_ptr(src_val.read_int())
            else: target.write_ptr(src_val.read_ptr())
        elif target.typ.is_signed(): target.write_int(src_val.read_int())
        elif target.typ.is_unsigned():
            if target.typ.sizeof == 8: target._write_ulong(src_val.read_ulong())
            else: target.write_int(src_val.read_uint())
        elif target.typ.is_struct() or target.typ.is_union():
            sz = type_size(target.typ)
            if src_val.is_lvalue and src_val.rvalue_val is None:
                data = src_val.mem.read_bytes(src_val.offset, sz)
            else: data = bytes(sz)
            self.mem.write_bytes(target.offset, data)
        else: target.write_int(src_val.read_int())

    def eval_call(self, expr, scope):
        func_node = expr.func
        if isinstance(func_node, IdentifierNode):
            func_name = func_node.name
            if func_name in self.functions:
                func_def = self.functions[func_name]
                arg_values = [self.eval_expr(arg, scope) for arg in expr.args]
                return self.call_function_with_args(func_def, arg_values)
            if func_name in BUILTIN_FUNCTIONS:
                arg_values = [self.eval_expr(arg, scope) for arg in expr.args]
                return BUILTIN_FUNCTIONS[func_name](self, arg_values, scope, expr)
        func_val = self.eval_expr(func_node, scope)
        if func_val.rvalue_val and func_val.rvalue_val[0] == 'func':
            func_name = func_val.rvalue_val[1]
            if func_name in self.functions:
                func_def = self.functions[func_name]
                arg_values = [self.eval_expr(arg, scope) for arg in expr.args]
                return self.call_function_with_args(func_def, arg_values)
            if func_name in BUILTIN_FUNCTIONS:
                arg_values = [self.eval_expr(arg, scope) for arg in expr.args]
                return BUILTIN_FUNCTIONS[func_name](self, arg_values, scope, expr)
        raise ProgramError(f"calling non-function")

    def call_function_with_args(self, func_def_node, arg_values):
        if func_def_node.body is None:
            raise ProgramError(f"function not defined")
        result = self.call_function(func_def_node, arg_values)
        if result is None:
            return Value(get_base_type(BaseType.INT), rvalue_val=('int', 0))
        return result

    def eval_member_access(self, expr, scope):
        obj_val = self.eval_expr(expr.obj, scope)
        if expr.is_arrow:
            if obj_val.typ.is_pointer():
                ptr = obj_val.read_ptr()
                struct_type = obj_val.typ.from_type
            else:
                ptr = obj_val.read_int()
                struct_type = obj_val.typ
        else:
            if obj_val.typ.is_struct() or obj_val.typ.is_union():
                ptr = obj_val.offset
                struct_type = obj_val.typ
            elif obj_val.typ.is_pointer():
                ptr = obj_val.read_ptr()
                struct_type = obj_val.typ.from_type
            else:
                raise ProgramError("member access on non-struct")
        if struct_type is None or struct_type.members is None:
            raise ProgramError("struct has no members")
        if expr.member not in struct_type.members:
            raise ProgramError(f"no member '{expr.member}'")
        member_type, member_offset = struct_type.members[expr.member]
        member_type = self.resolve_type(member_type)
        return Value(member_type, ptr + member_offset, is_lvalue=True, mem=self.mem)

    def eval_index(self, expr, scope):
        arr_val = self.eval_expr(expr.array, scope)
        idx_val = self.eval_expr(expr.index, scope)
        if arr_val.typ.is_array():
            elem_type = arr_val.typ.from_type
            base_offset = arr_val.offset
        elif arr_val.typ.is_pointer():
            elem_type = arr_val.typ.from_type
            base_offset = arr_val.read_ptr()
        else:
            raise ProgramError("cannot index non-array/pointer")
        idx = idx_val.read_int()
        return Value(elem_type, base_offset + idx * elem_type.sizeof, is_lvalue=True, mem=self.mem)

    def eval_cast(self, expr, scope):
        target_type = self.resolve_type(expr.target_type)
        val = self.eval_expr(expr.expr, scope)
        if target_type.is_fp():
            return Value(target_type, rvalue_val=('fp', val.read_fp()))
        elif target_type.is_signed():
            bits = target_type.sizeof * 8
            v = val.read_int() & ((1 << bits) - 1)
            if v >= (1 << (bits - 1)): v -= (1 << bits)
            return Value(target_type, rvalue_val=('int', v))
        elif target_type.is_unsigned():
            if target_type.sizeof == 8:
                return Value(target_type, rvalue_val=('int', val.read_ulong()))
            else:
                return Value(target_type, rvalue_val=('int', val.read_uint()))
        elif target_type.is_pointer():
            return Value(target_type, rvalue_val=('ptr', val.read_ptr()))
        else:
            return val

    def eval_sizeof(self, expr, scope):
        if expr.target_type is not None:
            target_type = self.resolve_type(expr.target_type)
            size = type_size(target_type)
        else:
            val = self.eval_expr(expr.expr, scope)
            size = type_size(val.typ)
        return Value(get_base_type(BaseType.UNSIGNED_LONG), rvalue_val=('int', size))

    def output_str(self, s):
        self.output.append(s)
        sys.stdout.write(s)

# ============================================================
# BUILT-IN FUNCTIONS
# ============================================================

def do_printf(interp, format_str, args):
    output = []
    arg_idx = 0
    i = 0
    fmt_len = len(format_str)

    while i < fmt_len:
        ch = format_str[i]
        if ch != '%':
            output.append(ch); i += 1; continue
        i += 1
        if i >= fmt_len:
            output.append('%'); break
        flags = ''
        while i < fmt_len and format_str[i] in '-+ #0':
            flags += format_str[i]; i += 1
        width = ''
        while i < fmt_len and format_str[i].isdigit():
            width += format_str[i]; i += 1
        precision = None
        if i < fmt_len and format_str[i] == '.':
            i += 1; precision = ''
            while i < fmt_len and format_str[i].isdigit():
                precision += format_str[i]; i += 1
        length = ''
        while i < fmt_len and format_str[i] in 'lhLzj':
            length += format_str[i]; i += 1
        if i >= fmt_len: break
        conv = format_str[i]; i += 1
        fmt_spec = '%' + flags + (width if width else '') + ('.' + precision if precision is not None else '')

        if conv == '%':
            output.append('%'); continue
        if arg_idx >= len(args):
            output.append('XXX'); continue
        arg = args[arg_idx]; arg_idx += 1

        if conv in 'di':
            val = arg.read_long() if 'l' in length else arg.read_int()
            output.append((fmt_spec + 'd') % val)
        elif conv == 'u':
            if 'l' in length: val = arg.read_ulong()
            else: val = arg.read_uint()
            output.append((fmt_spec + 'd') % val)
        elif conv in 'xX':
            if 'l' in length: val = arg.read_ulong()
            else: val = arg.read_uint()
            output.append((fmt_spec + conv) % val)
        elif conv == 'o':
            if 'l' in length: val = arg.read_ulong()
            else: val = arg.read_uint()
            output.append((fmt_spec + 'o') % val)
        elif conv == 'c':
            val = arg.read_int()
            output.append(chr(val & 0xFF))
        elif conv == 's':
            if arg.typ.is_pointer(): ptr = arg.read_ptr()
            elif arg.typ.is_array(): ptr = arg.offset
            else: ptr = arg.read_ptr()
            s = interp.mem.read_cstring(ptr)
            if precision is not None: s = s[:int(precision)]
            if width: output.append((fmt_spec + 's') % s)
            else: output.append(s)
        elif conv in 'fF':
            output.append((fmt_spec + 'f') % arg.read_fp())
        elif conv in 'eE':
            output.append((fmt_spec + conv) % arg.read_fp())
        elif conv in 'gG':
            output.append((fmt_spec + conv) % arg.read_fp())
        elif conv == 'p':
            output.append('0x' + format(arg.read_ptr(), 'x'))
        else:
            output.append(fmt_spec + conv)

    result_str = ''.join(output)
    interp.output_str(result_str)
    return len(result_str)

def c_printf(interp, args, scope, expr_node):
    if not args: return Value(get_base_type(BaseType.INT), rvalue_val=('int', 0))
    format_val = args[0]
    format_str = interp.mem.read_cstring(format_val.read_ptr())
    result = do_printf(interp, format_str, args[1:])
    return Value(get_base_type(BaseType.INT), rvalue_val=('int', result))

def c_fprintf(interp, args, scope, expr_node):
    if len(args) < 2: return Value(get_base_type(BaseType.INT), rvalue_val=('int', 0))
    format_str = interp.mem.read_cstring(args[1].read_ptr())
    result = do_printf(interp, format_str, args[2:])
    return Value(get_base_type(BaseType.INT), rvalue_val=('int', result))

def do_sprintf(interp, format_str, args):
    output = []
    arg_idx = 0; i = 0; fmt_len = len(format_str)
    while i < fmt_len:
        ch = format_str[i]
        if ch != '%': output.append(ch); i += 1; continue
        i += 1
        if i >= fmt_len: output.append('%'); break
        flags = ''
        while i < fmt_len and format_str[i] in '-+ #0': flags += format_str[i]; i += 1
        width = ''
        while i < fmt_len and format_str[i].isdigit(): width += format_str[i]; i += 1
        precision = None
        if i < fmt_len and format_str[i] == '.':
            i += 1; precision = ''
            while i < fmt_len and format_str[i].isdigit(): precision += format_str[i]; i += 1
        length = ''
        while i < fmt_len and format_str[i] in 'lhLzj': length += format_str[i]; i += 1
        if i >= fmt_len: break
        conv = format_str[i]; i += 1
        fmt_spec = '%' + flags + (width if width else '') + ('.' + precision if precision is not None else '')
        if conv == '%': output.append('%'); continue
        if arg_idx >= len(args): output.append('XXX'); continue
        arg = args[arg_idx]; arg_idx += 1
        if conv in 'di':
            val = arg.read_long() if 'l' in length else arg.read_int()
            output.append((fmt_spec + 'd') % val)
        elif conv == 'u':
            if 'l' in length: val = arg.read_ulong()
            else: val = arg.read_uint()
            output.append((fmt_spec + 'd') % val)
        elif conv in 'xX':
            if 'l' in length: val = arg.read_ulong()
            else: val = arg.read_uint()
            output.append((fmt_spec + conv) % val)
        elif conv == 'o':
            if 'l' in length: val = arg.read_ulong()
            else: val = arg.read_uint()
            output.append((fmt_spec + 'o') % val)
        elif conv == 'c':
            output.append(chr(arg.read_int() & 0xFF))
        elif conv == 's':
            if arg.typ.is_pointer(): ptr = arg.read_ptr()
            elif arg.typ.is_array(): ptr = arg.offset
            else: ptr = arg.read_ptr()
            s = interp.mem.read_cstring(ptr)
            if precision is not None: s = s[:int(precision)]
            if width: output.append((fmt_spec + 's') % s)
            else: output.append(s)
        elif conv in 'fF': output.append((fmt_spec + 'f') % arg.read_fp())
        elif conv in 'eE': output.append((fmt_spec + conv) % arg.read_fp())
        elif conv in 'gG': output.append((fmt_spec + conv) % arg.read_fp())
        elif conv == 'p': output.append('0x' + format(arg.read_ptr(), 'x'))
        else: output.append(fmt_spec + conv)
    return ''.join(output)

def c_sprintf(interp, args, scope, expr_node):
    buf_ptr = args[0].read_ptr() if args[0].typ.is_pointer() else args[0].offset
    format_str = interp.mem.read_cstring(args[1].read_ptr())
    result = do_sprintf(interp, format_str, args[2:])
    data = result.encode('latin-1') + b'\0'
    interp.mem.write_bytes(buf_ptr, data)
    return Value(get_base_type(BaseType.INT), rvalue_val=('int', len(result)))

def c_putchar(interp, args, scope, expr_node):
    ch = args[0].read_int()
    interp.output_str(chr(ch & 0xFF))
    return Value(get_base_type(BaseType.INT), rvalue_val=('int', ch))

def c_puts(interp, args, scope, expr_node):
    if args:
        arg = args[0]
        ptr = arg.read_ptr() if arg.typ.is_pointer() else (arg.offset if arg.typ.is_array() else arg.read_ptr())
        s = interp.mem.read_cstring(ptr)
        interp.output_str(s + '\n')
    return Value(get_base_type(BaseType.INT), rvalue_val=('int', 0))

def c_malloc(interp, args, scope, expr_node):
    size = args[0].read_int()
    offset = interp.mem.alloc_heap(size)
    return Value(get_pointer_type(get_base_type(BaseType.VOID)), rvalue_val=('ptr', offset))

def c_free(interp, args, scope, expr_node):
    return Value(get_base_type(BaseType.VOID), rvalue_val=('int', 0))

def c_exit(interp, args, scope, expr_node):
    code = args[0].read_int() if args else 0
    interp.exit_value = code
    raise ReturnException(Value(get_base_type(BaseType.INT), rvalue_val=('int', code)))

def c_abs(interp, args, scope, expr_node):
    return Value(get_base_type(BaseType.INT), rvalue_val=('int', abs(args[0].read_int())))

def c_strlen(interp, args, scope, expr_node):
    arg = args[0]
    ptr = arg.read_ptr() if arg.typ.is_pointer() else (arg.offset if arg.typ.is_array() else arg.read_ptr())
    return Value(get_base_type(BaseType.UNSIGNED_LONG), rvalue_val=('int', len(interp.mem.read_cstring(ptr))))

def c_strcmp(interp, args, scope, expr_node):
    s1_ptr = args[0].read_ptr() if args[0].typ.is_pointer() else args[0].offset
    s2_ptr = args[1].read_ptr() if args[1].typ.is_pointer() else args[1].offset
    s1 = interp.mem.read_cstring(s1_ptr)
    s2 = interp.mem.read_cstring(s2_ptr)
    if s1 < s2: r = -1
    elif s1 > s2: r = 1
    else: r = 0
    return Value(get_base_type(BaseType.INT), rvalue_val=('int', r))

def c_strcpy(interp, args, scope, expr_node):
    dst = args[0].read_ptr() if args[0].typ.is_pointer() else args[0].offset
    src = args[1].read_ptr() if args[1].typ.is_pointer() else args[1].offset
    s = interp.mem.read_cstring(src)
    interp.mem.write_bytes(dst, s.encode('latin-1') + b'\0')
    return Value(get_pointer_type(get_base_type(BaseType.CHAR)), rvalue_val=('ptr', dst))

def c_strcat(interp, args, scope, expr_node):
    dst = args[0].read_ptr() if args[0].typ.is_pointer() else args[0].offset
    src = args[1].read_ptr() if args[1].typ.is_pointer() else args[1].offset
    ds = interp.mem.read_cstring(dst)
    ss = interp.mem.read_cstring(src)
    interp.mem.write_bytes(dst, (ds + ss).encode('latin-1') + b'\0')
    return Value(get_pointer_type(get_base_type(BaseType.CHAR)), rvalue_val=('ptr', dst))

BUILTIN_FUNCTIONS = {
    'printf': c_printf, 'fprintf': c_fprintf, 'sprintf': c_sprintf,
    'putchar': c_putchar, 'puts': c_puts,
    'malloc': c_malloc, 'calloc': c_malloc, 'free': c_free,
    'exit': c_exit, 'abs': c_abs,
    'strlen': c_strlen, 'strcmp': c_strcmp, 'strcpy': c_strcpy, 'strcat': c_strcat,
}

# ============================================================
# MAIN
# ============================================================

def main():
    if len(sys.argv) < 2:
        print("Usage: picoc.py <file.c>", file=sys.stderr)
        sys.exit(1)
    filename = sys.argv[1]
    with open(filename, 'r') as f:
        source = f.read()
    interp = Interpreter()
    try:
        interp.run(source)
    except SystemExit:
        pass
    except ProgramError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    sys.exit(interp.exit_value)

if __name__ == '__main__':
    main()
