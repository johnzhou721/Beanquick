"""Helpers to create entries."""

from __future__ import annotations

from typing import overload
from typing import TYPE_CHECKING

from beancount.core import data
from beancount.core.amount import A as BEANCOUNT_A
from beancount.core.amount import Amount as BeancountAmount
from beancount.core.position import Cost as BeancountCost
from beancount.core.position import Position as BeancountPosition

from beanquick.beans import BEANCOUNT_V3

if TYPE_CHECKING:  # pragma: no cover
    import datetime
    from decimal import Decimal

    from beanquick.beans.abc import Balance
    from beanquick.beans.abc import Close
    from beanquick.beans.abc import Commodity
    from beanquick.beans.abc import Document
    from beanquick.beans.abc import Event
    from beanquick.beans.abc import Meta
    from beanquick.beans.abc import Note
    from beanquick.beans.abc import Open
    from beanquick.beans.abc import Pad
    from beanquick.beans.abc import Position
    from beanquick.beans.abc import Posting
    from beanquick.beans.abc import Price
    from beanquick.beans.abc import Transaction
    from beanquick.beans.flags import Flag
    from beanquick.beans.protocols import Amount
    from beanquick.beans.protocols import Cost


@overload
def amount(amt: Amount) -> Amount: ...  # pragma: no cover


@overload
def amount(amt: str) -> Amount: ...  # pragma: no cover


@overload
def amount(amt: Decimal, currency: str) -> Amount: ...  # pragma: no cover


def amount(amt: Amount | Decimal | str, currency: str | None = None) -> Amount:
    """Amount from a string or tuple."""
    if isinstance(amt, str):
        return BEANCOUNT_A(amt)  # type: ignore[return-value]
    if hasattr(amt, "number") and hasattr(amt, "currency"):
        return amt
    if not isinstance(currency, str):  # pragma: no cover
        raise TypeError
    return BeancountAmount(amt, currency)  # type: ignore[return-value]


_amount = amount


def cost(
    number: Decimal,
    currency: str,
    date: datetime.date,
    label: str | None = None,
) -> Cost:
    """Create a Cost."""
    return BeancountCost(number, currency, date, label)


def position(units: Amount, cost: Cost | None) -> Position:
    """Create a Position."""
    return BeancountPosition(  # type: ignore[return-value]
        units,  # type: ignore[arg-type]
        cost,  # type: ignore[arg-type]
    )


def posting(
    account: str,
    units: Amount | str,
    cost: Cost | None = None,
    price: Amount | str | None = None,
    flag: str | None = None,
    meta: Meta | None = None,
) -> Posting:
    """Create a Beancount Posting."""
    if price is not None:
        price = amount(price)
    return data.Posting(  # type: ignore[return-value]
        account,
        amount(units),  # type: ignore[arg-type]
        cost,  # type: ignore[arg-type]
        price,  # type: ignore[arg-type]
        flag,
        dict(meta) if meta is not None else None,
    )


_EMPTY_SET: frozenset[str] = frozenset()


def transaction(
    meta: Meta,
    date: datetime.date,
    flag: Flag,
    payee: str | None,
    narration: str,
    tags: frozenset[str] | None = None,
    links: frozenset[str] | None = None,
    postings: list[Posting] | None = None,
) -> Transaction:
    """Create a Beancount Transaction."""
    return data.Transaction(  # type: ignore[return-value]
        dict(meta),
        date,
        flag,
        payee,
        narration,
        tags if tags is not None else _EMPTY_SET,
        links if links is not None else _EMPTY_SET,
        postings if postings is not None else [],  # type: ignore[arg-type]
    )


def balance(
    meta: Meta,
    date: datetime.date,
    account: str,
    amount: Amount | str,
    tolerance: Decimal | None = None,
    diff_amount: Amount | None = None,
) -> Balance:
    """Create a Beancount Balance."""
    return data.Balance(  # type: ignore[return-value]
        dict(meta),
        date,
        account,
        _amount(amount),  # type: ignore[arg-type]
        tolerance,
        diff_amount,  # type: ignore[arg-type]
    )


def close(
    meta: Meta,
    date: datetime.date,
    account: str,
) -> Close:
    """Create a Beancount Open."""
    return data.Close(  # type: ignore[return-value]
        dict(meta),
        date,
        account,
    )

def commodity(
    meta: Meta,
    date: datetime.date,
    currency: str,
) -> Commodity:
    """Create a Beancount Commodity."""
    return data.Commodity(  # type: ignore[return-value]
        dict(meta),
        date,
        currency,
    )


def event(
    meta: Meta,
    date: datetime.date,
    type: str,
    description: str,
) -> Event:
    """Create a Beancount Event."""
    return data.Event(  # type: ignore[return-value]
        dict(meta),
        date,
        type,
        description,
    )


def document(
    meta: Meta,
    date: datetime.date,
    account: str,
    filename: str,
    tags: frozenset[str] | None = None,
    links: frozenset[str] | None = None,
) -> Document:
    """Create a Beancount Document."""
    return data.Document(  # type: ignore[return-value]
        dict(meta),
        date,
        account,
        filename,
        tags,
        links,
    )


def note(
    meta: Meta,
    date: datetime.date,
    account: str,
    comment: str,
    tags: frozenset[str] | None = None,
    links: frozenset[str] | None = None,
) -> Note:
    """Create a Beancount Note."""
    if not BEANCOUNT_V3:  # pragma: no cover
        return data.Note(  # type: ignore[call-arg,return-value]
            dict(meta),
            date,
            account,
            comment,
        )
    return data.Note(  # type: ignore[return-value]
        dict(meta),
        date,
        account,
        comment,
        tags,
        links,
    )


def pad(
    meta: Meta,
    date: datetime.date,
    account: str,
    source_account: str,
) -> Pad:
    """Create a Beancount Pad."""
    return data.Pad(  # type: ignore[return-value]
        dict(meta),
        date,
        account,
        source_account,
    )


def open(  # noqa: A001
    meta: Meta,
    date: datetime.date,
    account: str,
    currencies: list[str],
    booking: data.Booking | None = None,
) -> Open:
    """Create a Beancount Open."""
    return data.Open(  # type: ignore[return-value]
        dict(meta),
        date,
        account,
        currencies,
        booking,
    )


def price(
    meta: Meta,
    date: datetime.date,
    currency: str,
    amount: Amount | str,
) -> Price:
    """Create a Beancount Price."""
    return data.Price(  # type: ignore[return-value]
        dict(meta),
        date,
        currency,
        _amount(amount),  # type: ignore[arg-type]
    )
