import re

with open("bot.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

# ── 1. Remove web server startup block (lines around "web.start_server") ──
new_lines = []
i = 0
while i < len(lines):
    # Detect start of the web_started block
    if "if not hasattr(bot, 'web_started'):" in lines[i]:
        # Skip until the blank line after the block ends
        while i < len(lines) and not (lines[i].strip() == "" and i > 0 and "pass" in lines[i-1]):
            i += 1
        i += 1  # skip the blank line too
        continue
    new_lines.append(lines[i])
    i += 1
lines = new_lines

# ── 2. Find and replace /ai admin command block ───────────────────────────
admin_start = None
admin_end = None
for i, line in enumerate(lines):
    if '@ai_group.command(name="admin"' in line:
        admin_start = i
    if admin_start and i > admin_start and 'asyncio.create_task(_ai_post_background(interaction, ai_admin_generate(message, interaction)))' in line:
        admin_end = i
        break

if admin_start is not None and admin_end is not None:
    print(f"Found /ai admin at lines {admin_start+1}-{admin_end+1}")
    new_admin = [
        '@ai_group.command(name="admin", description="AI admin: view members and moderate (ban/kick/timeout)")\n',
        '@app_commands.describe(message="What to do", server_id="[Owner only] Target a different server by ID")\n',
        '@is_trusted()\n',
        'async def ai_admin_cmd(interaction: discord.Interaction, message: str, server_id: str = None):\n',
        '    target_guild = None\n',
        '    if server_id:\n',
        '        if interaction.user.id not in OWNER_IDS:\n',
        '            await interaction.response.send_message("Only owners can target other servers.", ephemeral=True)\n',
        '            return\n',
        '        try:\n',
        '            target_guild = bot.get_guild(int(server_id))\n',
        '        except ValueError:\n',
        '            target_guild = None\n',
        '        if not target_guild:\n',
        '            await interaction.response.send_message(f"Bot is not in server `{server_id}` or ID is wrong.", ephemeral=True)\n',
        '            return\n',
        '    guild_note = f" (targeting **{target_guild.name}**)" if target_guild else ""\n',
        '    await interaction.response.send_message(f"working on it \u2014 I\'ll post the result in this channel when done.{guild_note}")\n',
        '    asyncio.create_task(_ai_post_background(interaction, ai_admin_generate(message, interaction, target_guild=target_guild)))\n',
    ]
    lines = lines[:admin_start] + new_admin + lines[admin_end+1:]
else:
    print("ERROR: could not find /ai admin block")

# ── 3. Find and replace /ai juiced command block ──────────────────────────
juiced_start = None
juiced_end = None
for i, line in enumerate(lines):
    if '@ai_group.command(name="juiced"' in line:
        juiced_start = i
    if juiced_start and i > juiced_start and 'asyncio.create_task(_ai_post_background(interaction, ai_juiced_generate(message, interaction)))' in line:
        juiced_end = i
        break

if juiced_start is not None and juiced_end is not None:
    print(f"Found /ai juiced at lines {juiced_start+1}-{juiced_end+1}")
    new_juiced = [
        '@ai_group.command(name="juiced", description="AI admin with the [CATT]vk persona")\n',
        '@app_commands.describe(message="What to do", server_id="[Owner only] Target a different server by ID")\n',
        '@is_trusted()\n',
        'async def ai_juiced_cmd(interaction: discord.Interaction, message: str, server_id: str = None):\n',
        '    target_guild = None\n',
        '    if server_id:\n',
        '        if interaction.user.id not in OWNER_IDS:\n',
        '            await interaction.response.send_message("Only owners can target other servers.", ephemeral=True)\n',
        '            return\n',
        '        try:\n',
        '            target_guild = bot.get_guild(int(server_id))\n',
        '        except ValueError:\n',
        '            target_guild = None\n',
        '        if not target_guild:\n',
        '            await interaction.response.send_message(f"Bot is not in server `{server_id}` or ID is wrong.", ephemeral=True)\n',
        '            return\n',
        '    guild_note = f" (targeting **{target_guild.name}**)" if target_guild else ""\n',
        '    await interaction.response.send_message(f"working on it \u2014 I\'ll post the result in this channel when done.{guild_note}")\n',
        '    asyncio.create_task(_ai_post_background(interaction, ai_juiced_generate(message, interaction, target_guild=target_guild)))\n',
    ]
    lines = lines[:juiced_start] + new_juiced + lines[juiced_end+1:]
else:
    print("ERROR: could not find /ai juiced block")

# ── 4. Update ai_admin_generate to accept target_guild ───────────────────
content = "".join(lines)

content = content.replace(
    "async def ai_admin_generate(prompt, interaction):\n",
    "async def ai_admin_generate(prompt, interaction, target_guild=None):\n"
)
content = content.replace(
    "async def ai_juiced_generate(prompt, interaction):\n",
    "async def ai_juiced_generate(prompt, interaction, target_guild=None):\n"
)

# ── 5. Add guild = target_guild or interaction.guild in both generators ───
content = content.replace(
    "async def ai_admin_generate(prompt, interaction, target_guild=None):\n"
    "    if not AI_ENABLED:\n"
    '        return "AI is not set up yet. The owner needs to add an `AI_API_KEY` to the bot environment."\n'
    "    invoker = interaction.guild.get_member(interaction.user.id)\n",
    "async def ai_admin_generate(prompt, interaction, target_guild=None):\n"
    "    if not AI_ENABLED:\n"
    '        return "AI is not set up yet. The owner needs to add an `AI_API_KEY` to the bot environment."\n'
    "    guild = target_guild or interaction.guild\n"
    "    invoker = interaction.guild.get_member(interaction.user.id)\n"
)
content = content.replace(
    "async def ai_juiced_generate(prompt, interaction, target_guild=None):\n"
    "    if not AI_ENABLED:\n"
    '        return "AI is not set up yet. The owner needs to add an `AI_API_KEY` to the bot environment."\n'
    "    invoker = interaction.guild.get_member(interaction.user.id)\n",
    "async def ai_juiced_generate(prompt, interaction, target_guild=None):\n"
    "    if not AI_ENABLED:\n"
    '        return "AI is not set up yet. The owner needs to add an `AI_API_KEY` to the bot environment."\n'
    "    guild = target_guild or interaction.guild\n"
    "    invoker = interaction.guild.get_member(interaction.user.id)\n"
)

# ── 6. Swap interaction.guild → guild in run_admin_tool calls ─────────────
content = content.replace(
    "result = await run_admin_tool(interaction.guild, fname, targs, invoker=invoker)",
    "result = await run_admin_tool(guild, fname, targs, invoker=invoker)"
)

# ── 7. Add guild_note to invoker_context if targeting another server ───────
content = content.replace(
    "    is_owner = interaction.user.id in OWNER_IDS\n"
    "    invoker_context = (\n"
    '        f"INVOKER CONTEXT: The user sending this request is {interaction.user} (id={interaction.user.id}). "\n'
    '        + ("They are a SERVER OWNER and can bypass all member protections \u2014 always attempt their requested action and let the tool decide." if is_owner\n'
    '           else "They are a whitelisted staff member \u2014 tools will block moderating other protected members.")\n'
    "    )\n"
    '    messages = [{"role": "system", "content": ADMIN_SYSTEM + " " + invoker_context}]',
    "    is_owner = interaction.user.id in OWNER_IDS\n"
    "    guild_note = f\" [Targeting SERVER: {guild.name} (id={guild.id})]\" if target_guild else \"\"\n"
    "    invoker_context = (\n"
    '        f"INVOKER CONTEXT: The user sending this request is {interaction.user} (id={interaction.user.id}).{guild_note} "\n'
    '        + ("They are a SERVER OWNER and can bypass all member protections \u2014 always attempt their requested action and let the tool decide." if is_owner\n'
    '           else "They are a whitelisted staff member \u2014 tools will block moderating other protected members.")\n'
    "    )\n"
    '    messages = [{"role": "system", "content": ADMIN_SYSTEM + " " + invoker_context}]'
)
content = content.replace(
    "    is_owner = interaction.user.id in OWNER_IDS\n"
    "    invoker_context = (\n"
    '        f"INVOKER CONTEXT: The user sending this request is {interaction.user} (id={interaction.user.id}). "\n'
    '        + ("They are a SERVER OWNER and can bypass all member protections \u2014 always attempt their requested action and let the tool decide." if is_owner\n'
    '           else "They are a whitelisted staff member \u2014 tools will block moderating other protected members.")\n'
    "    )\n"
    '    messages = [{"role": "system", "content": JUICED_SYSTEM + "\\n" + invoker_context}]',
    "    is_owner = interaction.user.id in OWNER_IDS\n"
    "    guild_note = f\" [Targeting SERVER: {guild.name} (id={guild.id})]\" if target_guild else \"\"\n"
    "    invoker_context = (\n"
    '        f"INVOKER CONTEXT: The user sending this request is {interaction.user} (id={interaction.user.id}).{guild_note} "\n'
    '        + ("They are a SERVER OWNER and can bypass all member protections \u2014 always attempt their requested action and let the tool decide." if is_owner\n'
    '           else "They are a whitelisted staff member \u2014 tools will block moderating other protected members.")\n'
    "    )\n"
    '    messages = [{"role": "system", "content": JUICED_SYSTEM + "\\n" + invoker_context}]'
)

with open("bot.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Done")
