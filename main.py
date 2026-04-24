from flask import Flask, request, render_template_string
import os

app = Flask(__name__)

# صفحة تسجيل الدخول
login_page = """
<!DOCTYPE html>
<html>
<head>
    <title>Quotex Bot Login</title>
</head>
<body>
    <h2>Login to Quotex Bot</h2>
    <form method="POST" action="/login">
        <label>Email:</label><br>
        <input type="text" name="email"><br><br>
        <label>Password:</label><br>
        <input type="password" name="password"><br><br>
        <input type="submit" value="Login">
    </form>
</body>
</html>
"""

@app.route("/")
def home():
    return login_page

@app.route("/login", methods=["POST"])
def login():
    email = request.form.get("email")
    password = request.form.get("password")
    # هنا تقدر تضيف منطق Quotex API لاحقًا
    return f"✅ Logged in with {email}. Bot started!"

@app.route("/start")
def start():
    # مثال بسيط: يختار زوج وهمي ويعرض الاتجاه
    pair = "EUR/USD"
    direction = "⬆️ Up"
    return f"Trading started on {pair} with direction {direction}"

@app.route("/stop")
def stop():
    return "⛔ Trading stopped."

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Railway يعطي PORT تلقائي
    app.run(host="0.0.0.0", port=port)
