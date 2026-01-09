import discord
from discord.ext import commands
from discord import app_commands
from collections import defaultdict
from helpers.embedHelper import add_spacer
from helpers.admin import admin_meta


class HelpPages(discord.ui.View):
    def __init__(self, embeds: list[discord.Embed], viewer_id: int):
        super().__init__(timeout=120)
        self.embeds = embeds
        self.viewer_id = viewer_id
        self.index = 0

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.viewer_id:
            await interaction.response.send_message("❌ Only the person who opened this menu can change pages, use `/help` to check your own!", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True

    @discord.ui.button(label="⬅️ Prev", style=discord.ButtonStyle.secondary)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = (self.index - 1 + len(self.embeds)) % len(self.embeds)
        await interaction.response.edit_message(embed=self.embeds[self.index], view=self)

    @discord.ui.button(label="➡️ Next", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = (self.index + 1) % len(self.embeds)
        await interaction.response.edit_message(embed=self.embeds[self.index], view=self)


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @app_commands.command(name="help", description="Show the avaliable commands")
    async def help(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        grouped_commands = defaultdict(list)

        for command in self.bot.tree.walk_commands():
            try:
                await command._check_can_run(interaction)
            except app_commands.CheckFailure:
                continue

            cog_name = command.binding.__class__.__name__ if command.binding else "General"
            grouped_commands[cog_name].append(command)

        embeds = []
        chunk_size = 5

        for cog_name, command_list in grouped_commands.items():
            for i in range(0, len(command_list), chunk_size):

                embed = discord.Embed(
                    title="📖 Bot Commands",
                    description=f"**Catergory:** {cog_name}",
                    color=discord.Color.green()
                )

                chunk = command_list[i:i + chunk_size]

                for command in chunk:
                    embed.add_field(
                        name = f"/{command.name}",
                        value=command.description or "No Description Provided",
                        inline=False
                    )

                embeds.append(embed)

        if not embeds:
           await interaction.followup.send("🥲 No Commands Avaliable", ephemeral=True)
           return

        total_pages = len(embeds)
        for i, embed in enumerate(embeds, start=1):
            embed.set_footer(
                    text = f"Page {i} / {total_pages}"
                )


        view = HelpPages(embeds=embeds, viewer_id=interaction.user.id)

        await interaction.followup.send(embed=embeds[0], view=view, ephemeral=True)


    @app_commands.command(name="helpadmin", description="Admin-Only Commands Refrence")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @admin_meta(permissions= "Administrator", affects= [], notes= "Lists all of the admin commands with help")
    @admin_meta(permissions= "Administrator",
            affects= [
            ],
            notes= "Look through all of these and understand them")
    async def admin_help(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        admin_commands = []

        for command in self.bot.tree.walk_commands():
            if not command.callback:
                continue

            perms = getattr(command, "default_permissions", None)
            if not perms or not perms.administrator:
                continue

            admin_commands.append(command)


        embeds = []

        contents_page = discord.Embed(
            title="🤖 Admin Commands",
            description="Contents Page",
            color=discord.Color.yellow()
        )
        contents_page.add_field(
            name="",
            value="\n".join([f"- {command.name}" for command in admin_commands]),
            inline=False
        )
        embeds.append(contents_page)

        for command in admin_commands:
            embed = discord.Embed(
                title=f"/{command.name}",
                description=command.description or "No Description",
                color=discord.Color.yellow()
            )

            meta = getattr(command.callback, "admin_help", {})

            embed.add_field(
                name= "🔐 Permissions",
                value=meta.get("permissions", "Administrator"),
                inline=False
            )

            add_spacer(embed)

            embed.add_field(
                name="⚙️ Affects",
                value="\n".join(f"- {x}" for x in meta.get("affects", [])) or "None",
                inline=False
            )

            if "notes" in meta:
                add_spacer(embed)

                embed.add_field(
                    name="📝 Notes",
                    value=meta["notes"],
                    inline=False
                )

            embeds.append(embed)

        if not embeds:
           await interaction.followup.send("🥲 No Commands Avaliable", ephemeral=True)
           return

        total_pages = len(embeds)
        for i, embed in enumerate(embeds, start=1):
            embed.set_footer(
                    text = f"Page {i} / {total_pages}"
                )


        view = HelpPages(embeds=embeds, viewer_id=interaction.user.id)

        await interaction.followup.send(embed=embeds[0], view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Help(bot))