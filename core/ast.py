from dataclasses import dataclass, field
from typing import List, Optional, Union, Dict, Any

@dataclass(kw_only=True)
class Node:
    line: int = 0
    column: int = 0

@dataclass(kw_only=True)
class Program(Node):
    declarations: List[Node] = field(default_factory=list)

@dataclass(kw_only=True)
class Include(Node):
    filename: str = ""

@dataclass(kw_only=True)
class Define(Node):
    name: str = ""
    value: Optional[Node] = None

@dataclass(kw_only=True)
class Expression(Node):
    expr: Node = field(default_factory=lambda: Variable(name=""))

@dataclass(kw_only=True)
class VariableDecl(Node):
    type: str = ""
    name: str = ""
    value: Optional[Node] = None
    modifiers: List[str] = field(default_factory=list)
    
@dataclass(kw_only=True)
class ArrayDeclaration(Node):
    type: str = ""
    name: str = ""
    size: Optional[Node] = None
    value: Optional[Node] = None

@dataclass(kw_only=True)
class FunctionDecl(Node):
    return_type: str = ""
    name: str = ""
    params: List['Param'] = field(default_factory=list)
    body: Optional['Block'] = None
    modifiers: List[str] = field(default_factory=list)

@dataclass(kw_only=True)
class Param(Node):
    type: str = ""
    name: str = ""

@dataclass(kw_only=True)
class Block(Node):
    statements: List[Node] = field(default_factory=list)

@dataclass(kw_only=True)
class Return(Node):
    expr: Optional[Node] = None

@dataclass(kw_only=True)
class If(Node):
    condition: Node = field(default_factory=lambda: Bool(value=True))
    then_branch: Node = field(default_factory=lambda: Block(statements=[]))
    else_branch: Optional[Node] = None

@dataclass(kw_only=True)
class While(Node):
    condition: Node = field(default_factory=lambda: Bool(value=True))
    body: Node = field(default_factory=lambda: Block(statements=[]))

@dataclass(kw_only=True)
class For(Node):
    init: Optional[Node] = None
    condition: Optional[Node] = None
    increment: Optional[Node] = None
    body: Node = field(default_factory=lambda: Block(statements=[]))

@dataclass(kw_only=True)
class DoWhile(Node):
    body: Node = field(default_factory=lambda: Block(statements=[]))
    condition: Node = field(default_factory=lambda: Bool(value=True))

@dataclass(kw_only=True)
class Switch(Node):
    expr: Node = field(default_factory=lambda: Variable(name=""))
    cases: List['Case'] = field(default_factory=list)

@dataclass(kw_only=True)
class Case(Node):
    value: Optional[Node] = None
    statements: List[Node] = field(default_factory=list)

@dataclass(kw_only=True)
class Default(Node):
    statements: List[Node] = field(default_factory=list)

@dataclass(kw_only=True)
class Break(Node):
    pass

@dataclass(kw_only=True)
class Continue(Node):
    pass

@dataclass(kw_only=True)
class Goto(Node):
    label: str = ""

@dataclass(kw_only=True)
class Label(Node):
    name: str = ""
    statement: Node = field(default_factory=lambda: Block(statements=[]))

@dataclass(kw_only=True)
class BinaryOp(Node):
    op: str = ""
    left: Node = field(default_factory=lambda: Variable(name=""))
    right: Node = field(default_factory=lambda: Variable(name=""))

@dataclass(kw_only=True)
class UnaryOp(Node):
    op: str = ""
    expr: Node = field(default_factory=lambda: Variable(name=""))

@dataclass(kw_only=True)
class Call(Node):
    func: Node = field(default_factory=lambda: Variable(name=""))
    args: List[Node] = field(default_factory=list)

@dataclass(kw_only=True)
class ArrayAccess(Node):
    array: Node = field(default_factory=lambda: Variable(name=""))
    index: Node = field(default_factory=lambda: Variable(name=""))

@dataclass(kw_only=True)
class MemberAccess(Node):
    struct: Node = field(default_factory=lambda: Variable(name=""))
    member: str = ""
    is_arrow: bool = False

@dataclass(kw_only=True)
class Cast(Node):
    type: str = ""
    expr: Node = field(default_factory=lambda: Variable(name=""))

@dataclass(kw_only=True)
class SizeOf(Node):
    expr: Node = field(default_factory=lambda: Variable(name=""))

@dataclass(kw_only=True)
class Ternary(Node):
    condition: Node = field(default_factory=lambda: Bool(value=True))
    then_expr: Node = field(default_factory=lambda: Variable(name=""))
    else_expr: Node = field(default_factory=lambda: Variable(name=""))

@dataclass(kw_only=True)
class Assignment(Node):
    left: Node = field(default_factory=lambda: Variable(name=""))
    op: str = ""
    right: Node = field(default_factory=lambda: Variable(name=""))

@dataclass(kw_only=True)
class Variable(Node):
    name: str = ""

@dataclass(kw_only=True)
class Number(Node):
    value: Union[int, float] = 0

@dataclass(kw_only=True)
class String(Node):
    value: str = ""

@dataclass(kw_only=True)
class Char(Node):
    value: str = ""

@dataclass(kw_only=True)
class Bool(Node):
    value: bool = False

@dataclass(kw_only=True)
class Null(Node):
    pass

@dataclass(kw_only=True)
class StructDecl(Node):
    name: str = ""
    fields: List[VariableDecl] = field(default_factory=list)

@dataclass(kw_only=True)
class UnionDecl(Node):
    name: str = ""
    fields: List[VariableDecl] = field(default_factory=list)

@dataclass(kw_only=True)
class EnumDecl(Node):
    name: str = ""
    values: Dict[str, int] = field(default_factory=dict)

@dataclass(kw_only=True)
class Typedef(Node):
    type: Node = field(default_factory=lambda: Variable(name=""))
    alias: str = ""

# Мне так нада!
def ast_dump(node: Node, indent: int = 0) -> str:
    spaces = "  " * indent
    result = f"{spaces}{node.__class__.__name__}"
    
    if isinstance(node, Program):
        result += f" ({len(node.declarations)} деклараций этой вашей юса)"
        for decl in node.declarations:
            result += f"\n{ast_dump(decl, indent + 1)}"
    elif isinstance(node, FunctionDecl):
        result += f" {node.name} -> {node.return_type}"
        if node.body:
            result += f"\n{ast_dump(node.body, indent + 1)}"
    elif isinstance(node, Block):
        result += f" ({len(node.statements)} операторов у Бондарчука)"
        for stmt in node.statements:
            if stmt:
                result += f"\n{ast_dump(stmt, indent + 1)}"
    elif isinstance(node, Variable):
        result += f": {node.name}"
    elif isinstance(node, Number):
        result += f": {node.value}"
    elif isinstance(node, String):
        result += f': "{node.value}"'
    elif isinstance(node, BinaryOp):
        result += f": {node.op}"
        result += f"\n{ast_dump(node.left, indent + 1)}"
        result += f"\n{ast_dump(node.right, indent + 1)}"
    elif hasattr(node, 'name'):
        result += f": {node.name}"
    
    return result