from collections import Counter
from datetime import datetime as dt
from datetime import timedelta, timezone

import discord.errors

from pombot.storage import Storage
from pombot.lib.types import ActionType, Team
from pombot.config import Pomwars, Reactions, TIMEZONES
from pombot.lib.messages import send_embed_message

class Scoreboard:
    """A representation of the scoreboard in join channels."""
    def __init__(self, bot, scoreboard_channels) -> None:
        self.bot = bot
        self.scoreboard_channels = scoreboard_channels
        self.knight_population, self.viking_population = Storage.get_team_populations()
        self.knight_actions = Storage.get_actions(
            team=Team.KNIGHTS,
        )
        self.viking_actions = Storage.get_actions(
            team=Team.VIKINGS,
        )

    def update_vars(self) -> None:
        """Updates variables"""
        self.knight_population, self.viking_population = Storage.get_team_populations()
        self.knight_actions = Storage.get_actions(
            team=Team.KNIGHTS,
        )
        self.viking_actions = Storage.get_actions(
            team=Team.VIKINGS,
        )

    def population(self, team) -> int:
        """
        Returns a string of the population of a team
        """
        self.update_vars()

        team = self.viking_population if team == Team.VIKINGS else self.knight_population

        return team

    def dmg(self, team) -> int:
        """
        Returns a string of the total damage done by a team
        """
        self.update_vars()

        damage = 0
        team = self.viking_actions if team == Team.VIKINGS else self.knight_actions

        for action in team:
            if action.raw_damage:
                damage += int(action.raw_damage/100)

        return damage

    def attack_count(self, team) -> int:
        """Return the total attacks (whether successful or not) of a team."""
        self.update_vars()

        team_actions = self.viking_actions if team == Team.VIKINGS else self.knight_actions
        attack_types = [ActionType.NORMAL_ATTACK, ActionType.HEAVY_ATTACK]
        count = len([a for a in team_actions if a.type in attack_types and a.was_successful])

        return count

    def favorite_attack(self, team) -> str:
        """
        Returns a string of the most common attack done by a team
        """

        self.update_vars()

        team_actions = self.viking_actions if team == Team.VIKINGS else self.knight_actions

        type_counts = Counter([action.type for action in team_actions])

        if type_counts['normal_attack'] >= type_counts['heavy_attack']:
            fav = 'Normal'
        else:
            fav = 'Heavy'

        return fav

    async def update_msg(self):
        """
        Updates (or creates) the live scoreboards of all the guilds the bot is in.
        - Differentiates teams
        - Displays current winner
        - Shows amount of damage done by each team
        - Shows number of attacks done by each team
        - Shows populations
        - Shows favorite attacks
        """

        self.update_vars()

        full_channels, restricted_channels = [], []

        knight_dmg = self.dmg(Team.KNIGHTS)
        viking_dmg = self.dmg(Team.VIKINGS)

        knight_attacks = self.attack_count(Team.KNIGHTS)
        viking_attacks = self.attack_count(Team.VIKINGS)

        winner = ""
        if knight_dmg != viking_dmg: # To check for ties
            if self.dmg(Team.KNIGHTS) < self.dmg(Team.VIKINGS):
                winner = Team.VIKINGS
            else:
                winner = Team.KNIGHTS

        for channel in self.scoreboard_channels:
            history = channel.history(limit=1, oldest_first=True)

            lines = [
                "{dmg} damage dealt {emt}",
                "** **",
                "`Attacks:` {attacks} attacks",
                "`Favorite Attack:` {fav}",
                "`Member Count:` {participants} participants",
            ]

            knight_values = {
                "dmg": knight_dmg,
                "emt": f"{Pomwars.Emotes.ATTACK}",
                "fav": self.favorite_attack(Team.KNIGHTS),
                "attacks": knight_attacks,
                "participants": self.population(Team.KNIGHTS),
            }

            viking_values = {
                "dmg": viking_dmg,
                "emt": f"{Pomwars.Emotes.ATTACK}",
                "fav": self.favorite_attack(Team.VIKINGS),
                "attacks": viking_attacks,
                "participants": self.population(Team.VIKINGS),
            }

            team_fields_inline = True
            msg_fields = [
                [
                    "{emt} Knights{win}".format(
                        emt=Pomwars.Emotes.KNIGHT,
                        win=f" {Pomwars.Emotes.WINNER}" if winner==Team.KNIGHTS else '',
                    ),
                    "\n".join(lines).format(**knight_values),
                    team_fields_inline
                ],
                [
                    "{emt} Vikings{win}".format(
                        emt=Pomwars.Emotes.VIKING,
                        win=f" {Pomwars.Emotes.WINNER}" if winner==Team.VIKINGS else '',
                    ),
                    "\n".join(lines).format(**viking_values),
                    team_fields_inline
                ]
            ]

            msg_title = "Pom War Season 3 Warboard"
            msg_footer = f"React with {Reactions.WAR_JOIN_REACTION} to join a team!\n"
            msg_footer += "Once you've joined, react with a number for your timezone.\n"
            for i, emoji in enumerate(TIMEZONES):
                zone = timezone(timedelta(hours=TIMEZONES[emoji]))
                msg_footer += f"{emoji} {zone}\t"

            msg_reactions = [
                Reactions.WAR_JOIN_REACTION,
                Reactions.UTC_MINUS_10_TO_9,
                Reactions.UTC_MINUS_8_TO_7,
                Reactions.UTC_MINUS_6_TO_5,
                Reactions.UTC_MINUS_4_TO_3,
                Reactions.UTC_MINUS_2_TO_1,
                Reactions.UTC_PLUS_1_TO_2,
                Reactions.UTC_PLUS_3_TO_4,
                Reactions.UTC_PLUS_5_TO_6,
                Reactions.UTC_PLUS_7_TO_8,
                Reactions.UTC_PLUS_9_TO_10
            ]

            channel_messages = await history.flatten()
            scoreboard_msg = None
            if channel_messages:
                scoreboard_msg = channel_messages[0]
                if scoreboard_msg.author != self.bot.user:
                    full_channels.append(channel)
                    continue

            try:
                new_msg = await send_embed_message(
                    None,
                    title=msg_title,
                    description=None,
                    fields=msg_fields,
                    footer=msg_footer,
                    colour=Pomwars.ACTION_COLOUR,
                    _func=scoreboard_msg.edit if scoreboard_msg else channel.send
                )

                if new_msg:
                    scoreboard_msg = new_msg

                current_reactions = scoreboard_msg.reactions
                for reaction in msg_reactions:
                    if reaction not in current_reactions:
                        await scoreboard_msg.add_reaction(reaction)
            except discord.errors.Forbidden:
                restricted_channels.append(channel)

        return [full_channels, restricted_channels]
