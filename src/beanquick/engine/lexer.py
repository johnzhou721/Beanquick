import ply.lex as lex

from .helpers import BeanquickIllegalCharError

class BeanquickLexer:
    # Reserved keywords
    reserved = {
        'from': 'FROM',
        'to': 'TO',
        'bal': 'BAL',
        'pad': 'PAD',
        'px': 'PX',
    }

    # List of token names.
    tokens = [
        'AT_DATE',
        'AMOUNT',
        'ID',
        'ACCOUNT',
        'QUOTED_STRING',
        'PIPE_CONTENT',
        'LBRACE',
        'RBRACE',
        'HASH',
        'COLON',
        'CARET',
        'SLASH_COMMAND',
        'COMMAND_PARAM',
    ] + list(reserved.values())

    # Define lexer states
    states = (
        ('account', 'exclusive'),
        ('command', 'exclusive'),
    )

    # Regular expression rules for simple tokens
    t_LBRACE         = r'\{'
    t_RBRACE         = r'\}'
    t_HASH           = r'\#'
    t_CARET          = r'\^'
    t_ignore         = ' \t'  # Ignore spaces and tabs
    t_command_ignore = ' \t'  # Ignore spaces and tabs in command state

    # A regular expression rule with some action code
    def t_AMOUNT(self, t):
        r'[+-]?(?:\d*\.\d+|\d+)'  # Matches +5, -5.0, .5, 5.0, and 5
        t.value = float(t.value)
        return t

    def t_AT_DATE(self, t):
        r'@(?:"[^"]*"|[a-zA-Z0-9_\-\+]+)'
        if t.value.startswith('@"') and t.value.endswith('"'):
            t.value = t.value[2:-1]  # Strip @" and "
        else:
            t.value = t.value[1:]  # Strip the '@'
        return t

    def t_QUOTED_STRING(self, t):
        r'"[^"]*"'
        t.value = t.value[1:-1] # Strip the quotes
        return t

    def t_ID(self, t):
        r'[a-zA-Z_][a-zA-Z0-9_.-]*'
        t.type = self.reserved.get(t.value.lower(), 'ID') # Check for reserved words
        if t.type == 'BAL':
            t.lexer.begin('account')
        return t
    
    def t_COLON(self, t):
        r':'
        # Check if the previous token was FROM or TO
        if hasattr(self, '_last_token') and self._last_token in ['FROM', 'TO']:
            t.lexer.begin('account')  # Switch to account state
        return t
    
    def t_PIPE_CONTENT(self, t):
        r'\|([^|]*?)(?=\s*\||\#|\^|\{|\}|$)'
        t.value = t.value[1:].strip()
        return t

    def t_newline(self, t):
        r'\n+'
        t.lexer.lineno += len(t.value)
    
    # ACCOUNT state tokens
    def t_account_ACCOUNT(self, t):
        # The (?i) flag at the beginning makes the entire regex case-insensitive
        # But it only works fine for Python < 11
        # Instead explicitly handle case-insensitive matching
        r'[^\|\#\^\{\}\n]+?(?=\s+(?:[Ff][Rr][Oo][Mm]|[Tt][Oo])\b|\s+(?:[+-]?(?:\d*\.\d+|\d+))|\||\#|\^|\{|\}|\n|$)'
        t.value = t.value.strip()
        if t.value:
            t.lexer.begin('INITIAL')
            return t
        else:
            return None
    
    def t_account_newline(self, t):
        r'\n+'
        t.lexer.lineno += len(t.value)
        # t.lexer.begin('INITIAL')  # Return to initial state on newline
        # Stay in account state to allow newlines before account name

    # Add a catch-all for account state to handle end of input
    def t_account_eof(self, t):
        r'$'
        t.lexer.begin('INITIAL')
        return None
    
    def t_account_error(self, t):
        offending_char = str(t.value)[0] if t.value else "unknown"
        t.lexer.skip(1)
        raise BeanquickIllegalCharError(offending_char)
    
    def t_SLASH_COMMAND(self, t):
        r'/[a-zA-Z_][a-zA-Z0-9_.-]*'
        t.value = t.value[1:]
        t.lexer.begin('command')  # Switch to command state
        return t
    
    # COMMAND state tokens - for parsing command parameters
    def t_command_COMMAND_PARAM(self, t):
        r'(?:\d*\.\d+|\d+|[a-zA-Z_][a-zA-Z0-9_.-]*|"[^"]*")'
        # Handle different parameter types
        if t.value.startswith('"') and t.value.endswith('"'):
            t.value = t.value[1:-1]  # Strip quotes
        elif '.' in t.value and t.value.replace('.', '').isdigit():
            t.value = float(t.value)  # Convert to float
        elif t.value.isdigit():
            t.value = float(t.value)  # Convert to float (keeping consistent with AMOUNT)
        # Otherwise keep as string
        return t

    def t_command_newline(self, t):
        r'\n+'
        t.lexer.lineno += len(t.value)

    def t_command_eof(self, t):
        r'$'
        t.lexer.begin('INITIAL')
        return None
    
    def t_command_error(self, t):
        t.lexer.skip(1)  # Skip the bad character

    # Error handling rule
    def t_error(self, t):
        # Get the offending character safely
        offending_char = str(t.value)[0] if t.value else "unknown"

        # Skip the bad character and continue lexing
        t.lexer.skip(1)

        # Raise an error with the offending character
        raise BeanquickIllegalCharError(offending_char)
    
    def build(self, **kwargs):
        self.lexer = lex.lex(module=self, **kwargs)
        self._last_token = None
        # Store reference to original token method and replace it
        original_token = self.lexer.token
        
        def custom_token():
            tok = original_token()
            if tok:
                self._last_token = tok.type
            return tok
            
        self.lexer.token = custom_token
    
    def token(self):
        return self.lexer.token()
    
    def lex(self, data: str) -> list[lex.LexToken]: # For debugging primarily
        self.lexer.input(data)
        tokens = []
        while True:
            tok = self.lexer.token()
            if not tok:
                break
            tokens.append(tok)
        return tokens