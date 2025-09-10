"""(De)serialisation of entries.

When adding entries, these are saved via the JSON API - using the functionality
of this module to obtain the appropriate data structures from
`beancount.core.data`. Similarly, for the full entry completion, a JSON
representation of the entry is provided.

This is not intended to work well enough for full roundtrips yet.
"""

from __future__ import annotations

import datetime
import re
from decimal import Decimal
from typing import Any

from beancount.parser.parser import parse_string
from beancount.core.amount import CURRENCY_RE

from beanquick.beans import create
from beanquick.beans.abc import Directive
from beanquick.beans.abc import Posting
from beanquick.beans.abc import Transaction
from beanquick.beans.helpers import replace
from beanquick.helpers import BeanquickError
from beanquick.util.date import parse_date


class InvalidAmountError(BeanquickError):
    """Invalid amount."""

    def __init__(self, amount: str) -> None:
        super().__init__(f"Invalid amount: {amount}")



def deserialise_posting(posting: Any) -> Posting:
    """Parse JSON to a Beancount Posting."""
    amount = posting.get("amount", "")
    entries, errors, _ = parse_string(
        f'2000-01-01 * "" ""\n Assets:Account {amount}',
    )
    if errors:
        raise InvalidAmountError(amount)
    txn = entries[0]
    if not isinstance(txn, Transaction):  # pragma: no cover
        msg = "Expected transaction"
        raise TypeError(msg)
    pos = txn.postings[0]
    return replace(
        pos,
        account=posting["account"],
        meta=posting.get("meta", {}) or None,
    )


def deserialise(json_entry: Any) -> Directive:
    """Parse JSON to a Beancount entry.

    Args:
        json_entry: The entry.

    Raises:
        KeyError: if one of the required entry fields is missing.
        BeanquickError: if the type of the given entry is not supported.
    """
    date = parse_date(json_entry.get("date", ""))[0]
    if not isinstance(date, datetime.date):
        msg = "Invalid entry date."
        raise BeanquickError(msg)
    if json_entry["t"] == "Transaction":
        postings = [deserialise_posting(pos) for pos in json_entry["postings"]]
        return create.transaction(
            meta=json_entry["meta"],
            date=date,
            flag=json_entry.get("flag", ""),
            payee=json_entry.get("payee", ""),
            narration=json_entry["narration"] or "",
            tags=frozenset(json_entry["tags"]),
            links=frozenset(json_entry["links"]),
            postings=postings,
        )
    if json_entry["t"] == "Balance":
        raw_amount = json_entry["amount"]

        # Code from Amount.to_string with modifications
        match = re.match(
            r"\s*([-+]?[0-9.]+)\s*({currency})".format(currency=CURRENCY_RE), raw_amount
        )
        if not match:
            raise InvalidAmountError(raw_amount)
        number, currency = match.group(1, 2)
        amount = create.amount(Decimal(number), currency)

        return create.balance(
            meta=json_entry["meta"],
            date=date,
            account=json_entry["account"],
            amount=amount,
        )
    if json_entry["t"] == "Open":
        commodities = json_entry.get("commodities", [])
        return create.open(
            meta=json_entry["meta"],
            date=date,
            account=json_entry["account"],
            currencies=commodities,
        )
    if json_entry["t"] == "Note":
        comment = json_entry["comment"].replace('"', "")
        return create.note(
            meta=json_entry["meta"],
            date=date,
            account=json_entry["account"],
            comment=comment,
        )
    if json_entry["t"] == "Close":
        return create.close(
            meta=json_entry["meta"],
            date=date,
            account=json_entry["account"],
        )
    if json_entry["t"] == "Commodity":
        return create.commodity(
            meta=json_entry["meta"],
            date=date,
            currency=json_entry["currency"],
        )
    if json_entry["t"] == "Event":
        return create.event(
            meta=json_entry["meta"],
            date=date,
            type=json_entry["type"],
            description=json_entry["description"],
        )
    if json_entry["t"] == "Pad":
        return create.pad(
            meta=json_entry["meta"],
            date=date,
            account=json_entry["account"],
            source_account=json_entry["source_account"],
        )
    if json_entry["t"] == "Price":
        return create.price(
            meta=json_entry["meta"],
            date=date,
            currency=json_entry["currency"],
            amount=json_entry["amount"],
        )
    msg = "Unsupported entry type."
    raise BeanquickError(msg)
