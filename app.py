
from flask import Flask
from webhook.webhook import webhook_bp
from database.db import criar_tabelas

app = Flask(__name__)
app.register_blueprint(webhook_bp)

criar_tabelas()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
