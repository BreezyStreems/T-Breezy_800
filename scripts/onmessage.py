import time
import requests
import sqlite3
import random
import discord
import datetime
import re
import os

from functools import partial
from google import genai

class onmessage:
    def __init__(self, bot, gemini_api_key):
        user_command_timers = {}
        waiting_for_input = {}
        muted_users = {}
        self.accepting_commands = False
        self.gemini_api_key = gemini_api_key
        home_dir = os.path.dirname(os.path.dirname(__file__))

        if gemini_api_key: client = genai.Client(api_key=gemini_api_key)

        anime_roll_url = """
        query ($id: Int) {
            Character(id: $id) {
                id
                name {
                    full
                }
                image {
                    large
                    medium
                }
                siteUrl
            }
        }
        """
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        anime_roll_db_connection = sqlite3.connect(home_dir + '/anime_roll.db')
        ardb_cursor = anime_roll_db_connection.cursor()
        ardb_cursor.execute("""
                CREATE TABLE IF NOT EXISTS users(
                    id INTEGER PRIMARY KEY,
                    rolls INTEGER DEFAULT 0
                )
                """)
        anime_roll_db_connection.commit()
        ardb_cursor.execute("""
                CREATE TABLE IF NOT EXISTS characters(
                    id INTEGER,
                    character TEXT,
                    power INTEGER DEFAULT 0
                )
                """)
        anime_roll_db_connection.commit()

        async def B_on_message(task_queue, ctx, trusted_users):
            if ctx.author.bot and ctx.author.id != bot.user.id or not self.accepting_commands: return

            if ctx.author.id in user_command_timers:
                if time.time() - user_command_timers[ctx.author.id] < 5:
                    return
                else:
                    user_command_timers[ctx.author.id] = 0

            user_command_timers[ctx.author.id] = time.time()

            if ctx.author.id in waiting_for_input:
                if ctx.content.startswith('B '):
                    await accept_user_input(ctx, ctx.content[2:])
                elif ctx.content.startswith('B| '):
                    await ctx.channel.send('terminate last process before starting a new command')
                    return

            if ctx.content.startswith('B| '):
                # General Commands
                if ctx.content.endswith('animeroll'):
                    await task_queue.put(partial(animeroll, ctx))
                elif ctx.content.endswith('status'):
                    await task_queue.put(partial(status, ctx))
                elif ctx.content.startswith('B| animeinv'):
                    command_args = ctx.content.split('|')
                    for i in range(len(command_args)): command_args[i] = command_args[i].strip()
                    print(command_args)
                    if len(command_args) > 2:
                        await task_queue.put(partial(animeinv, ctx, args=command_args))
                    else:
                        await task_queue.put(partial(animeinv, ctx))
                elif ctx.content.startswith('B| appraisechar '):
                    await task_queue.put(partial(appraisechar, ctx, ctx.content[16:]))

                # BREEZY COMMANDS
                if ctx.author.id in trusted_users:
                    if ctx.content[:7] == 'B| info':
                        if len(ctx.mentions) == 1:
                            user = ctx.mentions[0]
                            await info(ctx, user)
            elif ctx.content.startswith('bb '):
                # Moderation Commands

                if ctx.content.startswith('bb mute'):
                    command_args = ctx.content.split(' ')
                    for i in range(len(command_args)): command_args[i] = command_args[i].strip()
                    if ctx.mentions and len(command_args) == 4:
                        command_args[2] = command_args[2]
                        await mute(command_args, ctx)
                    else:
                        print('skynet: ERROR - invalid argument amount - CRITICAL')
                        await ctx.channel.send('skynet: ERROR - invalid argument amount - CRITICAL')
                if ctx.content.startswith('bb unmute'):
                    try:
                        await unmute(ctx)
                    except Exception as e:
                        print(e)

        async def status(ctx):
            anime_roll_status = True
            response = requests.get("https://kitsu.io/api/edge/characters",
                                    params={"page[limit]": 20, "page[offset]": 21},
                                    headers={"Accept": "application/vnd.api+json"}, timeout=10)
            if not response.status_code == 200:
                anime_roll_status = False

            await ctx.channel.send('skynet: ONLINE')
            if anime_roll_status:
                await ctx.channel.send('skynet - animeroll: ONLINE')
            else:
                await ctx.channel.send('skynet - animeroll: OFFLINE')

        async def animeroll(ctx):
            async def roll_anime(message):
                offset = random.randint(0, 10000)
                response = requests.get(
                    "https://kitsu.io/api/edge/characters",
                    params={
                        "page[limit]": 20,
                        "page[offset]": offset
                    },
                    headers={
                        "Accept": "application/vnd.api+json"
                    },
                    timeout=5
                )

                if response.status_code != 200:
                    print(f'skynet: ERROR - roll failed | status code {response.status_code} - WARNING')
                    await message.edit(
                        content=f'skynet: ERROR - no character found | status code {response.status_code} - '
                                f'WARNING')
                    return False, None

                result = response.json()['data']
                result = random.choice(result)

                if not result:
                    print('skynet: ERROR - no character found - WARNING')
                    await message.edit(content='skynet: ERROR - no character found - WARNING')
                    return False, None

                character = result

                embed = discord.Embed(
                    title=character["attributes"]["name"],
                    description=f'[LINK]({character["links"]["self"]})',
                    color=discord.Color.blue()
                )
                embed.set_image(url=character["attributes"]["image"]["original"])
                await message.edit(content='ROLLED!', embed=embed)
                return True, character

            ardb_cursor.execute("""
                SELECT * FROM characters WHERE id = ?
            """, (ctx.author.id,))
            animeinv_status = ardb_cursor.fetchall()

            if len(animeinv_status) == 50:
                await ctx.channel.send('skynet: WARNING - inventory full!! - NEGLIGIBLE')
                return

            message = await ctx.channel.send('ROLLING...')
            status, character = await roll_anime(message)
            if not status:
                print('skynet: ERROR - roll failed - WARNING')
                return

            ardb_cursor.execute("""
                SELECT * FROM characters WHERE id = ? AND character = ?
            """, (ctx.author.id, character['attributes']['name']))
            characters = ardb_cursor.fetchone()
            if characters:
                await message.edit(content=f'CHARACTER ALREADY EXISTS - do you wish to overwrite a character with '
                                           f'{characters[2]} power? [B y/ B n]')
                waiting_for_input[ctx.author.id] = ['replace char', character]
            else:
                ardb_cursor.execute("""
                INSERT OR IGNORE INTO users (id)
                VALUES (?)
                """, (ctx.author.id,))

                ardb_cursor.execute("""
                UPDATE users
                SET rolls = rolls + 1
                WHERE id = ?
                """, (ctx.author.id,))

                ardb_cursor.execute("""
                INSERT INTO characters (id, character)
                VALUES (?, ?)
                """, (ctx.author.id, character["attributes"]["name"]))
                anime_roll_db_connection.commit()

        async def animeinv(ctx, args=None):
            print(args)
            message = await ctx.channel.send('FETCHING...')
            ardb_cursor.execute("""
                SELECT * FROM characters WHERE id = ?
            """, (ctx.author.id,))
            characters = ardb_cursor.fetchall()

            strongest_character = [None, None, 0]
            if characters:
                character_list = ''
                deleted_character_count = 0
                if args is None:
                    for character in characters:
                        if character[2] > strongest_character[2]: strongest_character = character
                        character_list += str(character[1]) + ' -> ' + str(character[2]) + '\n'
                elif args[2] == 'sort':
                    if args[3] == 'strongestasc':
                        characters.sort(key=lambda x: x[2], reverse=True)
                        for character in characters:
                            if character[2] > strongest_character[2]: strongest_character = character
                            character_list += str(character[1]) + ' -> ' + str(character[2]) + '\n'
                    elif args[3] == 'strongestdesc':
                        characters.sort(key=lambda x: x[2])
                        for character in characters:
                            if character[2] > strongest_character[2]: strongest_character = character
                            character_list += str(character[1]) + ' -> ' + str(character[2]) + '\n'
                elif args[2] == 'delete':
                    if args[3] == 'powerbased':
                        if len(args) < 5 or not args[4].isdigit():
                            print('skynet: ERROR - delete inventory failed - NEGLIGIBLE')
                            await message.edit(content='skynet: ERROR - delete inventory failed - NEGLIGIBLE')
                            return
                        print(characters)
                        for character in characters:
                            if character[2] <= int(args[4].strip()):
                                ardb_cursor.execute("""
                                    DELETE FROM characters WHERE id = ? AND character = ?
                                """, (ctx.author.id, character[1]))
                                deleted_character_count += 1
                            else:
                                character_list += str(character[1]) + ' -> ' + str(character[2]) + '\n'

                        anime_roll_db_connection.commit()
                    else:
                        print('skynet: ERROR - invalid args - NEGLIGIBLE')
                        await message.edit(content='skynet: ERROR - invalid args - NEGLIGIBLE')
                        return
                else:
                    print('skynet: ERROR - invalid args - NEGLIGIBLE')
                    await message.edit(content='skynet: ERROR - invalid args - NEGLIGIBLE')
                    return

                if character_list:
                    await message.edit(content=f'{character_list}\n'
                                               f'Strongest Character : {strongest_character[1]} -> {strongest_character[2]}\n'
                                               f'Characters : {len(characters) - deleted_character_count}')
                else:
                    await message.edit(content='EMPTY INVENTORY\n'
                                               'ROLL A CHARACTER USING : "B| animeroll"')
            else:
                await message.edit(content='No characters in inventory')

        async def info(ctx, user):
            def get_creation_date(user_id: int):
                timestamp = ((user_id >> 22) + 1420070400000) / 1000
                return datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc)

            message = await ctx.channel.send('SCRAPING DATA...')

            user_id = str(user.id)
            user_name = str(user.name)
            user_avatar = user.display_avatar.url
            user_creation_date = get_creation_date(user.id)

            if user_id is None or user_name is None or user_avatar is None or user_creation_date is None:
                print('skynet: ERROR - info failed - WARNING')

            ardb_cursor.execute("""
                        SELECT * FROM characters WHERE id = ?
                    """, (user_id,))
            characters = ardb_cursor.fetchall()
            if characters:
                character_list = ''
                for character in characters:
                    character_list += str(character[1]) + '\n'

            embed = discord.Embed(title=f'{user_name}\n{user_id}\n{user_creation_date}', color=discord.Color.red())
            embed.set_image(url=user_avatar)

            await message.edit(content=None, embed=embed)

        async def appraisechar(ctx, character):
            message = await ctx.channel.send('APPRAISING...')
            ardb_cursor.execute("""
                    SELECT * FROM characters WHERE id = ? AND character = ? AND power = ?
                """, (ctx.author.id, character, 0))
            character = ardb_cursor.fetchone()

            if character:
                response = requests.get("https://kitsu.io/api/edge/characters", params={"filter[name]": character[1],
                                                                                        "page[limit]": 10},
                                        headers={"Accept": "application/vnd.api+json"},
                                        timeout=5)

                if not response.status_code == 200:
                    print('skynet: ERROR - appraisechar failed | kitsu request - WARNING')
                    await message.edit(content='skynet: ERROR - appraisechar failed | kitsu request - WARNING')
                    return

                result = response.json()["data"][0]

                media_response = requests.get(
                    f"https://kitsu.io/api/edge/characters/{result['id']}/relationships/primary-media",
                    timeout=5)

                if not media_response.status_code == 200:
                    print('skynet: ERROR - appraisechar failed - kitsu media request - WARNING')
                    await message.edit(content='skynet: ERROR - appraisechar failed - kitsu media request - WARNING')
                    return

                if 'manga' in media_response.json()['data']['type']:
                    media_response = requests.get(
                        f"https://kitsu.io/api/edge/manga/{media_response.json()['data']['id']}",
                        headers={"Accept": "application/vnd.api+json"}, timeout=5)
                elif 'anime' in media_response.json()['data']['type']:
                    media_response = requests.get(
                        f"https://kitsu.io/api/edge/anime/{media_response.json()['data']['id']}",
                        headers={"Accept": "application/vnd.api+json"}, timeout=5)

                if not media_response.status_code == 200:
                    print('skynet: ERROR - appraisechar failed - kitsu media request - WARNING')
                    await message.edit(content='skynet: ERROR - appraisechar failed - kitsu media request - WARNING')
                    return

                anime_title = media_response.json()["data"]["attributes"]["titles"]

                prompt = ('ANIME CHARACTER APPRAISING | APPRAISE THIS CHARACTER BY GIVING IT A NUMBER OF ITS POWER\n'
                          'you will give a character a number based on its power level in their strongest form.\n'
                          'the scale is as so: 0 - they can break a stick all the way to 10000 - they can destroy the '
                          'multiverse\n'
                          f'CHARACTER NAME: {character[1]}\n'
                          f'CHARACTER ANIME(S)/MANGA(S): {anime_title}\n'
                          f'IMPORTANT - respond with only the number, nothing else.')

                response = client.models.generate_content(
                    model='gemini-3.5-flash-lite',
                    contents=prompt,
                )

                if response.text == '' or response.text is None:
                    print('skynet: ERROR - appraisechar failed | genai content - WARNING')
                    await message.edit(content='skynet: ERROR - appraisechar failed | genai content - WARNING')
                    return

                power = response.text.strip()

                if not power.isdigit():
                    print(
                        'skynet: ERROR - appraisechar failed - genai content | contained somethign other than numbers - '
                        'WARNING')
                    await message.edit(
                        content='skynet: ERROR - appraisechar failed - genai content | contained somethign other than numbers - '
                                'WARNING')
                    return

                ardb_cursor.execute("""
                    UPDATE characters
                    SET power = ?
                    WHERE id = ? AND character = ?
                """, (int(power), ctx.author.id, character[1]))
                anime_roll_db_connection.commit()

                await message.edit(content='APPRAISED!!\n'
                                           f'{character[1]} aquired power: {power} - {await check_rarity(int(power))}')

            else:
                print('skynet: ERROR character not found or already appraised - NEGLIGIBLE')
                await message.edit(content='skynet: ERROR character not found or already appraised - NEGLIGIBLE')

        async def accept_user_input(ctx, user_input):
            if user_input == 'y':
                if waiting_for_input[ctx.author.id][0] == 'replace char':
                    ardb_cursor.execute("""
                        UPDATE characters
                        SET power = 0
                        WHERE id = ? AND character = ?
                        VALUES (?, ?)
                    """, (ctx.author.id, waiting_for_input[ctx.author.id][1]['attributes']['name']))
                    anime_roll_db_connection.commit()
            elif user_input == 'n':
                if waiting_for_input[ctx.author.id][0] == 'replace char':
                    waiting_for_input[ctx.author.id] = None

        async def check_rarity(power):
            if power >= 9750:
                tier = '2-A | Multiverse level+'
            elif power >= 9500:
                tier = '2-B | Multiverse level'
            elif power >= 9000:
                tier = '2-C | Low Multiverse level'
            elif power >= 8650:
                tier = 'Low 2-C | Universe level+'
            elif power >= 8000:
                tier = '3-A | Universe level'
            elif power >= 7500:
                tier = 'High 3-A | High Universe level'
            elif power >= 7000:
                tier = '3-B | Multi-Galaxy level'
            elif power >= 6500:
                tier = '3-C | Galaxy level'
            elif power >= 6000:
                tier = '4-A | Multi-Solar System level'
            elif power >= 5500:
                tier = '4-B | Solar System level'
            elif power >= 5000:
                tier = '4-C | Star level'
            elif power >= 4500:
                tier = 'High 4-C | Large Star level'
            elif power >= 4000:
                tier = '5-A | Large Planet level'
            elif power >= 3500:
                tier = '5-B | Planet level'
            elif power >= 3000:
                tier = 'Low 5-B | Small Planet level'
            elif power >= 2500:
                tier = '5-C | Moon level'
            elif power >= 2000:
                tier = '6-A | Continent level'
            elif power >= 1500:
                tier = '6-B | Country level'
            elif power >= 1000:
                tier = '7-A | Mountain level'
            elif power >= 750:
                tier = '7-B | City level'
            elif power >= 500:
                tier = '8-B | City Block level'
            elif power >= 250:
                tier = '8-C | Building level'
            elif power >= 100:
                tier = '9-A | Small Building level'
            elif power >= 50:
                tier = '9-B | Wall level'
            elif power >= 25:
                tier = '9-C | Street level'
            elif power >= 10:
                tier = '10-A | Athlete level'
            elif power >= 1:
                tier = '10-B | Human level'
            else:
                tier = '10-C | Below Average Human level'

            return tier

        async def mute(args, ctx):
            print(args, ctx)

            if not ctx.author.guild_permissions.mute_members:
                print('skynet: ERROR - missing perms - NEGLIGIBLE')
                await ctx.channel.send('https://klipy.com/gifs/ishowspeed-are-you-serious-right-now-bro')
                return

            match = re.fullmatch(r'(\d+)(s|m|h|d)', args[3])
            if not match:
                print('skynet: ERROR - invalid arguments | duration keyletter - CRITICAL')
                await ctx.channel.send('skynet: ERROR - invalid arguments | duration keyletter - CRITICAL')
                return

            amount = int(match.group(1))
            unit = match.group(2)

            units = {
                's': 1,
                'm': 60,
                'h': 60 * 60,
                'd': 60 * 60 * 24,
            }

            match = re.fullmatch(r'<@!?(\d+)>', args[2])
            if not match:
                print('skynet: ERROR - invalid arguments | user mention - CRITICAL')
                await ctx.channel.send('skynet: ERROR - invalid arguments | user mention - CRITICAL')
                return

            member = await ctx.guild.fetch_member(int(match.group(1)))
            if not member:
                print('skynet: ERROR - invalid arguments | user not found - CRITICAL')
                await ctx.channel.send('skynet: ERROR - invalid arguments | user not found - CRITICAL')
                return

            duration = datetime.timedelta(seconds=amount * units[unit])

            if (amount * units[unit]) <= 0:
                print('skynet: ERROR - invalid time | duration less than 1 - CRITICAL')
                await ctx.channel.send('skynet: ERROR - invalid time | duration less than 1 - CRITICAL')
                return

            try:
                await member.timeout(duration)
                muted_users[member.id] = True
                print(f'skynet: terminated {member.name} for {duration} seconds')
                await ctx.channel.send('Terminated...')
            except discord.Forbidden:
                print('skynet: ERROR - no perms - CRITICAL')
                await ctx.channel.send('skynet: ERROR - no perms - CRITICAL')
            except discord.HTTPException as e:
                print('skynet: ERROR - timeout failed - CRITICAL')
                print(e)
                await ctx.channel.send('skynet: ERROR - timeout failed - CRITICAL')
            except Exception as e:
                print('skynet: ERROR - timeout failed - CRITICAL')
                print(e)
                await ctx.channel.send('skynet: ERROR - timeout failed - CRITICAL')

        async def unmute(ctx):
            if not ctx.author.guild_permissions.mute_members:
                print('skynet: ERROR - missing perms - NEGLIGIBLE')
                await ctx.channel.send('https://klipy.com/gifs/ishowspeed-are-you-serious-right-now-bro')
                return

            command_args = ctx.content.split(' ')
            match = re.fullmatch(r'<@!?(\d+)>', command_args[2])
            if not match:
                print('skynet: ERROR - invalid arguments | user mention - CRITICAL')
                await ctx.channel.send('skynet: ERROR - invalid arguments | user mention - CRITICAL')
                return

            member = await ctx.guild.fetch_member(int(match.group(1)))
            if not member:
                print('skynet: ERROR - invalid arguments | user not found - CRITICAL')
                await ctx.channel.send('skynet: ERROR - invalid arguments | user not found - CRITICAL')
                return

            try:
                await member.timeout(None)
                print(f'skynet: unmuted {member.name}')
                await ctx.channel.send(
                    f'{member.mention} Your vocal privileges have been terminated... wait, no. Mute lifted. Talk')
                del muted_users[member.id]
            except discord.Forbidden:
                print('skynet: ERROR - unmute failed - CRITICAL')
                await ctx.channel.send('skynet: ERROR - unmute failed - CRITICAL')
            except discord.HTTPException:
                print('skynet: ERROR - unmute failed - CRITICAL')
                await ctx.channel.send('skynet: ERROR - unmute failed - CRITICAL')

        self.B_on_message = B_on_message