import re
with open("website/index.html", "r", encoding="utf-8") as f: html = f.read()

# Fix whitelist add buttons
html = html.replace("onclick=\"addWL('wl-users','wl-user-in','??')\"", "onclick=\"addWLUser()\"")
html = html.replace("onclick=\"addWL('wl-roles','wl-role-in','??')\"", "onclick=\"addWLRole()\"")
html = html.replace("onclick=\"addWL('wl-links','wl-link-in','??')\"", "onclick=\"addWLLink()\"")

# Fix auto-response add button
html = re.sub(r"(id=\"ar-rep\"[^>]*/>\s*(?:<button[^>]*>Add</button>|$))", lambda m: m.group(0), html)
# Find the AR add button and update it
html = re.sub(r'(<div class="add-row ar-add-row">.*?)(</div>)', 
    lambda m: m.group(0).replace('>Add<', ' onclick="addAutoResponse()">Add<'), 
    html, flags=re.DOTALL)

# Fix moderation buttons
html = html.replace("onclick=\"modAction('ban')\"", "onclick=\"modAction('ban')\"")
html = html.replace("onclick=\"modAction('kick')\"", "onclick=\"modAction('kick')\"")
html = html.replace("onclick=\"modAction('timeout')\"", "onclick=\"modAction('timeout')\"")
html = html.replace("onclick=\"modAction('unban')\"", "onclick=\"modAction('unban')\"")
html = html.replace("onclick=\"modAction('purge')\"", "onclick=\"modAction('purge')\"")

with open("website/index.html", "w", encoding="utf-8") as f: f.write(html)
print("Done")
