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
from helpers.admin import admin_meta

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

def frac_to_str(x: Fraction) -> str:
    if x.denominator == 1:
        return str(x.numerator)
    return f"{x.numerator}/{x.denominator}"

def parse_frac_str(s: str) -> Fraction:
    if "/" in s:
        a,b = s.split("/", 1)
        return Fraction(int(a), int(b))
    return Fraction(int(s), 1)


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
    unlimited = (a == 0 or a == 1) and e > 0
    if not unlimited and e > MAKE_TEN_MAX_ABS_EXPONENT:
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
        elif c in "+-*/^!()":
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
        
        if a == FACT and b == LPAREN:
            raise ValueError("Put an operator between '!' and '('.")

def validate_uses_numbers_exactly_once(tokens: list[str], numbers: list[int]) -> None:
    used = extract_number_literals(tokens)
    if len(used) != 4:
        raise ValueError("You must use exactly 4 numbers (each once).")
    if sorted(used) != sorted(numbers):
        raise ValueError(f"You must use the numbers exactly once: {numbers}")


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
    
    return output
    

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

        raise ValueError(f"Unkown RPN token: {tok}")
    
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
        
BASIC_OPS = ["+", "-", "*", "/"]

def basic_solvable(numbers: list[int], target: int) -> bool:
    vals = [Fraction(n, 1) for n in numbers]

    def rec(arr: list[Fraction]) -> bool:
        if len(arr) == 1:
            return arr[0] == Fraction(target, 1)
        
        for i in range(len(arr)):
            for j in range(len(arr)):
                if i == j:
                    continue

                a = arr[i]
                b = arr[j]
                rest = [arr[k] for k in range(len(arr)) if k not in (i, j)]

                for op in BASIC_OPS:
                    if op == "+":
                        c = a + b
                    elif op == "-":
                        c = a - b
                    elif op == "*":
                        c = a * b
                    else:
                        if b == 0:
                            continue
                        c = a / b

                    if rec(rest + [c]):
                        return True
        return False
    
    return rec(vals)


def generate_daily_numbers() -> list[int]:
    while True:
        nums = [random.randint(1, 9) for _ in range(4)]
        if basic_solvable(nums, MAKE_TEN_TARGET):
            return nums


class BuilderView(discord.ui.View):
    def __init__(self, cog, user: discord.User, numbers: list[int], puzzle_date: str, allow_write: bool):
        super().__init__(timeout=300)
        self.cog = cog
        self.user = user
        self.numbers = numbers
        self.puzzle_date = puzzle_date
        self.allow_write = allow_write
        self.tokens: list[str] = []
        self.used_counts = {n: 0 for n in numbers}

        self.digit_used = [False, False, False, False]

        for i, n in enumerate(numbers):
            self.add_item(DigitButton(idx=i, label=str(n)))
        
        self.add_item(OpButton("+"))
        self.add_item(OpButton("-"))
        self.add_item(OpButton("*"))
        self.add_item(OpButton("/"))
        self.add_item(OpButton("^"))
        self.add_item(OpButton("("))
        self.add_item(OpButton(")"))
        self.add_item(OpButton("!"))

        self.add_item(ControlButton("🔙", "back"))
        self.add_item(ControlButton("Clear", "clear"))
        self.add_item(ControlButton("Submit", "submit", style = discord.ButtonStyle.success))
    
    async def interaction_check(self, interaction: discord.Interaction):
        return interaction.user.id == self.user.id
    
    def expr_str(self) -> str:
        out = []
        for t in self.tokens:
            if t == "!":
                if out:
                    out[-1] = out[-1] + "!"
                else:
                    out.append("!")
            else:
                out.append(t)
        return " ".join(out)
    
    def all_digits_used(self) -> bool:
        return all(self.digit_used)
    
    def current_value_text(self) -> str:
        if not self.all_digits_used():
            return "*(Use all 4 numbers to see a value)*"
        
        expr = self.expr_str()
        try:
            val = try_eval_expression(expr, self.numbers)
            return f"`{frac_to_str(val)}`"
        except Exception as e:
            return f"⚠️ {str(e)}"
    

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(title = "🧮 Make Ten - Build your expression")
        embed.add_field(name="Numbers", value=" ".join(str(n) for n in self.numbers), inline=False)
        embed.add_field(name="Target", value=str(MAKE_TEN_TARGET), inline=False)
        embed.add_field(name="Expression", value=f"`{self.expr_str() or ''}`" if self.tokens else "*(empty)*", inline=False)
        embed.add_field(name="Value", value=self.current_value_text(), inline=False)
        embed.set_footer(text="Each number must be used exactly once. No concatenation. No implicit multiplication. 💚")
        return embed

    async def refresh(self, interaction: discord.Interaction):
        await interaction.response.edit_message(embed=self.build_embed(), view=self)
    
    def push_digit(self, idx: int):
        if self.digit_used[idx]:
            return
        self.digit_used[idx] = True
        self.tokens.append(str(self.numbers[idx]))
    
    def push_token(self, tok:str):
        self.tokens.append(tok)
    
    def backspace(self):
        if not self.tokens:
            return
        
        last = self.tokens.pop()
        if last.isdigit():
            d = int(last)
            for i in range(3, -1, -1):
                if self.digit_used[i] and self.numbers[i] == d:
                    self.digit_used[i] = False
                    break
    
    def clear(self):
        self.tokens = []
        self.digit_used = [False, False, False, False]
    
    async def handle_submit(self, interaction: discord.Interaction):
        if not self.all_digits_used():
            await interaction.response.send_message("Use all 4 numbers before submitting.", ephemeral=True)
            return
        
        expr = self.expr_str()
        try:
            val = try_eval_expression(expr, self.numbers)
        except Exception as e:
            await interaction.response.send_message(f"Invalid Expression: {e}", ephemeral=True)
            return
        
        if val != Fraction(MAKE_TEN_TARGET, 1):
            await interaction.response.send_message(f"That evaluates to `{frac_to_str(val)}`, not {MAKE_TEN_TARGET}", ephemeral=True)
            return

        if self.allow_write:
            ok, msg = await self.cog.record_solution(self.puzzle_date, interaction.user, expr)
            if not ok:
                await interaction.response.send_message(msg, ephemeral=True)
                return
        
        await interaction.response.send_message(f"✅ Solved! `{expr}` = {MAKE_TEN_TARGET}", ephemeral=True)
        self.stop()


class DigitButton(discord.ui.Button):
    def __init__(self, idx: int, label: str):
        super().__init__(label=label, style=discord.ButtonStyle.primary, row=0)
        self.idx = idx
    
    async def callback(self, interaction: discord.Interaction):
        view: BuilderView = self.view
        view.push_digit(self.idx)

        self.disabled = True
        await view.refresh(interaction)

class OpButton(discord.ui.Button):
    def __init__(self, tok: str):
        label = tok
        style = discord.ButtonStyle.secondary
        row = 1
        if tok in ("(", ")", "!"):
            row = 2
        super().__init__(label=label, style=style, row=row)
        self.tok = tok

    async def callback(self, interaction: discord.Interaction):
        view: BuilderView = self.view
        view.push_token(self.tok)

        await view.refresh(interaction)

class ControlButton(discord.ui.Button):
    def __init__(self, label: str, action: str, style=discord.ButtonStyle.danger):
        super().__init__(label=label, style=style, row=3)
        self.action = action
    
    async def callback(self, interaction: discord.Interaction):
        view: BuilderView = self.view
        
        if self.action == "back":
            before = list(view.digit_used)
            view.backspace()
            after = view.digit_used

            for child in view.children:
                if isinstance(child, DigitButton):
                    if before[child.idx] and not after[child.idx]:
                        child.disabled = False
            
            await view.refresh(interaction)
            return
        
        if self.action == "clear":
            view.clear()

            for child in view.children:
                if isinstance(child, DigitButton):
                    child.disabled = False
            
            await view.refresh(interaction)
            return
    
        if self.action == "submit":
            await view.handle_submit(interaction)
            return



class DailyPanelView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Numbers Today", style=discord.ButtonStyle.secondary, custom_id="make_ten:today")
    async def today_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.show_today(interaction)

    @discord.ui.button(label="Play", style=discord.ButtonStyle.primary, custom_id="make_ten:Play")
    async def submit_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.open_builder(interaction)

    @discord.ui.button(label="Stats", style=discord.ButtonStyle.secondary, custom_id="make_ten:stats")
    async def stats_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.show_stats(interaction)


class MakeTen(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.add_view(DailyPanelView(self))
        self.daily_tick.start()
        self.daily_summary_tick.start()

    def cog_unload(self):
        self.daily_tick.cancel()
        self.daily_summary_tick.cancel()

    def load(self):
        return load_json(DATA_FILE, {"puzzles": {}, "users": {}})

    def save(self, data):
        save_json(DATA_FILE, data)

    def get_or_create_puzzle(self, date: str):
        data = self.load()
        puzzles = data.setdefault("puzzles", {})
        if date not in puzzles:
            puzzles[date] = {
                "numbers": generate_daily_numbers(),
                "target": MAKE_TEN_TARGET,
                "posted_message_id": None,
                "posted_channel_id": MAKE_TEN_CHANNEL_ID,
                "solutions": {},
                "summary_posted": False,
            }
            self.save(data)
        return puzzles[date]

    def build_daily_embed(self, date: str, puzzle: dict) -> discord.Embed:
        nums = puzzle["numbers"]
        e = discord.Embed(title=f"🧮 Make Ten - {date}")
        e.description = (
            "**Goal:** Use the 4 numbers **exactly once** to make **10**.\n\n"
            "**Allowed:** `+  -  *  /  ^  !  ( )`\n"
            "**Order of operations applies. Use parentheses to be explicit.**\n"
            "**Not allowed:** concatenation (`12`), implicit multiplication (`2(3)`), reusing a number.\n\n"
            "Press **Submit** to open the private calculator UI."
        )
        e.add_field(name="Numbers", value=" ".join(str(n) for n in nums), inline=False)
        e.add_field(name="Target", value=str(puzzle.get("target", MAKE_TEN_TARGET)), inline=True)

        solved = len(puzzle.get("solutions", {}))
        e.add_field(name="Solved today", value=str(solved), inline=True)
        e.set_footer(text="Opt-in mention available if enabled.")
        return e

    async def ensure_posted_today(self):
        date = today_str()
        data = self.load()
        puzzle = self.get_or_create_puzzle(date)

        if puzzle.get("posted_message_id"):
            return

        ch = self.bot.get_channel(MAKE_TEN_CHANNEL_ID)
        if not isinstance(ch, discord.TextChannel):
            return

        ping_content = None
        if MAKE_TEN_PING_ROLE_NAME:
            role = discord.utils.get(ch.guild.roles, name=MAKE_TEN_PING_ROLE_NAME)
            if role:
                ping_content = f"Opt-In Mentions: {role.mention}"

        embed = self.build_daily_embed(date, puzzle)
        msg = await ch.send(content=ping_content, embed=embed, view=DailyPanelView(self), silent=True)

        data = self.load()
        data["puzzles"][date]["posted_message_id"] = msg.id
        data["puzzles"][date]["posted_channel_id"] = ch.id
        self.save(data)

    async def announce_solve(self, user: discord.User, date: str):
        ch = self.bot.get_channel(MAKE_TEN_CHANNEL_ID)
        if not isinstance(ch, discord.TextChannel):
            return

        data = self.load()
        p = data.get("puzzles", {}).get(date, {})
        solved = len(p.get("solutions", {}))

        await ch.send(f"{user.mention} has solved today's puzzle 🎉 ({solved} solved so far)")


    async def post_summary_for_yesterday(self):
        y = yesterday_str()
        data = self.load()
        puzzles = data.get("puzzles", {})
        p = puzzles.get(y)
        if not p:
            return
        if p.get("summary_posted"):
            return

        sols: dict = p.get("solutions", {})
        if not sols:
            p["summary_posted"] = True
            self.save(data)
            return

        ch = self.bot.get_channel(MAKE_TEN_CHANNEL_ID)
        if not isinstance(ch, discord.TextChannel):
            return

        e = discord.Embed(title=f"📌 Make Ten - Summary for {y}")
        nums = p.get("numbers", [])
        e.description = f"Numbers were: **{' '.join(str(n) for n in nums)}** → target **{MAKE_TEN_TARGET}**\n\n**Solvers:**"

        lines = []
        items = sorted(sols.items(), key=lambda kv: kv[1].get("at", 0))
        for uid, rec in items:
            expr = rec.get("expr", "")
            lines.append(f"<@{uid}>   **`{expr}`**")

        chunk = "\n".join(lines)
        if len(chunk) > 3900:
            chunk = chunk[:3900] + "\n…"

        e.add_field(name="Solutions", value=chunk, inline=False)

        await ch.send(embed=e)

        data = self.load()
        data["puzzles"][y]["summary_posted"] = True
        self.save(data)

    def update_user_stats_on_solve(self, data: dict, user_id: str, solve_date: str):
        users = data.setdefault("users", {})
        u = users.setdefault(user_id, {
            "current_streak": 0,
            "best_streak": 0,
            "last_solve_date": None,
            "total_played": 0,
            "total_solved": 0
        })

        last = u.get("last_solve_date")
        u["total_played"] = int(u.get("total_played", 0)) + 1
        u["total_solved"] = int(u.get("total_solved", 0)) + 1

        if last:
            last_dt = datetime.date.fromisoformat(last)
            cur_dt = datetime.date.fromisoformat(solve_date)
            if (cur_dt - last_dt).days == 1:
                u["current_streak"] = int(u.get("current_streak", 0)) + 1
            elif (cur_dt - last_dt).days == 0:
                pass
            else:
                u["current_streak"] = 1
        else:
            u["current_streak"] = 1

        u["last_solve_date"] = solve_date
        u["best_streak"] = max(int(u.get("best_streak", 0)), int(u.get("current_streak", 0)))

    async def record_solution(self, date: str, user: discord.User, expr: str) -> tuple[bool, str]:
        data = self.load()
        puzzle = data.setdefault("puzzles", {}).setdefault(date, None)
        if puzzle is None:
            puzzle = self.get_or_create_puzzle(date)
            data = self.load()
            puzzle = data["puzzles"][date]

        sols = puzzle.setdefault("solutions", {})
        uid = str(user.id)

        if uid in sols:
            return (False, "You already solved today's puzzle.")

        sols[uid] = {"expr": expr, "at": now()}

        self.update_user_stats_on_solve(data, uid, date)
        self.save(data)

        await self.try_update_daily_post(date)
        await self.announce_solve(user, date)

        return (True, "ok")

    async def try_update_daily_post(self, date: str):
        data = self.load()
        p = data.get("puzzles", {}).get(date)
        if not p:
            return
        msg_id = p.get("posted_message_id")
        ch_id = p.get("posted_channel_id", MAKE_TEN_CHANNEL_ID)
        if not msg_id:
            return

        ch = self.bot.get_channel(ch_id)
        if not isinstance(ch, discord.TextChannel):
            return
        try:
            msg = await ch.fetch_message(int(msg_id))
        except Exception:
            return

        embed = self.build_daily_embed(date, p)
        await msg.edit(embed=embed, view=DailyPanelView(self))



    @tasks.loop(time=datetime.time(hour=0, minute=0, tzinfo=TZ))
    async def daily_tick(self):
        await self.ensure_posted_today()
    
    @tasks.loop(time=datetime.time(hour=0, minute=5, tzinfo=TZ))
    async def daily_summary_tick(self):
        await self.post_summary_for_yesterday()

    @daily_summary_tick.before_loop
    async def before_daily_summary_tick(self):
        await self.bot.wait_until_ready()
    
    @daily_tick.before_loop
    async def before_daily_tick(self):
        await self.bot.wait_until_ready()
        await self.ensure_posted_today()


    async def ensure_in_channel(self, interaction: discord.Interaction) -> bool:
        if interaction.channel_id != MAKE_TEN_CHANNEL_ID:
            ch = self.bot.get_channel(MAKE_TEN_CHANNEL_ID)
            mention = ch.mention if isinstance(ch, discord.TextChannel) else f"<#{MAKE_TEN_CHANNEL_ID}>"
            await interaction.response.send_message(f"Use this in {mention}.", ephemeral=True)
            return False
        return True

    async def show_today(self, interaction: discord.Interaction):
        if not await self.ensure_in_channel(interaction):
            return
        d = today_str()
        p = self.get_or_create_puzzle(d)
        e = discord.Embed(title=f"🧮 Make Ten - {d}")
        e.add_field(name="Numbers", value=" ".join(str(n) for n in p["numbers"]), inline=False)
        e.add_field(name="Target", value=str(MAKE_TEN_TARGET), inline=True)
        solved = len(p.get("solutions", {}))
        e.add_field(name="Solved today", value=str(solved), inline=True)
        await interaction.response.send_message(embed=e, ephemeral=True)

    async def open_builder(self, interaction: discord.Interaction, *, allow_write: bool = True):
        if not await self.ensure_in_channel(interaction):
            return
        d = today_str()
        p = self.get_or_create_puzzle(d)

        if allow_write:
            data = self.load()
            sols = data.get("puzzles", {}).get(d, {}).get("solutions", {})
            if str(interaction.user.id) in sols:
                return await interaction.response.send_message("You already solved today's puzzle.", ephemeral=True)

        view = BuilderView(self, interaction.user, p["numbers"], d, allow_write=allow_write)
        await interaction.response.send_message(embed=view.build_embed(), view=view, ephemeral=True)

    async def show_stats(self, interaction: discord.Interaction):
        if not await self.ensure_in_channel(interaction):
            return
        data = self.load()
        u = data.get("users", {}).get(str(interaction.user.id), {})
        cur = int(u.get("current_streak", 0))
        best = int(u.get("best_streak", 0))
        played = int(u.get("total_played", 0))
        solved = int(u.get("total_solved", 0))
        last = u.get("last_solve_date")

        e = discord.Embed(title=f"📈 Make Ten Stats - {interaction.user.display_name}")
        e.add_field(name="Current streak", value=str(cur), inline=True)
        e.add_field(name="Best streak", value=str(best), inline=True)
        e.add_field(name="Solved", value=f"{solved}", inline=True)
        e.add_field(name="Played", value=f"{played}", inline=True)
        e.add_field(name="Last solve", value=last or "—", inline=False)
        await interaction.response.send_message(embed=e, ephemeral=True)



    @app_commands.command(name="maketen", description="Show today's Make Ten numbers.")
    async def make_ten_today(self, interaction: discord.Interaction):
        await self.show_today(interaction)

    @app_commands.command(name="maketenplay", description="Open the private Make Ten calculator UI.")
    async def make_ten_play(self, interaction: discord.Interaction):
        await self.open_builder(interaction, allow_write=True)

    @app_commands.command(name="maketenstats", description="Show your Make Ten stats and streak.")
    async def make_ten_stats(self, interaction: discord.Interaction):
        await self.show_stats(interaction)

    @app_commands.command(name="maketenview", description="View any date's puzzle (YYYY-MM-DD).")
    @app_commands.describe(date="The date in the format YYYY-MM-DD")
    async def make_ten_view(self, interaction: discord.Interaction, date: str):
        if not await self.ensure_in_channel(interaction):
            return
        try:
            datetime.date.fromisoformat(date)
        except Exception:
            return await interaction.response.send_message("Date must be YYYY-MM-DD.", ephemeral=True)

        data = self.load()
        p = data.get("puzzles", {}).get(date)
        if not p:
            return await interaction.response.send_message("No puzzle saved for that date.", ephemeral=True)

        e = self.build_daily_embed(date, p)
        await interaction.response.send_message(embed=e, ephemeral=True)

    @app_commands.command(name="maketentest", description="Test the UI without writing to the data file.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @admin_meta(
        permissions="Administrator",
        affects=[],
        notes="For testing changes to the Make Ten gui"
    )
    async def make_ten_admin_test(self, interaction: discord.Interaction):
        if interaction.channel_id != MAKE_TEN_CHANNEL_ID:
            ch = self.bot.get_channel(MAKE_TEN_CHANNEL_ID)
            mention = ch.mention if isinstance(ch, discord.TextChannel) else f"<#{MAKE_TEN_CHANNEL_ID}>"
            return await interaction.response.send_message(f"Use this in {mention}.", ephemeral=True)

        nums = generate_daily_numbers()
        view = BuilderView(self, interaction.user, nums, puzzle_date="TEST", allow_write=False)
        await interaction.response.send_message(
            content="🧪 Admin test - this will NOT save anything.",
            embed=view.build_embed(),
            view=view,
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(MakeTen(bot))