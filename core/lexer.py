import re
from collections import namedtuple
from typing import Iterator, Optional
from .errors import LexerError

Token = namedtuple('Token', ['type', 'value', 'line', 'column'])

KEYWORDS = {
    'int', 'float', 'double', 'char', 'void', 'bool',
    'struct', 'union', 'enum', 'typedef',
    'if', 'else', 'while', 'for', 'do', 'switch', 'case', 'default',
    'break', 'continue', 'return', 'goto',
    'const', 'static', 'extern', 'register', 'volatile',
    'sizeof', 'typeof', 'alignof',
    'true', 'false', 'NULL',
    'signed', 'unsigned', 'short', 'long',
    '#include', '#define', '#ifdef', '#ifndef', '#endif', '#if', '#else', '#elif'
}

class KernelLexer:
    def __init__(self):
        self.tokens = []
        self.pos = 0
        
    def lex(self, code: str, filename: Optional[str] = None) -> Iterator[Token]:
        tok_regex = '|'.join([
            r'(?P<PREPROC>#[a-zA-Z_][a-zA-Z0-9_]*)',
            r'(?P<HEX>0[xX][0-9a-fA-F]+)',
            r'(?P<OCT>0[0-7]+)',
            r'(?P<FLOAT>\d+\.\d*([eE][+-]?\d+)?|\.\d+([eE][+-]?\d+)?)',
            r'(?P<INTEGER>\d+)',
            r'(?P<STRING>"([^"\\]|\\.)*")',
            r"(?P<CHAR>'[^'\\]*(\\.[^'\\]*)*')",
            r'(?P<ID>[a-zA-Z_][a-zA-Z0-9_]*)',
            r'(?P<OPERATOR>->|\+\+|--|<<|>>|<=|>=|==|!=|&&|\|\||\+=|-=|\*=|/=|%=|&=|\|=|\^=|<<=|>>=|[-+*/%=&|^~!<>?:.,;()\[\]{}])',
            r'(?P<WHITESPACE>[ \t]+)',
            r'(?P<NEWLINE>\n)',
            r'(?P<COMMENT>//[^\n]*|/\*.*?\*/)',
            r'(?P<MISMATCH>.)'
        ])
        
        line_num = 1
        line_start = 0
        in_comment = False
        
        for match in re.finditer(tok_regex, code, re.DOTALL):
            kind = match.lastgroup
            value = match.group()
            column = match.start() - line_start + 1
            
            if in_comment:
                if value.endswith('*/'):
                    in_comment = False
                continue
            
            if kind == 'PREPROC':
                yield Token('PREPROC', value, line_num, column)
            elif kind == 'HEX':
                yield Token('NUMBER', int(value, 16), line_num, column)
            elif kind == 'OCT':
                yield Token('NUMBER', int(value, 8), line_num, column)
            elif kind == 'FLOAT':
                yield Token('NUMBER', float(value), line_num, column)
            elif kind == 'INTEGER':
                yield Token('NUMBER', int(value), line_num, column)
            elif kind == 'STRING':
                content = value[1:-1]
                content = content.replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"').replace("\\'", "'").replace('\\\\', '\\')
                yield Token('STRING', content, line_num, column)
            elif kind == 'CHAR':
                content = value[1:-1]
                if content.startswith('\\'):
                    if content == '\\n': content = '\n'
                    elif content == '\\t': content = '\t'
                    elif content == '\\0': content = '\0'
                yield Token('CHAR', content, line_num, column)
            elif kind == 'ID':
                if value.lower() in KEYWORDS:
                    yield Token('KEYWORD', value.lower(), line_num, column)
                else:
                    yield Token('ID', value, line_num, column)
            elif kind == 'OPERATOR':
                yield Token('OPERATOR', value, line_num, column)
            elif kind == 'NEWLINE':
                line_num += 1
                line_start = match.end()
            elif kind == 'COMMENT':
                if value.startswith('/*') and not value.endswith('*/'):
                    in_comment = True
                continue
            elif kind == 'WHITESPACE':
                continue
            elif kind == 'MISMATCH':
                raise LexerError(f'Либо его не добавили... Либо ПРОВЕРЬ КОД!: {value!r}', line_num, column, filename)