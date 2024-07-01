from flask import Flask, render_template, request, jsonify
import os
from dotenv import load_dotenv

app = Flask(__name__)
load_dotenv()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/auth', methods=['POST'])
def auth():
    # Здесь добавьте свою логику аутентификации с Telegram
    return jsonify({'status': 'success'})

if __name__ == '__main__':
    app.run(debug=True)
