import asyncio
import datetime
import json
import os
import re
import time
from collections import defaultdict, deque
from typing import Union

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

def load_token():
    token = os.getenv("DISCORD_TOKEN", "").strip()
    if token:
        return token
    env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_file):
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    if key.strip() == "DISCORD_TOKEN":
                        return value.strip().strip('"').strip("'")
    return ""


TOKEN = load_token()
if not TOKEN:
    raise SystemExit("DISCORD_TOKEN environment variable is not set and no .env file found. See .env.example")

OWNER_ID = 847669208296063016

AI_API_KEY = os.getenv("AI_API_KEY", "").strip()
AI_MODEL = os.getenv("AI_MODEL", "deepseek-chat").strip()
AI_ENABLED = bool(AI_API_KEY)
AI_MEMORY = {}
AI_ADMIN_MEMORY = defaultdict(lambda: deque(maxlen=12))
AI_CHANNEL_ID = None

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

RAID_JOIN_WINDOW = 10
RAID_JOIN_COUNT = 6
JOIN_LOG = deque(maxlen=200)
RAID_JOIN_BUFFER = 60

CHANNEL_CREATE_WINDOW = 3
CHANNEL_CREATE_COUNT = 4
CHANNEL_CREATE_LOG = deque(maxlen=100)

spam_window = 5
spam_count = 5
spam_mute_minutes = 10
spam_ban_offenses = 3
SPAM_OFFENSES = defaultdict(int)
MESSAGE_LOG = defaultdict(lambda: deque(maxlen=100))
RAID_SLOWMODE = 0
RAID_SLOWMODE_SAVED = {}

AI_LIMIT = 10
AI_WINDOW = 3600
AI_USAGE = defaultdict(lambda: deque(maxlen=200))

DISCORD_INVITE_RE = re.compile(
    r"(?:discord\.(?:gg|com|app|io|me|li|gift|new)/|discordapp\.com/invite/|dsc\.gg/|dis\.gg/|\b[\w-]+\.gg/)[^\s]*",
    re.IGNORECASE,
)
LINK_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)

BAD_WORDS = [
    "nigger", "nigga", "niggas", "niggah", "niggaz", "nga", "nig", "niqqa", "negro", "negress",
    "coon", "coonass", "coonface", "coonfuck", "jigaboo", "jig", "zigaboo", "sambo", "mammy",
    "uncle tom", "unclestom", "porch monkey", "porchmonkey", "jungle bunny", "junglebunny",
    "tar baby", "tarbaby", "spear chucker", "spearchucker", "spook", "nappy head", "nappyhead",
    "blue gum", "bluegum", "cotton picker", "cottonpicker", "house nigger", "field nigger",
    "niglet", "nigglet", "nighead", "nignog", "nigaboo", "niggerhead", "nigger lover",
    "nigger loving", "niggerish", "nigging", "n word", "nword", "nigga lover", "blackie",
    "blacky", "darkie", "darky", "darkey", "abo", "abbo", "boong", "boonga", "wog", "wogs",
    "woggy", "golliwog", "golliwogg", "coonery", "spade", "buck", "lambo", "jungle fever",
    "mullato", "mulatto", "half breed", "halfbreed", "half-breed", "half caste", "halfcaste",
    "half-caste", "mudblood", "mud blood", "mongrel", "mixed race scum", "nephew of uncle tom",
    "ching chong", "chingchong", "ching-chong", "chink", "chinks", "chinky", "chinkface",
    "chinkfuck", "chinkstain", "ching", "chinaman", "chinamen", "chinese nigger", "chinese fag",
    "slope", "slopes", "slanty", "slant eye", "slanteye", "slant eyed", "slanteyes", "gook",
    "gooks", "gookface", "gookfuck", "zipperhead", "zipper head", "jap", "japs", "nip", "nippy",
    "asian nigger", "rice nigger", "rice eater", "riceeater", "rice digger", "dog eater",
    "dogeater", "cat eater", "cateater", "dogfucker", "eggroll nigger", "ladyboy lover",
    "dothead", "dot head", "dotface", "curry muncher", "currymuncher", "curry nigger",
    "curryfucker", "pickle eater", "pickleeater", "pajeet", "bomb head", "bombhead", "bomb maker",
    "towel head", "towelhead", "turban head", "turbanhead", "raghead", "rag head", "ragheadfuck",
    "camel jockey", "cameljockey", "camel fucker", "camel fuck", "cameleater", "sand nigger",
    "sandnigger", "sand monkey", "sandmonkey", "sand face", "sandface", "sand fucker",
    "sandfucker", "haji", "hajji", "haiji", "mooslim", "moose lim", "muslim cunt", "islamic scum",
    "kike", "kikes", "kikeface", "kikefuck", "kikette", "jewboy", "jew boy", "jewfucker",
    "jewwhore", "heeb", "hebe", "hymie", "sheeny", "yid", "yids", "zionazi", "christkiller",
    "christ killer", "kaffir", "kafir scum", "shylock", "jew shit", "jewcunt", "judenstein",
    "synagogue of satan", "spic", "spick", "spik", "spicface", "spicfuck", "spickfuck",
    "chili picker", "chillispicker", "chili nigger", "chile nigger", "beaner", "beaners",
    "beanerface", "beanerfuck", "wetback", "wet back", "wetbackfuck", "taco nigger", "taconigger",
    "border hopper", "borderhopper", "greaser", "greasers", "spic whore", "spic slut",
    "mexican monkey", "mexican nigger", "frijolero", "mayate", "sudaca", "bolillo",
    "mick", "micks", "micky", "paddy", "paddies", "bogtrotter", "bog trotter", "spud muncher",
    "spudmuncher", "potato eater", "potatoeater", "potato nigger", "irish nigger", "taffy",
    "taffs", "sheep shagger", "sheepshagger", "sheep fucker", "sheepfucker", "limey", "limeys",
    "pom", "poms", "pommy", "pommie", "brit bastard", "britbong", "jock", "jocks", "taig",
    "taigs", "hun", "huns", "hunfucker", "frog eater", "frogeater", "cheese eating surrender",
    "wop", "wops", "wopface", "guido", "guidos", "greaseball", "grease ball", "spaghetti nigger",
    "pizza nigger", "spaghettiface", "kraut", "krauts", "krautface", "krautfuck", "boche",
    "jerry fucker", "sauerkraut eater", "cracker", "crackers", "crackerass", "honky", "honkey",
    "honkies", "whitey", "white trash", "whitetrash", "white trash scum", "hillbilly",
    "hillbillies", "redneck", "red neck", "rednecks", "trailer trash", "trailertrash",
    "trailer park trash", "mayo monkey", "mayomuncher", "peckerwood", "pecker wood",
    "white nigger", "whitenigger", "snowflake nigger", "vanilla face", "cracka", "crackah",
    "charlie", "carlton", "black camp", "gyppo", "gippo", "gyp", "gypo", "gypsy scum",
    "pikey", "pikeys", "pikey scum", "chav", "chavs", "scally", "scallies", "ned", "neds",
    "commie", "commies", "commie cunt", "communist pig", "soviet pig", "ruski", "rusky", "ruskie",
    "bolshevik scum", "gabacho", "gabacha", "gusano", "faggot", "faggots", "faggotry",
    "faggotfuck", "fagbag", "fagbait", "fagbreath", "fagbutt", "fagfuck", "fagfucker",
    "fagget", "faggy", "faggish", "faghat", "faghag", "fagmuncher", "fagnugget", "fagot",
    "fags", "fagtastic", "fagtard", "fagwad", "fagwhore", "fag", "fruit", "fruits",
    "fudge packer", "fudgepacker", "fudge chamber", "pillow biter", "pillowbiter",
    "butt pirate", "buttpirate", "bum bandit", "bumbandit", "bum boy", "bumboy",
    "arse bandit", "arsebandit", "pansy", "poof", "poofter", "poofy", "dyke", "dykes",
    "bulldyke", "bulldyker", "rug muncher", "rugmuncher", "carpet muncher", "carpetmuncher",
    "muff diver", "muffdiver", "lesbo", "lesbos", "tranny", "trannies", "trannyfuck",
    "shemale", "she male", "heshe", "he-she", "sissy", "sissies", "homo", "homos",
    "queer", "queers", "queerfag", "fudgepacker", "trapfag", "clockable", "malefail",
    "retard", "retards", "retarded", "retardo", "retardface", "retardfuck", "retardness",
    "retardedness", "mong", "mongo", "mongoloid", "window licker", "windowlicker", "spaz",
    "spastic", "spacker", "spacka", "cripple", "crippled", "cripplefuck", "gimp", "gimped",
    "vegetable", "brain damage", "braindamaged", "braindead", "brain dead", "half wit",
    "halfwit", "half wits", "halfwits", "moron", "morons", "moronic", "imbecile", "imbeciles",
    "cretin", "cretins", "cretinous", "idiot", "idiots", "idiotic", "drooler", "mouthbreather",
    "mouth breather", "special olympics", "fucktard", "fucktards", "shittard", "asshat",
    "bitch", "bitches", "bitchass", "bitchface", "bitchfit", "bitchfuck", "bitchhole",
    "bitchlicker", "bitchslap", "bitchslapped", "bitchslapping", "bitchtits", "bitchy",
    "bitching", "bitchboy", "bitchcan", "bitchdog", "bitchfist", "bitchmuffin", "bitchtaco",
    "bitch whore", "bitchslut", "slut", "sluts", "slutbag", "slutbucket", "slutface",
    "sluthead", "slutmachine", "slutpocket", "slutsack", "slutshine", "sluttish", "slutty",
    "slutwhore", "whore", "whores", "whorebag", "whorebath", "whorechild", "whoreface",
    "whorehouse", "whoreish", "whoreline", "whoreload", "whorelord", "whoremonger", "whorepipe",
    "whorepocket", "whoreranch", "whorest", "ho", "hoe", "hoes", "thot", "thots", "skank",
    "skanks", "skanky", "slag", "slags", "tramp", "tramps", "trollop", "strumpet", "harlot",
    "bimbo", "bimbos", "cocktease", "cock tease", "prickteaser", "prick teaser", "ballbuster",
    "ball buster", "ballbusting", "femoid", "foid", "roastie", "cum dumpster", "cumdumpster",
    "cum dump", "cumdump", "cum guzzler", "cumguzzler", "cum slut", "cumslut", "cum whore",
    "cumwhore", "cumfart", "cumfucker", "cumgargler", "cumjacker", "cumstain", "creampie",
    "cream pie", "gangbang", "gang bang", "handjob", "hand job", "blowjob", "blow job",
    "blowjobs", "rimjob", "rim job", "titjob", "footjob", "deepthroat", "deep throat",
    "dildo", "dildos", "dildoface", "strap on", "strapon", "doggystyle", "doggy style",
    "ass to mouth", "gloryhole", "glory hole", "fuck", "fucker", "fuckers", "fucking",
    "fucked", "fuckface", "fuckhead", "fuckhole", "fuckstick", "fucknut", "fucknugget",
    "fuckwad", "fuckwit", "fuckwitt", "fuckboy", "fuckboi", "fuckbucket", "fuckbuddy",
    "fuckbuddies", "fuckery", "fuckfest", "fuckknuckle", "fucklard", "fucklet", "fuckling",
    "fuckmachine", "fuckmeat", "fuckmonger", "fucknuckle", "fuckoff", "fucko", "fuckrice",
    "fucktart", "fucktrumpet", "fucktwat", "fuckup", "fuckus", "fuckwaffle", "fuckwhistle",
    "fucked up", "fuckedup", "motherfucker", "motherfuckers", "motherfucking", "motherfuck",
    "mofo", "mofos", "fuk", "fukk", "fukker", "fukked", "fck", "fucked in the head",
    "go fuck yourself", "fuck your mother", "fuck ur mother", "fuck your dad", "fuck off",
    "holy fuck", "what the fuck", "fuck this", "fuck that", "cunt", "cunts", "cunthead",
    "cuntface", "cuntbag", "cuntbitch", "cunthole", "cuntlicker", "cuntlips", "cuntmuffin",
    "cuntrag", "cuntslut", "cuntstruck", "cuntwaffle", "cunty", "cunt hair", "cunthair",
    "dick", "dicks", "dickhead", "dickface", "dickhole", "dickbag", "dickbrain", "dickcheese",
    "dickfuck", "dickjuice", "dickmuncher", "dicknose", "dickrider", "dickskin", "dickstain",
    "dickwad", "dickweed", "dickwhip", "dickwobble", "dickwomble", "dickless", "dickbeater",
    "dickbreath", "dickheadfuck", "dickpic", "dick pic", "pussy", "pussies", "pussyass",
    "pussybeater", "pussyblaster", "pussycake", "pussycanyon", "pussydestroyer", "pussyfart",
    "pussyfuck", "pussyhole", "pussylicker", "pussylips", "pussymuncher", "pussypounder",
    "pussyslapper", "pussywagon", "pussywhipped", "pussy whipped", "pussyboy", "pussylover",
    "cock", "cocks", "cockass", "cockbag", "cockbite", "cockblaster", "cockblocker",
    "cockboy", "cockburger", "cockcage", "cockcamel", "cockcheese", "cockcrap", "cockdick",
    "cockdrinker", "cockduster", "cockeater", "cockface", "cockfarm", "cockgag", "cockgobbler",
    "cockgoblin", "cockgrinder", "cockhead", "cockhound", "cockjockey", "cockjug", "cockjunkie",
    "cocklicker", "cocklips", "cocklodger", "cockmonger", "cockmonster", "cockmouth",
    "cockmuncher", "cocknugget", "cockpipe", "cockpisser", "cockpleaser", "cockrider",
    "cockshaft", "cockshiner", "cockslap", "cockslug", "cocksmith", "cocksmoker", "cocksniffer",
    "cocksplash", "cocksucker", "cocksucking", "cocktart", "cocktease", "cockthrottle",
    "cocktipper", "cocktip", "cockwaffle", "cockwank", "cockwhore", "cockwobble", "cockwomble",
    "ass", "arse", "asshole", "assholes", "arsehole", "arseholes", "asshat", "asswipe",
    "arsewipe", "assclown", "assfuck", "assgoblin", "asshead", "asslicker", "assmunch",
    "assnugget", "asspirate", "assrammer", "assbang", "assblaster", "assburger", "asscheek",
    "asscock", "asscunt", "assdick", "assface", "assfaggot", "arselicker", "butthole",
    "butthurt", "buttfuck", "buttfucker", "knobhead", "knob head", "knobber", "bellend",
    "bell end", "bellendface", "twat", "twats", "twatface", "twatwaffle", "wanker", "wankers",
    "wank", "wanked", "wanking", "jerk off", "jerking off", "jack off", "jizz", "jizzed",
    "jizzface", "jizzstain", "boner", "hardon", "hard on", "nudes", "nude", "naked",
    "naked pics", "nakedpics", "nudity", "sex", "sexy", "seks", "sexytime", "sexchat",
    "sexting", "sextape", "sex tape", "porn", "porno", "pornos", "pornhub", "porntube",
    "xvideos", "xnxx", "redtube", "youporn", "pornstar", "porn stars", "pornsite", "onlyfans",
    "only fans", "fansly", "hentai", "hentaihub", "gonewild", "gone wild", "futanari",
    "futa", "loli", "lolicon", "shotacon", "shota", "pedo", "pedos", "pedophile", "pedophiles",
    "paedophile", "pederast", "nonce", "nonces", "child predator", "childpredator",
    "child molester", "child porn", "cp lover", "jailbait", "nude teens", "underage porn",
    "teen porn", "kid porn", "incest", "cuckold", "cuck", "cuckquean", "milf", "gilf",
    "hooker", "hookers", "tits", "titties", "tittie", "titty", "tittysucker", "titfuck",
    "titsucker", "boobs", "boobies", "boob job", "boobjob", "boobie", "boob tube",
    "masturbate", "masturbating", "masturbation", "cumming", "cumshot", "cum shot",
    "rape", "raped", "raping", "rapist", "rapists", "rapefuck", "rapeslut", "date rape",
    "gang rape", "rape victim blame", "kill yourself", "kill urself", "killyourself",
    "kill yourself please", "please kill yourself", "go kill yourself", "gokillyourself",
    "kys", "kms", "kyslmao", "end yourself", "endyourself", "off yourself", "offyourself",
    "neck yourself", "neckyourself", "rope yourself", "ropeyourself", "hang yourself",
    "hangyourself", "jump off a bridge", "jump off a cliff", "throw yourself off",
    "throw yourself in front of a train", "slit your wrists", "slit your throat",
    "cut yourself", "cutyourself", "self harm", "selfharm", "self-harm", "self delete",
    "selfdelete", "delete yourself", "deleteyourself", "uninstall life", "commit suicide",
    "commitsuicide", "you should die", "you should just die", "you deserve to die",
    "die in a fire", "burn in hell", "rot in hell", "go die", "go die in a hole",
    "die in a hole", "die", "go kys", "kys yourself", "noose yourself", "nooseyourself",
    "suicide", "suicidal", "unlive", "nazi", "nazis", "nazi scum", "nazifag", "hitler",
    "hitler lover", "hitler cunt", "heil hitler", "heilhitler", "sieg heil", "siegheil",
    "white power", "whitepower", "white supremacist", "1488", "14 88", "kkk",
    "ku klux klan", "klansman", "stormfront", "holohoax", "hoaxocaust", "auschwitz party",
    "final solution", "german reich", "heil", "hail hitler", "bhenchod", "madarchod",
    "bhosdike", "chutiya", "chut", "gaand", "gandu", "haramzada", "randi", "rand",
    "lund", "bhadwa", "bhen ke", "orospu", "yarrak", "sikik", "puto", "puta", "maricon",
    "pendejo", "cabron", "chingada", "verga", "pinche", "hijo de puta", "zorra",
    "imposter whore", "wind up whore", "fuck you", "bastard", "bastards", "bastardfuck",
    "dumbass", "dumbasses", "dumbfuck", "dumbassfuck", "jackass", "jackasses", "jackassfuck",
    "cum", "cums", "cumfuck", "shut the fuck up", "shut up retard",
    "stfu", "gtfo", "retard alert", "r slur", "t slur", "f slur", "n slur",
]
LEET_CHARS = {
    "i": "1!|i",
    "o": "0o",
    "e": "3e",
    "a": "4@a",
    "s": "5$s",
    "t": "7+t",
    "b": "8b",
    "g": "96g",
    "l": "1|l",
}


def build_word_pattern(word):
    groups = []
    for ch in word:
        chars = LEET_CHARS.get(ch, re.escape(ch))
        groups.append(f"[{chars}]{{1,3}}")
    return r"[\s.\-_,*|]*".join(groups)


BAD_WORD_RE = re.compile(r"\b(" + "|".join(build_word_pattern(w) for w in BAD_WORDS) + r")\b", re.IGNORECASE)

WATCHER_PERMS = dict(
    view_channel=True,
    read_message_history=True,
    create_instant_invite=True,
    add_reactions=True,
    send_messages=False,
)

WHITELIST_USER_IDS = set()
WHITELIST_ROLE_IDS = set()
WELCOME_ROLE_ID = None
AUTO_RESPONSES = {}
LINK_WHITELIST = set()

DEFAULT_LINK_WHITELIST = {
    "gofile.io", "tenor.com", "giphy.com", "clipy.com", "gfycat.com",
    "imgur.com", "cdn.discordapp.com",
}

TICKET_CONFIG = {}
TICKET_MEMBER_PERMS = dict(
    view_channel=True, read_message_history=True, send_messages=True,
    attach_files=True, embed_links=True, add_reactions=True,
    use_external_emojis=True, use_external_stickers=True,
    use_application_commands=True, create_public_threads=True,
    create_private_threads=True, send_messages_in_threads=True,
    mention_everyone=False, manage_webhooks=False,
)

AUDIT_CHANNEL_NAME = "bot-logs"
BACKUP_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot-backup.json")
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot-config.json")
ROOM_INACTIVE_DAYS = 14
CLEANUP_INTERVAL = 12 * 3600

raiding = False
locked_channels = []
channel_raid_protection = True
spam_detection = True
antibot = True
badwords_filter = True
antilink = True
audit_channel_id = None


def is_trusted():
    async def predicate(interaction: discord.Interaction):
        return (
            interaction.user.id == OWNER_ID
            or interaction.user.id in WHITELIST_USER_IDS
            or any(r.id in WHITELIST_ROLE_IDS for r in interaction.user.roles)
        )

    return app_commands.check(predicate)


def is_whitelisted(member):
    if member.id == OWNER_ID or member.id in WHITELIST_USER_IDS:
        return True
    if member.guild_permissions.administrator:
        return True
    return any(r.id in WHITELIST_ROLE_IDS for r in member.roles)


def save_config():
    data = {
        "channel_raid_protection": channel_raid_protection,
        "spam_detection": spam_detection,
        "spam_window": spam_window,
        "spam_count": spam_count,
        "spam_mute_minutes": spam_mute_minutes,
        "spam_ban_offenses": spam_ban_offenses,
        "raid_slowmode": RAID_SLOWMODE,
        "ai_channel_id": AI_CHANNEL_ID,
        "antibot": antibot,
        "badwords_filter": badwords_filter,
        "antilink": antilink,
        "welcome_role_id": WELCOME_ROLE_ID,
        "auto_responses": AUTO_RESPONSES,
        "link_whitelist": sorted(LINK_WHITELIST),
        "whitelist_users": sorted(WHITELIST_USER_IDS),
        "whitelist_roles": sorted(WHITELIST_ROLE_IDS),
        "room_inactive_days": ROOM_INACTIVE_DAYS,
        "audit_channel_id": audit_channel_id,
    }
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_config():
    global channel_raid_protection, spam_detection, antibot, badwords_filter, antilink
    global spam_window, spam_count, spam_mute_minutes, spam_ban_offenses, RAID_SLOWMODE
    global AI_CHANNEL_ID
    global WELCOME_ROLE_ID, AUTO_RESPONSES, LINK_WHITELIST, WHITELIST_USER_IDS, WHITELIST_ROLE_IDS
    global ROOM_INACTIVE_DAYS, audit_channel_id
    if not os.path.exists(CONFIG_FILE):
        return False
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    channel_raid_protection = data.get("channel_raid_protection", True)
    spam_detection = data.get("spam_detection", True)
    spam_window = data.get("spam_window", 5)
    spam_count = data.get("spam_count", 5)
    spam_mute_minutes = data.get("spam_mute_minutes", 10)
    spam_ban_offenses = data.get("spam_ban_offenses", 3)
    RAID_SLOWMODE = data.get("raid_slowmode", 0)
    AI_CHANNEL_ID = data.get("ai_channel_id")
    antibot = data.get("antibot", True)
    badwords_filter = data.get("badwords_filter", True)
    antilink = data.get("antilink", True)
    WELCOME_ROLE_ID = data.get("welcome_role_id")
    AUTO_RESPONSES = dict(data.get("auto_responses", {}))
    LINK_WHITELIST = set(data.get("link_whitelist", []))
    WHITELIST_USER_IDS = set(data.get("whitelist_users", []))
    WHITELIST_ROLE_IDS = set(data.get("whitelist_roles", []))
    ROOM_INACTIVE_DAYS = data.get("room_inactive_days", 14)
    audit_channel_id = data.get("audit_channel_id")
    return True


ROOM_PREFIX = "room-"
MARKET_PREFIX = "examples-marketplace-"


def is_private_room(channel):
    return (
        channel is not None
        and channel.category is not None
        and (channel.name.startswith(ROOM_PREFIX) or channel.name.startswith(MARKET_PREFIX))
    )


async def announce(guild, text):
    channel = guild.system_channel
    if channel is None or not channel.permissions_for(guild.me).send_messages:
        for ch in guild.text_channels:
            if ch.permissions_for(guild.me).send_messages:
                channel = ch
                break
    if channel is not None:
        try:
            await channel.send(text)
        except discord.HTTPException:
            pass


async def audit(guild, text):
    global audit_channel_id
    channel = guild.get_channel(audit_channel_id) if audit_channel_id else None
    if channel is None:
        channel = discord.utils.get(guild.text_channels, name=AUDIT_CHANNEL_NAME)
        if channel is None and guild.me.guild_permissions.manage_channels:
            try:
                channel = await guild.create_text_channel(AUDIT_CHANNEL_NAME, reason="Audit log")
            except discord.HTTPException:
                channel = None
        audit_channel_id = channel.id if channel else None
    if channel is not None and channel.permissions_for(guild.me).send_messages:
        try:
            await channel.send(f"`{datetime.datetime.now(datetime.timezone.utc).strftime('%H:%M')}` {text}")
        except discord.HTTPException:
            pass


async def lockdown_guild(guild):
    global locked_channels
    locked_channels = []
    default_role = guild.default_role
    tasks = []
    for channel in guild.channels:
        if not isinstance(channel, discord.TextChannel) and not isinstance(channel, discord.VoiceChannel):
            continue
        if not channel.permissions_for(guild.me).manage_channels:
            continue
        original = channel.overwrites_for(default_role)
        tasks.append(
            channel.set_permissions(
                default_role, send_messages=False, connect=False, reason="Raid lockdown"
            )
        )
        locked_channels.append((channel.id, original))
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    try:
        await guild.edit(verification_level=discord.VerificationLevel.high, reason="Raid lockdown")
    except discord.HTTPException:
        pass


async def unlock_guild(guild):
    global locked_channels
    default_role = guild.default_role
    tasks = []
    for channel_id, original in locked_channels:
        channel = guild.get_channel(channel_id)
        if channel is None:
            continue
        if not channel.permissions_for(guild.me).manage_channels:
            continue
        overwrite = original if not original.is_empty() else None
        tasks.append(
            channel.set_permissions(default_role, overwrite=overwrite, reason="Raid lockdown lifted")
        )
    locked_channels = []
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    for channel_id, delay in RAID_SLOWMODE_SAVED.items():
        channel = guild.get_channel(channel_id)
        if channel is not None:
            try:
                await channel.edit(slowmode_delay=delay, reason="Raid lockdown lifted")
            except discord.HTTPException:
                pass
    RAID_SLOWMODE_SAVED.clear()
    try:
        await guild.edit(verification_level=discord.VerificationLevel.low, reason="Raid lockdown lifted")
    except discord.HTTPException:
        pass


async def trigger_raid(guild, reason):
    global raiding
    raiding = True
    await announce(guild, f":rotating_light: **RAID DETECTED** ({reason}). Locking down the server. New joins will be kicked until it is safe.")
    await audit(guild, f":rotating_light: RAID triggered: {reason}")
    await lockdown_guild(guild)
    if RAID_SLOWMODE > 0:
        for ch in guild.text_channels:
            try:
                if ch.slowmode_delay != RAID_SLOWMODE:
                    RAID_SLOWMODE_SAVED[ch.id] = ch.slowmode_delay
                    await ch.edit(slowmode_delay=RAID_SLOWMODE, reason="Raid lockdown slowmode")
            except discord.HTTPException:
                pass


def serialize_overwrites(channel):
    out = []
    for target, overwrite in channel.overwrites.items():
        allow, deny = overwrite.pair()
        out.append(
            {
                "id": str(target.id),
                "type": "role" if isinstance(target, discord.Role) else "member",
                "allow": allow.value,
                "deny": deny.value,
            }
        )
    return out


def serialize_guild(guild):
    data = {"roles": [], "channels": []}
    for role in guild.roles:
        if role.is_default() or role.is_bot_managed():
            continue
        data["roles"].append(
            {
                "id": str(role.id),
                "name": role.name,
                "color": role.color.value,
                "hoist": role.hoist,
                "mentionable": role.mentionable,
                "permissions": role.permissions.value,
            }
        )
    for channel in guild.channels:
        if isinstance(channel, discord.CategoryChannel):
            data["channels"].append({"type": "category", "name": channel.name, "overwrites": serialize_overwrites(channel)})
        elif isinstance(channel, discord.TextChannel):
            data["channels"].append(
                {
                    "type": "text",
                    "name": channel.name,
                    "category": channel.category.name if channel.category else None,
                    "topic": channel.topic,
                    "slowmode": channel.slowmode_delay,
                    "overwrites": serialize_overwrites(channel),
                }
            )
        elif isinstance(channel, discord.VoiceChannel):
            data["channels"].append(
                {
                    "type": "voice",
                    "name": channel.name,
                    "category": channel.category.name if channel.category else None,
                    "bitrate": channel.bitrate,
                    "overwrites": serialize_overwrites(channel),
                }
            )
    return data


async def apply_overwrites(channel, entry, guild, role_map):
    for ov in entry.get("overwrites", []):
        target = None
        if ov["type"] == "role":
            target = role_map.get(ov["id"])
            if target is None:
                try:
                    target = guild.get_role(int(ov["id"]))
                except (ValueError, OverflowError):
                    target = None
        else:
            try:
                target = guild.get_member(int(ov["id"]))
            except (ValueError, OverflowError):
                target = None
        if target is None:
            continue
        try:
            await channel.set_permissions(
                target,
                overwrite=discord.PermissionOverwrite.from_pair(discord.Permissions(ov["allow"]), discord.Permissions(ov["deny"])),
                reason="Restore",
            )
        except discord.HTTPException:
            pass


async def restore_guild(guild, data):
    role_map = {}
    for r in data.get("roles", []):
        existing = discord.utils.get(guild.roles, name=r["name"])
        if existing:
            role_map[r["id"]] = existing
            continue
        try:
            new = await guild.create_role(
                name=r["name"],
                color=discord.Color(r["color"]),
                hoist=r.get("hoist", False),
                mentionable=r.get("mentionable", False),
                reason="Restore",
            )
            try:
                await new.edit(permissions=discord.Permissions(r["permissions"]), reason="Restore")
            except discord.HTTPException:
                pass
            role_map[r["id"]] = new
        except discord.HTTPException:
            pass

    created_categories = []
    for c in data.get("channels", []):
        try:
            if c["type"] == "category":
                category = discord.utils.get(guild.categories, name=c["name"])
                if category is None:
                    category = await guild.create_category(c["name"], reason="Restore")
                    created_categories.append(category.name)
                await apply_overwrites(category, c, guild, role_map)
            elif c["type"] == "text":
                category = discord.utils.get(guild.categories, name=c["category"]) if c.get("category") else None
                if c.get("category") and category is None:
                    category = await guild.create_category(c["category"], reason="Restore")
                existing = discord.utils.get(guild.text_channels, name=c["name"])
                if existing is None:
                    channel = await guild.create_text_channel(
                        c["name"],
                        category=category,
                        topic=c.get("topic"),
                        slowmode_delay=c.get("slowmode", 0),
                        reason="Restore",
                    )
                    await apply_overwrites(channel, c, guild, role_map)
            elif c["type"] == "voice":
                category = discord.utils.get(guild.categories, name=c["category"]) if c.get("category") else None
                if c.get("category") and category is None:
                    category = await guild.create_category(c["category"], reason="Restore")
                existing = discord.utils.get(guild.voice_channels, name=c["name"])
                if existing is None:
                    channel = await guild.create_voice_channel(c["name"], category=category, reason="Restore")
                    await apply_overwrites(channel, c, guild, role_map)
        except discord.HTTPException:
            continue
    return len(data.get("roles", [])), len(data.get("channels", []))


async def cleanup_rooms():
    for guild in bot.guilds:
        if ROOM_INACTIVE_DAYS <= 0:
            continue
        for ch in guild.text_channels:
            if not (ch.name.startswith(ROOM_PREFIX) or ch.name.startswith(MARKET_PREFIX)):
                continue
            try:
                last = None
                async for m in ch.history(limit=1):
                    last = m
                ref = last.created_at if last else ch.created_at
                if (discord.utils.utcnow() - ref).days >= ROOM_INACTIVE_DAYS:
                    await ch.delete(reason="Inactive room cleanup")
                    await audit(guild, f":broom: Deleted inactive room **{ch.name}** (no messages in {ROOM_INACTIVE_DAYS} days)")
            except discord.HTTPException:
                continue


async def create_private_channel(guild, creator, members, role, category, prefix, default_category_name):
    if category is None:
        category = discord.utils.get(guild.categories, name=default_category_name)
        if category is None:
            category = await guild.create_category(default_category_name)
        await category.set_permissions(guild.default_role, view_channel=False, reason="Private channel")
    name = (prefix + "-".join(m.name.lower() for m in members[:3]))[:100].rstrip("-")
    channel = await guild.create_text_channel(name, category=category)
    await channel.set_permissions(guild.default_role, view_channel=False, reason="Private channel")
    for m in members:
        await channel.set_permissions(m, view_channel=True, send_messages=True, reason="Private channel")
    if role is not None:
        await channel.set_permissions(role, **WATCHER_PERMS, reason="Watcher role")
    await channel.set_permissions(creator, view_channel=True, send_messages=True, reason="Private channel")
    await channel.set_permissions(guild.me, view_channel=True, send_messages=True, reason="Private channel")
    return channel


class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Open Ticket", style=discord.ButtonStyle.primary, custom_id="ticket_open", emoji="\U0001f3ab")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        cfg = TICKET_CONFIG
        if not cfg or cfg.get("guild_id") != guild.id:
            await interaction.response.send_message("Tickets aren't set up yet. Ask an admin to run /ticketsetup.", ephemeral=True)
            return
        open_category = guild.get_channel(cfg.get("open_category_id"))
        if not isinstance(open_category, discord.CategoryChannel):
            await interaction.response.send_message("The open-ticket category is missing.", ephemeral=True)
            return
        name = f"ticket-{interaction.user.name.lower()}"
        if discord.utils.get(open_category.text_channels, name=name):
            await interaction.response.send_message("You already have an open ticket.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        channel = await guild.create_text_channel(name, category=open_category, topic=str(interaction.user.id))
        await channel.set_permissions(guild.default_role, view_channel=False, send_messages=False, reason="Ticket")
        await channel.set_permissions(interaction.user, **TICKET_MEMBER_PERMS, reason="Ticket")
        support_role = guild.get_role(cfg.get("support_role_id"))
        if support_role is not None:
            await channel.set_permissions(support_role, **TICKET_MEMBER_PERMS, reason="Ticket support")
            await channel.send(f"{support_role.mention} {interaction.user.mention} opened a ticket and needs support.")
        await channel.send(
            f"Ticket opened by {interaction.user.mention}. Support will help you shortly.",
            view=CloseTicketView(),
        )
        await interaction.followup.send(f"Ticket opened: {channel.name}", ephemeral=True)


class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="ticket_close")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        cfg = TICKET_CONFIG
        if not cfg or cfg.get("guild_id") != guild.id:
            await interaction.response.send_message("Tickets aren't set up.", ephemeral=True)
            return
        closed_category = guild.get_channel(cfg.get("closed_category_id"))
        if not isinstance(closed_category, discord.CategoryChannel):
            await interaction.response.send_message("The closed-ticket category is missing.", ephemeral=True)
            return
        channel = interaction.channel
        if channel.category == closed_category:
            await interaction.response.send_message("This ticket is already closed.", ephemeral=True)
            return
        await interaction.response.defer()
        opener_id = None
        try:
            opener_id = int(channel.topic) if channel.topic else None
        except (ValueError, TypeError):
            opener_id = None
        if opener_id:
            opener = guild.get_member(opener_id)
            if opener is not None:
                await channel.set_permissions(opener, view_channel=True, send_messages=False, reason="Ticket closed")
        await channel.edit(category=closed_category, reason="Ticket closed")
        await channel.send(f":lock: Ticket closed by {interaction.user.mention}. Openers can no longer reply.")


async def room_cleanup_loop():
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            await cleanup_rooms()
        except Exception as e:
            print(e)
        await asyncio.sleep(CLEANUP_INTERVAL)


@bot.event
async def on_ready():
    if load_config():
        print("Loaded config from bot-config.json")
    for gid in (1536762391851696199, 1521614024587083908):
        guild = discord.Object(id=gid)
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
    bot.tree.clear_commands(guild=None)
    await bot.tree.sync()
    bot.loop.create_task(room_cleanup_loop())
    bot.ai_session = aiohttp.ClientSession()
    print(f"Logged in as {bot.user} ({bot.user.id}) - slash commands synced")


@bot.event
async def on_close():
    try:
        await bot.ai_session.close()
    except Exception:
        pass


@bot.event
async def on_member_join(member):
    if member.bot:
        if antibot and member.id != bot.user.id:
            try:
                await member.kick(reason="Unapproved bot join")
                await announce(member.guild, f":robot: Kicked unapproved bot **{member.name}**.")
                await audit(member.guild, f":robot: Kicked unapproved bot **{member.name}**")
            except discord.HTTPException:
                pass
        return

    if WELCOME_ROLE_ID:
        role = member.guild.get_role(WELCOME_ROLE_ID)
        if role is not None:
            try:
                await member.add_roles(role, reason="Welcome role")
            except discord.HTTPException:
                pass

    if raiding:
        try:
            await member.kick(reason="Join during raid lockdown")
        except discord.HTTPException:
            pass
        return

    now = time.monotonic()
    JOIN_LOG.append((now, member))
    recent = [m for t, m in JOIN_LOG if now - t <= RAID_JOIN_BUFFER]
    fresh = [m for t, m in recent if (now - t) <= RAID_JOIN_WINDOW]
    if len(fresh) >= RAID_JOIN_COUNT:
        await trigger_raid(member.guild, f"{len(fresh)} joins in {RAID_JOIN_WINDOW}s")


@bot.event
async def on_guild_channel_create(channel):
    if not channel_raid_protection:
        return
    guild = channel.guild
    now = time.monotonic()
    CHANNEL_CREATE_LOG.append((now, channel))
    fresh = [c for t, c in CHANNEL_CREATE_LOG if now - t <= CHANNEL_CREATE_WINDOW]
    if len(fresh) > CHANNEL_CREATE_COUNT:
        await announce(
            guild,
            f":rotating_light: **CHANNEL RAID DETECTED** - {len(fresh)} channels created in {CHANNEL_CREATE_WINDOW}s. Deleting them...",
        )
        await audit(guild, f":rotating_light: Channel raid: {len(fresh)} channels created in {CHANNEL_CREATE_WINDOW}s")
        deleted = 0
        for c in fresh:
            try:
                await c.delete(reason="Channel creation raid")
                deleted += 1
            except discord.HTTPException:
                pass
        await announce(guild, f":wastebasket: Deleted **{deleted}** channels created during the raid.")
        await audit(guild, f":wastebasket: Deleted {deleted} raided channels")


@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    content = message.content

    if not is_whitelisted(message.author):
        if DISCORD_INVITE_RE.search(content):
            try:
                await message.delete()
                await message.channel.send(f"{message.author.mention}, Discord invites aren't allowed here.", delete_after=5)
            except discord.HTTPException:
                pass

        if badwords_filter and BAD_WORD_RE.search(content):
            try:
                await message.delete()
                await message.channel.send(f"{message.author.mention}, that word isn't allowed here.", delete_after=5)
                await audit(message.guild, f":mute: Bad word from **{message.author}** deleted in #{message.channel.name}")
            except discord.HTTPException:
                pass

        if antilink:
            links = LINK_RE.findall(content)
            allowed = LINK_WHITELIST | DEFAULT_LINK_WHITELIST
            bad = [l for l in links if not any(d in l.lower() for d in allowed)]
            if bad:
                try:
                    await message.delete()
                    await message.channel.send(f"{message.author.mention}, links aren't allowed here.", delete_after=5)
                except discord.HTTPException:
                    pass

        if spam_detection:
            now = time.monotonic()
            log = MESSAGE_LOG[message.author.id]
            log.append(now)
            fresh = [t for t in log if now - t <= spam_window]
            MESSAGE_LOG[message.author.id] = deque(fresh, maxlen=100)
            if len(fresh) >= spam_count and message.guild.me.guild_permissions.moderate_members:
                SPAM_OFFENSES[message.author.id] += 1
                try:
                    if spam_ban_offenses > 0 and SPAM_OFFENSES[message.author.id] >= spam_ban_offenses:
                        await message.author.ban(reason=f"Repeated spam ({SPAM_OFFENSES[message.author.id]} offenses)")
                        await message.channel.send(f":hammer: **{message.author}** banned for repeated spam.")
                        await audit(message.guild, f":hammer: **{message.author}** banned for repeated spam ({SPAM_OFFENSES[message.author.id]} offenses)")
                    else:
                        await message.author.timeout(
                            discord.utils.utcnow() + datetime.timedelta(minutes=spam_mute_minutes),
                            reason="Spam detection",
                        )
                        await message.channel.send(f":mute: **{message.author}** muted for spamming.")
                except discord.HTTPException:
                    pass

    for trigger, response in AUTO_RESPONSES.items():
        if trigger in content.lower():
            try:
                await message.reply(response)
            except discord.HTTPException:
                pass
            break


@bot.tree.command(name="room", description="Create a private channel only for specific people")
@app_commands.describe(
    member="Who the channel is for",
    member2="Optional second person",
    member3="Optional third person",
    role="Optional role that can only WATCH (view, read history, invites, reactions)",
    category="Optional category to create the channel in",
)
@is_trusted()
async def room(interaction: discord.Interaction, member: discord.Member, member2: discord.Member = None, member3: discord.Member = None, role: discord.Role = None, category: discord.CategoryChannel = None):
    members = [m for m in (member, member2, member3) if m is not None]
    if not interaction.guild.me.guild_permissions.manage_channels:
        await interaction.response.send_message("I need the **Manage Channels** permission for this.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)

    channel = await create_private_channel(interaction.guild, interaction.user, members, role, category, ROOM_PREFIX, "Private Rooms")

    names = ", ".join(m.mention for m in members)
    await channel.send(f"Private channel for {names} created by {interaction.user.mention}.")
    await audit(interaction.guild, f":house: Room **{channel.name}** created by {interaction.user} for {', '.join(m.name for m in members)}")
    await interaction.followup.send(f"Done. {channel.mention}")


@bot.tree.command(name="marketplacecreate", description="Create a marketplace channel (same as a private room)")
@app_commands.describe(
    member="Who the channel is for",
    member2="Optional second person",
    member3="Optional third person",
    role="Optional role that can only WATCH (view, read history, invites, reactions)",
    category="Optional category to create the channel in",
)
@is_trusted()
async def marketplacecreate(interaction: discord.Interaction, member: discord.Member, member2: discord.Member = None, member3: discord.Member = None, role: discord.Role = None, category: discord.CategoryChannel = None):
    members = [m for m in (member, member2, member3) if m is not None]
    if not interaction.guild.me.guild_permissions.manage_channels:
        await interaction.response.send_message("I need the **Manage Channels** permission for this.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    channel = await create_private_channel(interaction.guild, interaction.user, members, role, category, MARKET_PREFIX, "Marketplace")
    names = ", ".join(m.mention for m in members)
    await channel.send(f"Marketplace channel for {names} created by {interaction.user.mention}.")
    await audit(interaction.guild, f":shopping_cart: Marketplace **{channel.name}** created by {interaction.user} for {', '.join(m.name for m in members)}")
    await interaction.followup.send(f"Done. {channel.mention}")


@bot.tree.command(name="roomadd", description="Add a user to your private room")
@app_commands.describe(member="User to add", channel="Room (defaults to current channel)")
@is_trusted()
async def roomadd(interaction: discord.Interaction, member: discord.Member, channel: discord.TextChannel = None):
    channel = channel or interaction.channel
    if not is_private_room(channel) or not channel.permissions_for(interaction.user).view_channel:
        await interaction.response.send_message("This isn't your private room.", ephemeral=True)
        return
    await channel.set_permissions(member, view_channel=True, send_messages=True, reason="Room add")
    await interaction.response.send_message(f"Added {member.mention} to {channel.mention}.", ephemeral=True)


@bot.tree.command(name="roomremove", description="Remove a user from your private room")
@app_commands.describe(member="User to remove", channel="Room (defaults to current channel)")
@is_trusted()
async def roomremove(interaction: discord.Interaction, member: discord.Member, channel: discord.TextChannel = None):
    channel = channel or interaction.channel
    if not is_private_room(channel) or not channel.permissions_for(interaction.user).view_channel:
        await interaction.response.send_message("This isn't your private room.", ephemeral=True)
        return
    await channel.set_permissions(member, overwrite=None, reason="Room remove")
    await interaction.response.send_message(f"Removed {member.mention} from {channel.mention}.", ephemeral=True)


@bot.tree.command(name="roomclose", description="Close and delete your private room")
@app_commands.describe(channel="Room (defaults to current channel)")
@is_trusted()
async def roomclose(interaction: discord.Interaction, channel: discord.TextChannel = None):
    channel = channel or interaction.channel
    if not is_private_room(channel) or not channel.permissions_for(interaction.user).manage_channels:
        await interaction.response.send_message("This isn't your private room.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    await audit(interaction.guild, f":house: Room **{channel.name}** closed by {interaction.user}")
    await channel.delete(reason="Room closed")
    await interaction.followup.send("Room deleted.")


@bot.tree.command(name="roomlist", description="Show who has access to a private room")
@app_commands.describe(channel="Room (defaults to current channel)")
@is_trusted()
async def roomlist(interaction: discord.Interaction, channel: discord.TextChannel = None):
    channel = channel or interaction.channel
    if not is_private_room(channel) or not channel.permissions_for(interaction.user).view_channel:
        await interaction.response.send_message("This isn't your private room.", ephemeral=True)
        return
    members = []
    roles = []
    for target, overwrite in channel.overwrites.items():
        if overwrite.view_channel:
            if isinstance(target, discord.Member):
                members.append(target.mention)
            elif isinstance(target, discord.Role):
                roles.append(target.mention)
    await interaction.response.send_message(
        f"**{channel.name}**\nMembers: {', '.join(members) if members else 'none'}\nRoles: {', '.join(roles) if roles else 'none'}",
        ephemeral=True,
    )


@bot.tree.command(name="watcheradd", description="Give a role watch-only access to a channel")
@app_commands.describe(role="Role to give watch-only access", channel="Channel (defaults to current channel)")
@is_trusted()
async def watcheradd(interaction: discord.Interaction, role: discord.Role, channel: discord.TextChannel = None):
    channel = channel or interaction.channel
    await channel.set_permissions(role, **WATCHER_PERMS, reason="Watcher role")
    await interaction.response.send_message(f"{role.mention} can now watch {channel.mention} but not type.", ephemeral=True)


@bot.tree.command(name="watcherremove", description="Remove watch-only access from a role")
@app_commands.describe(role="Role to remove", channel="Channel (defaults to current channel)")
@is_trusted()
async def watcherremove(interaction: discord.Interaction, role: discord.Role, channel: discord.TextChannel = None):
    channel = channel or interaction.channel
    await channel.set_permissions(role, overwrite=None, reason="Watcher role removed")
    await interaction.response.send_message(f"Removed watch-only access for {role.mention} on {channel.mention}.", ephemeral=True)


@bot.tree.command(name="ban", description="Ban a member")
@app_commands.describe(member="User to ban", reason="Ban reason")
@is_trusted()
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = None):
    if not interaction.guild.me.guild_permissions.ban_members:
        await interaction.response.send_message("I need the **Ban Members** permission for this.", ephemeral=True)
        return
    await member.ban(reason=reason or "Banned via command")
    await announce(interaction.guild, f":hammer: **{member}** banned by {interaction.user.mention}" + (f" - {reason}" if reason else ""))
    await audit(interaction.guild, f":hammer: **{member}** banned by {interaction.user}" + (f" - {reason}" if reason else ""))


@bot.tree.command(name="unban", description="Unban a user by ID")
@app_commands.describe(user_id="The user ID to unban", reason="Reason")
@is_trusted()
async def unban(interaction: discord.Interaction, user_id: str, reason: str = None):
    if not interaction.guild.me.guild_permissions.ban_members:
        await interaction.response.send_message("I need the **Ban Members** permission for this.", ephemeral=True)
        return
    try:
        user = await bot.fetch_user(int(user_id))
    except (discord.NotFound, discord.HTTPException, ValueError):
        await interaction.response.send_message("That doesn't look like a valid user ID.", ephemeral=True)
        return
    try:
        await interaction.guild.unban(user, reason=reason or "Unbanned via command")
        await audit(interaction.guild, f":hammer: **{user}** unbanned by {interaction.user}")
        await interaction.response.send_message(f"Unbanned {user}.", ephemeral=True)
    except discord.HTTPException:
        await interaction.response.send_message("Could not unban that user.", ephemeral=True)


@bot.tree.command(name="kick", description="Kick a member")
@app_commands.describe(member="User to kick", reason="Kick reason")
@is_trusted()
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = None):
    if not interaction.guild.me.guild_permissions.kick_members:
        await interaction.response.send_message("I need the **Kick Members** permission for this.", ephemeral=True)
        return
    await member.kick(reason=reason or "Kicked via command")
    await announce(interaction.guild, f":boot: **{member}** kicked by {interaction.user.mention}" + (f" - {reason}" if reason else ""))
    await audit(interaction.guild, f":boot: **{member}** kicked by {interaction.user}" + (f" - {reason}" if reason else ""))


@bot.tree.command(name="purge", description="Delete a number of messages in a channel")
@app_commands.describe(count="How many messages to delete (max 100)", channel="Channel (defaults to current channel)")
@is_trusted()
async def purge(interaction: discord.Interaction, count: int, channel: discord.TextChannel = None):
    channel = channel or interaction.channel
    count = max(1, min(count, 100))
    await interaction.response.defer(ephemeral=True)
    deleted = await channel.purge(limit=count)
    await interaction.followup.send(f"Deleted {len(deleted)} messages in {channel.mention}.")


@bot.tree.command(name="lockchannel", description="Lock a channel so no one can type")
@app_commands.describe(channel="Channel (defaults to current channel)")
@is_trusted()
async def lockchannel(interaction: discord.Interaction, channel: discord.TextChannel = None):
    channel = channel or interaction.channel
    await channel.set_permissions(interaction.guild.default_role, send_messages=False, reason="Channel lock")
    await interaction.response.send_message(f":lock: {channel.mention} locked.", ephemeral=True)


@bot.tree.command(name="unlockchannel", description="Unlock a channel")
@app_commands.describe(channel="Channel (defaults to current channel)")
@is_trusted()
async def unlockchannel(interaction: discord.Interaction, channel: discord.TextChannel = None):
    channel = channel or interaction.channel
    await channel.set_permissions(interaction.guild.default_role, overwrite=None, reason="Channel unlock")
    await interaction.response.send_message(f":unlock: {channel.mention} unlocked.", ephemeral=True)


@bot.tree.command(name="slowmode", description="Set slowmode on a channel")
@app_commands.describe(seconds="Seconds between messages (0 to disable)", channel="Channel (defaults to current channel)")
@is_trusted()
async def slowmode(interaction: discord.Interaction, seconds: int, channel: discord.TextChannel = None):
    channel = channel or interaction.channel
    seconds = max(0, min(seconds, 21600))
    await channel.edit(slowmode_delay=seconds)
    await interaction.response.send_message(
        f"Slowmode on {channel.mention}: {seconds}s" if seconds else f"Slowmode disabled on {channel.mention}.",
        ephemeral=True,
    )


@bot.tree.command(name="lock", description="Lock down the whole server (blocks sending everywhere)")
@is_trusted()
async def lock(interaction: discord.Interaction):
    if not interaction.guild.me.guild_permissions.manage_channels:
        await interaction.response.send_message("I need the **Manage Channels** permission for this.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    await lockdown_guild(interaction.guild)
    await announce(interaction.guild, ":lock: **Server locked down** manually by " + interaction.user.mention)
    await audit(interaction.guild, f":lock: Server locked down by {interaction.user}")
    await interaction.followup.send("Server locked down.")


@bot.tree.command(name="unlock", description="Lift the lockdown")
@is_trusted()
async def unlock(interaction: discord.Interaction):
    global raiding
    await interaction.response.defer(ephemeral=True)
    await unlock_guild(interaction.guild)
    raiding = False
    await announce(interaction.guild, ":unlock: **Lockdown lifted** by " + interaction.user.mention)
    await audit(interaction.guild, f":unlock: Lockdown lifted by {interaction.user}")
    await interaction.followup.send("Lockdown lifted.")


@bot.tree.command(name="endraid", description="End an active raid lockdown and unblock the server")
@is_trusted()
async def endraid(interaction: discord.Interaction):
    global raiding
    await interaction.response.defer(ephemeral=True)
    await unlock_guild(interaction.guild)
    raiding = False
    await announce(interaction.guild, ":white_check_mark: **Raid lockdown lifted** by " + interaction.user.mention)
    await audit(interaction.guild, f":white_check_mark: Raid lockdown lifted by {interaction.user}")
    await interaction.followup.send("Raid lockdown lifted.")


@bot.tree.command(name="raidprotection", description="Turn ON automatic channel-creation raid detection")
@is_trusted()
async def raidprotection_cmd(interaction: discord.Interaction):
    global channel_raid_protection
    channel_raid_protection = True
    await interaction.response.send_message(
        f"Channel raid protection **ON** - if more than {CHANNEL_CREATE_COUNT} channels are created within {CHANNEL_CREATE_WINDOW}s, they will be auto-deleted.",
        ephemeral=True,
    )


@bot.tree.command(name="raidprotectionoff", description="Turn OFF automatic channel-creation raid detection")
@is_trusted()
async def raidprotectionoff_cmd(interaction: discord.Interaction):
    global channel_raid_protection
    channel_raid_protection = False
    await interaction.response.send_message("Channel raid protection **OFF** - channels will no longer be auto-deleted.", ephemeral=True)


@bot.tree.command(name="spamdetect", description="Turn ON auto-mute for spammers")
@is_trusted()
async def spamdetect_cmd(interaction: discord.Interaction):
    global spam_detection
    spam_detection = True
    await interaction.response.send_message("Spam detection **ON** - users sending 5+ messages in 5s get a 10min mute.", ephemeral=True)


@bot.tree.command(name="spamdetectoff", description="Turn OFF auto-mute for spammers")
@is_trusted()
async def spamdetectoff_cmd(interaction: discord.Interaction):
    global spam_detection
    spam_detection = False
    await interaction.response.send_message("Spam detection **OFF**.", ephemeral=True)


@bot.tree.command(name="spamsettings", description="Configure spam detection")
@is_trusted()
async def spamsettings_cmd(
    interaction: discord.Interaction,
    count: app_commands.Range[int, 1, 50] = None,
    window: app_commands.Range[int, 1, 300] = None,
    mute_minutes: app_commands.Range[int, 1, 10080] = None,
    ban_offenses: app_commands.Range[int, 0, 10] = None,
):
    global spam_count, spam_window, spam_mute_minutes, spam_ban_offenses
    if count is not None:
        spam_count = count
    if window is not None:
        spam_window = window
    if mute_minutes is not None:
        spam_mute_minutes = mute_minutes
    if ban_offenses is not None:
        spam_ban_offenses = ban_offenses
    save_config()
    await interaction.response.send_message(
        f"Spam settings: **{spam_count} msgs** in **{spam_window}s** -> mute **{spam_mute_minutes}min** | ban after **{spam_ban_offenses}** offenses (0 = never).",
        ephemeral=True,
    )


@bot.tree.command(name="raidslowmode", description="Set channel slowmode applied during raid lockdown (0 = off)")
@is_trusted()
async def raidslowmode_cmd(interaction: discord.Interaction, seconds: app_commands.Range[int, 0, 21600]):
    global RAID_SLOWMODE
    RAID_SLOWMODE = seconds
    save_config()
    await interaction.response.send_message(
        f"Raid slowmode set to **{seconds}s** (0 = off).",
        ephemeral=True,
    )


@bot.tree.command(name="antibot", description="Turn ON auto-kick of bots that join unapproved")
@is_trusted()
async def antibot_cmd(interaction: discord.Interaction):
    global antibot
    antibot = True
    await interaction.response.send_message("Anti-bot **ON** - any bot joining will be kicked.", ephemeral=True)


@bot.tree.command(name="antibotoff", description="Turn OFF auto-kick of bots")
@is_trusted()
async def antibotoff_cmd(interaction: discord.Interaction):
    global antibot
    antibot = False
    await interaction.response.send_message("Anti-bot **OFF**.", ephemeral=True)


@bot.tree.command(name="welcomerole", description="Auto-assign a role to new members (no role = off)")
@app_commands.describe(role="Role to assign on join")
@is_trusted()
async def welcomerole(interaction: discord.Interaction, role: discord.Role = None):
    global WELCOME_ROLE_ID
    WELCOME_ROLE_ID = role.id if role else None
    await interaction.response.send_message(
        f"Welcome role set to {role.mention}." if role else "Welcome role disabled.",
        ephemeral=True,
    )


@bot.tree.command(name="autoresponse", description="Add an auto-response (word triggers a reply)")
@app_commands.describe(trigger="Word or phrase to trigger on", response="What the bot replies")
@is_trusted()
async def autoresponse(interaction: discord.Interaction, trigger: str, response: str):
    AUTO_RESPONSES[trigger.lower()] = response
    await interaction.response.send_message(f"Auto-response added: `{trigger}` -> {response}", ephemeral=True)


@bot.tree.command(name="autoresponseremove", description="Remove an auto-response")
@app_commands.describe(trigger="The trigger word to remove")
@is_trusted()
async def autoresponseremove(interaction: discord.Interaction, trigger: str):
    removed = AUTO_RESPONSES.pop(trigger.lower(), None)
    await interaction.response.send_message(
        f"Removed `{trigger}`." if removed else f"`{trigger}` isn't an auto-response.",
        ephemeral=True,
    )


@bot.tree.command(name="autoresponselist", description="List all auto-responses")
@is_trusted()
async def autoresponselist(interaction: discord.Interaction):
    if not AUTO_RESPONSES:
        await interaction.response.send_message("No auto-responses set.", ephemeral=True)
        return
    lines = "\n".join(f"`{k}` -> {v}" for k, v in AUTO_RESPONSES.items())
    await interaction.response.send_message(f"**Auto-responses:**\n{lines}", ephemeral=True)


@bot.tree.command(name="badwords", description="Turn ON bad word filter (deletes messages with profanity)")
@is_trusted()
async def badwords_cmd(interaction: discord.Interaction):
    global badwords_filter
    badwords_filter = True
    await interaction.response.send_message("Bad word filter **ON** - profanity gets deleted.", ephemeral=True)


@bot.tree.command(name="badwordsoff", description="Turn OFF bad word filter")
@is_trusted()
async def badwordsoff_cmd(interaction: discord.Interaction):
    global badwords_filter
    badwords_filter = False
    await interaction.response.send_message("Bad word filter **OFF**.", ephemeral=True)


@bot.tree.command(name="antilink", description="Turn ON link blocking (all links blocked unless whitelisted)")
@is_trusted()
async def antilink_cmd(interaction: discord.Interaction):
    global antilink
    antilink = True
    await interaction.response.send_message("Anti-link **ON** - links posted by non-whitelisted users get deleted.", ephemeral=True)


@bot.tree.command(name="antilinkoff", description="Turn OFF link blocking")
@is_trusted()
async def antilinkoff_cmd(interaction: discord.Interaction):
    global antilink
    antilink = False
    await interaction.response.send_message("Anti-link **OFF**.", ephemeral=True)


@bot.tree.command(name="linkwhitelist", description="Allow a domain through the link filter (e.g. youtube.com)")
@app_commands.describe(domain="Domain to allow")
@is_trusted()
async def linkwhitelist(interaction: discord.Interaction, domain: str):
    LINK_WHITELIST.add(domain.lower())
    await interaction.response.send_message(
        f"`{domain.lower()}` added to link whitelist. Current: {', '.join(sorted(LINK_WHITELIST)) if LINK_WHITELIST else 'none'}",
        ephemeral=True,
    )


@bot.tree.command(name="linkwhitelistremove", description="Remove a domain from the link whitelist")
@app_commands.describe(domain="Domain to remove")
@is_trusted()
async def linkwhitelistremove(interaction: discord.Interaction, domain: str):
    LINK_WHITELIST.discard(domain.lower())
    await interaction.response.send_message(
        f"`{domain.lower()}` removed. Current: {', '.join(sorted(LINK_WHITELIST)) if LINK_WHITELIST else 'none'}",
        ephemeral=True,
    )


@bot.tree.command(name="whitelist", description="Exempt a user or role from message protections (links, bad words, spam, invites)")
@app_commands.describe(target="User or role to exempt")
@is_trusted()
async def whitelist(interaction: discord.Interaction, target: Union[discord.Member, discord.Role]):
    if isinstance(target, discord.Role):
        WHITELIST_ROLE_IDS.add(target.id)
        await interaction.response.send_message(f"{target.mention} role is now whitelisted.", ephemeral=True)
    else:
        WHITELIST_USER_IDS.add(target.id)
        await interaction.response.send_message(f"{target.mention} is now whitelisted.", ephemeral=True)


@bot.tree.command(name="whitelistremove", description="Remove a user or role from the whitelist")
@app_commands.describe(target="User or role to un-exempt")
@is_trusted()
async def whitelistremove(interaction: discord.Interaction, target: Union[discord.Member, discord.Role]):
    if isinstance(target, discord.Role):
        WHITELIST_ROLE_IDS.discard(target.id)
        await interaction.response.send_message(f"{target.mention} role is no longer whitelisted.", ephemeral=True)
    else:
        WHITELIST_USER_IDS.discard(target.id)
        await interaction.response.send_message(f"{target.mention} is no longer whitelisted.", ephemeral=True)


config_group = app_commands.Group(name="config", description="Save, load or delete bot settings")


@config_group.command(name="create", description="Save all current settings to a config file")
@is_trusted()
async def config_create(interaction: discord.Interaction):
    save_config()
    await audit(interaction.guild, f":floppy_disk: Config saved by {interaction.user}")
    await interaction.response.send_message(
        f"Config saved to `{CONFIG_FILE}` - toggles, whitelists, welcome role, auto-responses, link whitelist and cleanup days.",
        ephemeral=True,
    )


@config_group.command(name="load", description="Load settings from the saved config file")
@is_trusted()
async def config_load(interaction: discord.Interaction):
    if load_config():
        await audit(interaction.guild, f":arrows_counterclockwise: Config loaded by {interaction.user}")
        await interaction.response.send_message("Config loaded - all settings restored.", ephemeral=True)
    else:
        await interaction.response.send_message("No config file found. Use `/config create` first.", ephemeral=True)


@config_group.command(name="delete", description="Delete the saved config file")
@is_trusted()
async def config_delete(interaction: discord.Interaction):
    if os.path.exists(CONFIG_FILE):
        os.remove(CONFIG_FILE)
        await interaction.response.send_message("Config file deleted.", ephemeral=True)
    else:
        await interaction.response.send_message("No config file found.", ephemeral=True)


bot.tree.add_command(config_group)


@bot.tree.command(name="ticketadd", description="Add a user to the current ticket")
@app_commands.describe(member="User to add to the ticket")
@is_trusted()
async def ticketadd(interaction: discord.Interaction, member: discord.Member):
    channel = interaction.channel
    if not channel.name.startswith("ticket-"):
        await interaction.response.send_message("Use this inside a ticket channel.", ephemeral=True)
        return
    guild = interaction.guild
    cfg = TICKET_CONFIG
    opener_id = None
    try:
        opener_id = int(channel.topic) if channel.topic else None
    except (ValueError, TypeError):
        opener_id = None
    support_role = guild.get_role(cfg.get("support_role_id")) if cfg else None
    is_support = support_role is not None and support_role in interaction.user.roles
    if not (
        interaction.user.id == OWNER_ID
        or interaction.user.guild_permissions.administrator
        or interaction.user.id == opener_id
        or is_support
    ):
        await interaction.response.send_message("Only the ticket owner or support can add people.", ephemeral=True)
        return
    await channel.set_permissions(member, **TICKET_MEMBER_PERMS, reason="Ticket add")
    await channel.send(f"{member.mention} was added to the ticket by {interaction.user.mention}.")
    await interaction.response.send_message(f"Added {member.mention} to the ticket.", ephemeral=True)


@bot.tree.command(name="ticketsetup", description="Set up the ticket system (categories, support role, panel location)")
@app_commands.describe(
    open_category="Category where opened tickets appear",
    closed_category="Category where closed tickets are moved to",
    support_role="Role that handles tickets",
    panel_channel="Channel where the Open Ticket button is posted",
)
@is_trusted()
async def ticketsetup(interaction: discord.Interaction, open_category: discord.CategoryChannel, closed_category: discord.CategoryChannel, support_role: discord.Role, panel_channel: discord.TextChannel):
    global TICKET_CONFIG
    old_panel = TICKET_CONFIG.get("panel_message_id")
    if old_panel:
        try:
            old_channel = interaction.guild.get_channel(TICKET_CONFIG.get("panel_channel_id"))
            if old_channel is not None:
                msg = await old_channel.fetch_message(old_panel)
                await msg.delete()
        except discord.HTTPException:
            pass
    TICKET_CONFIG = {
        "guild_id": interaction.guild.id,
        "open_category_id": open_category.id,
        "closed_category_id": closed_category.id,
        "support_role_id": support_role.id,
        "panel_channel_id": panel_channel.id,
        "panel_message_id": None,
    }
    msg = await panel_channel.send("\U0001f3ab **Need help?** Click the button below to open a ticket.", view=TicketView())
    TICKET_CONFIG["panel_message_id"] = msg.id
    await audit(interaction.guild, f"\U0001f3ab Ticket system set up by {interaction.user}")
    await interaction.response.send_message(
        f"Ticket system set up. Panel posted in {panel_channel.mention}.\n"
        f"Opened tickets: **{open_category.name}** | Closed tickets: **{closed_category.name}** | Support: **{support_role.name}**",
        ephemeral=True,
    )


@bot.tree.command(name="ticketpanel", description="Repost the Open Ticket button panel (uses existing setup)")
@is_trusted()
async def ticketpanel(interaction: discord.Interaction):
    cfg = TICKET_CONFIG
    if not cfg or cfg.get("guild_id") != interaction.guild.id:
        await interaction.response.send_message("Tickets aren't set up yet. Run /ticketsetup first.", ephemeral=True)
        return
    channel = interaction.guild.get_channel(cfg.get("panel_channel_id"))
    if not isinstance(channel, discord.TextChannel):
        await interaction.response.send_message("The panel channel is missing. Run /ticketsetup again.", ephemeral=True)
        return
    old_panel = cfg.get("panel_message_id")
    if old_panel:
        try:
            msg = await channel.fetch_message(old_panel)
            await msg.delete()
        except discord.HTTPException:
            pass
    msg = await channel.send("\U0001f3ab **Need help?** Click the button below to open a ticket.", view=TicketView())
    cfg["panel_message_id"] = msg.id
    await interaction.response.send_message(f"Panel reposted in {channel.mention}.", ephemeral=True)


@bot.tree.command(name="auditlog", description="Set which channel receives the bot's audit log")
@app_commands.describe(channel="Channel for logs")
@is_trusted()
async def auditlog(interaction: discord.Interaction, channel: discord.TextChannel):
    global audit_channel_id
    audit_channel_id = channel.id
    await interaction.response.send_message(f"Audit log set to {channel.mention}.", ephemeral=True)


@bot.tree.command(name="backup", description="Save the server's channels and roles to a backup file")
@is_trusted()
async def backup(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    data = serialize_guild(interaction.guild)
    with open(BACKUP_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    await audit(interaction.guild, f":floppy_disk: Backup saved by {interaction.user} ({len(data['roles'])} roles, {len(data['channels'])} channels)")
    await interaction.followup.send(f"Backup saved: {len(data['roles'])} roles, {len(data['channels'])} channels -> `{BACKUP_FILE}`")


@bot.tree.command(name="restore", description="Recreate missing channels and roles from the last backup")
@is_trusted()
async def restore(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if not os.path.exists(BACKUP_FILE):
        await interaction.followup.send("No backup file found. Run `/backup` first.", ephemeral=True)
        return
    try:
        with open(BACKUP_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        await interaction.followup.send(f"Could not read backup: {e}", ephemeral=True)
        return
    roles, channels = await restore_guild(interaction.guild, data)
    await audit(interaction.guild, f":arrows_counterclockwise: Restore run by {interaction.user}")
    await interaction.followup.send(f"Restore done. Missing items recreated: {roles} roles, {channels} channel entries. Existing channels were left alone.")


@bot.tree.command(name="cleanupdays", description="Set how many days a private room can be inactive before auto-delete (0 = off)")
@app_commands.describe(days="Days (0 disables auto-cleanup)")
@is_trusted()
async def cleanupdays(interaction: discord.Interaction, days: int):
    global ROOM_INACTIVE_DAYS
    ROOM_INACTIVE_DAYS = max(0, min(days, 365))
    await interaction.response.send_message(
        f"Room auto-cleanup: rooms inactive for **{ROOM_INACTIVE_DAYS}** days get deleted (checked every 12h)." if ROOM_INACTIVE_DAYS else "Room auto-cleanup **OFF**.",
        ephemeral=True,
    )


@bot.tree.command(name="cleanuprooms", description="Run the inactive-room cleanup right now")
@is_trusted()
async def cleanuprooms(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    before = {ch.id for ch in interaction.guild.text_channels if ch.name.startswith(ROOM_PREFIX) or ch.name.startswith(MARKET_PREFIX)}
    await cleanup_rooms()
    after = {ch.id for ch in interaction.guild.text_channels if ch.name.startswith(ROOM_PREFIX) or ch.name.startswith(MARKET_PREFIX)}
    removed = len(before - after)
    await interaction.followup.send(f"Cleanup done. Deleted **{removed}** inactive room(s).")


@bot.tree.command(name="raidstatus", description="Show all protection settings")
@is_trusted()
async def raidstatus(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"Raid mode: {'**ACTIVE** - server locked' if raiding else 'off'}\n"
        f"Channel raid protection: {'**ON**' if channel_raid_protection else '**OFF**'}\n"
        f"Spam detection: {'**ON**' if spam_detection else '**OFF**'} ({spam_count} msgs / {spam_window}s -> mute {spam_mute_minutes}min, ban after {spam_ban_offenses} offenses)\n"
        f"Raid slowmode: {'**ON** (' + str(RAID_SLOWMODE) + 's)' if RAID_SLOWMODE else '**OFF**'}\n"
        f"AI channel: {f'<#{AI_CHANNEL_ID}>' if AI_CHANNEL_ID else 'anywhere'}\n"
        f"Anti-bot: {'**ON**' if antibot else '**OFF**'}\n"
        f"Bad word filter: {'**ON**' if badwords_filter else '**OFF**'}\n"
        f"Anti-link: {'**ON**' if antilink else '**OFF**'}\n"
        f"Welcome role: {'**set**' if WELCOME_ROLE_ID else 'off'}\n"
        f"Whitelisted: {len(WHITELIST_USER_IDS)} users, {len(WHITELIST_ROLE_IDS)} roles\n"
        f"Auto-responses: {len(AUTO_RESPONSES)}\n"
        f"Room auto-cleanup: {'**ON** (' + str(ROOM_INACTIVE_DAYS) + ' days)' if ROOM_INACTIVE_DAYS else '**OFF**'}\n"
        f"Join trigger: {RAID_JOIN_COUNT}+ joins in {RAID_JOIN_WINDOW}s | Channel trigger: {CHANNEL_CREATE_COUNT}+ channels in {CHANNEL_CREATE_WINDOW}s",
        ephemeral=True,
    )


def fit(text, limit=1990):
    return text if len(text) <= limit else text[: limit - 3] + "..."


async def ai_call(messages, tools=None):
    payload = {"model": AI_MODEL, "messages": messages, "max_tokens": 700, "temperature": 0.7}
    if tools:
        payload["tools"] = tools
    headers = {"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"}
    try:
        async with bot.ai_session.post(
            "https://api.deepseek.com/chat/completions",
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=60),
        ) as resp:
            data = await resp.json()
            if resp.status != 200:
                return f"AI error: {data.get('error', {}).get('message', resp.status)}"
            return data["choices"][0]["message"]
    except Exception as e:
        print(f"AI error: {e}")
        return "AI is struggling right now, try again in a few seconds."


async def ai_generate(prompt, user_id):
    if not AI_ENABLED:
        return "AI is not set up yet. The owner needs to add an `AI_API_KEY` to the bot environment."
    if re.search(r"@(?:everyone|here)", prompt, re.IGNORECASE):
        return "No - I'm not going to ping @everyone or @here."
    memory = AI_MEMORY.setdefault(user_id, deque(maxlen=12))
    messages = [
        {"role": "system", "content": "You are a helpful assistant in a Discord server. Be friendly and concise."}
    ]
    for role, text in memory:
        messages.append({"role": role, "content": text})
    messages.append({"role": "user", "content": prompt})
    data = await ai_call(messages)
    if isinstance(data, str):
        return data
    reply = (data.get("content") or "").strip()
    reply = reply.replace("@everyone", "everyone").replace("@here", "here")
    memory.append(("user", prompt))
    memory.append(("assistant", reply))
    return fit(reply)


ADMIN_SYSTEM = (
    "You are the moderation assistant for this Discord server, working for the server owner's team. "
    "You have tools to view server data and fully manage it: search members, list channels/roles/stats, "
    "moderate members (ban, kick, timeout, unban, set nickname), manage roles (create, rename, delete, "
    "grant/remove to members, set role permissions list_roles create_role rename_role delete_role set_role_permissions grant_role remove_role), "
    "manage channels (create, rename, delete, set slowmode) and send or purge messages in channels. "
    "Use search_members to find a member's exact user id and list_roles/list_channels for ids before acting on them. "
    "The owner, the bot itself, admins and whitelisted staff are protected - tools refuse to moderate them, respect that. "
    "Never use @everyone or @here. Keep replies short and state clearly what you did."
)


def admin_resolve_member(guild, member_id, query):
    tid = (member_id or "").strip()
    if tid:
        try:
            member = guild.get_member(int(tid))
            if member:
                return member
        except ValueError:
            pass
    q = (query or tid).lower().strip()
    if not q:
        return None
    matches = [
        m for m in guild.members
        if m.name.lower() == q or m.display_name.lower() == q or str(m.id) == q
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        return "AMBIGUOUS"
    return None


def admin_protected(member):
    return member.id == OWNER_ID or member.id == bot.user.id or is_whitelisted(member)


def parse_color(value):
    if not value:
        return None
    try:
        return discord.Color(int(str(value).strip().lstrip("#"), 16))
    except ValueError:
        return None


def parse_permissions(value):
    valid = set(discord.Permissions.VALID_FLAGS)
    names = [n.strip().lower() for n in str(value).split(",") if n.strip()]
    return [n for n in names if n in valid], [n for n in names if n not in valid]


def scrub_mentions(text):
    return text.replace("@everyone", "everyone").replace("@here", "here").replace("<@&", "@")


def resolve_member_arg(guild, args):
    member = admin_resolve_member(guild, args.get("member_id", ""), args.get("query"))
    if member == "AMBIGUOUS":
        return None, "Multiple members match - use search_members to get the exact user id."
    if member is None:
        return None, "Member not found - use search_members to get the exact user id."
    return member, None


def resolve_role(guild, role_id, query):
    tid = (role_id or "").strip()
    if tid:
        try:
            role = guild.get_role(int(tid))
            if role:
                return role, None
        except ValueError:
            pass
    q = (query or tid or "").lower().strip()
    if not q:
        return None, "Provide a role id or name."
    matches = [r for r in guild.roles if r.name.lower() == q]
    if len(matches) == 1:
        return matches[0], None
    if len(matches) > 1:
        return None, "Multiple roles match - be more specific."
    return None, "Role not found."


def resolve_channel(guild, channel_id, query):
    tid = (channel_id or "").strip()
    if tid:
        try:
            channel = guild.get_channel_or_thread(int(tid))
            if channel:
                return channel, None
        except ValueError:
            pass
    q = (query or tid or "").lower().strip()
    if not q:
        return None, "Provide a channel id or name."
    matches = [c for c in guild.channels if c.name.lower() == q]
    if len(matches) == 1:
        return matches[0], None
    if len(matches) > 1:
        return None, "Multiple channels match - be more specific."
    return None, "Channel not found."


async def run_admin_tool(guild, name, args):
    if name == "search_members":
        q = (args.get("query") or "").lower().strip()
        if not q:
            return "Provide a query."
        matches = [m for m in guild.members if q in m.name.lower() or q in (m.display_name or m.name).lower() or q == str(m.id)]
        if not matches:
            return "No members found."
        lines = [
            f"- id={m.id} | {m.name} | display: {m.display_name} | bot: {m.bot}"
            for m in matches[:10]
        ]
        if len(matches) > 10:
            lines.append(f"... and {len(matches) - 10} more")
        return "\n".join(lines)
    if name == "list_channels":
        lines = [
            f"- id={c.id} | #{c.name} | {str(c.type).split('.')[-1]}"
            for c in guild.channels[:40]
        ]
        return "\n".join(lines) or "No channels."
    if name == "server_stats":
        bots = sum(1 for m in guild.members if m.bot)
        return (
            f"Members: {guild.member_count} (bots: {bots})\n"
            f"Text channels: {len(guild.text_channels)} | Voice: {len(guild.voice_channels)} | Categories: {len(guild.categories)}\n"
            f"Roles: {len(guild.roles)} | Boosts: {guild.premium_subscription_count}\n"
            f"Owner: {guild.owner} (id={guild.owner_id})"
        )
    if name == "list_roles":
        lines = [
            f"- id={r.id} | {r.name} | color: #{r.color.value:06x} | hoist: {r.hoist} | mentionable: {r.mentionable}"
            for r in sorted(guild.roles, key=lambda r: r.position, reverse=True)[:40]
        ]
        return "\n".join(lines) or "No roles."
    if name == "create_role":
        rname = (args.get("name") or "").strip()[:32]
        if not rname:
            return "Provide a role name."
        try:
            role = await guild.create_role(
                name=rname,
                color=parse_color(args.get("color")),
                hoist=bool(args.get("hoist")),
                mentionable=bool(args.get("mentionable")),
                reason="AI admin: create role",
            )
        except discord.HTTPException as e:
            return f"Failed to create role: {e}"
        await audit(guild, f":label: AI admin created role **{role.name}** (id={role.id})")
        return f"Created role **{role.name}** (id={role.id})."
    if name == "rename_role":
        target, err = resolve_role(guild, args.get("role_id"), args.get("query"))
        if err:
            return err
        new = (args.get("name") or "").strip()[:32]
        if not new:
            return "Provide a new name."
        await target.edit(name=new, reason="AI admin: rename role")
        await audit(guild, f":label: AI admin renamed role (id={target.id}) to **{new}**")
        return f"Renamed role (id={target.id}) to **{new}**."
    if name == "delete_role":
        target, err = resolve_role(guild, args.get("role_id"), args.get("query"))
        if err:
            return err
        if target.is_default() or target.is_bot_managed() or target == guild.premium_subscriber_role:
            return "Refused: cannot delete that role."
        await target.delete(reason="AI admin: delete role")
        await audit(guild, f":wastebasket: AI admin deleted role **{target.name}**")
        return f"Deleted role **{target.name}**."
    if name == "set_role_permissions":
        target, err = resolve_role(guild, args.get("role_id"), args.get("query"))
        if err:
            return err
        valid, invalid = parse_permissions(args.get("permissions") or "")
        if not valid and invalid:
            return f"Unknown permission names: {', '.join(invalid)}. Valid: {', '.join(sorted(discord.Permissions.VALID_FLAGS))}"
        perms = target.permissions
        for p in valid:
            setattr(perms, p, True)
        await target.edit(permissions=perms, reason="AI admin: set role permissions")
        await audit(guild, f":shield: AI admin granted role **{target.name}** permissions: {', '.join(valid) or 'none'}")
        return f"Granted {target.name}: {', '.join(valid) or 'no new permissions'}"
    if name == "grant_role":
        member, err = resolve_member_arg(guild, args)
        if err:
            return err
        target, err2 = resolve_role(guild, args.get("role_id"), args.get("role_query"))
        if err2:
            return err2
        await member.add_roles(target, reason="AI admin: grant role")
        await audit(guild, f":label: AI admin gave **{member}** role **{target.name}**")
        return f"Gave **{member}** the role **{target.name}**."
    if name == "remove_role":
        member, err = resolve_member_arg(guild, args)
        if err:
            return err
        if admin_protected(member):
            return f"Refused: **{member}** is protected (owner/bot/admin/whitelisted)."
        target, err2 = resolve_role(guild, args.get("role_id"), args.get("role_query"))
        if err2:
            return err2
        await member.remove_roles(target, reason="AI admin: remove role")
        await audit(guild, f":label: AI admin removed **{target.name}** from **{member}**")
        return f"Removed **{target.name}** from **{member}**."
    if name == "create_channel":
        cname = (args.get("name") or "").strip()[:32]
        if not cname:
            return "Provide a channel name."
        ctype = (args.get("type") or "text").lower()
        ct = {
            "text": discord.ChannelType.text,
            "voice": discord.ChannelType.voice,
            "category": discord.ChannelType.category,
        }.get(ctype)
        if ct is None:
            return "Channel type must be text, voice or category."
        cat = None
        if args.get("category"):
            cat = next((c for c in guild.categories if c.name.lower() == args["category"].lower()), None)
        try:
            ch = await guild.create_channel(name=cname, channel_type=ct, category=cat, reason="AI admin: create channel")
        except discord.HTTPException as e:
            return f"Failed to create channel: {e}"
        await audit(guild, f":construction: AI admin created channel **#{ch.name}** (id={ch.id})")
        return f"Created channel **#{ch.name}** (id={ch.id})."
    if name == "rename_channel":
        ch, err = resolve_channel(guild, args.get("channel_id"), args.get("query"))
        if err:
            return err
        new = (args.get("name") or "").strip()[:32]
        if not new:
            return "Provide a new name."
        await ch.edit(name=new, reason="AI admin: rename channel")
        await audit(guild, f":construction: AI admin renamed #{ch.id} to **#{new}**")
        return f"Renamed channel (id={ch.id}) to **#{new}**."
    if name == "delete_channel":
        ch, err = resolve_channel(guild, args.get("channel_id"), args.get("query"))
        if err:
            return err
        await ch.delete(reason="AI admin: delete channel")
        await audit(guild, f":wastebasket: AI admin deleted channel **#{ch.name}**")
        return f"Deleted channel **#{ch.name}**."
    if name == "set_slowmode":
        ch, err = resolve_channel(guild, args.get("channel_id"), args.get("query"))
        if err:
            return err
        seconds = max(0, min(int(args.get("seconds") or 0), 21600))
        await ch.edit(slowmode_delay=seconds, reason="AI admin: set slowmode")
        return f"Set slowmode of #{ch.name} to {seconds}s."
    if name == "send_message":
        ch, err = resolve_channel(guild, args.get("channel_id"), args.get("query"))
        if err:
            return err
        text = (args.get("text") or "").strip()[:1900]
        if not text:
            return "Provide text."
        try:
            await ch.send(scrub_mentions(text))
        except discord.HTTPException as e:
            return f"Failed to send: {e}"
        await audit(guild, f":speech_balloon: AI admin sent a message in #{ch.name}")
        return f"Sent the message in #{ch.name}."
    if name == "purge_messages":
        ch, err = resolve_channel(guild, args.get("channel_id"), args.get("query"))
        if err:
            return err
        count = max(1, min(int(args.get("count") or 5), 100))
        try:
            await ch.purge(limit=count, reason="AI admin: purge")
        except discord.HTTPException as e:
            return f"Purge failed: {e}"
        return f"Purged up to {count} messages from #{ch.name}."
    if name == "set_nickname":
        member, err = resolve_member_arg(guild, args)
        if err:
            return err
        if admin_protected(member):
            return f"Refused: **{member}** is protected (owner/bot/admin/whitelisted)."
        nick = (args.get("nickname") or "").strip()[:32]
        await member.edit(nick=nick or None, reason="AI admin: set nickname")
        await audit(guild, f":pencil: AI admin set **{member}**'s nickname to **{nick or 'none'}**")
        return f"Set **{member}**'s nickname to **{nick or 'none'}**."
    if name == "unban_member":
        mid = (args.get("member_id") or "").strip()
        reason = (args.get("reason") or "AI admin action").strip()[:300]
        try:
            await guild.unban(discord.Object(id=int(mid)), reason=reason)
            await audit(guild, f":unlock: AI admin unbanned user **{mid}** - {reason}")
            return f"Unbanned user id={mid}."
        except (discord.HTTPException, ValueError) as e:
            return f"Unban failed: {e}"
    member = admin_resolve_member(guild, args.get("member_id", ""), args.get("query"))
    if member == "AMBIGUOUS":
        return "Multiple members match - use search_members to get the exact user id."
    if member is None:
        return "Member not found - use search_members to get the exact user id."
    if admin_protected(member):
        return f"Refused: **{member}** is protected (owner/bot/admin/whitelisted)."
    reason = (args.get("reason") or "AI admin action").strip()[:300]
    if name == "ban_member":
        await member.ban(reason=reason, delete_message_days=0)
        await audit(guild, f":hammer: AI admin banned **{member} ({member.id})** - {reason}")
        return f"Banned **{member}** (id={member.id}). Reason: {reason}"
    if name == "kick_member":
        await member.kick(reason=reason)
        await audit(guild, f":boot: AI admin kicked **{member} ({member.id})** - {reason}")
        return f"Kicked **{member}** (id={member.id}). Reason: {reason}"
    if name == "timeout_member":
        minutes = max(1, min(int(args.get("minutes") or 10), 10080))
        await member.timeout(discord.utils.utcnow() + datetime.timedelta(minutes=minutes), reason=reason)
        await audit(guild, f":mute: AI admin timed out **{member} ({member.id})** for {minutes}min - {reason}")
        return f"Timed out **{member}** (id={member.id}) for {minutes} minutes. Reason: {reason}"
    return "Unknown tool."


async def ai_admin_generate(prompt, interaction):
    if not AI_ENABLED:
        return "AI is not set up yet. The owner needs to add an `AI_API_KEY` to the bot environment."
    memory = AI_ADMIN_MEMORY[interaction.user.id]
    messages = [{"role": "system", "content": ADMIN_SYSTEM}]
    for role, text in memory:
        messages.append({"role": role, "content": text})
    messages.append({"role": "user", "content": prompt})
    for _ in range(6):
        data = await ai_call(messages, tools=ADMIN_TOOLS)
        if isinstance(data, str):
            return data
        if data.get("tool_calls"):
            messages.append({"role": "assistant", "content": data.get("content") or "", "tool_calls": data["tool_calls"]})
            for tc in data["tool_calls"]:
                fname = tc["function"]["name"]
                try:
                    targs = json.loads(tc["function"]["arguments"] or "{}")
                except json.JSONDecodeError:
                    targs = {}
                try:
                    result = await run_admin_tool(interaction.guild, fname, targs)
                except discord.HTTPException as e:
                    result = f"Discord error: {e}"
                messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})
            continue
        reply = (data.get("content") or "Done.").strip()
        reply = reply.replace("@everyone", "everyone").replace("@here", "here")
        memory.append(("user", prompt))
        memory.append(("assistant", reply))
        return fit(reply)
    return "That required too many steps - I stopped. Try a simpler request."


ADMIN_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_members",
            "description": "Search server members by name (or id) to find their exact user id.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "Name or id to search"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_channels",
            "description": "List all channels in the server with their ids.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "server_stats",
            "description": "Get server statistics: member count, channel count, roles, boosts.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ban_member",
            "description": "Ban a member by user id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "member_id": {"type": "string", "description": "User id from search_members"},
                    "reason": {"type": "string"},
                },
                "required": ["member_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "unban_member",
            "description": "Unban a user by their user id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "member_id": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["member_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "kick_member",
            "description": "Kick a member by user id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "member_id": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["member_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "timeout_member",
            "description": "Timeout (mute) a member for a number of minutes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "member_id": {"type": "string"},
                    "minutes": {"type": "integer", "minimum": 1, "maximum": 10080},
                    "reason": {"type": "string"},
                },
                "required": ["member_id", "minutes"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_roles",
            "description": "List all roles in the server with their ids, color and settings.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_role",
            "description": "Create a new role.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "color": {"type": "string", "description": "Hex color like #FF0000"},
                    "hoist": {"type": "boolean", "description": "Show role separately in member list"},
                    "mentionable": {"type": "boolean"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rename_role",
            "description": "Rename a role by id or name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "role_id": {"type": "string"},
                    "query": {"type": "string", "description": "Role name as alternative to role_id"},
                    "name": {"type": "string"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_role",
            "description": "Delete a role by id or name (protected roles are refused).",
            "parameters": {
                "type": "object",
                "properties": {
                    "role_id": {"type": "string"},
                    "query": {"type": "string", "description": "Role name as alternative to role_id"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_role_permissions",
            "description": "Grant permissions to a role. Pass comma-separated permission names like 'manage_messages, kick_members, manage_channels'. Only grants, never removes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "role_id": {"type": "string"},
                    "query": {"type": "string", "description": "Role name as alternative to role_id"},
                    "permissions": {"type": "string"},
                },
                "required": ["permissions"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grant_role",
            "description": "Grant a role to a member.",
            "parameters": {
                "type": "object",
                "properties": {
                    "member_id": {"type": "string"},
                    "query": {"type": "string", "description": "Member name as alternative to member_id"},
                    "role_id": {"type": "string"},
                    "role_query": {"type": "string", "description": "Role name as alternative to role_id"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_role",
            "description": "Remove a role from a member (protected members are refused).",
            "parameters": {
                "type": "object",
                "properties": {
                    "member_id": {"type": "string"},
                    "query": {"type": "string", "description": "Member name as alternative to member_id"},
                    "role_id": {"type": "string"},
                    "role_query": {"type": "string", "description": "Role name as alternative to role_id"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_channel",
            "description": "Create a text, voice or category channel.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "type": {"type": "string", "enum": ["text", "voice", "category"]},
                    "category": {"type": "string", "description": "Category name to place it under"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rename_channel",
            "description": "Rename a channel by id or name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel_id": {"type": "string"},
                    "query": {"type": "string", "description": "Channel name as alternative to channel_id"},
                    "name": {"type": "string"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_channel",
            "description": "Delete a channel by id or name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel_id": {"type": "string"},
                    "query": {"type": "string", "description": "Channel name as alternative to channel_id"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_slowmode",
            "description": "Set slowmode (seconds between messages) on a text channel.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel_id": {"type": "string"},
                    "query": {"type": "string", "description": "Channel name as alternative to channel_id"},
                    "seconds": {"type": "integer", "minimum": 0, "maximum": 21600},
                },
                "required": ["seconds"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_message",
            "description": "Send a message in a text channel. @everyone/@here mentions are scrubbed by the tool.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel_id": {"type": "string"},
                    "query": {"type": "string", "description": "Channel name as alternative to channel_id"},
                    "text": {"type": "string"},
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "purge_messages",
            "description": "Delete the most recent N messages in a text channel (max 100).",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel_id": {"type": "string"},
                    "query": {"type": "string", "description": "Channel name as alternative to channel_id"},
                    "count": {"type": "integer", "minimum": 1, "maximum": 100},
                },
                "required": ["count"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_nickname",
            "description": "Set a member's nickname (empty clears it). Protected members are refused.",
            "parameters": {
                "type": "object",
                "properties": {
                    "member_id": {"type": "string"},
                    "query": {"type": "string", "description": "Member name as alternative to member_id"},
                    "nickname": {"type": "string"},
                },
                "required": ["nickname"],
            },
        },
    },
]


ai_group = app_commands.Group(name="ai", description="AI commands")


@ai_group.command(name="chat", description="Ask the AI assistant anything")
async def ai_chat_cmd(interaction: discord.Interaction, message: str):
    if AI_CHANNEL_ID and interaction.channel_id != AI_CHANNEL_ID and not is_whitelisted(interaction.user):
        chan = interaction.guild.get_channel(AI_CHANNEL_ID) if interaction.guild else None
        await interaction.response.send_message(
            f"/ai chat can only be used in {chan.mention if chan else f'<#{AI_CHANNEL_ID}>'}.",
            ephemeral=True,
        )
        return
    if not is_whitelisted(interaction.user):
        now = time.monotonic()
        log = AI_USAGE[interaction.user.id]
        log.append(now)
        fresh = [t for t in log if now - t <= AI_WINDOW]
        AI_USAGE[interaction.user.id] = deque(fresh, maxlen=200)
        if len(fresh) > AI_LIMIT:
            await interaction.response.send_message(
                f"You've reached the **{AI_LIMIT} /ai chat uses per hour** limit. Try again later.",
                ephemeral=True,
            )
            return
    await interaction.response.defer()
    reply = await ai_generate(message, interaction.user.id)
    await interaction.followup.send(reply)


@ai_group.command(name="admin", description="AI admin: view members and moderate (ban/kick/timeout)")
@is_trusted()
async def ai_admin_cmd(interaction: discord.Interaction, message: str):
    await interaction.response.defer()
    reply = await ai_admin_generate(message, interaction)
    await interaction.followup.send(reply)


bot.tree.add_command(ai_group)


@bot.tree.command(name="aichat", description="Turn chat mode ON for this channel")
@is_trusted()
async def aichat_cmd(interaction: discord.Interaction):
    await interaction.response.send_message(
        "AI chat mode is **disabled** for now.", ephemeral=True
    )


setup_group = app_commands.Group(name="setup", description="Server setup commands")


@setup_group.command(name="ai", description="Restrict /ai to a specific channel (no channel = anywhere)")
@is_trusted()
async def setup_ai(interaction: discord.Interaction, channel: discord.TextChannel = None):
    global AI_CHANNEL_ID
    AI_CHANNEL_ID = channel.id if channel else None
    save_config()
    if channel:
        await interaction.response.send_message(f"/ai is now restricted to {channel.mention}.", ephemeral=True)
    else:
        await interaction.response.send_message("/ai can be used in any channel now.", ephemeral=True)


bot.tree.add_command(setup_group)


@bot.tree.error
async def on_app_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message("You don't have permission to use this.", ephemeral=True)
    else:
        print(error)  # noqa: E501


if __name__ == "__main__":
    bot.run(TOKEN)
