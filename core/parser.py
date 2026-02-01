"""
Синтаксический анализатор для KERNELSCRIPT
Парсинг токенов в AST
"""

from typing import List, Optional
from .lexer import KernelLexer, Token
from .ast import *
from .errors import ParseError

class KernelParser:
    """Парсер C-подобного синтаксиса"""
    
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0
        self.debug = False
        self.in_function = False
        
    def peek(self, n: int = 0) -> Token:
        if self.pos + n < len(self.tokens):
            return self.tokens[self.pos + n]
        return Token('EOF', '', 0, 0)
    
    def consume(self) -> Token:
        token = self.peek()
        if token.type != 'EOF':
            self.pos += 1
        return token
    
    def expect(self, token_type: str, value: Optional[str] = None) -> Token:
        token = self.peek()
        if token.type == 'EOF':
            raise ParseError(f"Ожидался {token_type}, но достигнут конец файла", token.line, token.column)
        
        if token.type != token_type:
            raise ParseError(f"Ожидался {token_type}, получен {token.type}", token.line, token.column)
        
        if value is not None and token.value != value:
            raise ParseError(f"Ожидался {value}, получен {token.value}", token.line, token.column)
        
        return self.consume()
    
    def match(self, token_type: str, value: Optional[str] = None) -> bool:
        token = self.peek()
        if token.type == token_type and (value is None or token.value == value):
            return True
        return False
    
    def skip_newlines(self):
        while self.match('NEWLINE'):
            self.consume()
    
    def parse(self) -> Program:
        """Парсит всю программу"""
        declarations = []
        
        self.skip_newlines()
        while not self.match('EOF'):
            try:
                if self.match('PREPROC'):
                    decl = self.parse_preprocessor()
                    if decl:
                        declarations.append(decl)
                else:
                    decl = self.parse_top_level_declaration()
                    if decl:
                        declarations.append(decl)
                
                self.skip_newlines()
            except ParseError as e:
                if self.debug:
                    print(f"ParseError: {e} at line {e.line}, column {e.column}")
                self.consume()
        
        return Program(declarations=declarations)
        
    def parse_declaration(self, is_global: bool = False) -> Union[VariableDecl, ArrayDeclaration]:
        """Парсит объявление переменной ИЛИ массива"""
        type_spec = self.parse_type_specifier()
        
        if not self.match('ID'):
            raise ParseError("Ожидалось имя переменной")
        
        name = self.consume().value
        
        # ПРОВЕРКА НА МАССИВ: если после имени идет '['
        if self.match('OPERATOR', '['):
            return self.parse_array_declaration(type_spec, name, is_global)
        
        # Обычная переменная
        value = None
        if self.match('OPERATOR', '='):
            self.consume()
            value = self.parse_expression()
        
        if not is_global or (is_global and not self.in_function):
            self.expect('OPERATOR', ';')
        
        return VariableDecl(type=type_spec, name=name, value=value)
        
    def parse_array_declaration(self, type_spec: str, name: str, is_global: bool) -> ArrayDeclaration:
        """Парсит объявление массива: int arr[10]; или int arr[] = {1,2,3};"""
        self.expect('OPERATOR', '[')
        
        size = None
        if not self.match('OPERATOR', ']'):
            size = self.parse_expression()
        
        self.expect('OPERATOR', ']')
        
        value = None
        if self.match('OPERATOR', '='):
            self.consume()
            value = self.parse_initializer_list()
        
        if not is_global or (is_global and not self.in_function):
            self.expect('OPERATOR', ';')
        
        return ArrayDeclaration(type=type_spec, name=name, size=size, value=value)
    
    def parse_initializer_list(self) -> List[Node]:
        """Парсит список инициализации: {1, 2, 3}"""
        self.expect('OPERATOR', '{')
        
        values = []
        if not self.match('OPERATOR', '}'):
            values.append(self.parse_expression())
            while self.match('OPERATOR', ','):
                self.consume()
                if self.match('OPERATOR', '}'):
                    break
                values.append(self.parse_expression())
        
        self.expect('OPERATOR', '}')
        return values
    
    def parse_preprocessor(self) -> Optional[Node]:
        """Парсит препроцессорные директивы"""
        preproc = self.consume()
        
        if preproc.value == '#include':
            # Может быть <stdio.h> или "stdio.h"
            if self.match('OPERATOR', '<'):
                self.consume()  # Пропускаем '<'
                filename = []
                while not self.match('OPERATOR', '>') and not self.match('EOF'):
                    filename.append(self.consume().value)
                self.expect('OPERATOR', '>')
                filename = ''.join(filename)
            else:
                filename_token = self.expect('STRING')
                filename = filename_token.value.strip('"')
            
            self.skip_newlines()
            return Include(filename=filename)
        elif preproc.value == '#define':
            name = self.expect('ID').value
            value = None
            if not self.match('NEWLINE') and not self.match('EOF'):
                value = self.parse_expression()
            self.skip_newlines()
            return Define(name=name, value=value)
        
        # Пропускаем другие директивы
        while not self.match('NEWLINE') and not self.match('EOF'):
            self.consume()
        self.skip_newlines()
        return None
    
    def parse_top_level_declaration(self) -> Node:
        """Парсит объявление верхнего уровня"""
        saved_pos = self.pos
        
        # 1. Пробуем структуру/объединение/перечисление
        if self.match('KEYWORD'):
            kw = self.peek().value
            if kw == 'struct':
                return self.parse_struct_declaration()
            elif kw == 'union':
                return self.parse_union_declaration()
            elif kw == 'enum':
                return self.parse_enum_declaration()
            elif kw == 'typedef':
                return self.parse_typedef()
        
        # 2. Пробуем функцию
        try:
            return self.parse_function_declaration()
        except ParseError:
            self.pos = saved_pos
        
        # 3. Пробуем объявление переменной/массива
        try:
            return self.parse_declaration(is_global=True)
        except ParseError:
            self.pos = saved_pos
        
        # 4. Пробуем выражение (вызов функции и т.д.)
        try:
            expr = self.parse_expression()
            if self.match('OPERATOR', ';'):
                self.consume()
                return Expression(expr=expr)
        except ParseError:
            self.pos = saved_pos
        
        token = self.peek()
        raise ParseError(
            f"Не могу распарсить объявление, начинающееся с {token.type}='{token.value}'",
            token.line, token.column
        )
        
    def parse_union_declaration(self) -> UnionDecl:
        """Парсит объявление объединения: union Name { ... };"""
        self.expect('KEYWORD', 'union')
        
        name = ""
        if self.match('ID'):
            name = self.consume().value
        
        fields = []
        if self.match('OPERATOR', '{'):
            self.consume()
            self.skip_newlines()
            
            while not self.match('OPERATOR', '}'):
                field_type = self.parse_type_specifier()
                field_name = self.expect('ID').value
                
                # Массив в объединении?
                if self.match('OPERATOR', '['):
                    self.consume()
                    if not self.match('OPERATOR', ']'):
                        self.parse_expression()  # Размер массива
                    self.expect('OPERATOR', ']')
                    field_type += '[]'
                
                self.expect('OPERATOR', ';')
                self.skip_newlines()
                
                fields.append(VariableDecl(type=field_type, name=field_name))
            
            self.expect('OPERATOR', '}')
        
        self.expect('OPERATOR', ';')
        return UnionDecl(name=name, fields=fields)
      
    def parse_enum_declaration(self) -> EnumDecl:
        """Парсит объявление перечисления: enum Name { A, B, C };"""
        self.expect('KEYWORD', 'enum')
        
        name = ""
        if self.match('ID'):
            name = self.consume().value
        
        values = {}
        if self.match('OPERATOR', '{'):
            self.consume()
            self.skip_newlines()
            
            current_value = 0
            first = True
            
            while not self.match('OPERATOR', '}'):
                if not first:
                    self.expect('OPERATOR', ',')
                    self.skip_newlines()
                
                ident = self.expect('ID').value
                
                if self.match('OPERATOR', '='):
                    self.consume()
                    expr = self.parse_expression()
                    # Пока просто числа, потом добавим вычисление констант
                    if isinstance(expr, Number):
                        current_value = expr.value
                
                values[ident] = current_value
                current_value += 1
                first = False
                self.skip_newlines()
            
            self.expect('OPERATOR', '}')
        
        self.expect('OPERATOR', ';')
        return EnumDecl(name=name, values=values)
            
    def parse_typedef(self) -> Typedef:
        """Парсит определение типа: typedef int MyInt;"""
        self.expect('KEYWORD', 'typedef')
        
        # Парсим базовый тип
        base_type = self.parse_type_specifier()
        
        # Парсим алиас(ы)
        aliases = []
        
        # Может быть несколько: typedef int MyInt, *MyIntPtr;
        while True:
            # Указатели?
            pointers = 0
            while self.match('OPERATOR', '*'):
                self.consume()
                pointers += 1
            
            alias_name = self.expect('ID').value
            
            # Массив?
            array_dims = []
            while self.match('OPERATOR', '['):
                self.consume()
                if not self.match('OPERATOR', ']'):
                    self.parse_expression()  # Размер массива
                self.expect('OPERATOR', ']')
                array_dims.append('[]')
            
            # Собираем полный тип
            full_type = base_type
            if pointers:
                full_type += ' *' * pointers
            for dim in array_dims:
                full_type += dim
            
            aliases.append((alias_name, full_type))
            
            if not self.match('OPERATOR', ','):
                break
            self.consume()  # Пропускаем запятую
        
        self.expect('OPERATOR', ';')
        
        # Пока возвращаем первый алиас, потом можно расширить
        return Typedef(
            type=Variable(name=full_type),  # Упрощенно
            alias=aliases[0][0]
        )
        
    def parse_struct_declaration(self) -> StructDecl:
        """Парсит объявление структуры: struct Name { ... };"""
        self.expect('KEYWORD', 'struct')
        
        name = ""
        if self.match('ID'):
            name = self.consume().value
        
        fields = []
        if self.match('OPERATOR', '{'):
            self.consume()
            self.skip_newlines()
            
            while not self.match('OPERATOR', '}'):
                # Парсим поля структуры
                field_type = self.parse_type_specifier()
                field_name = self.expect('ID').value
                
                # Массив в структуре?
                array_size = None
                if self.match('OPERATOR', '['):
                    self.consume()
                    if not self.match('OPERATOR', ']'):
                        array_size = self.parse_expression()
                    self.expect('OPERATOR', ']')
                
                self.expect('OPERATOR', ';')
                self.skip_newlines()
                
                field_node = VariableDecl(type=field_type, name=field_name)
                if array_size is not None:
                    # Создаем узел массива для поля структуры
                    field_node = ArrayDeclaration(
                        type=field_type,
                        name=field_name,
                        size=array_size,
                        value=None
                    )
                
                fields.append(field_node)
            
            self.expect('OPERATOR', '}')
        
        self.expect('OPERATOR', ';')
        return StructDecl(name=name, fields=fields)
    
    def parse_type_specifier(self) -> str:
        """Парсит спецификатор типа"""
        type_parts = []
        
        if self.match('KEYWORD') and self.peek().value in ('signed', 'unsigned'):
            type_parts.append(self.consume().value)
        
        if self.match('KEYWORD') and self.peek().value in ('void', 'char', 'short', 'int', 'long', 'float', 'double', '_Bool'):
            type_parts.append(self.consume().value)
        elif self.match('ID'):
            type_parts.append(self.consume().value)
        else:
            raise ParseError("Ожидался тип")
        
        while self.match('OPERATOR', '*'):
            type_parts.append(self.consume().value)
        
        return ' '.join(type_parts)
    
    def parse_function_declaration(self) -> FunctionDecl:
        """Парсит объявление функции"""
        return_type = self.parse_type_specifier()
        
        if not self.match('ID'):
            raise ParseError("Ожидалось имя функции")
        name = self.consume().value
        
        self.expect('OPERATOR', '(')
        
        params = []
        # Сначала проверяем есть ли параметры
        saved_pos = self.pos
        try:
            # Пробуем распарсить первый параметр
            if not self.match('OPERATOR', ')'):
                params.append(self.parse_parameter())
                # Парсим остальные параметры через запятую
                while self.match('OPERATOR', ','):
                    self.consume()
                    if self.match('OPERATOR', ')'):
                        break
                    params.append(self.parse_parameter())
        except ParseError:
            # Если не получилось - возможно это `()` или `(void)`
            self.pos = saved_pos
            # Проверяем специальный случай `(void)`
            if self.match('KEYWORD', 'void'):
                self.consume()  # Пропускаем void
            # В любом случае ждём закрывающую скобку
        
        self.expect('OPERATOR', ')')
        
        body = None
        if self.match('OPERATOR', '{'):
            self.in_function = True
            body = self.parse_block()
            self.in_function = False
        else:
            self.expect('OPERATOR', ';')
        
        return FunctionDecl(return_type=return_type, name=name, params=params, body=body)
    
    def parse_parameter(self) -> Param:
        """Парсит параметр функции"""
        param_type = self.parse_type_specifier()
        
        param_name = None
        if self.match('ID'):
            param_name = self.consume().value
        
        return Param(type=param_type, name=param_name)
    
    def parse_variable_declaration(self, is_global: bool = False) -> VariableDecl:
        """Парсит объявление переменной"""
        type_spec = self.parse_type_specifier()
        
        if not self.match('ID'):
            raise ParseError("Ожидалось имя переменной")
        
        name = self.consume().value
        
        if self.match('OPERATOR', '['):
            self.consume()
            if not self.match('OPERATOR', ']'):
                self.parse_expression()
            self.expect('OPERATOR', ']')
            type_spec += '[]'
        
        value = None
        if self.match('OPERATOR', '='):
            self.consume()
            value = self.parse_expression()
        
        if not is_global or (is_global and not self.in_function):
            self.expect('OPERATOR', ';')
        
        return VariableDecl(type=type_spec, name=name, value=value)
    
    def parse_block(self) -> Block:
        """Парсит блок кода { ... }"""
        self.expect('OPERATOR', '{')
        
        statements = []
        self.skip_newlines()
        
        while not self.match('OPERATOR', '}'):
            if self.match('EOF'):
                raise ParseError("Незакрытый блок")
            
            stmt = self.parse_statement()
            if stmt:
                statements.append(stmt)
            
            self.skip_newlines()
        
        self.expect('OPERATOR', '}')
        return Block(statements=statements)
    
    def parse_statement(self) -> Optional[Node]:
        """Парсит оператор"""
        self.skip_newlines()
        
        if self.match('OPERATOR', ';'):
            self.consume()
            return None
        
        if self.match('KEYWORD'):
            keyword = self.peek().value
            
            if keyword == 'struct':
                return self.parse_struct_declaration()
            elif keyword == 'union':
                return self.parse_union_declaration()
            elif keyword == 'enum':
                return self.parse_enum_declaration()
            elif keyword == 'typedef':
                return self.parse_typedef()
            elif keyword == 'return':
                return self.parse_return()
            elif keyword == 'if':
                return self.parse_if()
            elif keyword == 'while':
                return self.parse_while()
            elif keyword == 'for':
                return self.parse_for()
            elif keyword == 'do':
                return self.parse_do_while()
            elif keyword == 'break':
                self.consume()
                self.expect('OPERATOR', ';')
                return Break()
            elif keyword == 'continue':
                self.consume()
                self.expect('OPERATOR', ';')
                return Continue()
        
        saved_pos = self.pos
        
        try:
            return self.parse_declaration(is_global=False)  # ИЗМЕНИЛ!
        except ParseError:
            self.pos = saved_pos
        
        try:
            expr = self.parse_expression()
            if self.match('OPERATOR', ';'):
                self.consume()
                return Expression(expr=expr)
        except ParseError:
            self.pos = saved_pos
        
        token = self.peek()
        raise ParseError(f"Не могу распарсить оператор, начинающийся с {token.type}='{token.value}'")
    
    def parse_return(self) -> Return:
        """Парсит return"""
        self.expect('KEYWORD', 'return')
        
        expr = None
        if not self.match('OPERATOR', ';'):
            expr = self.parse_expression()
        
        self.expect('OPERATOR', ';')
        return Return(expr=expr)
    
    def parse_if(self) -> If:
        """Парсит if"""
        self.expect('KEYWORD', 'if')
        self.expect('OPERATOR', '(')
        condition = self.parse_expression()
        self.expect('OPERATOR', ')')
        
        then_branch = self.parse_statement()
        
        else_branch = None
        if self.match('KEYWORD') and self.peek().value == 'else':
            self.consume()
            else_branch = self.parse_statement()
        
        return If(condition=condition, then_branch=then_branch, else_branch=else_branch)
    
    def parse_while(self) -> While:
        """Парсит while"""
        self.expect('KEYWORD', 'while')
        self.expect('OPERATOR', '(')
        condition = self.parse_expression()
        self.expect('OPERATOR', ')')
        
        body = self.parse_statement()
        
        return While(condition=condition, body=body)
    
    def parse_for(self) -> For:
        """Парсит for"""
        self.expect('KEYWORD', 'for')
        self.expect('OPERATOR', '(')
        
        init = None
        if not self.match('OPERATOR', ';'):
            init = self.parse_for_init()
        self.expect('OPERATOR', ';')
        
        condition = None
        if not self.match('OPERATOR', ';'):
            condition = self.parse_expression()
        self.expect('OPERATOR', ';')
        
        increment = None
        if not self.match('OPERATOR', ')'):
            increment = self.parse_expression()
        self.expect('OPERATOR', ')')
        
        body = self.parse_statement()
        
        return For(init=init, condition=condition, increment=increment, body=body)
    
    def parse_for_init(self) -> Node:
        """Парсит инициализацию for"""
        saved_pos = self.pos
        try:
            return self.parse_declaration(is_global=False)  # ИЗМЕНИЛ!
        except ParseError:
            self.pos = saved_pos
            return self.parse_expression()
    
    def parse_do_while(self) -> DoWhile:
        """Парсит do-while"""
        self.expect('KEYWORD', 'do')
        
        body = self.parse_statement()
        
        self.expect('KEYWORD', 'while')
        self.expect('OPERATOR', '(')
        condition = self.parse_expression()
        self.expect('OPERATOR', ')')
        self.expect('OPERATOR', ';')
        
        return DoWhile(body=body, condition=condition)
    
    def parse_expression(self) -> Node:
        return self.parse_assignment()
    
    def parse_assignment(self) -> Node:
        expr = self.parse_ternary()
        
        if self.match('OPERATOR') and self.peek().value in ('=', '+=', '-=', '*=', '/=', '%=', '&=', '|=', '^=', '<<=', '>>='):
            op = self.consume().value
            right = self.parse_assignment()
            return Assignment(left=expr, op=op, right=right)
        
        return expr
    
    def parse_ternary(self) -> Node:
        expr = self.parse_logical_or()
        
        if self.match('OPERATOR', '?'):
            self.consume()
            then_expr = self.parse_expression()
            self.expect('OPERATOR', ':')
            else_expr = self.parse_ternary()
            return Ternary(condition=expr, then_expr=then_expr, else_expr=else_expr)
        
        return expr
    
    def parse_logical_or(self) -> Node:
        expr = self.parse_logical_and()
        
        while self.match('OPERATOR', '||'):
            op = self.consume().value
            right = self.parse_logical_and()
            expr = BinaryOp(op=op, left=expr, right=right)
        
        return expr
    
    def parse_logical_and(self) -> Node:
        expr = self.parse_bitwise_or()
        
        while self.match('OPERATOR', '&&'):
            op = self.consume().value
            right = self.parse_bitwise_or()
            expr = BinaryOp(op=op, left=expr, right=right)
        
        return expr
    
    def parse_bitwise_or(self) -> Node:
        expr = self.parse_bitwise_xor()
        
        while self.match('OPERATOR', '|'):
            op = self.consume().value
            right = self.parse_bitwise_xor()
            expr = BinaryOp(op=op, left=expr, right=right)
        
        return expr
    
    def parse_bitwise_xor(self) -> Node:
        expr = self.parse_bitwise_and()
        
        while self.match('OPERATOR', '^'):
            op = self.consume().value
            right = self.parse_bitwise_and()
            expr = BinaryOp(op=op, left=expr, right=right)
        
        return expr
    
    def parse_bitwise_and(self) -> Node:
        expr = self.parse_equality()
        
        while self.match('OPERATOR', '&'):
            op = self.consume().value
            right = self.parse_equality()
            expr = BinaryOp(op=op, left=expr, right=right)
        
        return expr
    
    def parse_equality(self) -> Node:
        expr = self.parse_relational()
        
        while self.match('OPERATOR') and self.peek().value in ('==', '!='):
            op = self.consume().value
            right = self.parse_relational()
            expr = BinaryOp(op=op, left=expr, right=right)
        
        return expr
    
    def parse_relational(self) -> Node:
        expr = self.parse_shift()
        
        while self.match('OPERATOR') and self.peek().value in ('<', '>', '<=', '>='):
            op = self.consume().value
            right = self.parse_shift()
            expr = BinaryOp(op=op, left=expr, right=right)
        
        return expr
    
    def parse_shift(self) -> Node:
        expr = self.parse_additive()
        
        while self.match('OPERATOR') and self.peek().value in ('<<', '>>'):
            op = self.consume().value
            right = self.parse_additive()
            expr = BinaryOp(op=op, left=expr, right=right)
        
        return expr
    
    def parse_additive(self) -> Node:
        expr = self.parse_multiplicative()
        
        while self.match('OPERATOR') and self.peek().value in ('+', '-'):
            op = self.consume().value
            right = self.parse_multiplicative()
            expr = BinaryOp(op=op, left=expr, right=right)
        
        return expr
    
    def parse_multiplicative(self) -> Node:
        expr = self.parse_unary()
        
        while self.match('OPERATOR') and self.peek().value in ('*', '/', '%'):
            op = self.consume().value
            right = self.parse_unary()
            expr = BinaryOp(op=op, left=expr, right=right)
        
        return expr
    
    def parse_unary(self) -> Node:
        if self.match('OPERATOR') and self.peek().value in ('+', '-', '!', '~', '++', '--', '*', '&'):
            op = self.consume().value
            expr = self.parse_unary()
            return UnaryOp(op=op, expr=expr)
        
        if self.match('KEYWORD') and self.peek().value == 'sizeof':
            self.consume()
            if self.match('OPERATOR', '('):
                self.consume()
                saved_pos = self.pos
                try:
                    type_spec = self.parse_type_specifier()
                    self.expect('OPERATOR', ')')
                    return SizeOf(expr=type_spec)
                except ParseError:
                    self.pos = saved_pos
            
            expr = self.parse_unary()
            return SizeOf(expr=expr)
        
        return self.parse_postfix()
    
    def parse_postfix(self) -> Node:
        expr = self.parse_primary()
        
        while True:
            if self.match('OPERATOR', '['):
                self.consume()
                index = self.parse_expression()
                self.expect('OPERATOR', ']')
                expr = ArrayAccess(array=expr, index=index)
            elif self.match('OPERATOR', '('):
                self.consume()
                args = []
                if not self.match('OPERATOR', ')'):
                    args.append(self.parse_expression())
                    while self.match('OPERATOR', ','):
                        self.consume()
                        args.append(self.parse_expression())
                self.expect('OPERATOR', ')')
                expr = Call(func=expr, args=args)
            elif self.match('OPERATOR', '.'):
                self.consume()
                member = self.expect('ID').value
                expr = MemberAccess(struct=expr, member=member, is_arrow=False)
            elif self.match('OPERATOR', '->'):
                self.consume()
                member = self.expect('ID').value
                expr = MemberAccess(struct=expr, member=member, is_arrow=True)
            elif self.match('OPERATOR') and self.peek().value in ('++', '--'):
                op = self.consume().value
                expr = UnaryOp(op=op + '_post', expr=expr)
            else:
                break
        
        return expr
    
    def parse_primary(self) -> Node:
        token = self.peek()
        
        if token.type == 'EOF':
            raise ParseError("Неожиданный конец файла")
        
        if token.value == '(':
            self.consume()
            expr = self.parse_expression()
            self.expect('OPERATOR', ')')
            return expr
        
        elif token.type == 'ID':
            name = self.consume().value
            return Variable(name=name)
        
        elif token.type == 'NUMBER':
            value = self.consume().value
            # value уже число из лексера (int или float)
            return Number(value=value)
        
        elif token.type == 'STRING':
            value = self.consume().value
            return String(value=value)
        
        elif token.type == 'CHAR':
            value = self.consume().value
            return Char(value=value)
        
        elif token.type == 'KEYWORD':
            if token.value in ('true', 'false'):
                value = self.consume().value
                return Bool(value=(value == 'true'))
            elif token.value == 'NULL':
                self.consume()
                return Null()
        
        raise ParseError(f"Неожиданный токен {token.type}='{token.value}'", token.line, token.column)