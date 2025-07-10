from __future__ import annotations
"""
Intermediate Representation (IR) data classes for Beanquick parser.

This module defines the data structures used as intermediate representation
between the PLY parser and final Beancount data structures. These classes
are designed to be simple and mutable, serving as the direct output of the
PLY parser.

Classes:
    BeanquickPosting: Represents a posting within a transaction
    BeanquickTransaction: Represents a complete transaction entry
    BeanquickBalance: Represents a balance assertion
    BeanquickPad: Represents an automatic padding entry
    BeanquickPrice: Represents a price tracking entry
    BeanquickCommand: Represents a command entry

Types:
    BeanquickStatement: Union type representing any possible parsed statement
"""

import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union


@dataclass
class BeanquickPosting:
    account: str
    amount: Optional[float] = None
    currency: Optional[str] = None
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class BeanquickTransaction:
    type: str = "transaction"
    raw_date: Optional[str] = None
    date: Optional[datetime.date] = None
    links: List[str] = field(default_factory=list)
    control_amount: Optional[float] = None
    control_currency: Optional[str] = None
    flag: Optional[str] = None
    payee: Optional[str] = None
    narration: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)
    postings: List[BeanquickPosting] = field(default_factory=list)


@dataclass
class BeanquickBalance:
    type: str = "balance"
    raw_date: Optional[str] = None
    date: Optional[datetime.date] = None
    account: str = ""
    amount: float = 0.0
    currency: str = ""


@dataclass
class BeanquickPad:
    type: str = "pad"
    raw_date: Optional[str] = None
    date: Optional[datetime.date] = None
    account: str = ""
    target_account: str = ""


@dataclass
class BeanquickPrice:
    type: str = "price"
    raw_date: Optional[str] = None
    date: Optional[datetime.date] = None
    commodity: str = ""
    amount: float = 0.0
    currency: str = ""

@dataclass
class BeanquickCommand:
    type: str = "command"
    trigger: str = ""
    params: List[Union[str, float]] = field(default_factory=list)
    raw_input: str = ""

# Union type for all possible statement types
BeanquickStatement = Union[BeanquickTransaction, BeanquickBalance, BeanquickPad, BeanquickPrice]