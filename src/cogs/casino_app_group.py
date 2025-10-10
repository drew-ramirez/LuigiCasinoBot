###########################################################
# File: casino_app_group.py
#
# Description: Shared Discord app command group
###########################################################

from discord import app_commands

casino_group = app_commands.Group(
    name="casino",
    description="Luigi's Casino commands",
)


def ensure_group_registered(tree: app_commands.CommandTree) -> None:
    """Register the casino group with the command tree if not already present."""
    if tree.get_command("casino") is None:
        tree.add_command(casino_group)
