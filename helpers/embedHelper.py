import discord

def add_spacer(embed: discord.Embed):
    embed.add_field(name="\u200b", value="\u200b", inline=False)
