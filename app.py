import os
import requests
import mercadopago
from flask import Flask, request, jsonify

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")

VALOR = 5.99
sdk = mercadopago.SDK(MP_ACCESS_TOKEN)

def enviar_mensagem(chat_id, texto):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": chat_id,
        "text": texto
    })

def gerar_pix(chat_id):
    payment_data = {
        "transaction_amount": VALOR,
        "description": "Acesso VIP Telegram",
        "payment_method_id": "pix",
        "payer": {
            "email": f"user{chat_id}@bot.com"
        }
    }

    pagamento = sdk.payment().create(payment_data)
    response = pagamento["response"]

    qr_code = response["point_of_interaction"]["transaction_data"]["qr_code"]
    payment_id = response["id"]

    return qr_code, payment_id


# 🔹 WEBHOOK TELEGRAM (AGORA EM /telegram)
@app.route("/telegram", methods=["POST"])
def telegram_webhook():
    data = request.json

    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        texto = data["message"].get("text", "")

        if texto == "/start":
            enviar_mensagem(chat_id, "Bem-vindo!\nDigite /pagar para gerar seu PIX de R$5,99.")

        elif texto == "/pagar":
            qr_code, payment_id = gerar_pix(chat_id)
            enviar_mensagem(chat_id, f"Envie R$5,99 via PIX:\n\n{qr_code}")

    return jsonify({"status": "ok"})


# 🔹 WEBHOOK MERCADO PAGO
@app.route("/webhook", methods=["POST"])
def mp_webhook():
    data = request.json

    if data.get("type") == "payment":
        payment_id = data["data"]["id"]
        pagamento = sdk.payment().get(payment_id)
        status = pagamento["response"]["status"]

        if status == "approved":
            print("Pagamento aprovado!")

    return jsonify({"status": "ok"})


# 🔹 ROTA HOME
@app.route("/", methods=["GET"])
def home():
    return "Bot online"
