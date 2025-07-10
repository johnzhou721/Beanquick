from __future__ import annotations

import re
import datetime
from decimal import Decimal
from typing import Dict, Optional

from beanquick.util.date import smart_parse_date, local_today

from .template_renderer import TemplateRenderer
from .data import BeanquickTransaction, BeanquickBalance, BeanquickPad, BeanquickCommand, BeanquickStatement

class BeanquickProcessor:
    """Process and expand BC-CLI intermediate representation objects."""

    def __init__(self, config: Dict):
        # config can include aliases, default currency, etc.
        self.config = config
        self.template_renderer = TemplateRenderer()

    def process_statement(self, stmt: BeanquickStatement) -> BeanquickStatement:
        """Process any type of BC-CLI statement."""
        # 1. Parse date
        stmt.date = smart_parse_date(stmt.raw_date) if stmt.raw_date else local_today()

        # 2. Expand account aliases
        self._expand_aliases(stmt)

        # 3. If it's a transaction
        if isinstance(stmt, BeanquickTransaction):
            # Set default flag
            default_flag = self.config.get("defaults", {}).get("flag", "*")
            stmt.flag = default_flag

            # Set default narration if not provided
            if not stmt.narration:
                default_narration = self.config.get("defaults", {}).get("narration", "")
                # if default_narration:
                stmt.narration = default_narration

            # Perform amount balancing
            self._balance_transaction(stmt)
            
        return stmt

    def expand_command(self, cmd: BeanquickCommand) -> str:
        """
        Expand command using Jinja2 template engine.
        This method now delegates rendering tasks to JinjaTemplateRenderer.
        """
        command_templates = self.config.get("command_templates", {})
        
        if cmd.trigger not in command_templates:
            raise ValueError(f"Unknown command trigger: '{cmd.trigger}'")
        
        template_config = command_templates[cmd.trigger]
        
        # Delegate rendering task entirely to the new renderer module
        try:
            return self.template_renderer.render(
                template_config=template_config, 
                params=cmd.params
            )
        except ValueError as e:
            # Catch and re-raise errors from renderer with additional context
            raise ValueError(f"Failed to process command '{cmd.trigger}': {e}") from e
        
    def _resolve_date(self, raw_date: Optional[str]) -> str:
        """Convert @today, @-1d etc. to YYYY-MM-DD format."""
        if not raw_date or raw_date in ["@today", "@t"]:
            return datetime.date.today().isoformat()
        if raw_date in ["@yesterday", "@y", "@-1d"]:
            return (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        # More complex date parsing logic can be added here
        return raw_date

    def _expand_aliases(self, stmt: BeanquickStatement):
        """Expand account aliases."""
        aliases = self.config.get("aliases", {})
        if isinstance(stmt, BeanquickTransaction):
            for post in stmt.postings:
                post.account = aliases.get(post.account, post.account)
        elif isinstance(stmt, BeanquickBalance):
            stmt.account = aliases.get(stmt.account, stmt.account)
        elif isinstance(stmt, BeanquickPad):
            stmt.account = aliases.get(stmt.account, stmt.account)
            stmt.target_account = aliases.get(stmt.target_account, stmt.target_account)
        

    def _balance_transaction(self, txn: BeanquickTransaction):
        """Calculate and balance transaction amounts."""
        # Ensure all postings have currency
        default_currency = self.config.get("defaults", {}).get("currency", "USD")
        for p in txn.postings:
            p.currency = p.currency or txn.control_currency or default_currency

        # Find 'to' postings without amounts
        unbalanced_postings = [p for p in txn.postings[1:] if p.amount is None]

        if len(unbalanced_postings) > 1:
            raise ValueError("Transaction error: More than one posting without specified amount, cannot auto-balance.")

        # Calculate assigned amount
        assigned_amount = sum(p.amount for p in txn.postings if p.amount is not None)

        # If there's one posting without amount, calculate and fill it
        if len(unbalanced_postings) == 1:
            if txn.control_amount is not None:
                unbalanced_postings[0].amount = txn.control_amount - assigned_amount
            else:
                raise ValueError("Cannot auto-balance transaction: control amount is not specified")
        
        # Final validation
        final_sum = sum(Decimal(str(p.amount)) for p in txn.postings if p.amount is not None)
        control_amount = Decimal(str(txn.control_amount))
        if control_amount != final_sum:
            raise ValueError(f"Transaction unbalanced: total {txn.control_amount}, allocated {final_sum}")
