class KernelError(Exception):
    def __init__(self, message, line=None, column=None, filename=None):
        super().__init__(message)
        self.line = line
        self.column = column
        self.filename = filename

class ParseError(KernelError):
    pass

class CompileError(KernelError):
    pass

class RuntimeError(KernelError):
    pass

class LexerError(KernelError):
    pass

class TypeError(KernelError):
    pass