import logging
import re
from pathlib import Path

import discord
from discord import app_commands
from tortoise.exceptions import BaseORMException

from ballsdex.core.bot import BallsDexBot
from ballsdex.core.models import Ball
from ballsdex.core.utils.transformers import EconomyTransform, RegimeTransform
from ballsdex.settings import settings

log = logging.getLogger("ballsdex.packages.admin.balls")
FILENAME_RE = re.compile(r"^(.+)(\.\S+)$")

balls: dict[int, Ball] = {}


async def save_file(attachment: discord.Attachment) -> Path:
    path = Path(f"./admin_panel/media/{attachment.filename}")
    match = FILENAME_RE.match(attachment.filename)
    if not match:
        raise TypeError("The file you uploaded lacks an extension.")
    i = 1
    while path.exists():
        path = Path(f"./admin_panel/media/{match.group(1)}-{i}{match.group(2)}")
        i = i + 1
    await attachment.save(path)
    return path.relative_to("./admin_panel/media/")


class Custom(app_commands.Group):
    """
    Countryballs management
    """

    @app_commands.command(name="create")
    @app_commands.checks.has_any_role(*settings.root_role_ids)
    async def balls_create(
        self,
        interaction: discord.Interaction[BallsDexBot],
        *,
        name: app_commands.Range[str, None, 48],
        regime: RegimeTransform,
        health: int,
        attack: int,
        emoji_id: app_commands.Range[str, 17, 21],
        capacity_name: app_commands.Range[str, None, 64],
        capacity_description: app_commands.Range[str, None, 256],
        cart: discord.Attachment | None = None,
        image_credits: str,
        economy: EconomyTransform | None = None,
        rarity: float = 0.0,
        enabled: bool = False,
        tradeable: bool = False,
        catch_names: str | None = None,
        short_name: str | None = None,
        spart: discord.Attachment,
    ):
        """
        Shortcut command for creating countryballs. They are disabled by default.

        Parameters
        ----------
        name: str
        regime: Regime
        economy: Economy | None
        health: int
        attack: int
        emoji_id: str
            An emoji ID, the bot will check if it can access the custom emote
        capacity_name: str
        capacity_description: str
        cart: discord.Attachment
        image_credits: str
        rarity: float
            Value defining the rarity of this countryball, if enabled
        enabled: bool
            If true, the countryball can spawn and will show up in global completion
        tradeable: bool
            If false, all instances are untradeable
        spart: discord.Attachment
            Artwork used to spawn the countryball, with a default
        """
        if regime is None or interaction.response.is_done():  # economy autocomplete failed
            return

        if not emoji_id.isnumeric():
            await interaction.response.send_message(
                "`emoji_id` is not a valid number.", ephemeral=True
            )
            return

        if cart is None or spart is None:
            await interaction.response.send_message(
                "`Cart` and `Spart` are required", ephemeral=True
            )
            return

        if catch_names is None:
            catch_names = ""

        # emoji = interaction.client.get_emoji(int(emoji_id))
        # if not emoji:
        # await interaction.response.send_message(
        # "The bot does not have access to the given emoji.", ephemeral=True
        # )
        # return

        if short_name is None:
            short_name = ""

        await interaction.response.defer(ephemeral=True, thinking=True)

        # default_path = Path("./admin_panel/media/Card_Test_Placeholder.jpg")
        # missing_default = ""
        # if not cart and not default_path.exists():
        #     missing_default = (
        #         "**Warning:** The default card art is not set. This will result in errors when "
        #         f"attempting to look at this {settings.collectible_name}. You can edit this on "
        #         f"the web panel or add an image at `{default_path.as_posix()}`.\n"
        #     )

        try:
            cart_path = await save_file(cart)
        except Exception as e:
            log.exception("Failed saving file when creating countryball", exc_info=True)
            await interaction.followup.send(
                f"Failed saving the attached file: {cart.url}.\n"
                f"Partial error: {', '.join(str(x) for x in e.args)}\n"
                "The full error is in the bot logs."
            )
            return

        try:
            spart_path = await save_file(spart)
        except Exception as e:
            log.exception("Failed saving file when creating countryball", exc_info=True)
            await interaction.followup.send(
                f"Failed saving the attached file: {cart.url}.\n"
                f"Partial error: {', '.join(str(x) for x in e.args)}\n"
                "The full error is in the bot logs."
            )
            return

        try:
            ball = await Ball.create(
                country=name,
                regime=regime,
                economy=economy,
                health=health,
                attack=attack,
                rarity=rarity,
                enabled=enabled,
                tradeable=tradeable,
                emoji_id=emoji_id,
                wild_card="/" + str(spart_path),
                collection_card="/" + str(cart_path),
                credits=image_credits,
                capacity_name=capacity_name,
                capacity_description=capacity_description,
                catch_names=catch_names,
            )
        except BaseORMException as e:
            log.exception("Failed creating countryball with admin command", exc_info=True)
            await interaction.followup.send(
                f"Failed creating the {settings.collectible_name}.\n"
                f"Partial error: {', '.join(str(x) for x in e.args)}\n"
                "The full error is in the bot logs."
            )

            return

        files = [await cart.to_file()]
        if spart:
            files.append(await spart.to_file())
        await interaction.client.load_cache()
        admin_url = (
            f"[View online](<{settings.admin_url}/bd_models/ball/{ball.pk}/change/>)\n"
            if settings.admin_url
            else ""
        )
        await interaction.followup.send(
            f"Successfully created a {settings.collectible_name} with ID {ball.pk}! "
            f"The internal cache was reloaded.\n{admin_url}"
            f"{name=} regime={regime.name} economy={economy.name if economy else None} "
            f"{health=} {attack=} {rarity=} {enabled=} {tradeable=} emoji={emoji_id}",
            files=files,
        )

    @app_commands.command(name="bulk-update-rarities")
    @app_commands.checks.has_any_role(*settings.root_role_ids)
    async def bulk_update_rarities(
        self,
        interaction: discord.Interaction[BallsDexBot],
        rarity_command: str,
    ):
        await interaction.response.defer(thinking=True, ephemeral=True)

        rarities: dict[str, float] = {
            ballDetails.split(";")[0][0:48]: float(ballDetails.split(";")[1])
            for ballDetails in rarity_command.split("|")
        }

        balls = await Ball.all()
        bot_countryballs: dict[str, Ball] = {ball.country: ball for ball in balls}
        print(bot_countryballs)

        msg = ""
        for country, rarity in rarities.items():
            if country in bot_countryballs:
                msg += f"Set rarity of {country} to {rarity}\n"
                bot_countryballs[country].rarity = rarity
                await bot_countryballs[country].save(update_fields=("rarity"), force_update=True)
            else:
                msg += f"{settings.collectible_name} {country} not present in table\n"

        await interaction.followup.send(msg)