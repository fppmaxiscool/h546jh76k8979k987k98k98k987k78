with open('bot.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Remove lines 2586-2589 (1-indexed) = indices 2585-2588 (0-indexed)
# These are the broken, mis-indented block
# Verify content first
for i in range(2585, 2589):
    print(f"Line {i+1}: {repr(lines[i])}")

new_lines = lines[:2585] + lines[2589:]

with open('bot.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print(f"Done. {len(lines)} -> {len(new_lines)} lines")
