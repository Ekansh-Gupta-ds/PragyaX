"""
Mock AI Provider
Owned by: Ekansh (AI/ML Evaluation)

Deterministic, offline "AI" used for the demo: no API keys, no network.
- Multi-Subject Chat: Subject-aware keyword -> lesson lookup with tailored follow-ups and fallbacks.
  Supported subjects: Python Programming, Biology, Business/Entrepreneurship, AI/ML.
- Evaluation: Grades against reference keys with deterministic scoring and subject-scoped recommendations.
"""

import re
from typing import List, Dict, Any, Optional
from .base import BaseAIProvider


# ---------------------------------------------------------------------------
# Subject Aliases and Canonical Normalization
# ---------------------------------------------------------------------------

SUBJECT_ALIASES: Dict[str, str] = {
    # Python
    "python": "python",
    "python programming": "python",
    "subj_python": "python",
    "py": "python",
    # Biology
    "biology": "biology",
    "life sciences": "biology",
    "life science": "biology",
    "subj_biology": "biology",
    "bio": "biology",
    # Business & Entrepreneurship
    "business": "business",
    "entrepreneurship": "business",
    "business/entrepreneurship": "business",
    "business and entrepreneurship": "business",
    "subj_business": "business",
    "biz": "business",
    # AI / Machine Learning
    "ai_ml": "ai_ml",
    "ai/ml": "ai_ml",
    "ai": "ai_ml",
    "ml": "ai_ml",
    "artificial intelligence": "ai_ml",
    "machine learning": "ai_ml",
    "subj_aiml": "ai_ml",
    "subj_ai_ml": "ai_ml",
}

SUBJECT_DISPLAY_NAMES: Dict[str, str] = {
    "python": "Python Programming",
    "biology": "Biology",
    "business": "Business/Entrepreneurship",
    "ai_ml": "AI/ML",
}


def normalize_subject(subject: Optional[str]) -> str:
    """
    Normalizes subject names and aliases to canonical subject keys:
    'python', 'biology', 'business', 'ai_ml', or 'unknown'.
    """
    if not subject:
        return "python"
    cleaned = subject.strip().lower()
    return SUBJECT_ALIASES.get(cleaned, "unknown")


# ---------------------------------------------------------------------------
# 1. PYTHON LESSONS (Preserved 100% Verbatim)
# ---------------------------------------------------------------------------

PYTHON_LESSONS = [
    (
        ["comprehension", "comprehensions"],
        "**List comprehensions** build a list in one readable expression.\n\n"
        "**Syntax**: `[expression for item in iterable if condition]`\n\n"
        "```python\n"
        "evens_squared = [x**2 for x in range(10) if x % 2 == 0]\n"
        "# [0, 4, 16, 36, 64]\n"
        "```\n"
        "Swap `[]` for `()` to get a **generator expression** that computes items lazily, "
        "and use `{k: v for ...}` for a dict comprehension.",
        ["How does a generator expression differ from a list comprehension?",
         "What is dictionary comprehension syntax?",
         "When should I avoid list comprehensions?"],
    ),
    (
        ["generator", "generators", "yield", "lazy"],
        "A **generator** produces values one at a time, only when asked, so it uses O(1) memory.\n\n"
        "```python\n"
        "def countdown(n):\n"
        "    while n > 0:\n"
        "        yield n\n"
        "        n -= 1\n\n"
        "for x in countdown(3):\n"
        "    print(x)   # 3, 2, 1\n"
        "```\n"
        "`(x*x for x in range(10**6))` is a generator expression: nothing is computed until you iterate. "
        "Generators can be consumed **only once**.",
        ["How do list comprehensions work?",
         "What does the itertools module offer?",
         "How do loops work in Python?"],
    ),
    (
        ["decorator", "decorators"],
        "A **decorator** wraps a function to add behaviour without editing it.\n\n"
        "```python\n"
        "import functools, time\n\n"
        "def timer(func):\n"
        "    @functools.wraps(func)\n"
        "    def wrapper(*args, **kwargs):\n"
        "        t0 = time.perf_counter()\n"
        "        result = func(*args, **kwargs)\n"
        "        print(f'{func.__name__} took {time.perf_counter() - t0:.4f}s')\n"
        "        return result\n"
        "    return wrapper\n\n"
        "@timer\n"
        "def slow_add(a, b):\n"
        "    return a + b\n"
        "```\n"
        "`@timer` is shorthand for `slow_add = timer(slow_add)`.",
        ["What are *args and **kwargs?",
         "How do closures work in Python?",
         "Explain Python scope (LEGB)"],
    ),
    (
        ["scope", "legb", "global", "nonlocal", "closure", "closures"],
        "Python looks up names using the **LEGB** rule:\n\n"
        "1. **Local**: inside the current function\n"
        "2. **Enclosing**: inside any outer (enclosing) function\n"
        "3. **Global**: module level\n"
        "4. **Built-in**: `len`, `print`, `range`, ...\n\n"
        "```python\n"
        "x = 'global'\n"
        "def outer():\n"
        "    x = 'enclosing'\n"
        "    def inner():\n"
        "        return x      # finds 'enclosing'\n"
        "    return inner()\n"
        "```\n"
        "Use `nonlocal` to rebind an enclosing variable and `global` for a module variable. A function that "
        "remembers enclosing variables is a **closure**.",
        ["What is a Python decorator?",
         "How do functions work in Python?",
         "What is the difference between mutable and immutable types?"],
    ),
    (
        ["args", "kwargs", "*args", "**kwargs"],
        "`*args` collects extra **positional** arguments into a tuple; `**kwargs` collects extra **keyword** "
        "arguments into a dict.\n\n"
        "```python\n"
        "def report(title, *args, **kwargs):\n"
        "    print(title, args, kwargs)\n\n"
        "report('Scores', 90, 85, student='Asha')\n"
        "# Scores (90, 85) {'student': 'Asha'}\n"
        "```\n"
        "The same stars **unpack** at call time: `f(*my_list, **my_dict)`.",
        ["What is a Python decorator?",
         "How do default arguments behave?",
         "Explain Python scope (LEGB)"],
    ),
    (
        ["mutable", "immutable", "mutability", "default", "reference", "references", "copy"],
        "**Mutable** objects (`list`, `dict`, `set`) can change in place; **immutable** ones "
        "(`int`, `str`, `tuple`, `frozenset`) cannot.\n\n"
        "Variables are *references*. Two names can point to the same list:\n"
        "```python\n"
        "a = [1, 2]\n"
        "b = a\n"
        "b.append(3)\n"
        "print(a)   # [1, 2, 3]  same object!\n"
        "```\n"
        "**Classic trap**: default arguments are evaluated once, so `def f(items=[])` shares one list "
        "across calls. Use `def f(items=None): items = items or []` instead. Copy with `a.copy()` "
        "or `copy.deepcopy(a)` for nested data.",
        ["Why can't a list be a dictionary key?",
         "How do lists differ from tuples?",
         "How do functions work in Python?"],
    ),
    (
        ["slice", "slicing", "slices", "index", "indexing"],
        "**Slicing** uses `seq[start:stop:step]`; `stop` is *excluded*.\n\n"
        "```python\n"
        "data = [10, 20, 30, 40, 50]\n"
        "data[1:4]     # [20, 30, 40]\n"
        "data[::-1]    # [50, 40, 30, 20, 10]\n"
        "data[3:0:-1]  # [40, 30, 20]\n"
        "data[1:4:-1]  # []  (can't walk backwards from 1 to 4)\n"
        "```\n"
        "Negative indices count from the end: `data[-1]` is `50`. Slicing a list returns a **new** list.",
        ["How do lists differ from tuples?",
         "How do list comprehensions work?",
         "How do strings work in Python?"],
    ),
    (
        ["dict", "dictionary", "dictionaries", "hash", "hashable", "key", "keys"],
        "A **dictionary** maps keys to values with O(1) average lookup, using a hash table.\n\n"
        "```python\n"
        "scores = {'asha': 92, 'ravi': 78}\n"
        "scores['meera'] = 88\n"
        "scores.get('john', 0)    # 0 (no KeyError)\n"
        "for name, score in scores.items():\n"
        "    print(name, score)\n"
        "```\n"
        "Keys must be **hashable** (immutable): `str`, `int`, `tuple` work, `list` raises "
        "`TypeError: unhashable type: 'list'`.",
        ["What is dictionary comprehension syntax?",
         "What is the difference between mutable and immutable types?",
         "How do sets work?"],
    ),
    (
        ["list", "lists", "tuple", "tuples", "set", "sets", "collection", "collections"],
        "Python's core collections:\n\n"
        "1. **List `[]`**: ordered, mutable. `items.append(4)`\n"
        "2. **Tuple `()`**: ordered, **immutable**. Good for fixed records and dict keys.\n"
        "3. **Dict `{k: v}`**: key-value mapping with fast lookup.\n"
        "4. **Set `{1, 2}`**: unordered, unique items, fast membership tests.\n\n"
        "```python\n"
        "unique = set([3, 1, 3, 2])   # {1, 2, 3}\n"
        "point = (4, 5)               # tuple\n"
        "```\n"
        "If data shouldn't change after creation, prefer a tuple.",
        ["How does a list comprehension work?",
         "Why can't a list be used as a dictionary key?",
         "How does slicing work?"],
    ),
    (
        ["string", "strings", "str", "f-string", "fstring", "format"],
        "**Strings** are immutable sequences of characters.\n\n"
        "```python\n"
        "name = 'PragyaX'\n"
        "name.upper()          # 'PRAGYAX'\n"
        "name[0:6]             # 'Pragya'\n"
        "', '.join(['a', 'b'])  # 'a, b'\n"
        "f'Hello {name}, 2+2={2+2}'   # f-string formatting\n"
        "```\n"
        "Because strings are immutable, methods like `.replace()` return a **new** string.",
        ["How does slicing work?",
         "What is the difference between mutable and immutable types?",
         "How do loops work in Python?"],
    ),
    (
        ["exception", "exceptions", "error", "errors", "try", "except", "raise"],
        "Handle errors with **try / except**:\n\n"
        "```python\n"
        "try:\n"
        "    value = int(input('Number: '))\n"
        "except ValueError:\n"
        "    print('That was not a number')\n"
        "else:\n"
        "    print('Got', value)\n"
        "finally:\n"
        "    print('Always runs')\n"
        "```\n"
        "Catch **specific** exceptions (not bare `except:`), and `raise ValueError('msg')` to signal problems.",
        ["How do functions work in Python?",
         "How do classes work in Python?",
         "How do I read a file in Python?"],
    ),
    (
        ["class", "classes", "object", "objects", "oop", "inheritance", "self", "init", "__init__", "classmethod", "staticmethod", "dunder", "method", "methods"],
        "Python is object-oriented: a **class** is a blueprint, an **instance** is an object built from it.\n\n"
        "```python\n"
        "class Student:\n"
        "    def __init__(self, name):\n"
        "        self.name = name\n"
        "        self.xp = 0\n\n"
        "    def earn(self, points):\n"
        "        self.xp += points\n\n"
        "class Mentor(Student):          # inheritance\n"
        "    def earn(self, points):\n"
        "        super().earn(points * 2)\n"
        "```\n"
        "`self` is the instance; `super()` calls the parent. Python favours **duck typing**: "
        "if it has the method you need, you can use it.",
        ["What is the difference between @staticmethod and @classmethod?",
         "What are dunder methods like __str__?",
         "How do exceptions work?"],
    ),
    (
        ["function", "functions", "def", "lambda", "return", "parameter", "parameters", "argument", "arguments"],
        "Functions package reusable logic. They are **first-class objects**: you can pass and return them.\n\n"
        "```python\n"
        "def grade(score: int) -> str:\n"
        "    return 'Pass' if score >= 3 else 'Needs practice'\n\n"
        "square = lambda x: x * x      # small anonymous function\n"
        "sorted(['bb', 'a'], key=len)  # pass a function as an argument\n"
        "```\n"
        "**Watch out**: never use a mutable default like `def f(items=[])`; it's created only once.",
        ["What are *args and **kwargs?",
         "What is a Python decorator?",
         "Explain Python scope (LEGB)"],
    ),
    (
        ["recursion", "recursive"],
        "**Recursion** is a function calling itself on a smaller problem until it reaches a **base case**.\n\n"
        "```python\n"
        "def factorial(n):\n"
        "    if n <= 1:          # base case\n"
        "        return 1\n"
        "    return n * factorial(n - 1)\n"
        "```\n"
        "Python's default recursion limit is about 1000 frames; for deep problems prefer a loop.",
        ["How do loops work in Python?",
         "How do functions work in Python?",
         "What is a generator?"],
    ),
    (
        ["loop", "loops", "for", "while", "range", "enumerate", "break", "continue", "iterate"],
        "Python has two loops:\n\n"
        "```python\n"
        "for i, lang in enumerate(['Python', 'SQL']):\n"
        "    print(i, lang)\n\n"
        "n = 3\n"
        "while n > 0:\n"
        "    n -= 1\n"
        "```\n"
        "- `break` exits the loop, `continue` skips to the next iteration.\n"
        "- `range(start, stop, step)` generates numbers lazily.\n"
        "- Loops support an `else:` block that runs only if no `break` happened.",
        ["How do list comprehensions work?",
         "What is a generator?",
         "How do conditionals work?"],
    ),
    (
        ["if", "elif", "else", "condition", "conditions", "conditional", "conditionals", "boolean", "bool"],
        "**Conditionals** choose which code runs:\n\n"
        "```python\n"
        "score = 4\n"
        "if score == 5:\n"
        "    level = 'Advanced'\n"
        "elif score >= 3:\n"
        "    level = 'Intermediate'\n"
        "else:\n"
        "    level = 'Beginner'\n"
        "```\n"
        "Empty values (`0`, `''`, `[]`, `None`) are **falsy**. Combine tests with `and`, `or`, `not`, "
        "and use the one-liner `x if cond else y` for simple cases.",
        ["How do loops work in Python?",
         "What are Python data types?",
         "How do functions work in Python?"],
    ),
    (
        ["file", "files", "open", "read", "write", "with"],
        "Use `with open(...)` so files close automatically:\n\n"
        "```python\n"
        "with open('notes.txt', 'w', encoding='utf-8') as f:\n"
        "    f.write('Learn Python\\n')\n\n"
        "with open('notes.txt', encoding='utf-8') as f:\n"
        "    for line in f:\n"
        "        print(line.strip())\n"
        "```\n"
        "Modes: `'r'` read, `'w'` overwrite, `'a'` append. Wrap in `try/except FileNotFoundError` when needed.",
        ["How do exceptions work?",
         "How do strings work in Python?",
         "How do modules and imports work?"],
    ),
    (
        ["module", "modules", "import", "package", "packages", "pip"],
        "A **module** is any `.py` file; a **package** is a folder of modules.\n\n"
        "```python\n"
        "import math\n"
        "from collections import Counter\n\n"
        "math.sqrt(16)                 # 4.0\n"
        "Counter('banana')             # {'a': 3, 'n': 2, 'b': 1}\n"
        "```\n"
        "Install third-party packages with `pip install <name>` inside a virtual environment "
        "(`python -m venv .venv`).",
        ["How do I read a file in Python?",
         "How do classes work in Python?",
         "What is a generator?"],
    ),
    (
        ["variable", "variables", "type", "types", "int", "float", "data", "datatype"],
        "Variables are **names bound to objects**; Python infers the type at runtime.\n\n"
        "```python\n"
        "age = 21          # int\n"
        "pi = 3.14         # float\n"
        "name = 'Asha'     # str\n"
        "ready = True      # bool\n"
        "type(age)         # <class 'int'>\n"
        "isinstance(pi, float)  # True\n"
        "```\n"
        "Python is **dynamically** but **strongly** typed: `'3' + 3` raises a `TypeError`. "
        "Convert explicitly with `int('3')` or `str(3)`.",
        ["What is the difference between mutable and immutable types?",
         "How do lists differ from tuples?",
         "How do strings work in Python?"],
    ),
]

# Backward compatibility alias
LESSONS = PYTHON_LESSONS


# ---------------------------------------------------------------------------
# 2. BIOLOGY LESSONS
# ---------------------------------------------------------------------------

BIOLOGY_LESSONS = [
    (
        ["cell", "cells", "organelle", "organelles", "nucleus", "mitochondria", "ribosome", "ribosomes", "chloroplast", "chloroplasts", "membrane", "cytoplasm"],
        "**Cell Structure & Organelles**: Cells are the fundamental structural and functional units of all living organisms.\n\n"
        "- **Nucleus**: The command center containing genomic DNA and directing cellular activities.\n"
        "- **Mitochondria**: The 'powerhouses' of the cell, generating **ATP** via oxidative phosphorylation.\n"
        "- **Ribosomes**: Protein-synthesizing complexes translating mRNA into polypeptide chains.\n"
        "- **Chloroplasts**: Plant-specific organelles conducting photosynthesis to fix carbon into sugars.\n"
        "- **Plasma Membrane**: Phospholipid bilayer with embedded proteins providing selective permeability.",
        ["How do mitochondria produce cellular ATP?",
         "What is the structural difference between plant and animal cells?",
         "How does active transport differ from passive diffusion across membranes?"],
    ),
    (
        ["dna", "rna", "gene", "genes", "genetics", "allele", "alleles", "chromosome", "chromosomes", "nucleotide", "nucleotides", "transcription", "translation", "mutation", "mutations"],
        "**DNA & Molecular Genetics**: DNA encodes the genetic instructions for development and functioning.\n\n"
        "DNA forms a double helix of **nucleotide base pairs**:\n"
        "- **Adenine (A)** pairs with **Thymine (T)** (2 hydrogen bonds)\n"
        "- **Guanine (G)** pairs with **Cytosine (C)** (3 hydrogen bonds)\n\n"
        "**The Central Dogma**:\n"
        "`DNA` --(transcription via RNA polymerase)--> `mRNA` --(translation on ribosomes)--> `Protein`.\n\n"
        "An **allele** is an alternative variant of a gene; mutations can alter the reading frame or amino acid sequence.",
        ["What is the precise role of tRNA during translation?",
         "How do dominant and recessive alleles express in a Punnett square?",
         "What is the difference between point mutations and frameshift mutations?"],
    ),
    (
        ["photosynthesis", "respiration", "chlorophyll", "calvin", "light-dependent", "glycolysis", "krebs", "atp", "aerobic", "anaerobic"],
        "**Photosynthesis & Cellular Respiration**: Bioenergetic pathways that convert and harvest metabolic energy.\n\n"
        "**Photosynthesis** (in chloroplasts):\n"
        "`6CO2 + 6H2O + Light Energy -> C6H12O6 + 6O2`\n"
        "- *Light Reactions* (in thylakoid membranes): Split H2O, release O2, produce ATP and NADPH.\n"
        "- *Calvin Cycle* (in stroma): Fixes atmospheric CO2 into glucose.\n\n"
        "**Cellular Respiration** (in cytoplasm & mitochondria):\n"
        "`C6H12O6 + 6O2 -> 6CO2 + 6H2O + ~30-32 ATP`\n"
        "Steps: Glycolysis -> Pyruvate Oxidation -> Krebs Cycle -> Electron Transport Chain.",
        ["What occurs during the light-independent Calvin cycle?",
         "How does anaerobic fermentation compare to aerobic respiration in ATP yield?",
         "What is the proton gradient role across the inner mitochondrial membrane?"],
    ),
    (
        ["enzyme", "enzymes", "catalyst", "catalysts", "substrate", "substrates", "active site", "activation energy", "denature", "denaturation", "denatured", "inhibition", "inhibitor"],
        "**Enzymes & Biological Catalysis**: Enzymes are biological catalysts (primarily proteins) that speed up chemical reactions.\n\n"
        "- **Mechanism**: Enzymes lower the **activation energy** required for a reaction to proceed without being consumed.\n"
        "- **Active Site & Substrate**: The substrate binds to the enzyme's active site via the **induced-fit model**.\n"
        "- **Regulation & Denaturation**: Extreme temperatures or deviating pH disrupt tertiary hydrogen bonds, causing **denaturation** (loss of 3D shape and catalytic function).\n"
        "- **Inhibitors**: Competitive inhibitors bind directly to the active site; non-competitive inhibitors bind to an allosteric site.",
        ["What distinguishes competitive from non-competitive enzyme inhibition?",
         "Why does heat cause irreversible enzyme denaturation?",
         "What is the Michaelis-Menten constant (Km)?"],
    ),
    (
        ["ecology", "ecosystem", "ecosystems", "trophic", "food chain", "food web", "producer", "producers", "consumer", "consumers", "symbiosis", "symbiotic", "carrying capacity", "biodiversity", "niche"],
        "**Ecology & Ecosystem Dynamics**: Ecology examines how organisms interact with each other and their abiotic environment.\n\n"
        "- **Trophic Levels**: Producers (autotrophs) -> Primary Consumers (herbivores) -> Secondary/Tertiary Consumers (carnivores). Approximately **10% of energy** is transferred to the next level (the 10% ecological efficiency rule).\n"
        "- **Carrying Capacity (K)**: The maximum population size an environment can sustainably support given available resources.\n"
        "- **Symbiotic Relationships**:\n"
        "  - *Mutualism* (+/+): Both species benefit (e.g., pollinators and flowering plants).\n"
        "  - *Commensalism* (+/0): One benefits, the other is unaffected.\n"
        "  - *Parasitism* (+/-): One benefits at the expense of the host.",
        ["Why does the 10% energy transfer rule limit the length of food chains?",
         "How do density-dependent and density-independent factors regulate carrying capacity?",
         "What role do keystone species play in maintaining ecosystem biodiversity?"],
    ),
]


# ---------------------------------------------------------------------------
# 3. BUSINESS & ENTREPRENEURSHIP LESSONS
# ---------------------------------------------------------------------------

BUSINESS_LESSONS = [
    (
        ["value proposition", "problem-solution", "customer segment", "customer segments", "pain point", "pain points", "gain creator", "jobs to be done", "differentiator", "differentiation"],
        "**Value Proposition & Problem-Solution Fit**: A value proposition articulates why a customer should buy your solution over alternatives.\n\n"
        "- **Customer Profile**: Analyzes customer *Jobs* (what they want to accomplish), *Pains* (obstacles and risks), and *Gains* (positive outcomes).\n"
        "- **Value Map**: Outlines products/services, pain relievers, and gain creators.\n"
        "- **Problem-Solution Fit**: Achieved when you have evidence that customers genuinely care about certain jobs, pains, and gains, and your value proposition directly addresses them.\n"
        "Focus on quantifiable benefits (saving time, reducing cost, improving revenue) rather than merely listing features.",
        ["How do you validate a value proposition before writing code?",
         "What is the Jobs-to-be-Done (JTBD) customer interview framework?",
         "How do you differentiate a value proposition from a marketing slogan?"],
    ),
    (
        ["mvp", "minimum viable product", "lean startup", "build-measure-learn", "hypothesis", "prototype", "prototyping"],
        "**Minimum Viable Product (MVP) & Lean Startup**: An MVP is the simplest version of a product that allows a team to collect validated learning with minimal effort.\n\n"
        "- **Purpose**: The goal of an MVP is **learning**, not scaling. It tests core business hypotheses against real market feedback.\n"
        "- **Build-Measure-Learn**: The fundamental feedback loop of the Lean Startup methodology (Eric Ries). Turn ideas into products, measure customer response, and learn whether to pivot or persevere.\n"
        "- **Common Types**: Concierge MVPs (manual service behind the scenes), Wizard of Oz tests, landing page conversion tests, and clickable interactive prototypes.",
        ["What is the crucial difference between an MVP and an incomplete prototype?",
         "How do you formulate a testable, falsifiable business hypothesis?",
         "When should a founding team pivot versus persevere with an MVP?"],
    ),
    (
        ["product-market fit", "pmf", "product market fit", "retention", "cohort", "cohorts", "sean ellis", "churn", "market fit"],
        "**Product-Market Fit (PMF)**: PMF occurs when a product satisfies a strong, sustainable market demand in a sizable market.\n\n"
        "- **Retention Curve Flattening**: The truest indicator of PMF is a cohort retention curve that levels off horizontally, showing a core segment of sticky users.\n"
        "- **The Sean Ellis 40% Test**: A common heuristic asking users: *'How would you feel if you could no longer use this product?'* If >=40% answer *'very disappointed'*, it signals strong PMF.\n"
        "*(Note: The 40% test and retention targets are helpful heuristic benchmarks rather than universal laws; threshold expectations vary significantly between enterprise B2B contracts and consumer apps).* ",
        ["How do you read a cohort retention curve to detect product-market fit?",
         "Why does top-of-funnel customer acquisition fail if user retention is broken?",
         "What steps should a startup take if its Sean Ellis score is below 40%?"],
    ),
    (
        ["unit economics", "cac", "ltv", "customer acquisition cost", "lifetime value", "gross margin", "payback period", "burn rate", "runway", "arpu"],
        "**Unit Economics & Sustainable Monetization**: Measures the direct revenues and costs associated with acquiring and serving an individual customer.\n\n"
        "- **CAC (Customer Acquisition Cost)**: Total Sales & Marketing expenses divided by the number of new customers acquired.\n"
        "- **LTV (Lifetime Value)**: Gross Profit per customer multiplied by average customer lifespan (or Average Revenue Per User * Gross Margin % / Churn Rate).\n"
        "- **Heuristic Benchmarks**: Investors often look for an **LTV/CAC ratio >= 3x** with a CAC payback period under 12 months. However, these are context-dependent heuristics that vary by capital intensity, margin profile, and business stage.\n"
        "- **Gross Margin**: Revenue minus Cost of Goods Sold (COGS), expressed as a percentage.",
        ["How does user churn directly affect customer lifetime value (LTV)?",
         "What is CAC payback period and why is it critical for cash runway?",
         "What is the difference between gross margin and operating margin?"],
    ),
    (
        ["business model canvas", "canvas", "business model", "revenue stream", "revenue streams", "cost structure", "key resources", "key activities", "channels"],
        "**Business Model Canvas**: A strategic management template for documenting existing or new business models across 9 building blocks:\n\n"
        "1. **Customer Segments**: Who the business creates value for.\n"
        "2. **Value Propositions**: Products and services that solve customer problems.\n"
        "3. **Channels**: How value is delivered (sales, web, direct, retail).\n"
        "4. **Customer Relationships**: Interaction type (personal, automated, community).\n"
        "5. **Revenue Streams**: Transactional, subscription, freemium, licensing.\n"
        "6. **Key Resources**: Physical, intellectual, human, or financial assets.\n"
        "7. **Key Activities**: Core operational tasks required to execute the value proposition.\n"
        "8. **Key Partnerships**: Suppliers and alliances that reduce risk or provide leverage.\n"
        "9. **Cost Structure**: Fixed vs. variable costs driving the model.",
        ["How do freemium revenue models balance free-tier costs with premium conversions?",
         "What is the difference between cost-driven and value-driven business models?",
         "How do two-sided marketplace business models solve the cold-start problem?"],
    ),
]


# ---------------------------------------------------------------------------
# 4. AI & MACHINE LEARNING LESSONS
# ---------------------------------------------------------------------------

AIML_LESSONS = [
    (
        ["supervised", "unsupervised", "labeled", "unlabeled", "classification", "regression", "clustering", "k-means", "pca", "dimensionality reduction"],
        "**Supervised vs. Unsupervised Learning**: The two core paradigms of machine learning.\n\n"
        "- **Supervised Learning**: Algorithms train on **labeled input-output pairs** `(X, y)` to learn a predictive mapping.\n"
        "  - *Classification*: Predicts categorical labels (e.g., spam vs. ham, disease diagnosis).\n"
        "  - *Regression*: Predicts continuous numeric quantities (e.g., house prices, stock values).\n"
        "- **Unsupervised Learning**: Algorithms discover inherent structures, patterns, or groupings from **unlabeled data** `(X)` alone.\n"
        "  - *Clustering* (e.g., K-Means): Groups similar observations together.\n"
        "  - *Dimensionality Reduction* (e.g., PCA): Projects high-dimensional data into lower dimensions while preserving variance.",
        ["What is the fundamental difference between classification and regression?",
         "How does K-Means clustering initialize and optimize cluster centroids?",
         "What are real-world use cases of Principal Component Analysis (PCA)?"],
    ),
    (
        ["overfitting", "underfitting", "overfit", "underfit", "regularization", "bias-variance", "bias", "variance", "lasso", "ridge", "dropout", "early stopping", "generalization"],
        "**Overfitting, Underfitting & Regularization**: Controlling generalization error on unseen data.\n\n"
        "- **Overfitting (High Variance)**: The model memorizes training noise and outliers, yielding near-zero training error but high test error.\n"
        "- **Underfitting (High Bias)**: The model is too simple to capture underlying patterns, performing poorly on both training and test sets.\n"
        "- **Remediation Techniques**:\n"
        "  - *Data Split*: Strict Train / Validation / Test partitioning.\n"
        "  - *L1 Regularization (Lasso)*: Adds absolute weight penalty, driving weights to exact zeros (feature selection).\n"
        "  - *L2 Regularization (Ridge)*: Adds squared weight penalty, shrinking large weights smoothly.\n"
        "  - *Dropout*: Randomly deactivates a fraction of neurons during each training pass in deep networks.\n"
        "  - *Early Stopping*: Halts training once validation loss starts increasing.",
        ["How does the bias-variance tradeoff balance model complexity?",
         "What is the mathematical difference between L1 and L2 penalty terms?",
         "Why does dropout prevent co-adaptation of features in neural networks?"],
    ),
    (
        ["precision", "recall", "f1", "f1-score", "confusion matrix", "false positive", "false negative", "true positive", "true negative", "roc-auc"],
        "**Model Evaluation Metrics & Confusion Matrix**: Measuring performance beyond naive accuracy.\n\n"
        "The **Confusion Matrix** records True Positives (TP), False Positives (FP), True Negatives (TN), and False Negatives (FN):\n\n"
        "- **Precision** = `TP / (TP + FP)`: Out of all predicted positives, how many were actually positive? Critical when false alarms are costly (e.g., spam detection).\n"
        "- **Recall (Sensitivity)** = `TP / (TP + FN)`: Out of all actual positives, how many did the model detect? Vital when missed positives are catastrophic (e.g., medical cancer diagnosis).\n"
        "- **F1-Score**: The harmonic mean of precision and recall: `2 * (Precision * Recall) / (Precision + Recall)`.\n"
        "- **Accuracy** = `(TP + TN) / Total`: Can be severely misleading on imbalanced datasets (e.g. 99% accuracy by predicting only the majority class).",
        ["Why is simple accuracy misleading for fraud detection with severe class imbalance?",
         "How do you adjust the decision threshold to trade precision for recall?",
         "What does the Area Under the ROC Curve (ROC-AUC) measure?"],
    ),
    (
        ["neural network", "neural networks", "deep learning", "perceptron", "perceptrons", "activation function", "relu", "sigmoid", "backpropagation", "gradient descent"],
        "**Neural Networks & Deep Learning**: Layered architectures learning hierarchical representations.\n\n"
        "- **Perceptron**: Computes a linear combination of inputs: `z = Wx + b`, passed through a non-linear **activation function**.\n"
        "- **Activation Functions**:\n"
        "  - *ReLU* (`max(0, z)`): Standard for hidden layers; avoids vanishing gradients for positive inputs.\n"
        "  - *Sigmoid / Softmax*: Maps outputs to probabilities between 0 and 1.\n"
        "- **Forward Pass**: Data flows through layers to produce output predictions.\n"
        "- **Loss Function**: Measures prediction discrepancy (e.g., Mean Squared Error, Cross-Entropy).\n"
        "- **Backpropagation**: Uses the calculus chain rule to compute gradients of the loss with respect to all weights, updating them via **Gradient Descent** (`W = W - lr * grad`).",
        ["Why are non-linear activation functions essential for multi-layer neural networks?",
         "How does backpropagation propagate error gradients backwards through layers?",
         "What causes vanishing and exploding gradients in deep networks?"],
    ),
    (
        ["transformer", "transformers", "self-attention", "query vector", "token embeddings", "context window", "llm", "llms"],
        "**Transformers & Attention Mechanisms**: The foundational architecture powering modern Large Language Models (LLMs).\n\n"
        "- **Self-Attention**: Allows every token in an input sequence to dynamically weigh and attend to every other token in parallel, regardless of distance.\n"
        "- **Query, Key, Value (Q, K, V)**:\n"
        "  `Attention(Q, K, V) = softmax(Q * K^T / sqrt(d_k)) * V`\n"
        "- **Positional Encoding**: Added to token embeddings because transformers process sequences in parallel rather than recurrently step-by-step.\n"
        "- **Multi-Head Attention**: Runs multiple attention mechanisms in parallel, enabling the model to jointly attend to information from different representation subspaces.\n"
        "- **Foundation Models**: GPT (decoder-only autoregressive), BERT (encoder-only masked language modeling).",
        ["What is the intuitive intuition behind Query, Key, and Value vectors in self-attention?",
         "Why do transformers scale better with compute and dataset size than RNNs/LSTMs?",
         "What is the function of positional encodings in transformer architectures?"],
    ),
]


# ---------------------------------------------------------------------------
# Subject Catalogs & Starters
# ---------------------------------------------------------------------------

LESSONS_BY_SUBJECT: Dict[str, list] = {
    "python": PYTHON_LESSONS,
    "biology": BIOLOGY_LESSONS,
    "business": BUSINESS_LESSONS,
    "ai_ml": AIML_LESSONS,
}

GREETING_WORDS = {"hi", "hello", "hey", "namaste", "start", "help", "greetings"}

STARTER_FOLLOWUPS_BY_SUBJECT: Dict[str, List[str]] = {
    "python": [
        "What are Python data types?",
        "How do list comprehensions work?",
        "Explain Python scope (LEGB)",
    ],
    "biology": [
        "What are the functions of cell organelles?",
        "How does DNA base pairing work?",
        "Explain the stages of photosynthesis",
    ],
    "business": [
        "What makes a strong value proposition?",
        "How do you calculate CAC and LTV?",
        "What is an MVP in the Lean Startup approach?",
    ],
    "ai_ml": [
        "What is the difference between supervised and unsupervised learning?",
        "How do you prevent overfitting in machine learning?",
        "Explain precision vs recall with examples",
    ],
}

# Preserve global STARTER_FOLLOWUPS for Python compatibility
STARTER_FOLLOWUPS = STARTER_FOLLOWUPS_BY_SUBJECT["python"]


# ---------------------------------------------------------------------------
# Assessment Topic Recommendations by Subject
# ---------------------------------------------------------------------------

TOPIC_RECOMMENDATIONS_BY_SUBJECT: Dict[str, Dict[str, str]] = {
    "python": {
        "Default Parameter Evaluation & Mutability": "Mutable vs immutable objects and safe default arguments",
        "Sequence Slicing & Negative Steps": "Sequence slicing with start/stop/step and negative indices",
        "Hash Tables, Mutability & Dictionary Keys": "Dictionaries, hashing and why keys must be immutable",
        "List Comprehensions vs Generator Expressions": "Generators and lazy evaluation vs list comprehensions",
        "LEGB Variable Scope & Closures": "Variable scope (LEGB), closures and the nonlocal keyword",
    },
    "biology": {
        "Cell Biology & Organelles": "Review cell structure, mitochondria ATP synthesis, and membrane transport",
        "Molecular Genetics & DNA": "Review nucleotide base pairing, transcription, and translation mechanics",
        "Bioenergetics & Photosynthesis": "Review light-dependent reactions, Calvin cycle, and aerobic respiration",
        "Enzyme Kinetics & Regulation": "Review active sites, activation energy reduction, and denaturation factors",
        "Ecology & Ecosystem Dynamics": "Review trophic levels, the 10% energy rule, and ecological carrying capacity",
    },
    "business": {
        "Value Proposition & Market Need": "Review problem-solution validation, customer empathy mapping, and value creation",
        "Lean Methodology & MVP Design": "Review Build-Measure-Learn feedback loops and hypothesis experiment scoping",
        "Product-Market Fit & Retention": "Review cohort retention curves, PMF indicators, and user feedback synthesis",
        "Unit Economics & Monetization": "Review CAC, LTV calculations, gross margin, and sustainable unit economics",
        "Business Model Architecture": "Review the 9 Building Blocks of the Business Model Canvas",
    },
    "ai_ml": {
        "Supervised vs Unsupervised Paradigms": "Review labeled vs unlabeled training data, regression, and clustering algorithms",
        "Model Generalization & Regularization": "Review the bias-variance tradeoff, L1/L2 penalties, and dropout techniques",
        "Classification Metrics & Evaluation": "Review precision, recall, F1-score tradeoffs, and confusion matrix interpretation",
        "Neural Network Architectures": "Review activation functions, gradient descent optimization, and backpropagation",
        "Attention Mechanisms & Transformers": "Review self-attention, token embeddings, and modern transformer architectures",
    },
}

ADVANCED_RECOMMENDATIONS_BY_SUBJECT: Dict[str, List[str]] = {
    "python": [
        "Decorators and functools.wraps",
        "Iterators, generators and itertools",
        "Async programming with asyncio",
    ],
    "biology": [
        "CRISPR-Cas9 gene editing and molecular bioengineering",
        "Cellular signal transduction cascades and second messengers",
        "Bioinformatics, phylogenetic trees, and high-throughput sequencing",
    ],
    "business": [
        "Growth loops, viral coefficients, and distribution engine design",
        "Venture capital term sheets, cap table modeling, and dilution",
        "SaaS metrics, expansion revenue, and net revenue retention (NRR)",
    ],
    "ai_ml": [
        "Diffusion models and generative architectures",
        "Reinforcement Learning from Human Feedback (RLHF) and alignment",
        "Model quantization and parameter-efficient fine-tuning (LoRA / QLoRA)",
    ],
}

# Preserve global TOPIC_RECOMMENDATIONS and ADVANCED_RECOMMENDATIONS for Python compatibility
TOPIC_RECOMMENDATIONS = TOPIC_RECOMMENDATIONS_BY_SUBJECT["python"]
ADVANCED_RECOMMENDATIONS = ADVANCED_RECOMMENDATIONS_BY_SUBJECT["python"]


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def proficiency_for(score: int, total: int) -> str:
    """
    Deterministic proficiency thresholds (score out of total):
      >= 100% -> Advanced
      >= 60%  -> Intermediate
      < 60%   -> Beginner
    """
    ratio = score / total if total else 0
    if ratio >= 1.0:
        return "Advanced"
    if ratio >= 0.6:
        return "Intermediate"
    return "Beginner"


def _words(text: str) -> set:
    """Extracts lowercase word tokens."""
    return set(re.findall(r"[a-z0-9_*\-]+", text.lower()))


def _matches_keywords(text: str, words: set, keywords: List[str]) -> bool:
    """
    Checks if a prompt matches a set of keywords.
    Supports multi-word phrase matching as well as single-token matching.
    """
    text_lower = text.lower()
    for kw in keywords:
        kw_lower = kw.lower()
        if " " in kw_lower or "-" in kw_lower:
            if kw_lower in text_lower:
                return True
        elif kw_lower in words:
            return True
    return False


def _find_lesson(text: str, subject_key: str = "python") -> Optional[tuple]:
    """
    Finds matching lesson by keywords for the target subject.
    Strictly stays within the target subject catalog to guarantee isolation.
    """
    words = _words(text)

    # 1. Target subject catalog search
    if subject_key in LESSONS_BY_SUBJECT:
        catalog = LESSONS_BY_SUBJECT[subject_key]
        for keywords, lesson, followups in catalog:
            if _matches_keywords(text, words, keywords):
                return lesson, followups
        return None

    # 2. If subject is unknown, search across all catalogs
    for subj, catalog in LESSONS_BY_SUBJECT.items():
        for keywords, lesson, followups in catalog:
            if _matches_keywords(text, words, keywords):
                return lesson, followups

    return None


# ---------------------------------------------------------------------------
# Main MockAIProvider Class
# ---------------------------------------------------------------------------

class MockAIProvider(BaseAIProvider):
    """
    Deterministic local AI engine for the PragyaX demo.
    Zero external dependencies, zero network requests, 100% offline.
    Supports Python, Biology, Business/Entrepreneurship, and AI/ML.
    """

    @property
    def provider_name(self) -> str:
        return "PragyaX Mock AI (deterministic)"

    @property
    def is_mock(self) -> bool:
        return True

    def generate_chat_response(
        self, prompt: str, subject: str = "Python Programming", history: List[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Generates context-aware, deterministic pedagogical explanations across subjects.
        Guarantees backend compatibility by returning reply, provider, is_mock, and suggested_followups.
        """
        canonical_subject = normalize_subject(subject)
        display_subject = SUBJECT_DISPLAY_NAMES.get(canonical_subject, subject or "Learning")

        # 1. Keyword lesson matching
        found = _find_lesson(prompt, canonical_subject)
        if found:
            reply, followups = found

        # 2. Greeting check
        elif _words(prompt) & GREETING_WORDS:
            followups = STARTER_FOLLOWUPS_BY_SUBJECT.get(canonical_subject, STARTER_FOLLOWUPS_BY_SUBJECT["python"])

            if canonical_subject == "python":
                reply = (
                    f"Hi! I'm your **{display_subject}** study buddy (Demo AI).\n\n"
                    "Ask me about a concept and I'll explain it with a short example. Good places to start:\n"
                    "- Data types and variables\n"
                    "- Lists, tuples, dicts and sets\n"
                    "- Functions, scope and decorators\n"
                    "- Loops, comprehensions and generators\n\n"
                    "When you feel ready, take the 5-question assessment to measure your level."
                )
            elif canonical_subject == "biology":
                reply = (
                    f"Hi! I'm your **{display_subject}** study buddy (Demo AI).\n\n"
                    "Ask me about a biological principle and I'll explain it clearly. Great topics to explore:\n"
                    "- Cell structure and organelle functions\n"
                    "- DNA structure, genetics, and translation\n"
                    "- Photosynthesis and cellular respiration bioenergetics\n"
                    "- Enzyme kinetics and catalysis regulation\n"
                    "- Ecology, food webs, and carrying capacity\n\n"
                    "When you're ready, test your knowledge with the assessment!"
                )
            elif canonical_subject == "business":
                reply = (
                    f"Hi! I'm your **{display_subject}** mentor (Demo AI).\n\n"
                    "Ask me about startup and venture frameworks. Good topics to start with:\n"
                    "- Value propositions and customer discovery\n"
                    "- Minimum Viable Product (MVP) and Lean Startup loops\n"
                    "- Product-Market Fit (PMF) and retention heuristics\n"
                    "- Unit economics (CAC, LTV, and payback periods)\n"
                    "- The 9 blocks of the Business Model Canvas\n\n"
                    "Ready to validate your startup concepts? Take the 5-question assessment!"
                )
            elif canonical_subject == "ai_ml":
                reply = (
                    f"Hi! I'm your **{display_subject}** mentor (Demo AI).\n\n"
                    "Ask me about machine learning algorithms and systems. Excellent areas to cover:\n"
                    "- Supervised vs. unsupervised learning paradigms\n"
                    "- Overfitting, regularization (L1/L2), and bias-variance\n"
                    "- Classification metrics: precision, recall, and F1-score\n"
                    "- Neural networks, activation functions, and backpropagation\n"
                    "- Transformer architectures and self-attention mechanisms\n\n"
                    "When you feel prepared, challenge yourself with the assessment!"
                )
            else:
                reply = (
                    "Hi! I'm your **PragyaX AI** learning companion (Demo AI).\n\n"
                    "I support four interactive subject domains:\n"
                    "1. **Python Programming** (syntax, data structures, OOP, functions)\n"
                    "2. **Biology** (cells, genetics, bioenergetics, enzymes, ecology)\n"
                    "3. **Business/Entrepreneurship** (value props, MVPs, PMF, unit economics)\n"
                    "4. **AI/ML** (supervised learning, regularization, metrics, neural nets, transformers)\n\n"
                    "Pick a subject or ask a question to get started!"
                )
                followups = [
                    "Explain list comprehensions in Python",
                    "How does DNA base pairing work?",
                    "What is an MVP in entrepreneurship?",
                    "What is the difference between precision and recall?",
                ]

        # 3. Subject-specific fallback for unmatched questions
        else:
            if canonical_subject == "python":
                reply = (
                    "I'm the offline **Demo AI**, so I can only teach the core Python topics I know. "
                    "I couldn't match your question to one of them.\n\n"
                    "Try asking about: **variables & types, strings, conditionals, loops, lists/tuples/sets, "
                    "dictionaries, slicing, comprehensions, generators, functions, *args/**kwargs, scope (LEGB), "
                    "decorators, classes, exceptions, files, modules, recursion or mutability**.\n\n"
                    "Tip: the assessment focuses on mutability, slicing, dictionary keys, comprehensions and scope."
                )
                followups = STARTER_FOLLOWUPS_BY_SUBJECT["python"]
            elif canonical_subject == "biology":
                reply = (
                    "I'm the offline **Demo AI** for **Biology**. I couldn't match your question to one of my curated lessons.\n\n"
                    "Try asking about:\n"
                    "- **Cell organelles** (nucleus, mitochondria, ribosomes, chloroplasts, membrane)\n"
                    "- **DNA and genetics** (double helix, transcription, translation, alleles, mutations)\n"
                    "- **Photosynthesis & respiration** (light reactions, Calvin cycle, ATP, glycolysis)\n"
                    "- **Enzymes** (active sites, activation energy, denaturation, inhibition)\n"
                    "- **Ecology** (food webs, trophic levels, symbiosis, carrying capacity)\n\n"
                    "Tip: Review cell structures and DNA base pairing for assessment preparation."
                )
                followups = STARTER_FOLLOWUPS_BY_SUBJECT["biology"]
            elif canonical_subject == "business":
                reply = (
                    "I'm the offline **Demo AI** for **Business & Entrepreneurship**. I couldn't match your question to one of my lessons.\n\n"
                    "Try asking about:\n"
                    "- **Value Proposition** (Jobs-to-be-Done, pain relievers, gain creators)\n"
                    "- **Minimum Viable Product (MVP)** (Build-Measure-Learn, validation experiments)\n"
                    "- **Product-Market Fit (PMF)** (retention curves, Sean Ellis 40% heuristic test)\n"
                    "- **Unit Economics** (CAC, LTV, gross margin, payback periods)\n"
                    "- **Business Model Canvas** (the 9 building blocks, revenue streams, channels)\n\n"
                    "Tip: Focus on unit economics and customer validation for assessment preparation."
                )
                followups = STARTER_FOLLOWUPS_BY_SUBJECT["business"]
            elif canonical_subject == "ai_ml":
                reply = (
                    "I'm the offline **Demo AI** for **AI/ML**. I couldn't match your question to one of my curated lessons.\n\n"
                    "Try asking about:\n"
                    "- **Supervised vs. Unsupervised Learning** (classification, regression, clustering, PCA)\n"
                    "- **Overfitting & Regularization** (bias-variance, L1/L2 penalties, dropout, early stopping)\n"
                    "- **Evaluation Metrics** (confusion matrix, precision, recall, F1-score, ROC-AUC)\n"
                    "- **Neural Networks** (perceptrons, activation functions, backpropagation, loss)\n"
                    "- **Transformers** (self-attention, query vectors, token embeddings)\n\n"
                    "Tip: Review the bias-variance tradeoff and precision/recall trade-offs for assessment prep."
                )
                followups = STARTER_FOLLOWUPS_BY_SUBJECT["ai_ml"]
            else:
                reply = (
                    "I'm the offline **Demo AI**. I couldn't recognize that subject or match your question.\n\n"
                    "PragyaX currently offers learning modules for:\n"
                    "- **Python Programming**\n"
                    "- **Biology**\n"
                    "- **Business/Entrepreneurship**\n"
                    "- **AI/ML**\n\n"
                    "Please specify one of these subjects or ask a relevant conceptual question!"
                )
                followups = [
                    "What are Python data types?",
                    "How does DNA base pairing work?",
                    "How do you calculate CAC and LTV?",
                    "What is overfitting in machine learning?",
                ]

        return {
            "reply": reply,
            "provider": self.provider_name,
            "is_mock": self.is_mock,
            "suggested_followups": followups,
        }

    def evaluate_assessment(
        self,
        subject: str,
        questions: List[Dict[str, Any]],
        user_answers: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Evaluates a 5-question assessment deterministically against server-provided reference keys.
        Supports Python, Biology, Business, and AI/ML with subject-scoped remediation topics.
        """
        canonical_subject = normalize_subject(subject)
        display_subject = SUBJECT_DISPLAY_NAMES.get(canonical_subject, subject or "Subject")

        total = len(questions)
        score = 0
        breakdown = []
        missed_topics: List[str] = []

        for q in questions:
            correct = str(q.get("correct_option", "")).upper()
            selected = str(user_answers.get(q["id"], "")).strip().upper()
            is_correct = bool(selected and selected == correct)
            if is_correct:
                score += 1
            else:
                missed_topics.append(q.get("topic", f"{display_subject} fundamentals"))

            breakdown.append({
                "question_id": q["id"],
                "question_text": q["question_text"],
                "selected_option": selected or "Unanswered",
                "correct_option": correct,
                "is_correct": is_correct,
                "explanation": q.get("explanation", ""),
                "topic": q.get("topic", f"{display_subject} fundamentals"),
            })

        percentage = round(score / total * 100, 1) if total else 0.0
        level = proficiency_for(score, total)

        if level == "Advanced":
            summary = (f"Perfect score: {score}/{total} ({percentage}%). You have a strong grasp of these "
                       f"{display_subject} fundamentals. Move on to the advanced topics below.")
        elif level == "Intermediate":
            summary = (f"Good work: {score}/{total} ({percentage}%). Your core {display_subject} knowledge is solid; "
                       "review the questions you missed to close the gaps.")
        else:
            summary = (f"You scored {score}/{total} ({percentage}%). Start with the recommended topics below, "
                       "then use the Learning Chat to practise each concept before retaking the assessment.")

        # Subject-scoped topic recommendations
        subject_topic_map = TOPIC_RECOMMENDATIONS_BY_SUBJECT.get(
            canonical_subject, TOPIC_RECOMMENDATIONS_BY_SUBJECT["python"]
        )
        subject_advanced = ADVANCED_RECOMMENDATIONS_BY_SUBJECT.get(
            canonical_subject, ADVANCED_RECOMMENDATIONS_BY_SUBJECT["python"]
        )

        recommended = [
            subject_topic_map.get(t, f"Review: {t}") for t in missed_topics
        ] or subject_advanced

        return {
            "score": score,
            "total": total,
            "percentage": percentage,
            "proficiency_level": level,
            "breakdown": breakdown,
            "recommended_topics": recommended,
            "summary_feedback": summary,
            "is_mock": self.is_mock,
            "provider": self.provider_name,
        }
