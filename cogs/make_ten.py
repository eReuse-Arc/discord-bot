import discord
from discord.ext import commands, tasks
from discord import app_commands
from pathlib import Path
import json
import time
import random
import datetime
from zoneinfo import ZoneInfo
from fractions import Fraction
import math

from constants import MAKE_TEN_CHANNEL_ID, MAKE_TEN_PATH, MAKE_TEN_PING_ROLE_NAME, MAKE_TEN_TARGET, MAKE_TEN_MAX_FACTORIAL_N, MAKE_TEN_MAX_ABS_EXPONENT

DATA_FILE = Path(MAKE_TEN_PATH)

TZ = ZoneInfo("Australia/Sydney")

def now() -> int:
    return int(time.time())

def today_str() -> str:
    return datetime.datetime.now(TZ).date().isoformat()

def yesterday_str() -> str:
    return (datetime.datetime.now(TZ).date() - datetime.timedelta(days=1)).isoformat()

def load_json(path: Path, default = {}):
    if not path.exists():
        return default
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default

def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")



OPS = {"+", "-", "*", "/", "^"}
LPAREN = "("
RPAREN = ")"
FACT = "!"
NEG = "NEG"

def is_int_frac(x: Fraction) -> bool:
    return x.denominator == 1


def factorial_frac(x: Fraction) -> Fraction:
    if not is_int_frac(x):
        raise ValueError("Factorial requires an integer.")
    n = int(x)
    if n < 0:
        raise ValueError("Factorial requires a non-negative integer.")
    if n > MAKE_TEN_MAX_FACTORIAL_N:
        raise ValueError(f"Factorial too large (>{MAKE_TEN_MAX_FACTORIAL_N}).")
    return Fraction(math.factorial(n), 1)

def power_frac(a: Fraction, b: Fraction) -> Fraction:
    if not is_int_frac(b):
        raise ValueError("Exponent must be an integer")
    e = int(b)
    if abs(e) > MAKE_TEN_MAX_ABS_EXPONENT:
        raise ValueError(f"Exponent too large (|exp|>{MAKE_TEN_MAX_ABS_EXPONENT})")
    
    if e >= 0:
        return a ** e
    if a == 0:
        raise ValueError("0 cannot be raised to a negative power.")
    
    return Fraction(1,1) / (a ** (-e))

def tokenise(expr: str) -> list[str]:
    s = expr.replace(" ", "")
    if not s:
        return []
    
    tokens: list[str] = []
    for c in s:
        if c.isdigit():
            tokens.append(c)
        elif c in OPS + [FACT, LPAREN, RPAREN]:
            tokens.append(c)
        else:
            raise ValueError(f"Invalid character: {c}")
    
    return tokens
        
def extract_number_literals(tokens: list[str]) -> list[int]:
    return [int(t) for t in tokens if t.isdigit()]

def validate_no_concatenation(tokens: list[str]) -> None:
    for i in range(1, len(tokens)):
        a = tokens[i - 1]
        b = tokens[i]

        if a.isdigit() and b.isdigit():
            raise ValueError("Numbers cannot be concatenated (e.g. 12). Put an operator between.")
        
        if (a == RPAREN or a == FACT) and b.isdigit():
            raise ValueError("Put an operator between tokens (no implicit multiplication).")
        
        if a.isdigit() and b == LPAREN:
            raise ValueError("Put an operator befor '(' (no implicit multiplication).")
        
        if a == RPAREN and b == LPAREN:
            raise ValueError("Put an operator between ')' and '('.")

def validate_uses_numbers_exactly_once(tokens: list[str], numbers: list[int]) -> None:
    used = extract_number_literals(tokens)
    if len(used) != 4:
        raise ValueError("You must use exactly 4 numbers (each once).")
    if sorted(used) != sorted(numbers):
        raise(f"You must use the numbers exactly once: {numbers}")


PRECEDENCE = {"+": 1, "-": 1, "*": 2, "/": 2, "^": 3, NEG: 4, FACT: 5}
RIGHT_ASSOC = {"^", NEG }

def is_operator(tok: str) -> bool:
    return tok in OPS or tok in (NEG,)

def is_value(tok: str) -> bool:
    return tok.isdigit()

def shunting_yard(tokens: list[str]) -> list[str]:
    output: list[str] = []
    stack: list[str] = []

    prev: str | None = None

    for tok in tokens:
        if is_value(tok):
            output.append(tok)
            prev = tok
            continue
        
        if tok == FACT:
            if prev is None or (prev in OPS) or (prev == LPAREN):
                raise ValueError("Factorial must come after a number or ')'.")
            output.append(FACT)
            prev = tok
            continue

        if tok == LPAREN:
            stack.append(LPAREN)
            prev = tok
            continue

        if tok == RPAREN:
            found = False
            while stack:
                top = stack.pop()
                if top == LPAREN:
                    found = True
                    break
                output.append(top)
            if not found:
                raise ValueError("Mismatched Parentheses.")
            prev = tok
            continue

        if tok in OPS:
            op = tok
            if op == "-" and (prev is None or prev in OPS or prev == LPAREN):
                op = NEG
            
            if op != NEG and (prev is None or prev in OPS or prev == LPAREN):
                raise ValueError("Operator in invalid position.")
            
            while stack:
                top = stack[-1]
                if top == LPAREN:
                    break

                if top in PRECEDENCE:
                    p_top = PRECEDENCE[top]
                    p_op = PRECEDENCE[op]

                    if (op in RIGHT_ASSOC and p_op < p_top) or (op not in RIGHT_ASSOC and p_op <= p_top):
                        output.append(stack.pop())
                        continue
                break
        
            stack.append(op)
            prev = tok
            continue

        raise ValueError(f"Unkown token: {tok}")
    
    if prev in OPS or prev == LPAREN:
        raise ValueError("Expression ended unexpectedly.")
    
    while stack:
        top = stack.pop()
        if top in (LPAREN, RPAREN):
            raise ValueError("Mismatched Parentheses.")
        output.append(top)
    

def eval_rpn(rpn: list[str]) -> Fraction:
    stack: list[Fraction] = []

    for tok in rpn:
        if tok.isdigit():
            stack.append(Fraction(int(tok), 1))
            continue

        if tok == FACT:
            if not stack:
                raise ValueError("Factorial missing operand")
            a = stack.pop()
            stack.append(factorial_frac(a))
            continue

        if tok == NEG:
            if not stack:
                raise ValueError("Unary '-' missing operand")
            a = stack.pop()
            stack.append(-a)
            continue

        if tok in OPS:
            if len(stack) < 2:
                raise ValueError("Binary operator mising operands.")
            b = stack.pop()
            a = stack.pop()

            if tok == "+":
                stack.append(a + b)
            elif tok == "-":
                stack.append(a - b)
            elif tok == "*":
                stack.append(a * b)
            elif tok == "/":
                if b == 0:
                    raise ValueError("Division by zero.")
                stack.append(a / b)
            elif tok == "^":
                stack.append(power_frac(a, b))
            else:
                raise ValueError(f"Unkown operator: {tok}")
            continue

        raise ValueError("Unkown RPN token: {tok}")
    
    if len(stack) != 1:
        raise ValueError(f"Invalid expression")
    return stack[0]

def try_eval_expression(expr: str, numbers: list[int]) -> Fraction:
    tokens = tokenise(expr)
    if not tokens:
        raise ValueError("Empty Expression.")
    
    validate_no_concatenation(tokens)
    validate_uses_numbers_exactly_once(tokens, numbers)

    rpn = shunting_yard(tokens)
    return eval_rpn(rpn)
        
