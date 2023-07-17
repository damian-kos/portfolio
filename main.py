from flask import (
    Flask,
    render_template,
    redirect,
    url_for,
    flash,
    abort,
    request,
)
import smtplib
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import (
    UserMixin,
    login_user,
    LoginManager,
    login_required,
    current_user,
    logout_user,
)
from forms import CreatePostForm
from flask_gravatar import Gravatar
from functools import wraps
import forms
import os
import dotenv


# Creating flask App
app = Flask(__name__)
app.config["SECRET_KEY"] = "xd"
app.config["CKEDITOR_SERVE_LOCAL"] = True
# Allows to embed text editor window
app.config["CKEDITOR_ENABLE_CODESNIPPET"] = True
ckeditor = CKEditor(app)
# Allows to use Bootstrap within app
Bootstrap(app)

# Works with logins
login_manager = LoginManager()
login_manager.init_app(app)

# Connects to database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "sqlite:///blog.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

dotenv_file = dotenv.find_dotenv()
dotenv.load_dotenv(dotenv_file)
senders = os.environ["SENDER_EMAIL"]
sender_password = os.environ["SENDER_PASSWORD"]
receiver = os.environ["RECEIVER_ADDRESS"]
# Tables


# Post
class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    author = relationship("User", back_populates="posts")
    # comments = relationship("Comment", back_populates="parent_post")
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    post_type = db.Column(db.String(250), nullable=False)
    post_sorting_position = db.Column(db.Integer)


# User
class User(UserMixin, db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    posts = relationship("BlogPost", back_populates="author")

    name = db.Column(db.String(250), nullable=False)
    email = db.Column(db.String(250), unique=True, nullable=False)
    password = db.Column(db.String(250), nullable=False)


# with app.app_context():
#     db.create_all()


@app.route("/")
def get_all_posts():
    # Gets all posts from blog_posts table
    posts = BlogPost.query.filter_by(post_type="blog").order_by(
        BlogPost.post_sorting_position.desc()).all()

    return render_template("index.html",
                           all_posts=posts)


@app.route("/tech_posts")
def get_all_tech():
    # Gets all posts from tech_posts table
    posts = BlogPost.query.filter_by(post_type="tech").order_by(
        BlogPost.post_sorting_position.desc()).all()

    return render_template("tech.html", all_posts=posts)


@app.route("/register", methods=["GET", "POST"])
def register():
    # Creates a form on register.html page
    form = forms.RegisterUserForm()
    # If data is valid on submit it lets user to be created. First user will be an admin
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data).first():
            flash("Email is already used")
            return redirect(url_for("login"))
        new_user = User(
            email=form.email.data,
            password=generate_password_hash(
                form.password.data, method="pbkdf2:sha256", salt_length=8
            ),
            name=form.name.data,
        )
        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)

        return redirect(url_for("get_all_posts"))

    return render_template("register.html", form=form)


# Not entirely sure what it does, was taken from docs.
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


@app.route("/login", methods=["GET", "POST"])
def login():
    login_form = forms.LoginForm()
    if login_form.validate_on_submit():
        user = User.query.filter_by(email=login_form.email.data).first()
        if not user:
            flash("Invalid email provided")
        else:
            password = login_form.password.data

            if check_password_hash(user.password, password):
                login_user(user)
                return redirect(url_for("get_all_posts"))

            else:
                flash("Invalid password provided")
    return render_template("login.html", form=login_form)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("get_all_posts"))


def admin_only(func):
    # afaik @wraps decorator allows to keep all info, vars and other things from a function we will be wrapping.
    # Couldn't make @admin_only decorator working without it. Since it was not recognizing "current_user"
    @wraps(func)
    def wrap(*args, **kwargs):
        if current_user.id != 1:
            abort(403)
        else:
            return func(*args, **kwargs)

    return wrap


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    requested_post = BlogPost.query.get(post_id)
    return render_template("post.html", post=requested_post)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        data = request.form
        send_email(data["name"], data["email"], data["message"])
        return render_template("contact.html", msg_sent=True)
    return render_template("contact.html", msg_sent=False)


def send_email(name, email, message):
    email_message = f"Subject:New Message\n\nName: {name}\nEmail: {email}\nMessage: {message}"
    with smtplib.SMTP("smtp.gmail.com") as connection:
        connection.starttls()
        connection.login(senders, sender_password)
        connection.sendmail(
            senders,
            receiver,
            email_message,
        )


@app.route("/new-post", methods=["GET", "POST"])
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y"),
            post_type=form.post_type.data,
            post_sorting_position=form.post_sorting_position.data,
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post_type_from_url = request.args.get('post_type_from_url')
    print(f"POST TYPE: {post_type_from_url}")
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body,
        post_type=post.post_type,
        post_sorting_position=post.post_sorting_position,

    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        post.post_type = edit_form.post_type.data
        post.post_sorting_position = edit_form.post_sorting_position.data

        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form)


@app.route("/delete/<int:post_id>")
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for("get_all_posts"))


if __name__ == "__main__":
    app.run(debug=True)
