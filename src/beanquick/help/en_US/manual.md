# Beanquick User Manual

Welcome to Beanquick! This manual will help you quickly master the art of entering financial transactions with lightning speed and precision.

## Table of Contents

1. [What is Beanquick?](#what-is-beanquick)
2. [Getting Started](#getting-started)
3. [Basic Syntax](#basic-syntax)
4. [Transaction Types](#transaction-types)
5. [Beyond Transactions](#beyond-transactions)
6. [Templates](#templates)
7. [Quick Reference](#quick-reference)
8. [Getting More Help](#getting-more-help)

---

## What is Beanquick?

Beanquick is a fast, intuitive syntax for entering double-entry bookkeeping transactions that compile to **Beancount** format. Instead of writing verbose Beancount entries, you can use simple, natural language to record your financial transactions and Beanquick will automatically convert them into properly formatted Beancount entries.

[Beancount](https://github.com/beancount/beancount/)

---

## Getting Started

### Entry Modes

Beanquick offers two ways to enter your financial data:

**Quick Mode (Beanquick Syntax)**
- Fast, natural language entry using simple syntax
- Perfect for rapid data entry when you know the syntax

**Normal Mode (Form-Based Entry)**
- Guided forms with autocompletion
- Structured fields for dates, accounts, amounts, etc.
- Ideal for beginners or complex transactions

> 💡 **Tip:** Press `Cmd+/` (macOS) or `Ctrl+/` (Windows/Linux) to switch between modes anytime.

This manual focuses on the Quick Mode syntax, but both modes create the same Beancount entries.

### Your First Transaction in Quick Mode

> 💡 **Before you start:** Make sure you're in Quick Mode. Press `Cmd+/` (macOS) or `Ctrl+/` (Windows/Linux) to switch if needed.

Let's start with the simplest transaction - buying coffee:

```beanquick
5 from:cash to:coffee |morning coffee
```

This records spending `$5` from your cash account on coffee, with `morning coffee` as the narration.

This compiles to the following Beancount entry:

```beancount
2025-07-21 * "morning coffee"
  Assets:Cash                          -5.0 USD
  Expenses:Food:Coffee                  5.0 USD
```

Let's see it in action:
![Beanquick Quick Mode](../../resources/images/beanquick_quick_mode@0.5x.png)

### How It Works

Beanquick uses **account aliases** to transform simple names into full Beancount accounts:

**Account Expansion:**
- `cash` → `Assets:Cash`
- `coffee` → `Expenses:Food:Coffee`

These aliases are configured in your settings:

> 💡 **Tip:** Press `Cmd+,` (macOS) or `Ctrl+,` (Windows/Linux) to open settings and define your own account aliases.

![Beanquick Settings Aliases](../../resources/images/beanquick_settings_aliases@0.5x.png)

**Double-Entry Principles:**
- Each transaction has one source account (`from:`) and one or more destination accounts (`to:`)
- All amounts must balance - the total going out equals the total coming in
- In this example: `$5` leaves cash (`Assets:Cash -$5`) and `$5` goes to coffee expenses (`Expenses:Food:Coffee +$5`)

**[back to top](#beanquick-user-manual)**

---

## Basic Syntax

### Core Structure

```
[@date] amount [currency] from:account [{metadata}] to:account [{metadata}] [|payee|narration] [#tags] [^links] [{metadata}]
```

### Required Elements

1. **Amount**: How much money moved
2. **From account**: Where the money came from
3. **To account**: Where the money went to

### Optional Elements

- **Date**: When the transaction occurred
- **Currency**: What currency
- **Payee/Narration**: Who and what
- **Tags**: For categorization
- **Links**: For linking related transactions
- **Metadata**: Additional structured data

**[back to top](#beanquick-user-manual)**

---

## Transaction Types

> 💡 Tip: Set up your account aliases in the Settings before entering transactions.

### 1. Basic Expenses

`amount from:source to:expense`

```
25 from:cash to:food
50 from:checking to:gas
100 from:credit to:shopping
```

### 2. Transfers Between Accounts

`amount from:source to:destination`

```
100 from:checking to:savings
500 from:savings to:checking
50 from:wallet to:checking
```

### 3. Income Recording

`amount from:income to:asset`

```
3000 from:salary to:checking
50 from:interest to:savings
100 from:dividend to:checking
```

### 4. With Dates

`@date amount from:account to:account`

```
@yesterday 25 from:cash to:food
@2024-01-15 100 from:checking to:rent
@today 50 from:credit to:gas
```

**Date Formats**:
- `@today` - Today's date
- `@yesterday` - Yesterday's date
- `@2024-01-15` - Specific date (YYYY-MM-DD)
- `@today-5d` - 5 days ago (supports date arithmetic)

For additional supported date formats, refer to the [Date Formats](#date-formats) section.

### 5. With Currency

`amount currency from:account to:account`

```
25 USD from:cash to:food
100 EUR from:checking to:savings
50 GBP from:wallet to:transport
```

### 6. With Payee and Narration

`amount from:account to:account |payee|narration`

```
25 from:cash to:food |Starbucks|Morning coffee
50 from:credit to:gas |Shell|Fill up tank
100 from:checking to:utilities |Electric Company|Monthly bill
```

**Payee/Narration Formats**:
- `|Coffee` - Narration only
- `|Starbucks|Morning coffee` - Payee and narration

### 7. With Tags and Links

`amount from:account to:account #tag ^link`

```
25 from:cash to:food #dining
100 from:checking to:savings ^savings-goal
50 from:credit to:gas #transport ^car-expenses
```

**Multiple Tags/Links**:
```
25 from:cash to:food #dining #weekend ^date-night
```

### 8. With Metadata


Metadata can be attached to the transaction, the `from` account, or any `to` account using `{key:value}` blocks.

**Examples:**

- **Transaction-level metadata** (applies to the whole transaction):
  ```
  25 from:cash to:food #dining {receipt:ABC123 location:"Cafe"}
  ```

- **From account metadata**:
  ```
  100 from:checking {method:"mobile app"} to:savings
  ```

- **To account metadata**:
  ```
  50 from:credit to:gas {odometer:45000 trip:"vacation"}
  200 from:cash to:food 100 {category:groceries} to:transport {mode:bus}
  ```

You can mix and match metadata blocks as needed:
```
@2024-07-21 75 from:checking {atm:Bank123} to:food {receipt:ABC123} {note:Dinner}
```

### 9. Multiple Destinations

`amount from:account to:account1 amount1 to:account2 amount2`

```
100 from:checking to:savings 60 to:investment 40
200 from:cash to:food 75 to:transport 25 to:entertainment 100
```

**[back to top](#beanquick-user-manual)**

---

## Beyond Transactions

### Balance Assertions

Verify your account balances match your records:

`[@date] bal account amount currency`

```
bal checking 1000 USD
@today bal savings 5000 USD
@2024-01-01 bal cash 200 USD
```

### Pad Statements

Automatically balance accounts with opening balance equity:

`[@date] pad from:account to:equity`

```
pad from:checking to:equity
@2024-01-01 pad from:savings to:equity
```

### Price Statements

Record commodity prices:

`[@date] px commodity amount currency`

```
px AAPL 150 USD
@today px GOOGL 2500 USD
@2024-01-15 px MSFT 300 USD
```

### Complex Transactions

Combine multiple features:

```
@yesterday 75.50 USD from:checking to:food 25 to:transport 50.50 |Restaurant|Dinner with friends #dining #social ^date-night {tip: 15 rating: 5}
```

**[back to top](#beanquick-user-manual)**

---

## Templates

Beyond simple transactions, Beanquick offers powerful templates that can automate complex entries and save you time on repetitive tasks.

### What are Templates?

Templates are reusable transaction patterns powered by **Jinja2**, a powerful templating engine. Think of them as smart shortcuts that can:

- Generate multiple transactions at once
- Calculate amounts automatically
- Use variables and logic
- Handle recurring transactions with ease

[Jinja2](https://jinja.palletsprojects.com/)

### Your First Template

Templates are invoked using commands that start with a forward slash (`/`) and generate complete Beancount entries.

**Basic syntax**: `/template_name [args]`

**Template definition** (in your Settings):
```
{{ today }} * "morning coffee"
  Assets:Cash                    -{{ args[0] }} USD
  Expenses:Food:Coffee            {{ args[0] }} USD
```
![Beanquick Settings Templates](../../resources/images/beanquick_settings_templates@0.5x.png)

**Usage**:
```
/coffee 5
```

**Generates**:
```beancount
2025-07-21 * "morning coffee"
  Assets:Cash                           -5.0 USD
  Expenses:Food:Coffee                   5.0 USD
```

Let's see it in action:
![Beanquick Template](../../resources/images/beanquick_template@0.5x.png)

### How Templates Work

Let's break down how the template syntax works:

```
 |-> Jinja2 variable placeholder
 |
 |   |-> System variable: gets replaced with actual value
 |   |
{{ today }} * "morning coffee"
  Assets:Cash                -{{ args[0] }} USD
  Expenses:Food:Coffee        {{ args[0] }} USD
                                   |
                                   |-> first command argument (e.g., 5)
```

> **💡 Pro Tip:** Think of `{{ }}` as "fill-in-the-blanks" that get replaced with real values when you run the template.

When writing templates, Beanquick provides three types of variables you can use:

**1. System Variables**
- **`datetime`** - Python's datetime module for date/time operations
- **`today`** - Today's date in ISO format (e.g., "2025-07-21")
- **`yesterday`** - Yesterday's date in ISO format (e.g., "2025-07-20")

**2. Arguments from the command line**

When you type `/coffee 5 "matcha tea"`, these become:
- `{{ args[0] }}` = `5`
- `{{ args[1] }}` = `"matcha tea"`

**3. Default values you configure**

In your template settings, you can set up defaults that make templates smarter:

![Template Variable Example](../../resources/images/beanquick_settings_template_variables@0.5x.png)

#### Overriding Defaults

You can override any default value by using named parameters:

```
/coffee 5                           # Uses default narration
/coffee 5 narration="matcha tea"    # Override the narration
```

**Example with overrides:**
```
/coffee 5 narration="matcha tea"
```

**Becomes:**
```beancount
2025-07-21 * "matcha tea"
  Assets:Cash                  -5.0 USD
  Expenses:Food:Coffee          5.0 USD
```

Notice how the narration changed from `morning coffee` (the default) to `matcha tea` (the override)

> 💡 **Tip:** System variables cannot be overridden.

**[back to top](#beanquick-user-manual)**

---

## Quick Reference

### Basic Transaction
```
amount from:account to:account
```

### Multiple Destinations
```
amount from:account to:account1 amount1 to:account2 amount2
```

### With All Options
```
@date amount currency from:account {key:value} to:account {key:value} |payee|narration #tag ^link {key:value}
```

### Other Statements
```
bal account amount currency          # Balance assertion
pad from:account to:equity           # Pad statement  
px commodity amount currency         # Price statement
/template_name [params]              # Expand templates
```

### Date Formats

**Supported Date Formats:**
- `@today`, `@yesterday`, `@tomorrow` — Relative dates
- `@2024-01-15` — Specific date (YYYY-MM-DD)
- `@2024-01` — Month (YYYY-MM)
- `@2024` — Year
- `@2024-Q1`, `@2024-W42`, `@FY2024`, `@FY2024-Q2` — Quarter, week, fiscal year, fiscal quarter
- `@day+5`, `@day-2w`, `@2024-01-15+3d` — Arithmetic (add/subtract days, weeks, months, years, quarters)
- `@"end of 2024-Q1"`, `@"middle of 2024-01"` — Position modifiers (start, end, middle of period)
- `@"N days ago"`, `@"N weeks from now"` — Natural language relative

**[back to top](#beanquick-user-manual)**

---

## Getting More Help

- **Telegram Group**: Join the Beanquick user community on Telegram for real-time help, tips, and discussion. [Telegram Group](https://t.me/beanquick)
![Temegram Group](../../resources/images/beanquick_telegram@0.5x.png)
- **GitHub Repository**: Visit the Beanquick GitHub repo for source code, issues, and updates.[Beanquick GitHub repo](https://github.com/TwoBitsWare/Beanquick)
- **Beancount Documentation**: Refer to the Beancount documentation for underlying accounting principles and advanced usage.[Beancount documentation](https://beancount.github.io/docs/)

---

**[back to top](#beanquick-user-manual)**
