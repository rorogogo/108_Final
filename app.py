from flask import Flask, request, render_template, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_session import Session
from hashlib import sha256
import random
import string

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///users.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"

db = SQLAlchemy(app)
Session(app)

class Users(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(25), unique=True, nullable=False)
    password = db.Column(db.String(70), nullable=False)
    data = db.Column(db.String(425), nullable=False)

    # Return the username when this user is displayed.
    def __str__(self):
        return self.username

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
    data = '{"endmin":false,"perlica":false,"zhuangfy":false,"chen":false,"tangtang":false,"rossi":false,"laevatain":false,"yvonne":false,"gilberta":false,"ardelia":false,"ember":false,"lastrite":false,"lifeng":false,"pogranichnik":false,"alesh":false,"arclight":false,"avywenna":false,"dapan":false,"snowshine":false,"wulfgard":false,"xaihi":false,"akekuri":false,"antal":false,"catcher":false,"estella":false,"flourite":false}'

    POST(name, pw, data)
    return redirect("/")


@app.route("/dashboard")
def dashboard():
    if not session.get("name"):
        return redirect("/")
    return render_template("dashboard.html")

@app.route("/DESTROY", methods=["GET"])
def DESTROY():
    DELETE("JohnEndfield")
    return redirect("/")

@app.route("/profile")
def profile():
    if not session.get("name"):
        return redirect("/")
    return render_template("profile.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == '__main__':
    app.run()

