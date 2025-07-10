from __future__ import annotations

from decimal import Decimal

from beancount.core import data
from beancount.core.amount import Amount

from .data import (
    BeanquickStatement, BeanquickTransaction,
    BeanquickPosting, BeanquickPrice,
    BeanquickBalance, BeanquickPad
)

def generate_native_posting(posting: BeanquickPosting, is_from: bool = False, from_amount: Decimal = Decimal(0)) -> data.Posting:
    """
    Convert a BeanquickPosting to a beancount.core.data.Posting.
    """
    if is_from:
        amount_dec = -from_amount
    else:
        amount_dec = Decimal(str(posting.amount))

    units = Amount(amount_dec, posting.currency or "")
    
    return data.Posting(
        account=posting.account,
        units=units,
        cost=None,
        price=None,
        flag=None,
        meta=posting.metadata or {}
    )

def generate_native_transaction(txn: BeanquickTransaction) -> data.Transaction:
    """Convert a BeanquickTransaction to a beancount.core.data.Transaction."""
    if txn.date is None:
        raise ValueError("Transaction date cannot be None")
    
    from_posting_ir = next((p for p in txn.postings if getattr(p, 'is_from', False)), None)
    if not from_posting_ir:
        # In our design, the 'from' posting is always the first in the postings list
        from_posting_ir = txn.postings[0]

    from_amount_dec = Decimal(str(txn.control_amount))
    native_postings = [generate_native_posting(from_posting_ir, is_from=True, from_amount=from_amount_dec)]

    # Generate 'to' postings
    for p in txn.postings:
         if p != from_posting_ir:
            native_postings.append(generate_native_posting(p))
            
    return data.Transaction(
        meta=txn.metadata or {},
        date=txn.date,
        flag=txn.flag or "*",
        payee=txn.payee,
        narration=txn.narration,
        tags=frozenset(txn.tags or []),
        links=frozenset(txn.links or []),
        postings=native_postings
    )

def generate_native_balance(bal: BeanquickBalance) -> data.Balance:
    """Convert a BeanquickBalance to a beancount.core.data.Balance."""
    if bal.date is None:
        raise ValueError("Balance date cannot be None")
    
    amount_obj = Amount(Decimal(str(bal.amount)), bal.currency)
    return data.Balance(
        meta={},
        date=bal.date,
        account=bal.account,
        amount=amount_obj,
        tolerance=None,
        diff_amount=None,
    )

def generate_native_pad(pad: BeanquickPad) -> data.Pad:
    """Convert a BeanquickPad to a beancount.core.data.Pad."""
    if pad.date is None:
        raise ValueError("Pad date cannot be None")
    
    return data.Pad(meta={}, date=pad.date, account=pad.account, source_account=pad.target_account)
    
def generate_native_price(px: BeanquickPrice) -> data.Price:
    """Convert a BeanquickPrice to a beancount.core.data.Price."""
    if px.date is None:
        raise ValueError("Price date cannot be None")
    
    amount_obj = Amount(Decimal(str(px.amount)), px.currency)
    return data.Price(meta={}, date=px.date, currency=px.commodity, amount=amount_obj)


def to_native(stmt: BeanquickStatement) -> data.Directive:
    """Main conversion function that converts any type of IR object to native object."""
    if isinstance(stmt, BeanquickTransaction):
        return generate_native_transaction(stmt)
    if isinstance(stmt, BeanquickBalance):
        return generate_native_balance(stmt)
    if isinstance(stmt, BeanquickPad):
        return generate_native_pad(stmt)
    if isinstance(stmt, BeanquickPrice):
        return generate_native_price(stmt)
    raise TypeError(f"Unsupported BeanquickStatement type: {type(stmt)}")