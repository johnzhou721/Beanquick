import logging

import ply.yacc as yacc
from collections import namedtuple

from .lexer import BeanquickLexer
from .helpers import BeanquickParseError
from .data import (
    BeanquickStatement,
    BeanquickTransaction, BeanquickPosting, BeanquickBalance,
    BeanquickPad, BeanquickPrice, BeanquickCommand
)

logger = logging.getLogger(__name__)

Tag = namedtuple('Tag', ['value'])
Link = namedtuple('Link', ['value'])

class BeanquickParser:
    tokens = BeanquickLexer.tokens

    # Top-level statement
    def p_statement(self, p):
        '''
        statement : transaction
                | balance
                | pad
                | price
                | command
        '''
        p[0] = p[1]

    # Transaction rule
    def p_transaction(self, p):
        '''
        transaction : optional_date amount_currency postings optional_payee_narration_block optional_tag_link_block optional_txn_metadata
        '''
        # p[1]=date, p[2]=(amt,cur), p[3]=postings, p[4]=(payee,narr), p[5]=(tags, links), p[6]=txn_meta
        amount, currency = p[2]
        payee, narration = (p[4] if p[4] else (None, None))
        tags, links = (p[5] if p[5] else (None, None))

        p[0] = BeanquickTransaction(
            raw_date=p[1],
            links=links or [],
            control_amount=amount,
            control_currency=currency,
            postings=p[3],
            payee=payee,
            narration=narration,
            tags=tags or [],
            metadata=p[6] or {}
        )

    # --- Optional components of a transaction ---
    def p_optional_date(self, p):
        '''optional_date : AT_DATE
                         | empty'''
        p[0] = p[1]

    def p_amount_currency(self, p):
        '''amount_currency : AMOUNT ID
                           | AMOUNT'''
        if len(p) == 3:
            p[0] = (p[1], p[2])  # amount and currency
        else:
            p[0] = (p[1], None)  # amount only, currency will be None
            
    # --- Postings rules (the core logic for from/to) ---
    def p_postings(self, p):
        '''postings : from_posting to_postings'''
        p[0] = [p[1]] + p[2]

    def p_from_posting(self, p):
        '''from_posting : FROM COLON ACCOUNT optional_posting_metadata'''
        # from posting does not parse amount, amount is determined by total and to postings
        p[0] = BeanquickPosting(account=p[3], metadata=p[4] or {})

    def p_to_postings(self, p):
        '''to_postings : to_posting
                       | to_postings to_posting'''
        if len(p) == 2:
            p[0] = [p[1]]
        else:
            p[0] = p[1] + [p[2]]

    def p_to_posting(self, p):
        '''to_posting : TO COLON ACCOUNT optional_amount optional_posting_metadata'''
        amount, currency = p[4]
        p[0] = BeanquickPosting(account=p[3], amount=amount, currency=currency, metadata=p[5] or {})

    def p_optional_amount(self, p):
        '''optional_amount : AMOUNT ID
                           | AMOUNT
                           | empty'''
        if len(p) == 3:
            p[0] = (p[1], p[2])
        elif len(p) == 2:
            p[0] = (p[1], None)
        else:
            p[0] = (None, None)

    # --- Narration, Tags, and Metadata rules ---
    def p_optional_payee_narration_block(self, p):
        '''optional_payee_narration_block : PIPE_CONTENT PIPE_CONTENT
                                          | PIPE_CONTENT
                                          | empty'''
        if len(p) == 3:  # |payee|narration
            p[0] = (p[1], p[2])
        elif len(p) == 2:  # |narration only
            p[0] = (None, p[1])
        else:  # empty
            p[0] = None

    def p_optional_tag_link_block(self, p):
        '''optional_tag_link_block : tag_link_list
                                   | empty'''
        if p[1] is None:
            p[0] = None
        else:
            # Separate tags and links from the mixed list
            tags = [item.value for item in p[1] if isinstance(item, Tag)]
            links = [item.value for item in p[1] if isinstance(item, Link)]
            p[0] = (tags, links)

    def p_tag_link_list(self, p):
        '''tag_link_list : tag_link_list tag_or_link
                        | tag_or_link'''
        if len(p) == 2:
            p[0] = [p[1]]
        else:
            p[0] = p[1] + [p[2]]

    def p_tag_or_link(self, p):
        '''tag_or_link : tag
                       | link'''
        p[0] = p[1]

    def p_tag(self, p):
        '''tag : HASH ID'''
        p[0] = Tag(p[2])

    def p_link(self, p):
        '''link : CARET ID'''
        p[0] = Link(p[2])

    def p_optional_txn_metadata(self, p):
        '''optional_txn_metadata : metadata_block
                                 | empty'''
        p[0] = p[1]
        
    def p_optional_posting_metadata(self, p):
        '''optional_posting_metadata : metadata_block
                                     | empty'''
        p[0] = p[1]

    def p_metadata_block(self, p):
        '''metadata_block : LBRACE kv_pairs RBRACE'''
        p[0] = dict(p[2])

    def p_kv_pairs(self, p):
        '''kv_pairs : kv_pair
                    | kv_pairs kv_pair'''
        if len(p) == 2:
            p[0] = [p[1]]
        else:
            p[0] = p[1] + [p[2]]

    def p_kv_pair(self, p):
        '''kv_pair : ID COLON value'''
        p[0] = (p[1], p[3])
        
    def p_value(self, p):
        '''value : ID
                 | QUOTED_STRING
                 | AMOUNT'''
        p[0] = p[1]

    # --- Balance, Pad, Price rules ---
    def p_balance(self, p):
        """balance : optional_date BAL ACCOUNT AMOUNT ID"""
        p[0] = BeanquickBalance(raw_date=p[1], account=p[3], amount=p[4], currency=p[5])

    def p_pad(self, p):
        """pad : optional_date PAD FROM COLON ACCOUNT TO COLON ACCOUNT"""
        p[0] = BeanquickPad(raw_date=p[1], account=p[5], target_account=p[8])

    def p_price(self, p):
        """price : optional_date PX ID AMOUNT ID"""
        p[0] = BeanquickPrice(raw_date=p[1], commodity=p[3], amount=p[4], currency=p[5])

    def p_command(self, p):
        '''command : SLASH_COMMAND optional_command_params'''
        raw_input = f"/{p[1]}"
        if p[2]:
            raw_input += " " + " ".join(str(param) for param in p[2])

        p[0] = BeanquickCommand(
            trigger=p[1],
            params=p[2] or [],
            raw_input=raw_input
        )
    
    def p_optional_command_params(self, p):
        '''optional_command_params : command_params
                                   | empty'''
        p[0] = p[1]

    def p_command_params(self, p):
        '''command_params : command_params COMMAND_PARAM
                          | COMMAND_PARAM'''
        if len(p) == 2:
            p[0]= [p[1]]
        else:
            p[0] = p[1] + [p[2]]
            
    # --- Empty rule ---
    def p_empty(self, p):
        'empty : '
        pass

    # --- Error rule ---
    def p_error(self, p):
        if p:
            raise BeanquickParseError(f"Syntax error near token '{p.type}' ('{p.value}') on line {p.lineno}, position {p.lexpos}")
        else:
            # This case might be triggered by an empty input after the trigger,
            # or if the lexer itself fails to provide tokens.
            raise BeanquickParseError("Syntax error: unexpected end of input or lexing problem.")

    
    def build(self, **kwargs):
        # import os
        # debug_dir = os.path.join(os.path.dirname(__file__), 'debug')
        # os.makedirs(debug_dir, exist_ok=True)
        
        # kwargs.setdefault('debug', True)
        # kwargs.setdefault('debugfile', os.path.join(debug_dir, 'parser.out'))
        # kwargs.setdefault('outputdir', debug_dir)
        
        try:
            self.parser = yacc.yacc(module=self, **kwargs)
        except Exception as e:
            # Check for common issues
            if hasattr(self, 'tokens'):
                logger.error(f"Tokens defined: {self.tokens}")
            else:
                logger.error("No tokens attribute found")
            raise

    def parse(self, data: str, lexer_instance: BeanquickLexer) -> BeanquickStatement | None:
        return self.parser.parse(input=data, lexer=lexer_instance.lexer)

