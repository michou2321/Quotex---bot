from flask import Flask, request
from quotexpy import Quotex

app = Flask(__name__)

# نخزن الجلسة لكل مستخدم
sessions = {}

@app.route('/login', methods=['POST'])
def login():
    email = request.form.get("email")
    password = request.form.get("password")
    if not email or not password:
        return "Please provide email and password", 400
    
    qx = Quotex(email, password)
    sessions[email] = qx
    return f"Logged in as {email}"

@app.route('/start', m
