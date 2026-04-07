from flask import Flask, render_template
import os

from flask import send_from_directory

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

@app.route('/sitemap.xml')
def sitemap():
    return send_from_directory('static', 'sitemap.xml')


