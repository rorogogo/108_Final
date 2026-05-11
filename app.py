from flask import Flask, request, render_template, render_template_string, redirect, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_session import Session
from sqlalchemy import text
from hashlib import sha256
import os
import random
import re
import string
import json
import itertools
from difflib import SequenceMatcher

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    from groq import Groq
except ImportError:
    Groq = None

if load_dotenv:
    load_dotenv()

app = Flask(__name__)

app.config["SECRET_KEY"] = "endfield-dev-secret"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///users.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config["GROQ_MODEL"] = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
app.config["GROQ_WEB_MODEL"] = os.getenv("GROQ_WEB_MODEL", "compound-beta-mini")
if app.config["GROQ_WEB_MODEL"] == "groq/compound-mini":
    app.config["GROQ_WEB_MODEL"] = "compound-beta-mini"
elif app.config["GROQ_WEB_MODEL"] == "groq/compound":
    app.config["GROQ_WEB_MODEL"] = "compound-beta"
app.config["GROQ_SEARCH_DOMAINS"] = [
    domain.strip()
    for domain in os.getenv(
        "GROQ_SEARCH_DOMAINS",
        "endfield.gryphline.com,www.gryphline.com,gryphline.com,endfield.wiki.gg,arknights.wiki.gg,web-static.hg-cdn.com"
    ).split(",")
    if domain.strip()
]

db = SQLAlchemy(app)
Session(app)

with open("data/characters.json") as f:
    CHARACTERS = json.load(f)

with open("data/teams.json") as f:
    PREBUILT_TEAMS = json.load(f)

with open("data/builds.json") as f:
    BUILD_GUIDES = json.load(f)

with open("data/weapons.json") as f:
    WEAPONS = json.load(f)

DEFAULT_CHARACTER_DATA = {
    char_id: data.get("owned", False)
    for char_id, data in CHARACTERS.items()
}
DEFAULT_CHARACTER_DATA["endmin"] = True
PUBLIC_CHARACTER_DATA = {
    char_id: True
    for char_id in CHARACTERS
}
DEFAULT_WEAPON_DATA = {
    weapon_id: False
    for weapon_id in WEAPONS
}
PUBLIC_WEAPON_DATA = {
    weapon_id: True
    for weapon_id in WEAPONS
}

def get_character(char_id):
    return CHARACTERS.get(char_id, None)

def get_weapon(weapon_id):
    return WEAPONS.get(weapon_id, None)

def get_weapon_data(user):
    if not user:
        return PUBLIC_WEAPON_DATA.copy()
    try:
        data = json.loads(user.weapon_data or "{}")
    except json.JSONDecodeError:
        data = {}
    return {
        weapon_id: bool(data.get(weapon_id, False))
        for weapon_id in WEAPONS
    }

def sort_weapons(weapons):
    return sorted(
        weapons,
        key=lambda weapon: (weapon.get("rarity", 0), weapon.get("base_atk", 0), weapon.get("id", "")),
        reverse=True
    )

def weapons_for_type(weapon_type):
    if not weapon_type:
        return []
    return sort_weapons([
        weapon
        for weapon in WEAPONS.values()
        if weapon.get("type") == weapon_type
    ])

def characters_for_weapon_type(weapon_type):
    return [
        {
            "id": char_id,
            "name": character.get("name", char_id),
            "image": character.get("image")
        }
        for char_id, character in CHARACTERS.items()
        if character.get("weapon_type") == weapon_type
    ]

def weapon_name(weapon_id):
    weapon = WEAPONS.get(weapon_id)
    if not weapon:
        return weapon_id
    return weapon.get("name") or weapon.get("id", weapon_id)

def normalize_label(value):
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()

def find_weapon_by_name(name):
    wanted = normalize_label(name)
    for weapon_id, weapon in WEAPONS.items():
        if normalize_label(weapon.get("name", weapon_id)) == wanted:
            return weapon_id, weapon
    return None, None

def weapon_text(weapon):
    return " ".join([
        weapon.get("name", ""),
        weapon.get("type_label", ""),
        " ".join(weapon.get("stats", []))
    ]).lower()

STAT_ALIASES = {
    "attack": ["attack", "atk"],
    "crit rate": ["critical rate", "crit rate"],
    "crit damage": ["critical damage", "crit damage"],
    "physical damage": ["physical dmg", "physical damage"],
    "heat damage": ["heat dmg", "heat damage", "combustion"],
    "cryo damage": ["cryo dmg", "cryo damage", "solidification"],
    "electric damage": ["electric dmg", "electric damage", "electrification"],
    "nature damage": ["nature dmg", "nature damage", "corrosion"],
    "arts damage": ["arts dmg", "arts damage"],
    "arts intensity": ["arts intensity"],
    "skill damage": ["skill dmg", "skill damage", "battle skill"],
    "ultimate damage": ["ultimate dmg", "ultimate damage", "ultimate"],
    "ultimate gain": ["ultimate gain", "ultimate gain efficiency"],
    "sp recovery": ["sp recovery", "skill sp"],
    "skill uptime": ["sp recovery", "ultimate gain", "battle skill"],
    "team damage": ["team", "allies", "ally"],
    "team attack": ["team atk", "allies atk", "team attack", "ally"],
    "support bonus": ["team", "allies", "healing", "shield", "treatment"],
    "healing": ["healing", "treatment", "hp treatment"],
    "treatment efficiency": ["treatment efficiency", "healing"],
    "shield": ["shield", "protected"],
    "max hp": ["max hp", "hp"],
    "defense": ["defense", "def"],
    "vulnerability": ["vulnerable", "vulnerability"]
}

def stat_match_score(stat, text):
    terms = STAT_ALIASES.get(stat.lower(), [stat.lower()])
    return sum(1 for term in terms if term in text)

def score_weapon_for_character(char_id, weapon, guide=None):
    guide = guide or BUILD_GUIDES.get(char_id, BUILD_GUIDES.get("default", {}))
    preferred_stats = guide.get("stats", [])
    recommended = guide.get("weapons", [])
    weapon_label = weapon.get("name", weapon.get("id", ""))
    text = weapon_text(weapon)

    score = weapon.get("base_atk", 0) * 0.08 + weapon.get("rarity", 0) * 7
    reasons = [
        f"{weapon.get('rarity', '?')} star",
        f"ATK {weapon.get('base_atk', '?')}"
    ]

    for index, recommended_name in enumerate(recommended):
        similarity = SequenceMatcher(None, normalize_label(recommended_name), normalize_label(weapon_label)).ratio()
        if similarity >= 0.9:
            bonus = max(28 - index * 6, 8)
            score += bonus
            reasons.append("listed as a top recommendation" if index == 0 else "listed as a recommended option")
            break

    matched_stats = []
    for stat in preferred_stats:
        matches = stat_match_score(stat, text)
        if matches:
            score += matches * 8
            matched_stats.append(stat)

    if matched_stats:
        reasons.append("matches " + ", ".join(matched_stats[:3]))

    return {
        "weapon": weapon,
        "score": round(score, 1),
        "reasons": reasons[:4]
    }

def rank_weapons_for_character(char_id):
    character = CHARACTERS.get(char_id, {})
    guide = BUILD_GUIDES.get(char_id, BUILD_GUIDES.get("default", {}))
    compatible = weapons_for_type(character.get("weapon_type"))
    rankings = [
        score_weapon_for_character(char_id, weapon, guide)
        for weapon in compatible
    ]
    return sorted(
        rankings,
        key=lambda item: item["score"],
        reverse=True
    )

def recommended_weapons_for_character(char_id):
    guide = BUILD_GUIDES.get(char_id, {})
    ranked_names = [
        item["weapon"].get("name", item["weapon"].get("id"))
        for item in rank_weapons_for_character(char_id)
    ]
    combined = guide.get("weapons", []) + ranked_names

    seen = set()
    recommendations = []
    for weapon in combined:
        if weapon and weapon not in seen:
            seen.add(weapon)
            recommendations.append(weapon)
    return recommendations

class Users(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(25), unique=True, nullable=False)
    password = db.Column(db.String(70), nullable=False)
    data = db.Column(db.Text, nullable=False)
    profile_pic = db.Column(db.Text, nullable=True)
    build_data = db.Column(db.Text, nullable=True)
    weapon_data = db.Column(db.Text, nullable=True)

    # Return the username when this user is displayed.
    def __str__(self):
        return self.username
    
class Teams(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    characters = db.Column(db.Text, nullable=False)  # JSON list of 4 chars
    creator = db.Column(db.String(25), nullable=False)
    votes = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=db.func.now())

class TeamVotes(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    value = db.Column(db.Integer, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("team_id", "user_id", name="unique_team_user_vote"),
    )

with app.app_context():
    db.create_all()
    columns = [
        row[1]
        for row in db.session.execute(text("PRAGMA table_info(users)")).fetchall()
    ]
    if "build_data" not in columns:
        db.session.execute(text("ALTER TABLE users ADD COLUMN build_data TEXT"))
    if "weapon_data" not in columns:
        db.session.execute(text("ALTER TABLE users ADD COLUMN weapon_data TEXT"))
    db.session.commit()

#-------------------------------------------------------------

def GET(name):
    x = Users.query.filter_by(username=name).first()
    return x.password if x else None

def POST(name, password, data):
    new_user = Users(
        username=name,
        password=password,
        data=data,
        weapon_data=json.dumps(DEFAULT_WEAPON_DATA)
    )
    db.session.add(new_user)
    db.session.commit()
    return 1

def PUT(name, grade):
    putrequest = Users.query.filter_by(username=name).first()
    putrequest.grade = grade
    db.session.commit()
    return 1

def DELETE(name):
    user = Users.query.filter_by(username=name).first()
    if user:
        db.session.delete(user)
        db.session.commit()

# ----------------------------------------------------------

@app.route("/")
def index():
    return redirect("/dashboard")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    name = request.form.get("username")
    pw = request.form.get("password")

    dbpw = GET(name)
    if not dbpw:
        return redirect("/login")
    mrsalt = dbpw[:6]
    pw = pw + mrsalt
    pw = sha256(pw.encode()).hexdigest()

    if pw == dbpw[-64:]:
        print("awesome")
        session["name"] = name
        return redirect("/dashboard")
    else:
        print("sucks; " + pw + " : " + dbpw[-64:])
        return redirect("/login")


@app.route("/signup", methods=["GET", "POST"])
def signup_page():
    if request.method == "GET":
        return render_template("signup.html")

    name = request.form.get("username", "").strip()
    if Users.query.filter_by(username=name).first():
        return redirect("/signup?exists")
    if len(name) > 25 or not name:
        return redirect("/signup?toolong")

    pw = request.form.get("password", "")
    if not pw:
        return redirect("/signup?missing")

    mrsalt = ''.join(random.SystemRandom().choice(string.ascii_letters + string.digits) for _ in range(6))
    pw += mrsalt
    pw = sha256(pw.encode()).hexdigest()
    pw = mrsalt + pw
    data = json.dumps(DEFAULT_CHARACTER_DATA)

    POST(name, pw, data)
    return redirect("/login")

@app.route("/update-profile", methods=["POST"])
def update_profile():
    if not session.get("name"):
        return {"error": "not logged in"}, 403
    data = request.get_json()
    name = data.get("name", "").strip()
    profile_pic = data.get("profilePic")
    build_data = data.get("buildData")
    user = Users.query.filter_by(username=session["name"]).first()
    if name:
        existing = Users.query.filter(Users.username == name, Users.id != user.id).first()
        if existing:
            return {"error": "username taken"}, 409
        user.username = name
        session["name"] = name  # keep session in sync
    if profile_pic:
        user.profile_pic = profile_pic
    if build_data is not None:
        user.build_data = build_data
    db.session.commit()
    return jsonify({"status": "ok"})

@app.route("/dashboard")
def dashboard():
    is_logged_in = bool(session.get("name"))
    user = Users.query.filter_by(username=session["name"]).first() if is_logged_in else None

    return render_template(
        "dashboard.html",
        data=json.loads(user.data) if user else PUBLIC_CHARACTER_DATA,
        characters=CHARACTERS,
        name=user.username if user else "Guest",
        profile_pic=user.profile_pic if user else None,
        is_logged_in=is_logged_in
    )

@app.route("/DESTROY", methods=["GET"])
def DESTROY():
    DELETE("JohnEndfield")
    return redirect("/")

@app.route("/profile")
def profile():
    if not session.get("name"):
        return redirect("/login")

    user = Users.query.filter_by(username=session["name"]).first()
    return render_template("profile.html", user=user)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/dashboard")

@app.route("/update-characters", methods=["POST"])
def update_characters():
    if not session.get("name"):
        return {"error": "not logged in"}, 403

    user = Users.query.filter_by(username=session["name"]).first()
    new_data = request.json

    user.data = json.dumps(new_data)
    db.session.commit()

    return {"status": "ok"}

@app.route("/api/weapons")
def api_weapons():
    return jsonify(WEAPONS)

@app.route("/weapons")
def weapons():
    is_logged_in = bool(session.get("name"))
    user = Users.query.filter_by(username=session["name"]).first() if is_logged_in else None
    owned_weapons = get_weapon_data(user)

    with open("templates/weapons.html", encoding="utf-8") as template_file:
        template_source = template_file.read()

    return render_template_string(
        template_source,
        weapons=WEAPONS,
        owned=owned_weapons,
        owned_count=sum(1 for is_owned in owned_weapons.values() if is_owned),
        user=user,
        profile_pic=(user.profile_pic or "") if user else "",
        is_logged_in=is_logged_in
    )

@app.route("/test-weapons")
def test_weapons_route():
    return render_template("test_weapons.html", weapons=WEAPONS)

@app.route("/update-weapons", methods=["POST"])
def update_weapons():
    if not session.get("name"):
        return {"error": "not logged in"}, 403

    user = Users.query.filter_by(username=session["name"]).first()
    new_data = request.json or {}
    user.weapon_data = json.dumps({
        weapon_id: bool(new_data.get(weapon_id, False))
        for weapon_id in WEAPONS
    })
    db.session.commit()

    return {"status": "ok"}

@app.route("/weapon/<weapon_id>")
def weapon_detail(weapon_id):
    weapon = get_weapon(weapon_id)
    if not weapon:
        return redirect("/weapons")

    is_logged_in = bool(session.get("name"))
    user = Users.query.filter_by(username=session["name"]).first() if is_logged_in else None
    owned_weapons = get_weapon_data(user)

    return render_template(
        "weapon.html",
        weapon_id=weapon_id,
        weapon=weapon,
        owned=owned_weapons.get(weapon_id, weapon.get("owned", False)),
        compatible_characters=characters_for_weapon_type(weapon.get("type")),
        user=user,
        profile_pic=(user.profile_pic or "") if user else "",
        is_logged_in=is_logged_in
    )

@app.route("/character/<char_id>")
def character_detail(char_id):
    character = get_character(char_id)
    if not character:
        return redirect("/dashboard")

    is_logged_in = bool(session.get("name"))
    user = Users.query.filter_by(username=session["name"]).first() if is_logged_in else None
    owned = json.loads(user.data) if user else PUBLIC_CHARACTER_DATA
    guide = BUILD_GUIDES.get(char_id, BUILD_GUIDES.get("default", {}))

    return render_template(
        "character.html",
        char_id=char_id,
        character=character,
        guide=guide,
        compatible_weapons=weapons_for_type(character.get("weapon_type")),
        recommended_weapons=recommended_weapons_for_character(char_id)[:5],
        weapon_rankings=rank_weapons_for_character(char_id)[:8],
        owned=owned.get(char_id, character.get("owned", False)),
        user=user,
        profile_pic=(user.profile_pic or "") if user else "",
        is_logged_in=is_logged_in
    )

@app.route("/teams")
def teams():
    is_logged_in = bool(session.get("name"))
    user = Users.query.filter_by(username=session["name"]).first() if is_logged_in else None
    owned = json.loads(user.data) if user else PUBLIC_CHARACTER_DATA
    user_votes = {
        vote.team_id: vote.value
        for vote in TeamVotes.query.filter_by(user_id=user.id).all()
    } if user else {}
    teams = [
        {
            "id": team.id,
            "name": team.name,
            "characters": json.loads(team.characters),
            "creator": team.creator,
            "votes": team.votes,
            "user_vote": user_votes.get(team.id, 0)
        }
        for team in Teams.query.order_by(Teams.votes.desc()).all()
    ]
    profile_pic = (user.profile_pic or "") if user else ""
    return render_template(
        "teams.html",
        teams=teams,
        prebuilt=PREBUILT_TEAMS,
        characters=CHARACTERS,
        owned=owned,
        user=user,
        profile_pic=profile_pic,
        is_logged_in=is_logged_in
    )

@app.route("/vote-team", methods=["POST"])
def vote_team():
    if not session.get("name"):
        return {"error": "not logged in"}, 403

    data = request.get_json(silent=True) or {}
    team_id = data.get("team_id")
    value = int(data.get("value", 0))
    if value not in (-1, 1):
        return {"error": "vote must be 1 or -1"}, 400

    team = Teams.query.get(team_id)
    if not team:
        return {"error": "team not found"}, 404

    user = Users.query.filter_by(username=session["name"]).first()
    existing = TeamVotes.query.filter_by(team_id=team.id, user_id=user.id).first()

    if existing and existing.value == value:
        team.votes -= existing.value
        db.session.delete(existing)
        user_vote = 0
    elif existing:
        team.votes += value - existing.value
        existing.value = value
        user_vote = value
    else:
        team.votes += value
        db.session.add(TeamVotes(team_id=team.id, user_id=user.id, value=value))
        user_vote = value

    db.session.commit()
    return {"status": "ok", "votes": team.votes, "user_vote": user_vote}

def score_team(team):
    score = 0
    roles = []
    elements = []
    for char in team:
        data = get_character(char)
        if not data:
            continue
        roles.extend(data.get("roles", []))
        elements.append(data.get("element"))
    # role scoring
    if "dps" in roles:
        score += 2
    if "tank" in roles:
        score += 2
    if "support" in roles:
        score += 2
    # element diversity bonus
    score += len({element for element in elements if element and element != "unknown"}) * 0.5
    score += len(team) * 0.1
    return score

def generate_best_team(owned_chars):
    if len(owned_chars) < 4:
        return tuple(owned_chars)

    best = None
    best_score = -1
    for team in itertools.combinations(owned_chars, 4):
        s = score_team(team)
        if s > best_score:
            best_score = s
            best = team
    return best

def character_name(char_id):
    return CHARACTERS.get(char_id, {}).get("name", char_id)

def find_character_in_message(message):
    lower_message = message.lower()
    for char_id, character in CHARACTERS.items():
        names = {char_id.lower(), character.get("name", "").lower()}
        if any(name and name in lower_message for name in names):
            return char_id
    return None

def format_character_list(character_ids):
    return ", ".join(character_name(char_id) for char_id in character_ids)

def is_endfield_related(message):
    lower_message = message.lower()
    endfield_terms = [
        "endfield",
        "arknights",
        "gryphline",
        "hypergryph",
        "talos-ii",
        "talos ii"
    ]
    if any(term in lower_message for term in endfield_terms):
        return True

    return find_character_in_message(message) is not None

def wants_web_search(message):
    lower_message = message.lower()
    web_terms = [
        "web",
        "search",
        "look up",
        "latest",
        "current",
        "official",
        "news",
        "update",
        "patch",
        "release",
        "event",
        "redeem",
        "code",
        "download"
    ]
    return any(term in lower_message for term in web_terms)

def is_casual_message(message):
    lower_message = message.lower()
    casual_patterns = [
        r"\bhello\b",
        r"\bhi\b",
        r"\bhey\b",
        r"\bhow are you\b",
        r"\bwhat'?s up\b",
        r"\bthanks\b",
        r"\bthank you\b"
    ]
    return any(re.search(pattern, lower_message) for pattern in casual_patterns)

def is_site_topic(message):
    lower_message = message.lower()
    topic_terms = [
        "roster",
        "team",
        "weapon",
        "build",
        "gear",
        "stats",
        "put on",
        "equip",
        "equipment",
        "loadout",
        "character",
        "owned",
        "have",
        "recommend",
        "suggest",
        "support",
        "dps",
        "tank",
        "element"
    ]
    return (
        is_endfield_related(message)
        or find_character_in_message(message) is not None
        or any(term in lower_message for term in topic_terms)
    )

def site_chatbot_context(user):
    owned = json.loads(user.data) if user else PUBLIC_CHARACTER_DATA
    owned_weapon_data = get_weapon_data(user)
    owned_chars = [
        {
            "id": char_id,
            "name": character_name(char_id),
            "roles": CHARACTERS.get(char_id, {}).get("roles", []),
            "element": CHARACTERS.get(char_id, {}).get("element", "unknown"),
            "weapon_type": CHARACTERS.get(char_id, {}).get("weapon_type", "unknown"),
            "recommended_weapons": recommended_weapons_for_character(char_id)[:6],
            "weapon_calculator": [
                {
                    "weapon": item["weapon"].get("name", item["weapon"].get("id")),
                    "score": item["score"],
                    "reasons": item["reasons"]
                }
                for item in rank_weapons_for_character(char_id)[:5]
            ]
        }
        for char_id, owned_char in owned.items()
        if owned_char
    ]
    roster = [
        {
            "id": char_id,
            "name": character.get("name", char_id),
            "roles": character.get("roles", []),
            "element": character.get("element", "unknown"),
            "weapon_type": character.get("weapon_type", "unknown"),
            "recommended_weapons": recommended_weapons_for_character(char_id)[:6],
            "wanted_stats": BUILD_GUIDES.get(char_id, BUILD_GUIDES.get("default", {})).get("stats", []),
            "owned": bool(owned.get(char_id, character.get("owned", False)))
        }
        for char_id, character in CHARACTERS.items()
    ]
    shared_teams = [
        {
            "name": team.name,
            "characters": [
                character_name(char_id)
                for char_id in json.loads(team.characters)
            ],
            "creator": team.creator,
            "votes": team.votes
        }
        for team in Teams.query.order_by(Teams.votes.desc()).limit(10).all()
    ]

    return {
        "user": {
            "username": user.username if user else "Guest",
            "owned_characters": owned_chars,
            "owned_weapons": [
                WEAPONS[weapon_id].get("name", weapon_id)
                for weapon_id, is_owned in owned_weapon_data.items()
                if is_owned
            ],
            "weapon_and_build_notes": ((user.build_data if user else "") or "")[:3000]
        },
        "roster": roster,
        "starter_build_guides": BUILD_GUIDES,
        "weapons": list(WEAPONS.values()),
        "starter_teams": PREBUILT_TEAMS,
        "shared_teams": shared_teams
    }

def recent_chat_context(history):
    clean_history = []
    for item in history[-6:]:
        role = item.get("role")
        content = str(item.get("content", "")).strip()
        if role in {"user", "assistant"} and content:
            clean_history.append({
                "role": role,
                "content": content[:1200]
            })
    return clean_history

def last_character_from_history(history):
    for item in reversed(history[-6:]):
        content = str(item.get("content", ""))
        char_id = find_character_in_message(content)
        if char_id:
            return char_id
    return None

def is_weapon_question(message):
    lower_message = message.lower()
    weapon_terms = ["weapon", "weapons", "equip", "equipment", "put on", "loadout"]
    return any(term in lower_message for term in weapon_terms)

def user_rejected_previous_weapon(message):
    lower_message = message.lower()
    rejection_terms = [
        "i don't have",
        "i dont have",
        "do not have",
        "don't own",
        "dont own",
        "not have",
        "not own",
        "missing that",
        "don't got",
        "dont got"
    ]
    return any(term in lower_message for term in rejection_terms)

def last_recommended_weapon(history, weapons):
    for item in reversed(history[-6:]):
        if item.get("role") != "assistant":
            continue
        content = str(item.get("content", "")).lower()
        for index, weapon in enumerate(weapons):
            if weapon.lower() in content:
                return index
    return None

def choose_weapon(weapons, history, message):
    if not weapons:
        return None, None

    weapon_index = 0
    if user_rejected_previous_weapon(message):
        previous_index = last_recommended_weapon(history, weapons)
        if previous_index is not None:
            weapon_index = min(previous_index + 1, len(weapons) - 1)

    backup_index = weapon_index + 1 if weapon_index + 1 < len(weapons) else None
    return weapons[weapon_index], weapons[backup_index] if backup_index is not None else None

def calculator_result_for_weapon(char_id, weapon_name_value):
    normalized = normalize_label(weapon_name_value or "")
    for item in rank_weapons_for_character(char_id):
        if normalize_label(item["weapon"].get("name", "")) == normalized:
            return item
    return None

def groq_chatbot_reply(message, user, history=None):
    history = recent_chat_context(history or [])
    if Groq is None:
        return (
            "Groq is not installed for this Python environment yet. "
            "Run python3 -m pip install -r requirements.txt, restart Flask, and try again."
        )

    if not os.getenv("GROQ_API_KEY"):
        return (
            "Groq is not configured yet. Add your API key to a .env file or environment variable "
            "as GROQ_API_KEY, restart Flask, and I can answer as the smart chatbox."
        )

    use_web_search = wants_web_search(message)
    if use_web_search and not is_endfield_related(message):
        return (
            "I can only search the web for Arknights: Endfield topics. "
            "Ask about Endfield news, characters, updates, releases, or official info."
        )

    context = site_chatbot_context(user)
    off_topic = not is_site_topic(message) and not is_casual_message(message)
    system_message = (
        "You are Build Bot, a friendly assistant inside an Arknights: Endfield roster website. "
        "You can answer greetings warmly, but you must always guide the conversation back to Arknights: Endfield, "
        "the user's roster, teams, weapons, or builds. "
        "For off-topic questions, give at most one short friendly sentence, then pivot back to Endfield. "
        "Do not continue off-topic conversations or ask off-topic follow-up questions. "
        "For roster, character, team, weapon, build, game, or Endfield questions, answer only using the SITE DATA provided by the server. "
        "Do not use outside game knowledge, do not invent weapons, builds, stats, character facts, or team synergies. "
        "If the site data does not contain enough game information, say what is missing and suggest what the user can add "
        "on the Profile page or roster page. "
        "Use the site data silently. Do not mention internal field names, JSON keys, database labels, or phrases like "
        "site_data, starter_build_guides, weapon_and_build_notes, saved teams, or according to the data. "
        "Write naturally, as if you are directly advising the player. "
        "When recommending weapons, use the character's recommended weapon list first, then compatible weapons of the same weapon type as backups. "
        "Use the weapon_calculator scores and reasons when the user asks why a weapon is good or asks for the strongest option. "
        "When the user asks for weapon details, include the weapon's Lv.90 ATK and one or two useful stat/effect lines from the weapon data. "
        "Keep answers short and easy to scan. Avoid long paragraphs. "
        "For character build, weapon, gear, or stats advice, start with 'Here's what I would suggest:' and then use a short bullet list. "
        "Use bullets like Build, Weapon, Stats, Team note, and Missing info when relevant. "
        "Do not write more than 5 bullets unless the user asks for details. "
        "For weapon-only questions, recommend exactly one best weapon first. Do not list multiple weapons as 'or' options. "
        "If the user says they do not have the weapon you just recommended, use recent chat history and suggest the next best weapon "
        "from the character's weapon list. Start that answer with 'Here's the next best option:' and do not repeat the full build. "
        "Use the recent chat history to understand follow-up questions. For example, if the user asks about Perlica "
        "and then asks 'what weapon do you recommend?', answer about Perlica unless the user clearly changes topic."
    )
    if use_web_search:
        system_message += (
            " The user is asking for current web information. You may use web search, but only for Arknights: Endfield. "
            "Ignore or refuse anything unrelated to Endfield. Prefer official or Endfield-specific sources from the allowed domains. "
            "Clearly separate site-data facts from web-found facts, and do not use web information to invent personal roster/build data."
        )

    prompt = {
        "site_data": context,
        "recent_chat_history": history,
        "off_topic": off_topic,
        "web_search_allowed": use_web_search,
        "allowed_search_domains": app.config["GROQ_SEARCH_DOMAINS"] if use_web_search else [],
        "user_question": message
    }

    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    request_args = {
        "model": app.config["GROQ_WEB_MODEL"] if use_web_search else app.config["GROQ_MODEL"],
        "messages": [
            {
                "role": "system",
                "content": system_message
            },
            {
                "role": "user",
                "content": json.dumps(prompt)
            }
        ],
        "temperature": 0.2,
        "max_tokens": 700
    }
    if use_web_search:
        request_args["include_domains"] = app.config["GROQ_SEARCH_DOMAINS"]
        request_args["citation_options"] = "enabled"

    completion = client.chat.completions.create(**request_args)
    return completion.choices[0].message.content.strip()

def chatbot_reply(message, user, history=None):
    history = recent_chat_context(history or [])
    clean_message = message.strip()
    if not clean_message:
        return "Ask me about your roster, teams, weapons, or builds."

    lower_message = clean_message.lower()
    if is_casual_message(clean_message):
        return (
            "Hey, I am doing good. Let us keep it focused on Endfield: I can help with your roster, "
            "builds, teams, weapons, or saved notes."
        )

    if not is_site_topic(clean_message):
        return (
            "That is a fun thought, but I am here to stay focused on Endfield. "
            "Ask me about your roster, teams, weapons, builds, or character plans."
        )

    owned = json.loads(user.data) if user else PUBLIC_CHARACTER_DATA
    owned_chars = [char_id for char_id, owned_char in owned.items() if owned_char]
    build_notes = ((user.build_data if user else "") or "").strip()
    requested_char = find_character_in_message(clean_message) or last_character_from_history(history)

    build_terms = ["weapon", "build", "gear", "stats", "put on", "equip", "equipment", "loadout"]
    if any(word in lower_message for word in build_terms) or user_rejected_previous_weapon(clean_message):
        if requested_char:
            guide = BUILD_GUIDES.get(requested_char, BUILD_GUIDES.get("default", {}))
            owned_text = "You own this character." if requested_char in owned_chars else "You have not marked this character as owned."
            weapon_list = recommended_weapons_for_character(requested_char)
            weapon, backup_weapon = choose_weapon(weapon_list, history, clean_message)
            stats = ", ".join(guide.get("stats", []))

            if is_weapon_question(clean_message) or user_rejected_previous_weapon(clean_message):
                if user_rejected_previous_weapon(clean_message) and weapon:
                    intro = "Here's the next best option:"
                else:
                    intro = "Here's what I would suggest:"

                reply = (
                    f"{intro}\n"
                    f"- Character: {character_name(requested_char)}\n"
                    f"- Weapon: {weapon or 'use the best option you have available'}\n"
                    f"- Why: it fits a {guide.get('build', 'flexible')} setup"
                )
                calculator_result = calculator_result_for_weapon(requested_char, weapon)
                if calculator_result:
                    reply += (
                        f"\n- Calculator: {calculator_result['score']} score, "
                        + ", ".join(calculator_result["reasons"][:3])
                    )
                if backup_weapon:
                    reply += f"\n- Backup: {backup_weapon}"
                if not weapon_list:
                    reply += "\n- Missing info: add weapon options for this character on the Profile page"
                return reply

            reply = (
                "Here's what I would suggest:\n"
                f"- Character: {character_name(requested_char)}\n"
                f"- Build: {guide.get('build', 'Flexible starter option')}\n"
                f"- Weapon: {weapon or 'use the best option you have available'}\n"
                f"- Stats: {stats or 'focus on stats that support their main role'}\n"
                f"- Note: {owned_text}"
            )
            if build_notes:
                reply += f"\n- Your notes: {build_notes}"
            return reply

        if build_notes:
            return f"Your saved weapon/build notes are: {build_notes}"
        return "Tell me which character you want to build, or add your weapon/build notes on the Profile page."

    if any(word in lower_message for word in ["owned", "have", "roster", "characters"]):
        if not owned_chars:
            return "You have not marked any characters as owned yet."
        return f"Your owned characters are: {format_character_list(owned_chars)}."

    if any(word in lower_message for word in ["team", "suggest", "recommend", "best"]):
        best = generate_best_team(owned_chars)
        if not best:
            return "Mark a few characters as owned first, then I can suggest a team."

        team_names = format_character_list(best)
        return (
            f"I would start with {team_names}. "
            "This suggestion favors known DPS/support coverage and element variety from the data we have."
        )

    if build_notes:
        return (
            "I can use your saved build notes and owned roster. "
            f"Your notes say: {build_notes}"
        )

    return (
        "I can help with owned characters, team suggestions, weapons, and starter builds. "
        "Add your personal weapon/build notes on the Profile page for better answers."
    )

@app.route("/create-team", methods=["POST"])
def create_team():
    if not session.get("name"):
        return {"error": "not logged in"}, 403

    data = request.json
    characters = data.get("characters", [])
    if len(characters) != 4:
        return {"error": "choose exactly four characters"}, 400

    team = Teams(
        name=data["name"].strip() or "Untitled Team",
        characters=json.dumps(characters),
        creator=session["name"]
    )

    db.session.add(team)
    db.session.commit()

    return {"status": "ok"}

@app.route("/generate-team", methods=["POST"])
def generate_team():
    if not session.get("name"):
        return {"error": "not logged in"}, 403

    user = Users.query.filter_by(username=session["name"]).first()
    owned = json.loads(user.data)
    owned_chars = [k for k, v in owned.items() if v]
    best = generate_best_team(owned_chars)
    return jsonify({
        "team": list(best) if best else []
    })

@app.route("/chatbot", methods=["POST"])
def chatbot():
    user = Users.query.filter_by(username=session["name"]).first() if session.get("name") else None
    data = request.get_json(silent=True) or {}
    message = data.get("message", "")
    history = recent_chat_context(data.get("history", []))

    try:
        reply = groq_chatbot_reply(message, user, history)
    except Exception as error:
        print(f"Groq chatbot error: {type(error).__name__}: {error}")
        reply = (
            f"I could not reach Groq right now ({type(error).__name__}). "
            "Check the Flask terminal for the exact error. Here is the basic site-data answer: "
            + chatbot_reply(message, user, history)
        )

    return jsonify({"reply": reply})

if __name__ == '__main__':
    app.run()
