import os
import smtplib
from dotenv import load_dotenv
from datetime import date
from flask import Flask, abort, render_template, redirect, url_for, flash, request
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user, login_required
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import relationship
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm

load_dotenv()

my_mail = os.getenv("MY_MAIL")
app_password = os.getenv("APP_PASSWORD")


app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
ckeditor = CKEditor(app)
Bootstrap5(app)

login_manager = LoginManager()
login_manager.init_app(app)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///posts.db'
db = SQLAlchemy()
db.init_app(app)

gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None
                    )


class Users(db.Model, UserMixin):
    __tablename__ = "usersx"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(250), unique=True, nullable=False)
    email = db.Column(db.String(250), unique=True, nullable=False)
    password = db.Column(db.String(500), nullable=False)
    posts = relationship("BlogPost", back_populates="author")
    comments = relationship("Comment", back_populates="comment_author")


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("usersx.id"))
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    author = relationship("Users", back_populates="posts")
    img_url = db.Column(db.String(250), nullable=False)
    post_comments = relationship("Comment", back_populates="parent_post")


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("usersx.id"))
    post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))
    comment_author = relationship("Users", back_populates="comments")
    parent_post = relationship("BlogPost", back_populates="post_comments")
    text = db.Column(db.Text, nullable=False)


with app.app_context():
    db.create_all()


def check_password(user, entered_password):
    if check_password_hash(pwhash=user.password, password=entered_password):
        login_user(user=user)
        return True
    else:
        return False\



def send_mail(name, email, phone, msg):
    with smtplib.SMTP("smtp.gmail.com") as connection:
        connection.starttls()
        connection.login(user=my_mail, password=app_password)
        connection.sendmail(
            from_addr=my_mail,
            to_addrs=my_mail,
            msg=f"Subject:Message from {name}\n\nemail: {email}\nphone: {phone}\nmessage: {msg}\n"
        )


def admin_only(function):
    @wraps(function)
    def wrapper_function(*args, **kwargs):
        if current_user.id == 1:
            return function(*args, **kwargs)
        else:
            return abort(code=403)
    return wrapper_function


@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(Users, user_id)


@app.route('/register', methods=["POST", "GET"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        entered_password = form.password.data
        entered_email = form.email.data
        user = db.session.execute(db.select(Users).where(Users.email == entered_email)).scalar()
        if user:
            flash(message="You've Already Signed up with that email, Log in Instead", category="error")
            return redirect(url_for("login"))
        hashed_and_salted_password = generate_password_hash(
            password=entered_password,
            salt_length=20,
        )
        with app.app_context():
            new_user = Users(
                username=form.username.data,
                email=entered_email,
                password=hashed_and_salted_password,
            )
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
        return redirect(url_for("get_all_posts"))
    return render_template("register.html", form=form)


@app.route('/login', methods=["POST", "GET"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        entered_mail = form.email.data
        entered_password = form.password.data
        try:
            user = db.session.execute(db.select(Users).where(Users.email == entered_mail)).scalar()
            if check_password(user=user, entered_password=entered_password):
                return redirect(url_for("get_all_posts"))
            else:
                flash(message="Invalid password. Please try again", category="error")
                return redirect(url_for("login"))
        except AttributeError:
            flash(message="Email not registered yet! Please register below", category="error")
            return redirect(url_for("register"))
    return render_template("login.html", form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route('/')
def get_all_posts():
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    return render_template("index.html", all_posts=posts)


@app.route("/post/<int:post_id>", methods=["POST", "GET"])
def show_post(post_id):
    requested_post = db.get_or_404(BlogPost, post_id)
    all_comments = db.session.execute(db.select(Comment)).scalars().all()
    form = CommentForm()
    if form.validate_on_submit():
        if current_user.is_authenticated:
            new_comment = Comment(
                text=form.body.data,
                comment_author=current_user,
                parent_post=requested_post,
            )
            db.session.add(new_comment)
            db.session.commit()
        else:
            flash(message="You need to be logged in/registered, in order to post a comment", category="error")
            return redirect(url_for("login"))
    return render_template("post.html", post=requested_post, form=form, all_comments=all_comments)


@app.route("/new-post", methods=["GET", "POST"])
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        if current_user.is_authenticated:
            new_post = BlogPost(
                title=form.title.data,
                subtitle=form.subtitle.data,
                body=form.body.data,
                img_url=form.img_url.data,
                author=current_user,
                date=date.today().strftime("%B %d, %Y")
            )
            db.session.add(new_post)
            db.session.commit()
            return redirect(url_for("get_all_posts"))
        else:
            flash(message="You need to login/register to upload a post.", category="error")
            return redirect(url_for("login"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True)


@app.route("/delete/<int:post_id>")
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        phone = request.form["phone"]
        msg = request.form["message"]
        send_mail(name, email, phone, msg)
        return render_template("contact.html", msg_sent=True)
    return render_template("contact.html", msg_sent=False)


if __name__ == "__main__":
    app.run(debug=True, port=5002)
