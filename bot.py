import os, telebot, requests, feedparser, time
from groq import Groq
from datetime import datetime

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_KEY = os.getenv("GROQ_API_KEY")
if not TOKEN or not GROQ_KEY:
    raise Exception("Missing TELEGRAM_BOT_TOKEN or GROQ_API_KEY environment variables")
bot = telebot.TeleBot(TOKEN)
groq_client = Groq(api_key=GROQ_KEY)

user_style = {}
income_data = {}
last_bid = {}

RSS_FEEDS = ["https://www.freelancer.com/rss.xml"]
KEYWORDS = ["бот", "парсинг", "скрипт", "телеграм", "python", "дизайн", "логотип", "копирайт", "статья", "перевод"]

def fetch_rss_jobs():
    jobs = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:
                title = entry.get("title", "")
                desc = entry.get("summary", "")
                if any(kw in f"{title} {desc}".lower() for kw in KEYWORDS):
                    jobs.append({"title": title, "desc": desc[:300], "link": entry.get("link", "")})
        except:
            continue
    return jobs

def ask_ai(prompt):
    try:
        resp = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant"
        )
        return resp.choices[0].message.content
    except:
        return "AI offline"

def generate_bid(order_text, chat_id=None):
    style = user_style.get(chat_id, "")
    style_instr = f"Style: {style}\n" if style else ""
    prompt = f"""You are a freelancer. Write a short, polite, and convincing response to this job.
{style_instr}
Job: {order_text}
Response:"""
    return ask_ai(prompt)

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, """👋 SES Global Office активен!
/hunt - заказы | /bid 1 - отклик | /send - показать
/learn стиль | /earned сумма | /income - доход | /ask вопрос""")

@bot.message_handler(commands=['hunt'])
def hunt(message):
    jobs = fetch_rss_jobs()
    if not jobs:
        bot.reply_to(message, "Пока заказов нет.")
        return
    response = "📋 **Заказы:**\n"
    for i, job in enumerate(jobs[:5], 1):
        response += f"\n{i}. {job['title']}\n{job['desc']}\n{job['link']}\n"
    response += "\nВведите /bid и номер заказа."
    bot.reply_to(message, response, parse_mode="Markdown")

@bot.message_handler(commands=['bid'])
def bid_cmd(message):
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "Укажите номер. /bid 1")
            return
        num = int(parts[1])
        jobs = fetch_rss_jobs()
        if not jobs or num < 1 or num > len(jobs):
            bot.reply_to(message, "Нет такого заказа. /hunt")
            return
        order = jobs[num-1]
        order_text = f"{order['title']}\n{order['desc']}"
        bid = generate_bid(order_text, chat_id=message.chat.id)
        last_bid[message.chat.id] = bid
        bot.reply_to(message, f"✍️ Отклик:\n{bid}\n/send чтобы показать.")
    except:
        bot.reply_to(message, "Ошибка. /bid 1")

@bot.message_handler(commands=['send'])
def send_bid(message):
    bid = last_bid.get(message.chat.id)
    if not bid:
        bot.reply_to(message, "Сначала /bid")
        return
    bot.reply_to(message, f"📨 {bid}")

@bot.message_handler(commands=['learn'])
def learn(message):
    text = message.text.replace('/learn', '').strip()
    if not text:
        bot.reply_to(message, "Пример: /learn Я люблю короткие отклики")
        return
    user_style[message.chat.id] = text
    bot.reply_to(message, f"✅ Стиль сохранён: {text}")

@bot.message_handler(commands=['earned'])
def earned(message):
    try:
        parts = message.text.split(maxsplit=2)
        amount = float(parts[1])
        note = parts[2] if len(parts) > 2 else ""
        if message.chat.id not in income_data:
            income_data[message.chat.id] = []
        income_data[message.chat.id].append({"amount": amount, "date": str(datetime.now()), "note": note})
        total = sum(i['amount'] for i in income_data[message.chat.id])
        bot.reply_to(message, f"✅ +${amount:.2f}\nНалог (5%): ${amount*0.05:.2f}\nВсего: ${total:.2f}")
    except:
        bot.reply_to(message, "Формат: /earned 50 за логотип")

@bot.message_handler(commands=['income'])
def income(message):
    data = income_data.get(message.chat.id, [])
    if not data:
        bot.reply_to(message, "💰 Пока $0")
        return
    total = sum(i['amount'] for i in data)
    tax = total * 0.05
    bot.reply_to(message, f"📊 Всего: ${total:.2f}\nНалог: ${tax:.2f}\nЧистыми: ${total-tax:.2f}")

@bot.message_handler(commands=['ask'])
def ask_cmd(message):
    q = message.text.replace('/ask', '').strip()
    if not q:
        bot.reply_to(message, "Вопрос после /ask")
    else:
        bot.reply_to(message, ask_ai(q))

if __name__ == '__main__':
    while True:
        try:
            bot.polling()
        except:
            time.sleep(5)
