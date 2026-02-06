import discord
from constants import ADMIN_ROLES

def admin_meta(**meta):
    def decorator(func):
        func.admin_help = meta
        return func
    return decorator

def is_admin(member: discord.Member) -> bool:
    return any(r.name in ADMIN_ROLES for r in member.roles)