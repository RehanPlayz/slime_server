import discord, asyncio, os, sys
from discord.ext import commands, tasks
import server_functions
from server_functions import lprint, use_rcon, format_args, mc_command, mc_status

__version__ = "4.0.1"
__author__ = "D Thomas"
__email__ = "dt01@pm.me"
__license__ = "GPL 3"
__status__ = "Development"

# Exits script if no token.
if os.path.isfile(server_functions.bot_token_file):
    with open(server_functions.bot_token_file, 'r') as file:
        TOKEN = file.readline()
else:
    print("Missing Token File:", server_functions.bot_token_file)
    exit()

# Make sure this doesn't conflict with other bots.
bot = commands.Bot(command_prefix='?')


@bot.event
async def on_ready():
    await bot.wait_until_ready()

    if server_functions.channel_id:
        channel = bot.get_channel(server_functions.channel_id)
        await channel.send('**Bot PRIMED** :white_check_mark:')

    lprint(f"({__version__}) Bot PRIMED.")


# ========== Basics: Say, whisper, online players, server command pass through.
class Basics(commands.Cog):
    def __init__(self, bot): self.bot = bot

    @commands.command(aliases=['command', '/', 'c'])
    async def servercommand(self, ctx, *args):
        """
        Pass command directly to server.

        Args:
            command [str]: Server command, do not include the slash /.

        Usage:
            ?command broadcast Hello Everyone!
            ?/ list

        Note: You will get the latest 2 lines from server output, if you need more use ?log.
        """

        args = format_args(args)
        if not await mc_command(f"{args}", bot_ctx=ctx): return

        lprint(ctx, "Sent command: " + args)
        await ctx.invoke(self.bot.get_command('serverlog'), lines=3)

    @commands.command(aliases=['broadcast', 's'])
    async def say(self, ctx, *msg):
        """
        sends message to all online players.

        Args:
            msg [str]: Message to broadcast.

        Usage:
            ?s Hello World!
        """

        msg = format_args(msg, return_empty_str=True)

        if not msg: await ctx.send("Usage: `?s <message>`\nExample: `?s Hello everyone!`")
        else:
            if await mc_command('say ' + msg, bot_ctx=ctx):
                await ctx.send("Message circulated to all active players :loudspeaker:")
                lprint(ctx, f"Server said: {msg}")

    @commands.command(aliases=['whisper', 't', 'w'])
    async def tell(self, ctx, player='', *msg):
        """
        Message online player directly.

        Args:
            player <str>: Player name, casing does not matter.
            msg [str]: The message, no need for quotes.

        Usage:
            ?tell Steve Hello there!
            ?t Jesse Do you have diamonds?
        """

        msg = format_args(msg)
        if not player or not msg:
            await ctx.send("Usage: `?t <player> <message>`\nExample: `?t MysticFrogo sup hundo`")
            return False

        if not await mc_command(f"tell {player} {msg}", bot_ctx=ctx): return

        await ctx.send(f"Communiqué transmitted to: `{player}` :mailbox_with_mail:")
        lprint(ctx, f"Messaged {player} : {msg}")

    @commands.command(aliases=['pl', 'playerlist', 'listplayers', 'list'])
    async def players(self, ctx):
        """Show list of online players."""

        if not await mc_command("", bot_ctx=ctx): return

        response = await mc_command("list")

        if use_rcon is True: log_data = response
        else:
            await asyncio.sleep(2)
            log_data = server_functions.mc_log('players online')

        if not log_data:
            await ctx.send("**ERROR:** Trouble fetching player list.")
            return False

        log_data = log_data.split(':')
        text = log_data[-2]
        player_names = log_data[-1]
        # If there's no players active, player_names will still contain some anso escape characters.
        if len(player_names.strip()) < 5:
            await ctx.send(f"{text}. ¯\_(ツ)_/¯")
        else:
            # Outputs player names in special discord format. If using RCON, need to clip off 4 trailing unreadable characters.
            players_names = [f"`{i.strip()[:-4]}`\n" if use_rcon else f"`{i.strip()}`\n" for i in (log_data[-1]).split(',')]
            await ctx.send(text + ':\n' + ''.join(players_names))

        lprint(ctx, "Fetched player list.")

    @commands.command(aliases=['chat', 'playerchat', 'getchat', 'showchat'])
    async def chatlog(self, ctx, lines=15):
        """
        Shows chat log. Does not include whispers.

        Args:
            lines [int:15]: How many log lines to look through. This is not how many chat lines to show.
        """

        await ctx.send(f"***Loading {lines} Chat Log...*** :speech_balloon:")

        log_data = server_functions.mc_log(']: <', match_lines=lines, filter_mode=True, return_reversed=True)
        try: log_data = log_data.strip().split('\n')
        except:
            await ctx.send("**ERROR:** Problem fetching chat logs, there may be nothing to fetch.")
            return False

        for line in log_data:
            try:
                line = line.split(']')
                await ctx.send(f"`{str(line[0][1:] + ':' + line[2][1:])}`")
            except: pass

        await ctx.send("-----END-----")
        lprint(ctx, f"Fetched chat.")


# ========== Player: gamemode, kill, tp, etc
class Player(commands.Cog):
    def __init__(self, bot): self.bot = bot

    @commands.command(aliases=['pk', 'playerkill'])
    async def kill(self, ctx, player='', *reason):
        """
        Kill a player.

        Args:
            player <str>: Target player, casing does not matter.
            reason [str]: Reason for kill, do not put in quotes.

        Usage:
            ?kill Steve Because he needs to die!
            ?pk Steve
        """

        if not player:
            await ctx.send("Usage: `?pk <player> [reason]`\nExample: `?pk MysticFrogo 5 Because he killed my dog!`")
            return False

        reason = format_args(reason)
        if not await mc_command(f"say ---WARNING--- {player} will be EXTERMINATED! : {reason}", bot_ctx=ctx): return

        await mc_command(f'kill {player}')

        await ctx.send(f"`{player}` :gun: assassinated!")
        lprint(ctx, f"Killed: {player}")

    @commands.command(aliases=['delayedkill', 'delayedplayerkill', 'dpk', 'dk'])
    async def delaykill(self, ctx, player='', delay=5, *reason):
        """
        Kill player after time elapsed.

        Args:
            player <str>: Target player.
            delay [int:5]: Wait time in seconds.
            reason [str]: Reason for kill.

        Usage:
            ?delayedkill Steve 5 Do I need a reason?
            ?pk Steve 15
        """

        reason = format_args(reason)
        if not player:
            await ctx.send("Usage: `?dpk <player> <seconds> [reason]`\nExample: `?dpk MysticFrogo 5 Because he took my diamonds!`")
            return False

        if not await mc_command(f"say ---WARNING--- {player} will self-destruct in {delay}s : {reason}", bot_ctx=ctx): return

        await ctx.send(f"Killing {player} in {delay}s :bomb:")
        await asyncio.sleep(delay)
        await mc_command(f'kill {player}')

        await ctx.send(f"`{player}` soul has been freed.")
        lprint(ctx, f"Delay killed: {player}")

    @commands.command(aliases=['tp'])
    async def teleport(self, ctx, player='', target='', *reason):
        """
        Teleport player to another player.

        Args:
            player <str>: Player to teleport.
            target <str>: Destination, player to teleport to.
            reason [str]: Reason for teleport.

        Usage:
            ?teleport Steve Jesse I wanted to see him
            ?tp Jesse Steve
        """

        if not player or not target:
            await ctx.send("Usage: `?tp <player> <target_player> [reason]`\nExample: `?tp R3diculous MysticFrogo I need to see him now!`")
            return False

        reason = format_args(reason)
        if not await mc_command(f"say ---INFO--- Flinging {player} towards {target} in 5s : {reason}", bot_ctx=ctx): return

        await asyncio.sleep(5)
        await mc_command(f"tp {player} {target}")

        await ctx.send(f"**Teleported:** `{player}` to `{target}`")
        lprint(ctx, f"Teleported {player} to {target}")

    @commands.command(aliases=['gm'])
    async def gamemode(self, ctx, player='', mode='', *reason):
        """
        Change player's gamemode.

        Args:
            player <str>: Target player.
            mode <str>: Game mode survival|adventure|creative|spectator.
            reeason [str]: Optional reason for gamemode change.

        Usage:
            ?gamemode Steve creative In creative for test purposes.
            ?gm Jesse survival
        """

        if not player or mode not in ['survival', 'creative', 'spectator', 'adventure']:
            await ctx.send(f"Usage: `?gm <name> <mode> [reason]`\nExample: `?gm MysticFrogo creative`, `?gm R3diculous survival Back to being mortal!`")
            return False

        reason = format_args(reason)
        if not await mc_command(f"say {player} now in {mode}: {reason}", bot_ctx=ctx): return

        await mc_command(f"gamemode {mode} {player}")

        await ctx.send(f"`{player}` is now in `{mode}` indefinitely.")
        lprint(ctx, f"Set {player} to: {mode}")

    @commands.command(aliases=['gamemodetimed', 'timedgm', 'tgm', 'gmt'])
    async def timedgamemode(self, ctx, player='', mode='', duration=60, *reason):
        """
        Change player's gamemode for specified amount of seconds, then will change player back to survival.

        Args:
            player <str>: Target player.
            state [str:creative]: Game mode survival/adventure/creative/spectator. Default is creative for 30s.
            duration [int:30]: Duration in seconds.
            *reason [str]: Reason for change.

        Usage:
            ?timedgamemode Steve spectator Steve needs a time out!
            ?tgm Jesse adventure Jesse going on a adventure.
        """

        if not player or mode not in ['survival', 'creative', 'spectator', 'adventure']:
            await ctx.send("Usage: `?tgm <player> <mode> <seconds> [reason]`\nExample: `?tgm MysticFrogo spectator 120 Needs a time out`")
            return False

        reason = format_args(reason)
        if not await mc_command(f"say ---INFO--- {player} set to {mode} for {duration}s : {reason}", bot_ctx=ctx): return

        await mc_command(f"gamemode {mode} {player}")
        await ctx.send(f"`{player}` set to `{mode}` for `{duration}s` :hourglass:")
        lprint(ctx, f"Set gamemode: {player} for {duration}s")

        await asyncio.sleep(duration)
        await mc_command(f"say ---INFO--- Times up! {player} is now back to survival.")
        await mc_command(f"gamemode survival {player}")
        await ctx.send(f"`{player}` is back to survival.")


# ========== Permissions: Ban, Whitelist, Kick, OP.
class Permissions(commands.Cog):
    def __init__(self, bot): self.bot = bot

    @commands.command()
    async def kick(self, ctx, player='', *reason):
        """
        Kick player from server.

        Args:
            player <str>: Player to kick.
            reason [str]: Optional reason for kick.

        Usage:
            ?kick Steve Because he was trolling
            ?kick Jesse
        """

        if not player:
            await ctx.send("Usage: `?kick <player> [reason]`\nExample: `?kick R3diculous Trolling too much`")
            return False

        reason = format_args(reason)
        if not await mc_command(f'say ---WARNING--- {player} will be ejected from server in 5s : {reason}', bot_ctx=ctx): return

        await asyncio.sleep(5)
        await mc_command(f"kick {player}")

        await ctx.send(f"`{player}` is outta here :wave:")
        lprint(ctx, f"Kicked {player}")

    @commands.command(aliases=['exile', 'banish'])
    async def ban(self, ctx, player='', *reason):
        """
        Ban player from server.

        Args:
            player <str>: Player to ban.
            reason [str]: Reason for ban.

        Usage:
            ?ban Steve Player killing
            ?ban Jesse
        """

        if not player:
            await ctx.send("Usage: `?ban <player> [reason]`\nExample: `?ban MysticFrogo Bad troll`")
            return False

        reason = format_args(reason)
        if not await mc_command(f"say ---WARNING--- Banishing {player} in 5s : {reason}", bot_ctx=ctx):
            return

        await asyncio.sleep(5)

        await mc_command(f"ban {player} {reason}")

        await ctx.send(f"Dropkicked and exiled: `{player}` :no_entry_sign:")
        lprint(ctx, f"Banned {player} : {reason}")

    @commands.command(aliases=['unban'])
    async def pardon(self, ctx, player='', *reason):
        """
        Pardon (unban) player.

        Args:
            player <str>: Player to pardon.
            reason [str]: Reason for pardon.

        Usage:
            ?pardon Steve He has turn over a new leaf.
            ?unban Jesse
        """

        if not player:
            await ctx.send("Usage: `?pardon <player> [reason]`\nExample: `?ban R3diculous He has been forgiven`")
            return False

        reason = format_args(reason)
        if not await mc_command(f"say ---INFO--- {player} has been vindicated: {reason} :tada:", bot_ctx=ctx):return

        await mc_command(f"pardon {player}")

        await ctx.send(f"Cleansed `{player}` :flag_white:")
        lprint(ctx, f"Pardoned {player} : {reason}")

    @commands.command(aliases=['bl', 'bans'])
    async def banlist(self, ctx):
        """Show list of current bans."""

        if not await mc_command("", bot_ctx=ctx): return

        # Gets online players, formats output for Discord depending on using RCON or reading from server log.
        banned_players = ''
        response = await mc_command("banlist")

        if use_rcon is True:
            if 'There are no bans' in response:
                banned_players = 'No exiles!'
            else:
                data = response.split(':', 1)
                for line in data[1].split('.'):
                    line = server_functions.remove_ansi(line)
                    line = line.split(':')
                    reason = server_functions.remove_ansi(line[-1].strip())  # Sometimes you'll get ansi escape chars in your reason.
                    player = line[0].split(' ')[0].strip()
                    banner = line[0].split(' ')[-1].strip()
                    if len(player) < 2:
                        continue
                    banned_players += f"`{player}` banned by `{banner}` : `{reason}`\n"

                banned_players += data[0] + '.'  # Gets line that says 'There are x bans'.

        else:
            if log_data := server_functions.mc_log('banlist'):
                for line in filter(None, log_data.split('\n')):  # Filters out blank lines you sometimes get.
                    if 'There are no bans' in line:
                        banned_players = 'No exiled ones!'
                        break
                    elif 'There are' in line:
                        banned_players += line.split(':')[-2]
                        break

                    # Gets relevant data from current log line, and formats it for Discord output.
                    # Example line: Slime was banned by Server: No reason given
                    # Extracts Player name, who banned the player, and the reason.
                    ban_log_line = line.split(':')[-2:]
                    player = ban_log_line[0].split(' ')[1].strip()
                    banner = ban_log_line[0].split(' ')[-1].strip()
                    reason = ban_log_line[-1].strip()
                    banned_players += f"`{player}` banned by `{banner}` : `{reason}`\n"
            else: banned_players = '**ERROR:** Trouble fetching ban list.'

        await ctx.send(banned_players)
        lprint(ctx, f"Fetched banned list.")

    @commands.command(aliases=['wl', 'whitel', 'white', 'wlist'])
    async def whitelist(self, ctx, arg='', arg2=''):
        """
        Whitelist commands. Turn on/off, add/remove, etc.

        Args:
            arg [str:None]: User passed in arguments for whitelist command, see below for arguments and usage.
            player [str:None]: Specify player or to specify more options for other arguments, like enforce for example.

        Discord Args:
            list: Show whitelist, same as if no arguments.
            add/add <player>: Player add/remove to whitelist.
            on/off: Whitelist enable/disable
            reload: Reloads from whitelist.json file.
            enforce <status/on/off>: Changes 'enforce-whitelist' in server properties file.
                Kicks players that are not on the whitelist when using ?whitelist reload command.
                Server reboot required for enforce-whitelist to take effect.

        Usage:
            ?whitelist list
            ?whitelist add MysticFrogo
            ?whitelist enforce on
            ?whitelist on
            ?whitelist reload
        """

        # Checks if inputted any arguments.
        if not arg: await ctx.send(f"\nUsage Examples: `?whitelist add MysticFrogo`, `?whitelist on`, `?whitelist enforce on`, use `?help whitelist` or `?help2` for more.")

        # Checks if can send command to server.
        if not await mc_command("", bot_ctx=ctx): return

        # Enable/disable whitelisting.
        if arg.lower() in server_functions.enable_inputs:
            await mc_command('whitelist on')
            await ctx.send("**Whitelist ACTIVE**")
            lprint(ctx, f"Whitelist activated.")
        elif arg.lower() in server_functions.disable_inputs:
            await mc_command('whitelist off')
            await ctx.send("**Whitelist INACTIVE**")
            lprint(ctx, f"Whitelist deactivated.")

        # Add/remove user to whitelist (one at a time).
        elif arg == 'add' and arg2:
            await mc_command(f"whitelist {arg} {arg2}")
            await ctx.send(f"Added `{arg2}` to whitelist  :page_with_curl::pen_fountain:")
            lprint(ctx, f"Added to whitelist: {arg2}")
        elif arg == 'remove' and arg2:
            await mc_command(f"whitelist {arg} {arg2}")
            await ctx.send(f"Removed `{arg2}` from whitelist.")
            lprint(ctx, f"Removed from whitelist: {arg2}")

        # Reload server whitelisting feature.
        elif arg == 'reload':
            await mc_command('whitelist reload')
            await ctx.send("***Reloading Whitelist...***\nIf `enforce-whitelist` property is set to `true`, players not on whitelist will be kicked.")

        # Check/enable/disable whitelist enforce feature.
        elif arg == 'enforce' and (not arg2 or 'status' in arg2):  # Shows if passed in ?enforce-whitelist status.
            await ctx.invoke(self.bot.get_command('properties'), 'enforce-whitelist')
            await ctx.send(f"\nUsage Examples: `?whitelist enforce true`, `?whitelist enforce false`.")
            return False
        elif arg == 'enforce' and arg2 in ['true', 'on']:
            await ctx.invoke(self.bot.get_command('properties'), 'enforce-whitelist', 'true')
        elif arg == 'enforce' and arg2 in ['false', 'off']:
            await ctx.invoke(self.bot.get_command('properties'), 'enforce-whitelist', 'false')

        # List whitelisted.
        elif not arg or arg == 'list':
            if use_rcon:
                log_data = await mc_command('whitelist list')
                log_data = server_functions.remove_ansi(log_data).split(':')
            else:
                await mc_command('whitelist list')
                # Parses log entry lines, separating 'There are x whitelisted players:' from the list of players.
                log_data = server_functions.mc_log('whitelisted players:').split(':')[-2:]
                await asyncio.sleep(2)

            # Then, formats player names in Discord `player` markdown.
            players = [f"`{player.strip()}`" for player in log_data[1].split(', ')]
            await ctx.send(f"{log_data[0].strip()}\n{', '.join(players)}")
            lprint(ctx, f"Showing whitelist: {log_data[1]}")
            return False
        else: await ctx.send("**ERROR:** Something went wrong.")

    @commands.command(aliases=['ol', 'ops', 'listops'])
    async def oplist(self, ctx):
        """Show list of server operators."""

        op_players = [f"`{i['name']}`" for i in server_functions.read_json('ops.json')]
        if op_players:
            await ctx.send(f"**OP List** :scroll:")
            await ctx.send('\n'.join(op_players))
        else: await ctx.send("No players are OP.")

        lprint(ctx, f"Fetched server operators list.")

    @commands.command(aliases=['op', 'addop'])
    async def opadd(self, ctx, player='', *reason):
        """
        Add server operator (OP).

        Args:
            player <str>: Player to make server operator.
            reason [str]: Optional reason for new OP status.

        Usage:
            ?opadd Steve Testing purposes
            ?opadd Jesse
        """

        if not player:
            await ctx.send("Usage: `?op <player> [reason]`\nExample: `?op R3diculous Need to be a God!`")
            return False

        if not await mc_command("", bot_ctx=ctx): return

        reason = format_args(reason)

        if use_rcon:
            command_success = await mc_command(f"op {player}")
        else:
            _, status_checker = await mc_command(f"op {player}")
            command_success = server_functions.mc_log(player, stopgap_str=status_checker)

        if command_success:
            await mc_command(f"say ---INFO--- {player} is now OP : {reason}")
            await ctx.send(f"**New OP Player:** `{player}`")
        else: await ctx.send("**ERROR:** Problem setting OP status.")
        lprint(ctx, f"New server op: {player}")

    @commands.command(aliases=['oprm', 'rmop', 'deop', 'removeop'])
    async def opremove(self, ctx, player='', *reason):
        """
        Remove player OP status (deop).

        Args:
            player <str>: Target player.
            reason [str]: Reason for deop.

        Usage:
            ?opremove Steve abusing goodhood.
            ?opremove Jesse
        """

        if not player:
            await ctx.send("Usage: `?deop <player> [reason]`\nExample: `?op MysticFrogo Was abusing God powers!`")
            return False

        if not await mc_command("", bot_ctx=ctx): return

        reason = format_args(reason)
        if use_rcon:
            command_success = await mc_command(f"deop {player}")
        else:
            _, status_checker = await mc_command(f"deop {player}")
            command_success = server_functions.mc_log(player, stopgap_str=status_checker)

        if command_success:
            await mc_command(f"say ---INFO--- {player} no longer OP : {reason}")
            await ctx.send(f"**Player OP Removed:** `{player}`")
        else: await ctx.send("**ERROR:** Problem removing OP status.")
        lprint(ctx, f"Removed server OP: {player}")

    @commands.command(aliases=['optimed', 'top'])
    async def timedop(self, ctx, player='', time_limit=1, *reason):
        """
        Set player as OP for x seconds.

        Args:
            player <str>: Target player.
            time_limit [int:1]: Time limit in seconds.

        Usage:
            ?timedop Steve 30 Need to check something real quick.
            ?top jesse 60
        """

        if not player:
            await ctx.send("Usage: `?top <player> <minutes> [reason]`\nExample: `?top R3diculous Testing purposes`")
            return False

        await mc_command(f"say ---INFO--- {player} granted OP for {time_limit}m : {reason}")
        await ctx.send(f"***Temporary OP:*** `{player}` for {time_limit}m :hourglass:")
        lprint(f"Temporary OP: {player} for {time_limit}m")
        await ctx.invoke(self.bot.get_command('opadd'), player, *reason)
        await asyncio.sleep(time_limit * 60)
        await ctx.invoke(self.bot.get_command('opremove'), player, *reason)


# ========== World weather, time.
class World(commands.Cog):
    def __init__(self, bot): self.bot = bot

    @commands.command(aliases=['weather'])
    async def setweather(self, ctx, state='', duration=0):
        """
        Set weather.

        Args:
            state: <clear/rain/thunder>: Weather to change to.
            duration [int:0]: Duration in seconds.

        Usage:
            ?setweather rain
            ?weather thunder 60
        """

        if not state:
            await ctx.send("Usage: `?weather <state> [duration]`\nExample: `?weather rain`")
            return False

        if not await mc_command(f'weather {state} {duration}', bot_ctx=ctx): return

        if duration:
            await ctx.send(f"I see some `{state}` in the near future, {duration}s.")
        else: await ctx.send(f"Forecast entails `{state}`.")
        lprint(ctx, f"Weather set to: {state} for {duration}s")

    @commands.command(aliases=['time'])
    async def settime(self, ctx, set_time=''):
        """
        Set time.

        Args:
            set_time [int:None]: Set time either using day|night|noon|midnight or numerically.

        Usage:
            ?settime day
            ?time 12
        """

        if not await mc_command("", bot_ctx=ctx): return

        if set_time:
            await mc_command(f"time set {set_time}")
            await ctx.send("Time Updated  :clock:")
        else: await ctx.send("Need time input, like: `12`, `day`")
        lprint(ctx, f"Timed set: {set_time}")


# ========== Server: autosave loop, Start, Stop, Status, edit property, server log.
class Server(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        if server_functions.autosave_status is True:
            self.autosave_loop.start()

    @commands.command(aliases=['sa', 'save-all'])
    async def saveall(self, ctx):
        """Save current world using server save-all command."""

        if not await mc_command('save-all', bot_ctx=ctx): return

        await ctx.send("World Saved  :floppy_disk:")
        await ctx.send("**NOTE:** This is not the same as making a backup using `?backup`.")
        lprint(ctx, "Saved world.")

    @commands.command(aliases=['asave'])
    async def autosave(self, ctx, arg=''):
        """
        Sends save-all command at interval of x minutes.

        Args:
            arg: turn on/off autosave, or set interval in minutes.

        Usage:
            ?autosave
            ?autosave on
            ?autosave 60
        """

        if not arg: await ctx.send(f"Usage Examples: Update interval (minutes) `?autosave 60`, turn on `?autosave on`.")

        # Parses user input and sets invertal for autosave.
        try: arg = int(arg)
        except: pass
        else:
            server_functions.autosave_interval = arg
            server_functions.edit_file('autosave_interval', f" {arg}", server_functions.slime_vars_file)

        # Enables/disables autosave tasks.loop(). Also edits slime_vars.py file, so autosave state can be saved on bot restarts.
        arg = str(arg)
        if arg.lower() in server_functions.enable_inputs:
            server_functions.autosave_status = True
            self.autosave_loop.start()
            server_functions.edit_file('autosave_status', ' True', server_functions.slime_vars_file)
            lprint(ctx, f'Autosave on, interval: {server_functions.autosave_interval}m')
        elif arg.lower() in server_functions.disable_inputs:
            server_functions.autosave_status = False
            self.autosave_loop.cancel()
            server_functions.edit_file('autosave_status', ' False', server_functions.slime_vars_file)
            lprint(ctx, 'Autosave off')

        await ctx.send(f"Auto save function: {'**ENABLED** :repeat::floppy_disk:' if server_functions.autosave_status else '**DISABLED**'}")
        await ctx.send(f"Auto save interval: **{server_functions.autosave_interval}** minutes.")
        await ctx.send('**Note:** Auto save loop will pause when server is stopped with `?stop` command, and will unpause when server is started with `?start` command.')
        lprint(ctx, 'Fetched autosave information.')

    @tasks.loop(seconds=server_functions.autosave_interval * 60)
    async def autosave_loop(self):
        """Automatically sends save-all command to server at interval of x minutes."""

        if not await mc_status():
            self.autosave_loop.cancel()
            lprint("Paused autosave loop, server currently inactive.")
            return False

        await mc_command('save-all')
        lprint(f"Autosaved, interval: {server_functions.autosave_interval}m")

    @autosave_loop.before_loop
    async def before_autosaveall_loop(self):
        """Makes sure bot is ready before autosave_loop can be used."""

        await self.bot.wait_until_ready()

    @commands.command(aliases=['stat', 'stats', 'status', 'showserverstatus', 'sstatus', 'sss'])
    async def serverstatus(self, ctx):
        """Shows server active status, version, motd, and online players"""

        embed = discord.Embed(title='Server Status :gear:')
        embed.add_field(name='Current Server', value=f"Status: {'**ACTIVE** :green_circle:' if await mc_status() is True else '**INACTIVE** :red_circle:'}\nServer: {server_functions.server_selected[0]}\nDescription: {server_functions.server_selected[1]}\n", inline=False)
        embed.add_field(name='MOTD', value=f"{server_functions.get_mc_motd()}", inline=False)
        embed.add_field(name='Version', value=f"{server_functions.mc_version()}", inline=False)
        embed.add_field(name='Address', value=f"IP: `{server_functions.get_server_ip()}`\nURL: `{server_functions.server_url}` ({server_functions.check_server_url()})", inline=False)
        embed.add_field(name='Autosave', value=f"Status: {'**ENABLED**' if server_functions.autosave_status is True else '**DISABLED**'}\nInterval: **{server_functions.autosave_interval}** minutes", inline=False)
        embed.add_field(name='Location', value=f"`{server_functions.server_path}`", inline=False)
        embed.add_field(name='Start Command', value=f"`{server_functions.server_selected[2]}`", inline=False)  # Shows server name, and small description.
        await ctx.send(embed=embed)

        if await mc_status() is True:
            await ctx.invoke(self.bot.get_command('players'))

        lprint(ctx, "Fetched server status.")

    @commands.command(aliases=['log'])
    async def serverlog(self, ctx, lines=5):
        """
        Show server log.

        Args:
            lines [int:5]: How many most recent lines to show. Max of 20 lines!

        Usage:
            ?serverlog
            ?log 10
        """

        await ctx.send(f"***Loading {lines} Log Lines*** :tools:")
        log_data = server_functions.mc_log(lines=lines, log_mode=True, return_reversed=True)
        for line in log_data.split('\n'):
            await ctx.send(f"`{line}`")

        await ctx.send("-----END-----")
        lprint(ctx, f"Fetched {lines} lines from server log.")

    @commands.command(aliases=['start', 'boot', 'startserver', 'serverboot'])
    async def serverstart(self, ctx):
        """
        Start server.

        Note: Depending on your system, server may take 15 to 40+ seconds to fully boot.
        """

        if await mc_status() is True:
            await ctx.send("**Server ACTIVE**")
            return False

        await ctx.send("***Launching Server...*** :rocket:")
        server_functions.mc_start()
        await ctx.send("***Fetching Status in 20s...***")
        await asyncio.sleep(20)

        await ctx.invoke(self.bot.get_command('serverstatus'))
        lprint(ctx, "Starting server.")

        if server_functions.autosave_status is True:
            self.autosave_loop.start()
            await ctx.send("Auto save loop: **UNPAUSED** :repeat:")

    @commands.command(aliases=['stop', 'halt', 'serverhalt', 'shutdown'])
    async def serverstop(self, ctx, now=''):
        """
        Stop server, gives players 15s warning.

        Args:
            now [str]: Stops server immediately without giving online players 15s warning.

        Usage:
            ?stop
            ?stop now
        """

        if not await mc_status():
            await ctx.send("**Server INACTIVE** :red_circle:")
            return

        if not await mc_command("", bot_ctx=ctx): return

        if 'now' in now:
            await mc_command('save-all')
            await asyncio.sleep(3)
            await mc_command('stop')
        else:
            await mc_command('say ---WARNING--- Server will halt in 15s!')
            await ctx.send("***Halting in 15s...***")
            await asyncio.sleep(10)
            await mc_command('say ---WARNING--- 5s left!')
            await asyncio.sleep(5)
            await mc_command('save-all')
            await asyncio.sleep(3)
            await mc_command('stop')

        await asyncio.sleep(5)
        await ctx.send("**Server HALTED** :stop_sign:")
        server_functions.mc_subprocess = None
        lprint(ctx, "Stopping server.")

        if server_functions.autosave_status is True:
            self.autosave_loop.cancel()
            await ctx.send("Auto save loop: **PAUSED** :pause_button:")

    @commands.command(aliases=['reboot', 'restart', 'rebootserver', 'restartserver', 'serverreboot'])
    async def serverrestart(self, ctx, now=''):
        """
        Restarts server with 15s warning to players.

        Args:
            now [str]: Restarts server immediately without giving online players 15s warning.

        Usage:
            ?restart
            ?reboot now
        """

        await mc_command('say ---WARNING--- Server Rebooting...')
        lprint(ctx, "Restarting server.")
        await ctx.send("***Restarting...*** :arrows_counterclockwise:")
        await ctx.invoke(self.bot.get_command('serverstop'), now=now)

        await asyncio.sleep(3)
        await ctx.invoke(self.bot.get_command('serverstart'))

    @commands.command(aliases=['version', 'v', 'serverv'])
    async def serverversion(self, ctx):
        """Gets Minecraft server version."""

        response = server_functions.mc_version()
        await ctx.send(f"Current version: `{response}`")
        lprint("Fetched Minecraft server version: " + response)

    @commands.command(aliases=['lversion', 'lver', 'lv'])
    async def latestversion(self, ctx):
        """Gets latest Minecraft server version number from official website."""

        response = server_functions.get_latest_version()
        await ctx.send(f"Latest version: `{response}`")
        lprint("Fetched latest Minecraft server version: " + response)

    @commands.command(aliases=['property', 'p'])
    async def properties(self, ctx, target_property='', *value):
        """
        Check or change a server.properties property. May require restart.

        Note: Passing in 'all' for target property argument (with nothing for value argument) will show all the properties.

        Args:
            target_property [str:None]: Target property to change, must be exact in casing and spelling and some may include a dash -.
            value [str]: New value. For some properties you will need to input a lowercase true or false, and for others you may input a string (quotes not needed).

        Usage:
            ?property motd
            ?property spawn-protection 2
            ?property all
        """

        if not target_property:
            await ctx.send("Usage: `?p <property_name> [new_value]`\nExample: `?p motd`, `?p motd Hello World!`")
            return False

        if value:
            await ctx.send("Property Updated  :memo:")
            value = ' '.join(value)
        else: value = ''

        server_functions.edit_file(target_property, value)
        fetched_property = server_functions.edit_file(target_property)
        await asyncio.sleep(2)

        if fetched_property:
            await ctx.send(f"`{fetched_property[0].strip()}`")
            lprint(ctx, f"Server property: {fetched_property[0].strip()}")
        else:
            await ctx.send(f"**ERROR:** 404 Property not found.")
            lprint(f"Matching property not found.")

    @commands.command(aliases=['serveronlinemode', 'omode', 'om'])
    async def onlinemode(self, ctx, mode=''):
        """
        Check or enable/disable onlinemode property. Restart required.

        Args:
            mode <true/false>: Update onlinemode property in server.properties file. Must be in lowercase.

        Usage:
            ?onlinemode true
            ?omode false
        """

        if not mode:
            await ctx.send(f"online mode: `{server_functions.edit_file('online-mode')[1]}`")
            lprint(ctx, "Fetched online-mode state.")
        elif mode in ['true', 'false']:
            server_functions.edit_file('online-mode', mode)[0]
            property = server_functions.edit_file('online-mode')
            await ctx.send(f"Updated online mode: `{property[1]}`")
            await ctx.send("**Note:** Server restart required for change to take effect.")
            lprint(ctx, f"Updated online-mode: {property[1].strip()}")
        else: await ctx.send("Need a true or false argument (in lowercase).")

    @commands.command(aliases=['updatemotd', 'servermotd'])
    async def motd(self, ctx, *message):
        """
        Check or Update motd property. Restart required.

        Args:
            message [str]: New message for message of the day for server. No quotes needed.

        Usage:
            ?motd
            ?motd YAGA YEWY!
        """

        message = format_args(message, return_empty_str=True)

        if use_rcon:
            motd_property = server_functions.get_mc_motd()
        elif server_functions.server_files_access:
            server_functions.edit_file('motd', message)
            motd_property = server_functions.edit_file('motd')
        else: motd_property = '**ERROR:** Fetching server motd failed.'

        if message:
            await ctx.send(f"Updated MOTD: `{motd_property[0].strip()}`")
            lprint("Updated MOTD: " + motd_property[1].strip())
        else:
            await ctx.send(f"Current MOTD: `{motd_property[1]}`")
            lprint("Fetched MOTD: " + motd_property[1].strip())

    @commands.command(aliases=['serverrcon'])
    async def rcon(self, ctx, state=''):
        """
        Check RCON status, enable/disable enable-rcon property. Restart required.

        Args:
            state <true/false>: Set enable-rcon property in server.properties file, true or false must be in lowercase.

        Usage:
            ?rcon
            ?rcon true
            ?rcon false

        """

        if state in ['true', 'false', '']:
            response = server_functions.edit_file('enable-rcon', state)
            await ctx.send(f"`{response[0]}`")
        else: await ctx.send("Need a true or false argument (in lowercase).")

    @commands.command(aliases=['updateserver', 'su'])
    async def serverupdate(self, ctx, now=''):
        """
        Updates server.jar file by downloading latest from official Minecraft website.

        Note: This will not make a backup beforehand, suggest doing so with ?serverbackup command.

        Args:
            now [str]: Stops server immediately without giving online players 15s warning.
        """

        if 'vanilla' not in server_functions.server_selected:
            await ctx.send(f"**ERROR:** This command only works with vanilla servers. You have `{server_functions.server_selected[0]}` selected.")
            return False

        lprint(ctx, "Updating server.jar...")
        await ctx.send("***Updating...*** :arrows_counterclockwise:")

        if await mc_status() is True:
            await ctx.invoke(self.bot.get_command('serverstop'), now=now)
        await asyncio.sleep(5)

        await ctx.send("***Downloading latest server.jar***")
        server = server_functions.download_new_server()

        if server is True:
            await ctx.send(f"Downloaded latest version: `{server}`")
            await asyncio.sleep(3)
            await ctx.invoke(self.bot.get_command('serverstart'))
        else: await ctx.send("**ERROR:** Updating server failed. Suggest restoring from a backup if updating corrupted any files.")

        lprint(ctx, "Server Updated.")


# ========== World backup/restore functions.
class World_Backups(commands.Cog):
    def __init__(self, bot): self.bot = bot

    @commands.command(aliases=['worldbackups', 'backuplist', 'wbl'])
    async def worldbackupslist(self, ctx, amount=10):
        """
        Show world backups.

        Args:
            amount [int:5]: Number of most recent backups to show.

        Usage:
            ?saves
            ?saves 10
        """

        embed = discord.Embed(title='World Backups :tools:')
        worlds = server_functions.fetch_worlds()
        if worlds is False:
            await ctx.send("No world backups found.")
            return False

        for backup in worlds[-amount:]:
            embed.add_field(name=backup[0], value=f"`{backup[1]}`", inline=False)
        await ctx.send(embed=embed)
        await ctx.send("Use `?worldrestore <index>` to restore world save.")

        await ctx.send("**WARNING:** Restore will overwrite current world. Make a backup using `?backup <codename>`.")
        lprint(ctx, f"Fetched {amount} most recent world saves.")

    @commands.command(aliases=['worldbackup', 'backup', 'backupworld', 'wbn'])
    async def worldbackupnew(self, ctx, *name):
        """
        new backup of current world.

        Args:
            name [str]: Keywords or codename for new save. No quotes needed.

        Usage:
            ?backup everything not on fire
            ?backup Jan checkpoint
        """

        if not name:
            await ctx.send("Usage: `?wbn <name>`\nExample: `?wbn Before the reckoning`")
            return False
        name = format_args(name)

        if await mc_command("", bot_ctx=ctx):
            await mc_command(f"say ---INFO--- Standby, world is currently being archived. Codename: {name}")
            await mc_command(f"save-all")
            await asyncio.sleep(3)

        await ctx.send("***Creating World Backup...*** :new::floppy_disk:")
        new_backup = server_functions.backup_world(name)
        if new_backup:
            await ctx.send(f"**New World Backup:** `{new_backup}`")
        else: await ctx.send("**ERROR:** Problem saving the world! || it's doomed!||")

        await ctx.invoke(self.bot.get_command('worldbackupslist'))
        lprint(ctx, "New world backup: " + new_backup)

    @commands.command(aliases=['worldrestore', 'wbr', 'wr'])
    async def worldbackuprestore(self, ctx, index='', now=''):
        """
        Restore a world backup.

        Note: This will not make a backup beforehand, suggest doing so with ?backup command.

        Args:
            index <int:None>: Get index with ?saves command.
            now [str]: Skip 15s wait to stop server. E.g. ?restore 0 now

        Usage:
            ?restore 3
        """

        try: index = int(index)
        except:
            await ctx.send("Usage: `?wbr <index> [now]`\nExample: `?wbr 0 now`")
            return False

        fetched_restore = server_functions.get_world_from_index(index)
        lprint(ctx, "World restoring to: " + fetched_restore)
        await ctx.send("***Restoring World...*** :floppy_disk::leftwards_arrow_with_hook:")
        if not await mc_command("", bot_ctx=ctx):
            await mc_command(f"say ---WARNING--- Initiating jump to save point in 5s! : {fetched_restore}")
            await asyncio.sleep(5)
            await ctx.invoke(self.bot.get_command('serverstop'), now=now)

        await ctx.send(f"***Restored World:*** `{fetched_restore}`")
        server_functions.restore_world(fetched_restore)  # Gives computer time to move around world files.
        await asyncio.sleep(3)

    @commands.command(aliases=['worlddelete', 'backupdelete', 'wbd'])
    async def worldbackupdelete(self, ctx, index=''):
        """
        Delete a world backup.

        Args:
            index <int>: Get index with ?saves command.

        Usage:
            ?delete 0
        """

        try: index = int(index)
        except:
            await ctx.send("Usage: `?wbd <index>`\nExample: `?wbd 1`")
            return False

        to_delete = server_functions.get_world_from_index(index)
        await ctx.send("***Deleting World Backup...*** :floppy_disk::wastebasket:")
        server_functions.delete_world(to_delete)

        await ctx.send(f"**World Backup Deleted:** `{to_delete}`")
        lprint(ctx, "Deleted world backup: " + to_delete)

    @commands.command(aliases=['rebirth', 'hades', 'resetworld'])
    async def worldreset(self, ctx, now=''):
        """
        Deletes world save (does not touch other server files).

        Note: This will not make a backup beforehand, suggest doing so with ?backup command.
        """

        await mc_command("say ---WARNING--- Project Rebirth will commence in T-5s!", bot_ctx=ctx)
        await ctx.send(":fire:**Project Rebirth Commencing**:fire:")
        await ctx.send("**NOTE:** Next launch may take longer.")

        if await mc_status() is True:
            await ctx.invoke(self.bot.get_command('serverstop'), now=now)

        await ctx.send("**Finished.**")
        await ctx.send("You can now start the server with `?start`.")

        server_functions.restore_world(reset=True)
        await asyncio.sleep(3)

        lprint(ctx, "World Reset.")


# ========== Server backup/restore functions.
class Server_Backups(commands.Cog):
    def __init__(self, bot): self.bot = bot

    @commands.command(aliases=['sselect', 'servers', 'serverslist', 'ss', 'sl'])
    async def serverselect(self, ctx, name=''):
        """
        Select server to use all other commands on. Each server has their own world_backups and server_restore folders.

        Args:
            name: name of server to select, use ?selectserver list or without arguments to show list.

        Usage:
            ?selectserver list
            ?selectserver papermc
        """

        if not name or 'list' in name:
            embed = discord.Embed(title='Server List :desktop:')
            for server in server_functions.server_list.values():
                # Shows server name, description, location, and start command.
                embed.add_field(name=server[0], value=f"Description: {server[1]}\nLocation: `{server_functions.mc_path}/{server_functions.server_selected[0]}`\nStart Command: `{server[2]}`", inline=False)
            await ctx.send(embed=embed)
            await ctx.send(f"**Current Server:** `{server_functions.server_selected[0]}`")
        elif name in server_functions.server_list.keys():
            server_functions.server_selected = server_functions.server_list[name]
            server_functions.server_path = f"{server_functions.mc_path}/{server_functions.server_selected[0]}"
            server_functions.edit_file('server_selected', f" server_list['{name}']", server_functions.slime_vars_file)
            await ctx.invoke(self.bot.get_command('restartbot'))
        else: await ctx.send("**ERROR:** Server not found.\nUse `?serverselect` or `?ss` to show list of available servers.")

    @commands.command(aliases=['serverbackups', 'sbl'])
    async def serverbackupslist(self, ctx, amount=10):
        """
        List server backups.

        Args:
            amount [int:5]: How many most recent backups to show.

        Usage:
            ?serversaves
            ?serversaves 10
        """

        embed = discord.Embed(title='Server Backups :tools:')
        servers = server_functions.fetch_servers()

        if servers is False:
            await ctx.send("No server backups found.")
            return False

        for save in servers[-amount:]:
            embed.add_field(name=save[0], value=f"`{save[1]}`", inline=False)
        await ctx.send(embed=embed)

        await ctx.send("Use `?serverrestore <index>` to restore server.")
        await ctx.send("**WARNING:** Restore will overwrite current server. Create backup using `?serverbackup <codename>`.")
        lprint(ctx, f"Fetched {amount} world backups.")

    @commands.command(aliases=['serverbackup', 'sbn'])
    async def serverbackupnew(self, ctx, *name):
        """
        New backup of server files (not just world save).

        Args:
            name [str]: Keyword or codename for save.

        Usage:
            ?serverbackup Dec checkpoint
        """

        if not name:
            await ctx.send("Usage: `?sbn <name>`\nExample: `?wbn Everything just dandy`")
            return False

        name = format_args(name)
        await ctx.send(f"***Creating Server Backup...*** :new::floppy_disk:")
        if await mc_command("", bot_ctx=ctx): await mc_command(f"save-all")

        await asyncio.sleep(5)
        new_backup = server_functions.backup_server(name)
        if new_backup:
            await ctx.send(f"**New Server Backup:** `{new_backup}`")
        else: await ctx.send("**ERROR:** Server backup failed! :interrobang:")

        await ctx.invoke(self.bot.get_command('serverbackupslist'))
        lprint(ctx, "New server backup: " + new_backup)

    @commands.command(aliases=['serverrestore', 'sbr'])
    async def serverbackuprestore(self, ctx, index='', now=''):
        """
        Restore server backup.

        Args:
            index <int:None>: Get index number from ?serversaves command.
            now [str:None]: Stop server without 15s wait.

        Usage:
            ?serverrestore 0
        """

        try: index = int(index)
        except:
            await ctx.send("Usage: `?sbr <index> [now]`\nExample: `?sbr 2 now`")
            return False

        fetched_restore = server_functions.get_server_from_index(index)
        lprint(ctx, "Server restoring to: " + fetched_restore)
        await ctx.send(f"***Restoring Server...*** :floppy_disk::leftwards_arrow_with_hook:")

        if await mc_status() is True:
            await mc_command(f"say ---WARNING--- Initiating jump to save point in 5s! : {fetched_restore}")
            await asyncio.sleep(5)
            await ctx.invoke(self.bot.get_command('serverstop'), now=now)

        if server_functions.restore_server(fetched_restore):
            await ctx.send(f"**Server Restored:** `{fetched_restore}`")
        else: await ctx.send("**ERROR:** Could not restore server!")

    @commands.command(aliases=['serverdelete', 'sbd'])
    async def serverbackupdelete(self, ctx, index=''):
        """
        Delete a server backup.

        Args:
            index <int>: Index of server save, get with ?serversaves command.

        Usage:
            ?serverdelete 0
            ?serverrm 5
        """

        try: index = int(index)
        except:
            await ctx.send("Usage: `?sbd <index>`\nExample: `?sbd 3`")
            return False

        to_delete = server_functions.get_server_from_index(index)
        await ctx.send("***Deleting Server Backup...*** :floppy_disk::wastebasket:")
        server_functions.delete_server(to_delete)

        await ctx.send(f"**Server Backup Deleted:** `{to_delete}`")
        lprint(ctx, "Deleted server backup: " + to_delete)


# ========== Extra: restart bot, botlog, get ip, help2.
class Bot_Functions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=['rbot', 'rebootbot', 'botrestart', 'botreboot'])
    async def restartbot(self, ctx, now=''):
        """Restart this bot."""

        await ctx.send("***Rebooting Bot...*** :arrows_counterclockwise: ")
        lprint(ctx, "Restarting bot.")

        if server_functions.use_subprocess is True:
            await ctx.invoke(self.bot.get_command("serverstop"), now=now)

        os.chdir(server_functions.bot_files_path)
        os.execl(sys.executable, sys.executable, *sys.argv)

    @commands.command(aliases=['blog'])
    async def botlog(self, ctx, lines=5):
        """
        Show bot log.

        Args:
            lines [int:5]: Number of most recent lines to show.

        Usage:
            ?botlog
            ?blog 15
        """

        log_data = server_functions.mc_log(file_path=server_functions.bot_log_file, lines=lines, log_mode=True, return_reversed=True)

        # Shows server log line by line.
        for line in log_data.split('\n'):
            await ctx.send(f"`{line}`")

        await ctx.send("-----END-----")
        lprint(ctx, f"Fetched {lines} lines from bot log.")

    @commands.command(aliases=['updatebot', 'bupdate', 'bu'])
    async def botupdate(self, ctx):
        """Gets update from GitHub."""

        await ctx.send("***Comming Soon...***")

    @commands.command()
    async def help2(self, ctx):
        """Shows help page with embed format, using reactions to navigate pages."""

        lprint(ctx, "Fetched help page.")
        current_command, embed_page, contents = 0, 1, []
        pages, current_page, page_limit = 3, 1, 15

        def new_embed(page):
            return discord.Embed(title=f'Help Page {page}/{pages} :question:')

        embed = new_embed(embed_page)
        for command in server_functions.read_csv('command_info.csv'):
            if not command: continue

            embed.add_field(name=command[0], value=f"{command[1]}\n{', '.join(command[2:])}", inline=False)
            current_command += 1
            if not current_command % page_limit:
                embed_page += 1
                contents.append(embed)
                embed = new_embed(embed_page)
        contents.append(embed)

        # getting the message object for editing and reacting
        message = await ctx.send(embed=contents[0])
        await message.add_reaction("◀️")
        await message.add_reaction("▶️")

        # This makes sure nobody except the command sender can interact with the "menu"
        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in ["◀️", "▶️"]

        while True:
            try:
                # waiting for a reaction to be added - times out after x seconds, 60 in this
                reaction, user = await bot.wait_for("reaction_add", timeout=60, check=check)
                if str(reaction.emoji) == "▶️" and current_page != pages:
                    current_page += 1
                    await message.edit(embed=contents[current_page - 1])
                    await message.remove_reaction(reaction, user)
                elif str(reaction.emoji) == "◀️" and current_page > 1:
                    current_page -= 1
                    await message.edit(embed=contents[current_page - 1])
                    await message.remove_reaction(reaction, user)

                # removes reactions if the user tries to go forward on the last page or backwards on the first page
                else: await message.remove_reaction(reaction, user)

            # end loop if user doesn't react after x seconds
            except asyncio.TimeoutError:
                await message.delete()
                break

    @commands.command(aliases=['getip', 'address', 'getaddress', 'serverip', 'serveraddress'])
    async def ip(self, ctx):
        """
        Shows IP address for server.

        Usage:
            ?ip
            ?address
        """

        await ctx.send(f"Server IP: `{server_functions.get_server_ip()}`")
        await ctx.send(f"Alternative Address: `{server_functions.server_url}` ({server_functions.check_server_url()})")
        lprint(ctx, 'Fetched server address.')

    @commands.command(aliases=['websites', 'showlinks', 'usefullinks', 'sites', 'urls'])
    async def links(self, ctx):
        """
        Shows list of useful websites.

        Usage:
            ?links
            ?sites
        """

        embed = discord.Embed(title='Useful Websites :computer:')

        # Creates embed of links from useful_websites dictionary from slime_vars.py.
        for name, url in server_functions.useful_websites.items():
            embed.add_field(name=name, value=url, inline=False)

        await ctx.send(embed=embed)


# Adds functions to bot.
for cog in [Basics, Player, Permissions, World, Server, World_Backups, Server_Backups, Bot_Functions]:
    bot.add_cog(cog(bot))

# Disable certain commands depending on if using Tmux, RCON, or subprocess.
if_no_tmux = ['serverstart', 'serverrestart']
if_using_rcon = ['oplist', 'properties', 'rcon', 'onelinemode', 'serverstart', 'serverrestart', 'worldbackupslist', 'worldbackupnew', 'worldbackuprestore', 'worldbackupdelete', 'worldreset',
                 'serverbackupslist', 'serverbackupnew', 'serverbackupdelete', 'serverbackuprestore', 'serverreset', 'serverupdate', 'serverlog']

if server_functions.server_files_access is False and server_functions.use_rcon is True:
    for command in if_no_tmux: bot.remove_command(command)

if server_functions.use_tmux is False:
    for command in if_no_tmux: bot.remove_command(command)

if __name__ == '__main__':
    bot.run(TOKEN)
