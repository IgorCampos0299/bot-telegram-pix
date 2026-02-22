import os
import time
import requests
import telebot
import mercadopago
import sqlite3
from datetime import datetime, timedelta
import threading

DB_PATH = "db.sqlite"

def db_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def db_init():
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS assinaturas (
            user_id INTEGER PRIMARY KEY,
            expira_em TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def set_expiracao(user_id: int, dias: int = 30):
    expira = (datetime.utcnow() + timedelta(days=dias)).isoformat()
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO assinaturas (user_id, expira_em)
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET expira_em=excluded.expira_em
    """, (user_id, expira))
    conn.commit()
    conn.close()

def listar_expirados():
    agora = datetime.utcnow().isoformat()
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM assinaturas WHERE expira_em < ?", (agora,))
    rows = cur.fetchall()
    conn.close()
    return [r[0] for r in rows]

def remover_registro(user_id: int):
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM assinaturas WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

def remover_do_grupo(user_id: int):
    # banir
    url_ban = f"https://api.telegram.org/bot{BOT_TOKEN}/banChatMember"
    r1 = requests.post(url_ban, json={"chat_id": GROUP_ID, "user_id": user_id}, timeout=15)
    # desbanir (permite voltar pagando de novo)
    url_unban = f"https://api.telegram.org/bot{BOT_TOKEN}/unbanChatMember"
    r2 = requests.post(url_unban, json={"chat_id": GROUP_ID, "user_id": user_id}, timeout=15)
    return r1.ok and r2.ok

def job_remocao():
    while True:
        try:
            expirados = listar_expirados()
            for user_id in expirados:
                ok = remover_do_grupo(user_id)
                # remove do banco independentemente, pra não ficar tentando pra sempre
                remover_registro(user_id)
        except Exception:
            pass

        # roda a cada 6 horas (pode ajustar)
        time.sleep(6 * 60 * 60)



BOT_TOKEN = os.getenv("BOT_TOKEN")
MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")

if not BOT_TOKEN or not MP_ACCESS_TOKEN or not GROUP_ID:
    print("Faltam variáveis: BOT_TOKEN, MP_ACCESS_TOKEN, GROUP_ID")
    raise SystemExit(1)

GROUP_ID = int(GROUP_ID)

bot = telebot.TeleBot(BOT_TOKEN)
sdk = mercadopago.SDK(MP_ACCESS_TOKEN)

VALOR = 5.99

def criar_convite_unico() -> str:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/createChatInviteLink"
    payload = {
        "chat_id": GROUP_ID,
        "member_limit": 1,
        "expire_date": int(time.time()) + 600  # 10 min
    }
    r = requests.post(url, json=payload, timeout=15)
    r.raise_for_status()
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(data)
    return data["result"]["invite_link"]

def gerar_pix(user_id):
    payment_data = {
        "transaction_amount": float(VALOR),
        "description": "Acesso VIP Telegram",
        "payment_method_id": "pix",
        "payer": {"email": f"user{user_id}@bot.com"}
    }

    pagamento = sdk.payment().create(payment_data)
    resposta = pagamento["response"]

    qr_code = resposta["point_of_interaction"]["transaction_data"]["qr_code"]
    payment_id = resposta["id"]
    return qr_code, payment_id

def verificar_pagamento(payment_id):
    pagamento = sdk.payment().get(payment_id)
    return pagamento["response"]["status"]

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "Bem-vindo!\nDigite /pagar para gerar seu PIX de R$5,99.")

@bot.message_handler(commands=['pagar'])
def pagar(message):
    user_id = message.from_user.id
    bot.reply_to(message, "Gerando PIX...")

    try:
        qr_code, payment_id = gerar_pix(user_id)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Erro ao gerar PIX: {e}")
        return

    bot.send_message(
        message.chat.id,
        "💳 Envie R$5,99 via PIX:\n\n"
        "Copie o código abaixo:\n\n"
        f"<pre>{qr_code}</pre>\n\n"
        "Aguardando pagamento...",
        parse_mode="HTML"
    )

    for _ in range(36):  # 3 minutos
        time.sleep(5)
        try:
            status = verificar_pagamento(payment_id)
        except Exception:
            continue

        if status == "approved":
            try:
                invite_link = criar_convite_unico()
            except Exception as e:
                bot.send_message(
                    message.chat.id,
                    "✅ Pagamento aprovado!\n"
                    "❌ Mas não consegui criar o link do grupo.\n"
                    "Confirme se eu sou ADMIN e tenho permissão de convidar usuários."
                )
                return

            bot.send_message(
                message.chat.id,
                "✅ Pagamento aprovado!\n\n"
                set_expiracao(user_id, dias=30)
                f"🔗 Aqui está seu acesso (1 uso / expira em 10 min):\n{invite_link}"
            )
            return

        if status in ("rejected", "cancelled"):
            bot.send_message(message.chat.id, f"❌ Pagamento {status}. Gere outro com /pagar.")
            return

    bot.send_message(message.chat.id, "⏳ Pagamento não identificado a tempo. Tente /pagar novamente.")

print("Bot rodando com PIX + acesso ao grupo...")
db_init()
threading.Thread(target=job_remocao, daemon=True).start()
bot.infinity_polling(timeout=60, long_polling_timeout=60)
