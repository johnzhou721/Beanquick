
# Beancount 语法

> **来源：** 此内容改编自 [Fava 的 Beancount 语法参考](https://github.com/beancount/fava)

以下是 Beancount 语言语法的简要参考。另请参阅完整的[语法文档](http://furius.ca/beancount/doc/syntax)和[语法速查表](http://furius.ca/beancount/doc/cheatsheet)。

## 目录

- [商品](#商品-commodities)
- [账户](#账户-accounts)
- [指令](#指令-directives)
  - [开立和平仓账户](#开立和平仓账户-open-and-close-accounts)
  - [商品声明](#商品声明-commodities)
  - [价格](#价格-prices)
  - [注释](#注释-notes)
  - [文档](#文档-documents)
  - [交易](#交易-transactions)
  - [分录](#分录-postings)
  - [余额断言和填充](#余额断言和填充-balance-assertions-and-padding)
  - [事件](#事件-events)
  - [选项](#选项-options)
  - [其他](#其他-other)
  - [注释语法](#注释语法-comments)

---

Beancount 定义了一种语言，用于在文本文件中输入金融交易，然后可以由 Beancount 处理。理解 Beancount 语法需要了解以下几个重要构建块：

* 商品（Commodities）
* 账户（Accounts）
* 指令（Directives）

## 商品 (Commodities)

全部大写：`USD`, `EUR`, `CAD`, `GOOG`, `AAPL`, `RBF1005`, `HOME_MAYST`, `AIRMILES`, `HOURS`。

**[返回顶部](#beancount-语法)**

## 账户 (Accounts)

账户由冒号分隔的大写单词列表给出。它们必须以表（如下）中列出的五个根账户之一开头。冒号分隔定义了一个隐式层次结构，例如，我们说 `Assets:Cash` 是 `Assets` 的子账户。

| 类型        | 符号 | 示例描述           | 示例账户                |
|-------------|------|--------------------|-------------------------|
| 资产 (Assets) | +    | 现金、支票账户等     | Assets:Checking         |
| 负债 (Liabilities) | -    | 信用卡等           | Liabilities:CreditCard  |
| 收入 (Income) | -    | 工资等             | Income:EmployerA        |
| 支出 (Expenses) | +    | 支出类别           | Expenses:Fun:Cinema     |
| 权益 (Equity) | -    | 通常自动生成       | Equity:Opening-Balances |

五个根账户的名称可以通过以下选项更改：

```
option "name_assets"      "Vermoegen"
option "name_liabilities"  "Verbindlichkeiten"
option "name_income"       "Einkommen"
option "name_expenses"     "Ausgaben"
option "name_equity"       "Eigenkapital"
```

**[返回顶部](#beancount-语法)**

## 指令 (Directives)

基本构建块是指令（也称为条目）。大多数指令以日期开头，然后是指令类型，然后是特定于指令的参数。输入文件中指令的顺序无关紧要，因为 Beancount 会根据每个指令的日期对其进行排序。

通用语法：`YYYY-MM-DD <directive> <arguments...>`

### 开立和平仓账户 (Open and Close accounts)

要开立或平仓账户，请使用 `open` 和 `close` 指令：

```
2015-05-29 open Expenses:Restaurant
; 具有某些货币约束的账户：
2015-05-29 open Assets:Checking     USD,EUR
; ...
2016-02-23 close Assets:Checking
```

### 商品声明 (Commodities)

声明商品是可选的。如果您想按货币附加元数据，请使用此功能。如果您为下面的货币指定了 `name`，则将鼠标悬停在 Fava 中的货币名称上时，此名称将显示为工具提示。同样，使用 `precision` 元数据，您可以指定要在 Fava 中显示的小数位数，从而覆盖从输入数据自动推断的精度。

```
1998-07-22 commodity AAPL
  name: "Apple Computer Inc."
  precision: 3
```

### 价格 (Prices)

您可以使用此指令填充历史价格数据库：

```
2015-04-30 price AAPL   125.15 USD
2015-05-30 price AAPL   130.28 USD
```

### 注释 (Notes)

```
2013-03-20 note Assets:Checking "打电话询问有关回扣的事宜"
```

### 文档 (Documents)

```
2013-03-20 document Assets:Checking "path/to/statement.pdf"
```

**[返回顶部](#beancount-语法)**

### 交易 (Transactions)

```
2015-05-30 * "关于此交易的一些说明"
  Liabilities:CreditCard  -101.23 USD
  Expenses:Restaurant       101.23 USD

2015-05-30 ! "有线电视公司" "电话费" #tag ^link
  id: "TW378743437"
  Expenses:Home:Phone  87.45 USD
  Assets:Checking                 ; 您可以省略一个金额
```

### 分录 (Postings)

```
2015-05-30 * "包含各种分录的示例交易"
  Account:Name   123.45 USD                           ; 简单单位
  Account:Name      10 GOOG {502.12 USD}              ; 带成本
  Account:Name  1000.00 USD  @ 1.10 CAD               ; 带价格
  Account:Name      10 GOOG {502.12 USD} @ 1.10 CAD   ; 带成本和价格
  Account:Name      10 GOOG {502.12 USD, 2014-05-12}  ; 带成本日期
  ! Account:Name 123.45 USD                           ; 带标记
```

### 余额断言和填充 (Balance Assertions and Padding)

仅针对给定货币断言金额：

```
2015-06-01 balance Liabilities:CreditCard  -634.30 USD
```

自动插入交易以满足以下断言：

```
2015-06-01 pad Assets:Checking Equity:Opening-Balances
```

### 事件 (Events)

```
2015-06-01 event "location" "New York, USA"
2015-06-01 event "address" "123 May Street"
```

### 选项 (Options)

有关支持的选项的完整列表，请参阅 [Beancount 选项参考](http://furius.ca/beancount/doc/options)。

```
option "title" "我的个人账本"
```

### 其他 (Other)

```
pushtag #trip-to-peru
; ... 给定的标签将添加到 pushtag 和 poptag 之间的所有条目中
poptag  #trip-to-peru
```

### 注释语法 (Comments)

```
; 内联注释以分号开头
* 任何不以有效指令开头的行也会被静默忽略
```

---

**[返回顶部](#beancount-语法)**
