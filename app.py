from flask import Flask, request
import requests
import os

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")

@app.route("/", methods=["GET"])
def home():
    return "Bot online"

@app.route("/telegram", methods=["POST"])
def telegram_webhook():
    data = request.get_json()

    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")

        resposta = f"Você disse: {text}"

        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": resposta}
        )

    return "ok", 200

if __name__ == "__main__":
    app.run()
