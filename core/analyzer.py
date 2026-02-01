from typing import Dict, List, Optional, Set, Any
from .ast import *
from .errors import CompileError, TypeError
from collections import deque

class Symbol:
    def __init__(self, name: str, type: str, node: Node, scope_level: int = 0, is_constant: bool = False):
        self.name = name
        self.type = type
        self.node = node
        self.scope_level = scope_level
        self.is_constant = is_constant
        self.is_used = False
        self.is_initialized = False

class Scope:
    def __init__(self, parent: Optional['Scope'] = None, name: str = ""):
        self.parent = parent
        self.name = name
        self.symbols: Dict[str, Symbol] = {}
        self.level = parent.level + 1 if parent else 0
        self.children: List['Scope'] = []
        if parent:
            parent.children.append(self)
    
    def add_symbol(self, symbol: Symbol):
        if symbol.name in self.symbols:
            raise CompileError(f"Переопределение '{symbol.name}'")
        self.symbols[symbol.name] = symbol
    
    def lookup(self, name: str) -> Optional[Symbol]:
        if name in self.symbols:
            return self.symbols[name]
        if self.parent:
            return self.parent.lookup(name)
        return None
    
    def lookup_current(self, name: str) -> Optional[Symbol]:
        return self.symbols.get(name)

class BasicBlock:
    def __init__(self, name: str = ""):
        self.name = name
        self.instructions: List[Node] = []
        self.next: Optional['BasicBlock'] = None
        self.true_branch: Optional['BasicBlock'] = None
        self.false_branch: Optional['BasicBlock'] = None
        self.is_loop_header = False
        self.is_exit = False

class SemanticAnalyzer:
    def __init__(self):
        self.global_scope = Scope(name="global")
        self.current_scope = self.global_scope
        self.errors: List[CompileError] = []
        self.warnings: List[str] = []
        self._add_builtin_types()
    
    def _add_builtin_types(self):
        for t in ['void', 'char', 'int', 'float', 'double', 'bool']:
            self.global_scope.add_symbol(Symbol(t, "type", Variable(name=t)))
    
    def analyze(self, program: Program):
        self.enter_scope("program")
        
        for decl in program.declarations:
            self._visit_node(decl)
        
        self.leave_scope()
        self._find_unused()
        
        if self.errors:
            raise self.errors[0]
    
    def enter_scope(self, name: str = ""):
        self.current_scope = Scope(self.current_scope, name)
    
    def leave_scope(self):
        if self.current_scope.parent:
            self.current_scope = self.current_scope.parent
    
    def add_error(self, message: str, node: Node):
        self.errors.append(CompileError(message, node.line, node.column))
    
    def add_warning(self, message: str, node: Node):
        self.warnings.append(f"Line {node.line}: {message}")
    
    def _find_unused(self):
        def check(sc: Scope):
            for s in sc.symbols.values():
                if not s.is_used and not s.name.startswith('_') and s.type not in ['type', 'function']:
                    self.add_warning(f"Неиспользуется '{s.name}'", s.node)
            for child in sc.children:
                check(child)
        check(self.global_scope)
    
    def _visit_node(self, node: Node) -> Any:
        method_name = f'visit_{node.__class__.__name__}'
        if hasattr(self, method_name):
            return getattr(self, method_name)(node)
        return self._default_visit(node)
    
    def _default_visit(self, node: Node):
        for val in node.__dict__.values():
            if isinstance(val, Node):
                self._visit_node(val)
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, Node):
                        self._visit_node(item)
    
    def visit_Program(self, node: Program):
        for decl in node.declarations:
            self._visit_node(decl)
    
    def visit_FunctionDecl(self, node: FunctionDecl):
        func_sym = Symbol(node.name, f"function:{node.return_type}", node, is_constant=True)
        self.current_scope.add_symbol(func_sym)
        
        if node.body:
            self.enter_scope(f"function:{node.name}")
            for p in node.params:
                param_sym = Symbol(p.name, p.type, p)
                self.current_scope.add_symbol(param_sym)
            self._visit_node(node.body)
            if node.return_type != 'void':
                if not self._check_for_return(node.body):
                    self.add_warning(f"Функция '{node.name}' может отжать значение", node)
            self.leave_scope()
    
    def _check_for_return(self, node: Node) -> bool:
        if isinstance(node, Return):
            return True
        elif isinstance(node, Block):
            for s in node.statements:
                if self._check_for_return(s):
                    return True
        elif isinstance(node, If):
            has_then = self._check_for_return(node.then_branch)
            has_else = node.else_branch and self._check_for_return(node.else_branch)
            return has_then and has_else
        return False
    
    def visit_VariableDecl(self, node: VariableDecl):
        type_exists = self.current_scope.lookup(node.type)
        if not type_exists and node.type not in ['int', 'char', 'float', 'double', 'void', 'bool']:
            self.add_error(f"Нет типа '{node.type}'", node)
        
        var_sym = Symbol(node.name, node.type, node, self.current_scope.level)
        try:
            self.current_scope.add_symbol(var_sym)
        except CompileError as e:
            self.add_error(str(e), node)
        
        if node.value:
            self._visit_node(node.value)
            if isinstance(node.value, Number):
                if 'int' not in node.type and 'float' not in node.type:
                    self.add_warning(f"Инициализация типа '{node.type}' числом", node)
            var_sym.is_initialized = True
    
    def visit_ArrayDeclaration(self, node: ArrayDeclaration):
        array_sym = Symbol(node.name, f"{node.type}[]", node, self.current_scope.level)
        try:
            self.current_scope.add_symbol(array_sym)
        except CompileError as e:
            self.add_error(str(e), node)
        
        if node.size:
            self._visit_node(node.size)
            if isinstance(node.size, Number) and node.size.value <= 0:
                self.add_error("Размер массива должен быть положительным", node.size)
        
        if node.value and isinstance(node.value, list):
            for init in node.value:
                self._visit_node(init)
    
    def visit_Assignment(self, node: Assignment):
        self._visit_node(node.left)
        self._visit_node(node.right)
        if isinstance(node.left, Variable):
            sym = self.current_scope.lookup(node.left.name)
            if sym:
                sym.is_used = True
                if sym.is_constant:
                    self.add_error(f"Нельзя изменять КОНСТАНТУ (постоянная величина) '{node.left.name}'", node)
    
    def visit_Variable(self, node: Variable):
        sym = self.current_scope.lookup(node.name)
        if not sym:
            self.add_error(f"Нет переменной '{node.name}'", node)
        else:
            sym.is_used = True
    
    def visit_BinaryOp(self, node: BinaryOp):
        self._visit_node(node.left)
        self._visit_node(node.right)
        if node.op == '/' and isinstance(node.right, Number) and node.right.value == 0:
            self.add_error("Деление на ноль", node.right)
    
    def visit_Call(self, node: Call):
        self._visit_node(node.func)
        for arg in node.args:
            self._visit_node(arg)
        if isinstance(node.func, Variable):
            func_sym = self.current_scope.lookup(node.func.name)
            if func_sym and 'function:' in func_sym.type:
                # todo: аргументы!
                pass
    
    def visit_Return(self, node: Return):
        if node.expr:
            self._visit_node(node.expr)
    
    def visit_If(self, node: If):
        self._visit_node(node.condition)
        self.enter_scope("if_then")
        self._visit_node(node.then_branch)
        self.leave_scope()
        if node.else_branch:
            self.enter_scope("if_else")
            self._visit_node(node.else_branch)
            self.leave_scope()
    
    def visit_While(self, node: While):
        self._visit_node(node.condition)
        self.enter_scope("while")
        self._visit_node(node.body)
        self.leave_scope()
    
    def visit_For(self, node: For):
        if node.init:
            self._visit_node(node.init)
        if node.condition:
            self._visit_node(node.condition)
        if node.increment:
            self._visit_node(node.increment)
        self.enter_scope("for")
        self._visit_node(node.body)
        self.leave_scope()
    
    def visit_StructDecl(self, node: StructDecl):
        struct_sym = Symbol(node.name, f"struct:{node.name}", node, is_constant=True)
        try:
            self.current_scope.add_symbol(struct_sym)
        except CompileError as e:
            self.add_error(str(e), node)
        self.enter_scope(f"struct:{node.name}")
        for field in node.fields:
            self._visit_node(field)
        self.leave_scope()
    
    def ast_to_cfg(self, node: Node) -> BasicBlock:
        def build_cfg_from_block(block_node: Block) -> BasicBlock:
            entry_block = BasicBlock("entry")
            current = entry_block
            
            for stmt in block_node.statements:
                if isinstance(stmt, If):
                    cond_block = BasicBlock("cond")
                    true_block = build_cfg_from_block(
                        stmt.then_branch if isinstance(stmt.then_branch, Block) 
                        else Block(statements=[stmt.then_branch])
                    )
                    
                    false_block = None
                    if stmt.else_branch:
                        false_block = build_cfg_from_block(
                            stmt.else_branch if isinstance(stmt.else_branch, Block)
                            else Block(statements=[stmt.else_branch])
                        )
                    
                    current.next = cond_block
                    cond_block.true_branch = true_block
                    cond_block.false_branch = false_block or BasicBlock("merge")
                    
                    current = cond_block.false_branch
                    
                elif isinstance(stmt, While):
                    loop_start = BasicBlock("loop_header")
                    loop_start.is_loop_header = True
                    
                    body_block = build_cfg_from_block(
                        stmt.body if isinstance(stmt.body, Block)
                        else Block(statements=[stmt.body])
                    )
                    
                    current.next = loop_start
                    loop_start.true_branch = body_block
                    loop_start.false_branch = BasicBlock("loop_exit")
                    body_block.next = loop_start
                    
                    current = loop_start.false_branch
                    
                elif isinstance(stmt, Return):
                    ret_block = BasicBlock("return")
                    ret_block.is_exit = True
                    ret_block.instructions.append(stmt)
                    current.next = ret_block
                    current = BasicBlock("unreachable")
                    
                else:
                    current.instructions.append(stmt)
            
            return entry_block
        
        if isinstance(node, Block):
            return build_cfg_from_block(node)
        elif isinstance(node, FunctionDecl) and node.body:
            func_block = BasicBlock(f"func_{node.name}")
            cfg = build_cfg_from_block(node.body)
            func_block.next = cfg
            return func_block
        
        return BasicBlock("unknown")