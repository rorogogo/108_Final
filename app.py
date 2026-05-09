from flask import Flask, request, render_template, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_session import Session
from hashlib import sha256
from datetime import datetime
import random
import string
import json
import itertools

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///users.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"

db = SQLAlchemy(app)
Session(app)

with open("data/characters.json") as f:
    CHARACTERS = json.load(f)

def get_character(char_id):
    return CHARACTERS.get(char_id, None)

class Users(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(25), unique=True, nullable=False)
    password = db.Column(db.String(70), nullable=False)
    data = db.Column(db.String(425), nullable=False)
    profile_pic = db.Column(db.Text, nullable=True)

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

with app.app_context():
    db.create_all()

#-------------------------------------------------------------

def GET(name):
    x = Users.query.filter_by(username=name).first()
    return x.password if x else None

def POST(name, password, data):
    new_user = Users(username=name, password=password, data=data)
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

@app.route('/', methods=["GET", "POST"])
def index():
    if request.method == "GET":
        return render_template("login.html")

    name = request.form.get("username")
    pw = request.form.get("password")

    dbpw = GET(name)
    if not dbpw:
        return redirect("/")
    mrsalt = dbpw[:6]
    pw = pw + mrsalt
    pw = sha256(pw.encode()).hexdigest()

    if pw == dbpw[-64:]:
        print("awesome")
        session["name"] = name
        return redirect("/dashboard")
    else:
        print("sucks; " + pw + " : " + dbpw[-64:])
        return redirect("/")


@app.route("/signup", methods=["GET", "POST"])
def signup_page():
    if request.method == "GET":
        return render_template("signup.html")

    name = request.form.get("username")
    if Users.query.filter_by(username=name).first():
        return redirect("/signup?exists")
    if len(name) > 25:
        return redirect("/signup?toolong")

    pw = request.form.get("password")
    mrsalt = ''.join(random.SystemRandom().choice(string.ascii_letters + string.digits) for _ in range(6))
    pw += mrsalt
    pw = sha256(pw.encode()).hexdigest()
    pw = mrsalt + pw
    data = '{"endmin":true,"perlica":false,"zhuangfy":false,"chen":false,"tangtang":false,"rossi":false,"laevatain":false,"yvonne":false,"gilberta":false,"ardelia":false,"ember":false,"lastrite":false,"lifeng":false,"pogranichnik":false,"alesh":false,"arclight":false,"avywenna":false,"dapan":false,"snowshine":false,"wulfgard":false,"xaihi":false,"akekuri":false,"antal":false,"catcher":false,"estella":false,"flourite":false}'

    POST(name, pw, data)
    return redirect("/")

@app.route("/update-profile", methods=["POST"])
def update_profile():
    if not session.get("name"):
        return {"error": "not logged in"}, 403
    data = request.get_json()
    name = data.get("name")
    profile_pic = data.get("profilePic")
    user = Users.query.filter_by(username=session["name"]).first()
    if name:
        user.username = name
        session["name"] = name  # keep session in sync
    if profile_pic:
        user.profile_pic = profile_pic
    db.session.commit()
    return jsonify({"status": "ok"})

@app.route("/dashboard")
def dashboard():
    if not session.get("name"):
        return redirect("/")

    user = Users.query.filter_by(username=session["name"]).first()

    return render_template(
        "dashboard.html",
        data=user.data,
        name=user.username,
        profile_pic=user.profile_pic
    )

@app.route("/DESTROY", methods=["GET"])
def DESTROY():
    DELETE("JohnEndfield")
    return redirect("/")

@app.route("/profile")
def profile():
    if not session.get("name"):
        return redirect("/")

    user = Users.query.filter_by(username=session["name"]).first()
    return render_template("profile.html", user=user)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/update-characters", methods=["POST"])
def update_characters():
    if not session.get("name"):
        return {"error": "not logged in"}, 403

    user = Users.query.filter_by(username=session["name"]).first()
    new_data = request.json

    user.data = json.dumps(new_data)
    db.session.commit()

    return {"status": "ok"}

@app.route("/teams")
def teams():
    teams = Teams.query.order_by(Teams.votes.desc()).all()
    return render_template("teams.html", teams=teams, prebuilt=PREBUILT_TEAMS)

@app.route("/vote-team", methods=["POST"])
def vote_team():
    team_id = request.json["team_id"]
    team = Teams.query.get(team_id)
    team.votes += 1
    db.session.commit()
    return {"status": "ok"}
with open("data/teams.json") as f:
    PREBUILT_TEAMS = json.load(f)

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
    score += len(set(elements)) * 0.5
    return score

def generate_best_team(owned_chars):
    best = None
    best_score = -1
    for team in itertools.combinations(owned_chars, 4):
        s = score_team(team)
        if s > best_score:
            best_score = s
            best = team
    return best

@app.route("/create-team", methods=["POST"])
def create_team():
    if not session.get("name"):
        return {"error": "not logged in"}, 403

    data = request.json

    team = Teams(
        name=data["name"],
        characters=json.dumps(data["characters"]),
        creator=session["name"]
    )

    db.session.add(team)
    db.session.commit()

    return {"status": "ok"}

@app.route("/generate-team", methods=["POST"])
def generate_team():
    user = Users.query.filter_by(username=session["name"]).first()
    owned = json.loads(user.data)
    owned_chars = [k for k, v in owned.items() if v]
    best = generate_best_team(owned_chars)
    return jsonify({
        "team": list(best) if best else []
    })

if __name__ == '__main__':
    app.run()

