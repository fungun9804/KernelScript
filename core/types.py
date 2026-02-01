from dataclasses import dataclass
from typing import Dict, List, Optional, Union

@dataclass
class Type:
    name: str
    size: int = 0
    
    def __str__(self):
        return self.name

@dataclass
class PrimitiveType(Type):
    pass

@dataclass  
class PointerType(Type):
    base_type: Type
    
    def __str__(self):
        return f"{self.base_type}*"

@dataclass
class ArrayType(Type):
    element_type: Type
    size: Optional[int] = None
    
    def __str__(self):
        if self.size:
            return f"{self.element_type}[{self.size}]"
        return f"{self.element_type}[]"

class TypeSystem:
    def __init__(self):
        self.types: Dict[str, Type] = {}
        self._init()
    
    def _init(self):
        for n, s in [('void', 0), ('char', 1), ('int', 4), ('float', 4), ('double', 8), ('bool', 1)]:
            self.types[n] = PrimitiveType(n, s)
    
    def get_type(self, type_name: str) -> Optional[Type]:
        return self.types.get(type_name)
    
    def add_type(self, name: str, type_obj: Type):
        self.types[name] = type_obj