from discord import app_commands
import discord
from constants import *

def isAdmin(interaction: discord.Interaction) -> bool:
    return any(role.name in ADMIN_ROLES for role in interaction.user.roles)