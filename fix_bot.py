with open("bot.py", "r", encoding="utf-8") as f:
    src = f.read()

# ── 1. run_admin_tool: add invoker= parameter ──────────────────────────────
src = src.replace(
    "async def run_admin_tool(guild, name, args):",
    "async def run_admin_tool(guild, name, args, invoker=None):"
)

# ── 2. Insert admin_protected_for helper after admin_protected ─────────────
helper = """\n\ndef admin_protected_for(member, invoker=None):\n    \\"\\"\\"Return True if member is protected, UNLESS invoker is the server owner (OWNER_ID).\\"\\"\\"\\n    if invoker is not None and invoker.id == OWNER_ID:\\n        return member.id == bot.user.id  # owner can do anything except moderate the bot itself\\n    return admin_protected(member)\\n"""
src = src.replace(
    "\n\ndef parse_color(value):",
    helper + "\n\ndef parse_color(value):"
)

# ── 3. Swap admin_protected calls inside run_admin_tool to admin_protected_for ─
# mute_member
src = src.replace(
    'if admin_protected(member):\n            return f"Refused: **{member}** is protected (owner/bot/admin/whitelisted)."\n        toggle = bool(args.get("muted"))',
    'if admin_protected_for(member, invoker):\n            return f"Refused: **{member}** is protected (owner/bot/admin/whitelisted)."\n        toggle = bool(args.get("muted"))'
)
# deafen_member
src = src.replace(
    'if admin_protected(member):\n            return f"Refused: **{member}** is protected (owner/bot/admin/whitelisted)."\n        toggle = bool(args.get("deafened"))',
    'if admin_protected_for(member, invoker):\n            return f"Refused: **{member}** is protected (owner/bot/admin/whitelisted)."\n        toggle = bool(args.get("deafened"))'
)
# set_nickname
src = src.replace(
    'if admin_protected(member):\n            return f"Refused: **{member}** is protected (owner/bot/admin/whitelisted)."\n        nick = (args.get("nickname")',
    'if admin_protected_for(member, invoker):\n            return f"Refused: **{member}** is protected (owner/bot/admin/whitelisted)."\n        nick = (args.get("nickname")'
)
# remove_role
src = src.replace(
    'if admin_protected(member):\n            return f"Refused: **{member}** is protected (owner/bot/admin/whitelisted)."\n        target, err2 = resolve_role(guild, args.get("role_id"), args.get("role_query"))',
    'if admin_protected_for(member, invoker):\n            return f"Refused: **{member}** is protected (owner/bot/admin/whitelisted)."\n        target, err2 = resolve_role(guild, args.get("role_id"), args.get("role_query"))'
)
# ban/kick/timeout fallthrough at bottom of run_admin_tool
src = src.replace(
    '    if admin_protected(member):\n        return f"Refused: **{member}** is protected (owner/bot/admin/whitelisted)."\n    reason = (args.get("reason")',
    '    if admin_protected_for(member, invoker):\n        return f"Refused: **{member}** is protected (owner/bot/admin/whitelisted)."\n    reason = (args.get("reason")'
)

# ── 4. grant_role: block escalation above invoker highest role ─────────────
src = src.replace(
    '        await member.add_roles(target, reason="AI admin: grant role")\n        await audit(guild, f":label: AI admin gave **{member}** role **{target.name}**")\n        return f"Gave **{member}** the role **{target.name}**."',
    '        if invoker and invoker.id != OWNER_ID:\n            invoker_top = max((r.position for r in invoker.roles), default=0)\n            if target.position >= invoker_top:\n                return f"Refused: you cannot grant **{target.name}** (pos {target.position}) — it is at or above your own highest role (pos {invoker_top})."\n        await member.add_roles(target, reason="AI admin: grant role")\n        await audit(guild, f":label: AI admin gave **{member}** role **{target.name}**")\n        return f"Gave **{member}** the role **{target.name}**."'
)

# ── 5. set_role_position: block moving role above invoker highest ──────────
src = src.replace(
    '        await target.edit(position=roles[new_idx].position, reason="AI admin: set role position")',
    '        if invoker and invoker.id != OWNER_ID:\n            invoker_top = max((r.position for r in invoker.roles), default=0)\n            if target.position >= invoker_top or roles[new_idx].position >= invoker_top:\n                return f"Refused: you cannot move roles to or above your own highest role position ({invoker_top})."\n        await target.edit(position=roles[new_idx].position, reason="AI admin: set role position")'
)

# ── 6. Pass invoker into run_admin_tool in ai_admin_generate ─────────────
src = src.replace(
    "async def ai_admin_generate(prompt, interaction):\n    if not AI_ENABLED:\n        return \"AI is not set up yet. The owner needs to add an `AI_API_KEY` to the bot environment.\"\n    memory = AI_ADMIN_MEMORY[interaction.user.id]",
    "async def ai_admin_generate(prompt, interaction):\n    if not AI_ENABLED:\n        return \"AI is not set up yet. The owner needs to add an `AI_API_KEY` to the bot environment.\"\n    invoker = interaction.guild.get_member(interaction.user.id)\n    memory = AI_ADMIN_MEMORY[interaction.user.id]"
)
src = src.replace(
    "                    result = await run_admin_tool(interaction.guild, fname, targs)\n                except discord.HTTPException as e:\n                    result = f\"Discord error: {e}\"\n                messages.append({\"role\": \"tool\", \"tool_call_id\": tc[\"id\"], \"content\": result})\n            if sum(len(m.get(\"content\") or str(m.get(\"tool_calls\") or \"\")) for m in messages) > 1_000_000:\n                return \"Context window is full from tool use - stopping before the API rejects the request.\"\n            continue\n        reply = (data.get(\"content\") or \"Done.\").strip()\n        reply = reply.replace(\"@everyone\", \"everyone\").replace(\"@here\", \"here\")\n        memory.append((\"user\", prompt))\n        memory.append((\"assistant\", reply))\n        return fit(reply)\n\n\nasync def ai_juiced_generate",
    "                    result = await run_admin_tool(interaction.guild, fname, targs, invoker=invoker)\n                except discord.HTTPException as e:\n                    result = f\"Discord error: {e}\"\n                messages.append({\"role\": \"tool\", \"tool_call_id\": tc[\"id\"], \"content\": result})\n            if sum(len(m.get(\"content\") or str(m.get(\"tool_calls\") or \"\")) for m in messages) > 1_000_000:\n                return \"Context window is full from tool use - stopping before the API rejects the request.\"\n            continue\n        reply = (data.get(\"content\") or \"Done.\").strip()\n        reply = reply.replace(\"@everyone\", \"everyone\").replace(\"@here\", \"here\")\n        memory.append((\"user\", prompt))\n        memory.append((\"assistant\", reply))\n        return fit(reply)\n\n\nasync def ai_juiced_generate"
)

# ── 7. Pass invoker into run_admin_tool in ai_juiced_generate ─────────────
src = src.replace(
    "async def ai_juiced_generate(prompt, interaction):\n    if not AI_ENABLED:\n        return \"AI is not set up yet. The owner needs to add an `AI_API_KEY` to the bot environment.\"\n    memory = AI_JUICED_MEMORY[interaction.user.id]",
    "async def ai_juiced_generate(prompt, interaction):\n    if not AI_ENABLED:\n        return \"AI is not set up yet. The owner needs to add an `AI_API_KEY` to the bot environment.\"\n    invoker = interaction.guild.get_member(interaction.user.id)\n    memory = AI_JUICED_MEMORY[interaction.user.id]"
)
src = src.replace(
    "                    result = await run_admin_tool(interaction.guild, fname, targs)\n                except discord.HTTPException as e:\n                    result = f\"Discord error: {e}\"\n                messages.append({\"role\": \"tool\", \"tool_call_id\": tc[\"id\"], \"content\": result})\n            if sum(len(m.get(\"content\") or str(m.get(\"tool_calls\") or \"\")) for m in messages) > 1_000_000:\n                return \"Context window is full from tool use - stopping before the API rejects the request.\"\n            continue\n        reply = (data.get(\"content\") or \"Done.\").strip()\n        reply = reply.replace(\"@everyone\", \"everyone\").replace(\"@here\", \"here\")\n        memory.append((\"user\", prompt))\n        memory.append((\"assistant\", reply))\n        return fit(reply)\n\n\nADMIN_TOOLS",
    "                    result = await run_admin_tool(interaction.guild, fname, targs, invoker=invoker)\n                except discord.HTTPException as e:\n                    result = f\"Discord error: {e}\"\n                messages.append({\"role\": \"tool\", \"tool_call_id\": tc[\"id\"], \"content\": result})\n            if sum(len(m.get(\"content\") or str(m.get(\"tool_calls\") or \"\")) for m in messages) > 1_000_000:\n                return \"Context window is full from tool use - stopping before the API rejects the request.\"\n            continue\n        reply = (data.get(\"content\") or \"Done.\").strip()\n        reply = reply.replace(\"@everyone\", \"everyone\").replace(\"@here\", \"here\")\n        memory.append((\"user\", prompt))\n        memory.append((\"assistant\", reply))\n        return fit(reply)\n\n\nADMIN_TOOLS"
)

# ── 8. Log unauthorized /ai admin and /ai juiced attempts ─────────────────
src = src.replace(
    '@bot.tree.error\nasync def on_app_error(interaction: discord.Interaction, error: app_commands.AppCommandError):\n    if isinstance(error, app_commands.CheckFailure):\n        await interaction.response.send_message("You don\'t have permission to use this.", ephemeral=True)\n    else:\n        print(error)  # noqa: E501',
    '@bot.tree.error\nasync def on_app_error(interaction: discord.Interaction, error: app_commands.AppCommandError):\n    if isinstance(error, app_commands.CheckFailure):\n        await interaction.response.send_message("You don\'t have permission to use this.", ephemeral=True)\n        cmd_name = getattr(interaction.command, "qualified_name", "")\n        if cmd_name in ("ai admin", "ai juiced") and interaction.guild:\n            options = (interaction.data or {}).get("options", [])\n            attempted = ""\n            for opt in options:\n                for sub in opt.get("options", []):\n                    if sub.get("name") == "message":\n                        attempted = sub.get("value", "")\n            if attempted:\n                log_text = (\n                    f":no_entry: **Unauthorized /{cmd_name}** attempt by "\n                    f"**{interaction.user}** (id={interaction.user.id})\\n"\n                    f"Message they tried: `{attempted[:500]}`"\n                )\n                asyncio.create_task(audit(interaction.guild, log_text))\n    else:\n        print(error)  # noqa: E501'
)

with open("bot.py", "w", encoding="utf-8") as f:
    f.write(src)
print("Done")
