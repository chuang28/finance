from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure responses aren't cached


@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # select stocks that user bought
    portfolio_temp = db.execute("SELECT shares, symbol FROM portfolio WHERE id= :id", id=session["user_id"])
    # create TOTAL(cash+shares) variable for later use
    totalcash = 0
    # update stock that user bought and total cash
    for i in portfolio_temp:
        symbol = i["symbol"]
        shares = i["shares"]
        stock = lookup(symbol)
        total = shares * stock["price"]
        totalcash += total
        db.execute("UPDATE portfolio SET price=:price, total= :total WHERE id= :id AND symbol= :symbol",\
                    price=usd(stock["price"]), total=usd(total), id=session["user_id"], symbol=symbol)

    # update user's cash in portfolio
    updatedcash = db.execute("SELECT cash FROM users WHERE id= :id", id=session["user_id"])

    # calculate total asset
    totalcash += updatedcash[0]["cash"]
    # update portfolio
    updatedportfolio = db.execute("SELECT * from portfolio WHERE id= :id", id=session["user_id"])

    return render_template("index.html", stocks=updatedportfolio, cash=usd(updatedcash[0]["cash"]),\
                            total=usd(totalcash))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "GET":
        return render_template("buy.html")
    else:
        # make sure valid symbol
        buy = request.form.get("symbol")
        if not buy:
            return apology("Must enter stock symbol")
        # make sure valid shares
        shares = int(request.form.get("shares"))
        if not shares:
            return apology("Must enter number of shares")

        # check how much cash does user have
        cash = db.execute("SELECT cash FROM users WHERE id = :id", id = session["user_id"])

        stock = lookup(request.form.get("symbol"))
        name = stock['name']
        symbol = stock['symbol']
        price = stock['price']

        if shares * price > cash[0]["cash"]:
            return apology("You don't have enough money!")

        # update to history
        transaction = db.execute("INSERT INTO history (symbol, shares, price, id) VALUES(:symbol, :shares, :price, :id)",\
                                    symbol=stock["symbol"], shares=shares, price=usd(stock["price"]), id=session["user_id"])

        # update users cash
        db.execute("UPDATE users SET cash = cash - :purchase WHERE id = :id", id=session["user_id"],\
                    purchase=stock["price"] * float(shares))

        # check stock already in portfolio or not
        usershares = db.execute("SELECT shares FROM portfolio WHERE id= :id AND symbol= :symbol",\
        id=session["user_id"], symbol=stock["symbol"])

        # if users don't have that stock, create new one
        if not usershares:
            db.execute("INSERT INTO portfolio (symbol,name, shares, price, total, id) VALUES ( :symbol, :name,\
                        :shares, :price, :total, :id)", symbol=stock["symbol"], name=stock["name"], shares=shares, \
                        price=usd(stock["price"]), total=usd(shares * stock["price"]), id=session["user_id"])
        else:
            sharestotal = usershares[0]["shares"] + shares
            db.execute("UPDATE portfolio SET shares= :shares WHERE id= :id AND symbol= :symbol",\
                        shares=sharestotal, id=session["user_id"], symbol=stock["symbol"])

        return redirect(url_for("index") )

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    history = db.execute("SELECT symbol,shares, price, transacted FROM history WHERE id= :id", id= session["user_id"])
    return render_template("history.html", histories = history)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        quote = lookup(request.form.get("symbol"))
        if not quote:
            return apology("Stock is not valid")
        return render_template("quoted.html", name=quote)
    else:
        return render_template("quote.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":

        # get the username
        username = request.form.get("username")
        if not username:
            return apology("Missing username")
        # get password and confirmation
        password = request.form.get("password")
        if not password:
            return apology("Missing password")

        confirmation = request.form.get("confirmation")
        if password != confirmation:
            return apology("Password doesn't match")

        # encrypt password
        hashp = generate_password_hash(password)

        # insert user into users, check username is unique
        result = db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)",\
                                username=request.form.get("username"), hash=hashp)
        if not result:
            return apology("Username already existed")

        # store user id
        # user_id = db.execute("SELECT id FROM users WHERE username IS username", username=request.form.get("username"))  user_id[0]["id"]
        session["user_id"] = result
        return redirect(url_for("index"))

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "GET":

        stocks = db.execute("SELECT symbol FROM portfolio WHERE id= :id", id=session["user_id"])
        return render_template("sell.html", stocks=stocks)


    else:
        sell = request.form.get("symbol")
        if not sell:
            return apology("Invalid stock symbol")

        shares = int(request.form.get("shares"))
        if not shares:
            return apology("Must enter number of shares")

        stock = lookup(request.form.get("symbol"))

        # check stock already in portfolio or not
        usershares = db.execute("SELECT shares FROM portfolio WHERE id= :id AND symbol= :symbol",\
                                id=session["user_id"], symbol=stock["symbol"])

        # check users have enough shares to sell
        if not usershares or int(usershares[0]["shares"]) < shares:
            return apology("Not enough shares")

        # update to history
        db.execute("INSERT INTO history (symbol, shares, price, id) VALUES(:symbol, :shares, :price, :id)",\
        symbol=stock["symbol"], shares=-shares, price=usd(stock["price"]), id=session["user_id"])

        # update users cash
        db.execute("UPDATE users SET cash = cash +:purchase WHERE id = :id", id=session["user_id"],\
                    purchase=stock["price"] * float(shares))
        # shares count
        sharestotal = usershares[0]["shares"] - shares

        # update portfolio
        if (usershares[0]["shares"]-shares == 0):
            db.execute("DELETE FROM portfolio WHERE id= :id AND symbol=:symbol", id=session["user_id"], symbol=stock["symbol"])
        else:
            db.execute("UPDATE portfolio SET shares= :shares WHERE id= :id AND symbol= :symbol",\
                        shares=sharestotal, id=session["user_id"], symbol=stock["symbol"])

    return redirect(url_for("index"))


def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
