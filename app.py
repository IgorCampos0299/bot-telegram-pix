import os
import telebot

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "Bot funcionando 🚀")

@bot.message_handler(func=lambda message: True)
def echo(message):
    bot.reply_to(message, f"Você disse: {message.text}")

print("Bot rodando...")
bot.infinity_polling()
