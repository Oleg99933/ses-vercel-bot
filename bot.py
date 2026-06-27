import os, telebot, requests, feedparser, time, json, threading
from groq import Groq
from datetime import datetime

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
GROQ_KEY = os.environ["GROQ_API_KEY"]
bot = telebot.TeleBot(TOKEN)
groq_client = Groq(api_key=GROQ_KEY)

user_style = {}
income_data = {}
last_bid = {}
custom_agents = {}
monitoring_active = {}

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
    style_instr = f"Стиль отклика: {style}\n" if style else ""
    prompt = f"""Ты — фрилансер. Напиши короткий, вежливый и убедительный отклик на заказ.
{style_instr}
Заказ: {order_text}
Отклик:"""
    return ask_ai(prompt)

def create_agent_from_description(description):
    prompt = f"""Придумай роль и базовый промпт для нового AI‑агента, который будет решать такие задачи:
{description}
Ответь строго в формате JSON: {{"role": "...", "prompt": "..."}}"""
    try:
        return json.loads(ask_ai(prompt))
    except:
        return {"role": "Новый агент", "prompt": description}

def background_monitor(chat_id):
    while monitoring_active.get(chat_id, False):
        jobs = fetch_rss_jobs()
        if jobs:
            bot.send_message(chat_id, "🔔 Найдены новые заказы! Введите /hunt чтобы посмотреть.")
        time.sleep(600)

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, """👋 S.E.S. Global Office активен!

📡 ОХОТА: /hunt — найти заказы | /bid 1 — отклик | /send — показать отклик
🧬 АГЕНТЫ: /newagent описание — создать агента | /agents — список
💰 ФИНАНСЫ: /earned 50 за работу | /income — отчёт | /tax — налог
🎭 СТИЛЬ: /learn твой стиль | /style — показать
⚙️ СИСТЕМА: /monitor on | /ask вопрос""")

@bot.message_handler(commands=['hunt'])
def hunt(message):
    jobs = fetch_rss_jobs()
    if not jobs:
        bot.reply_to(message, "Пока подходящих заказов нет.")
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
            bot.reply_to(message, "Укажите номер заказа. Пример: /bid 1")
            return
        num = int(parts[1])
        jobs = fetch_rss_jobs()
        if not jobs or num < 1 or num > len(jobs):
            bot.reply_to(message, "Нет такого заказа. Сначала /hunt.")
            return
        order = jobs[num-1]
        order_text = f"{order['title']}\n{order['desc']}"
        bid = generate_bid(order_text, chat_id=message.chat.id)
        last_bid[message.chat.id] = bid
        bot.reply_to(message, f"✍️ **Отклик для заказа №{num}:**\n\n{bid}\n\nЧтобы снова показать, введите /send")
    except:
        bot.reply_to(message, "Ошибка. /bid 1")

@bot.message_handler(commands=['send'])
def send_bid(message):
    bid = last_bid.get(message.chat.id)
    if not bid:
        bot.reply_to(message, "Сначала сгенерируйте отклик через /bid")
        return
    bot.reply_to(message, f"📨 {bid}")

@bot.message_handler(commands=['learn'])
def learn(message):
    text = message.text.replace('/learn', '').strip()
    if not text:
        bot.reply_to(message, "Напишите стиль. Пример: /learn Я люблю короткие и смелые отклики")
        return
    user_style[message.chat.id] = text
    bot.reply_to(message, f"✅ Стиль сохранён: {text}")

@bot.message_handler(commands=['style'])
def style(message):
    s = user_style.get(message.chat.id)
    bot.reply_to(message, f"🎭 Текущий стиль: {s}" if s else "Стиль не задан. Используйте /learn")

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
        bot.reply_to(message, "💰 Пока доходов нет.")
        return
    total = sum(i['amount'] for i in data)
    tax = total * 0.05
    bot.reply_to(message, f"📊 Всего: ${total:.2f}\nНалог (5%): ${tax:.2f}\nЧистыми: ${total-tax:.2f}")

@bot.message_handler(commands=['tax'])
def tax(message):
    data = income_data.get(message.chat.id, [])
    if not data:
        bot.reply_to(message, "Нет данных для расчёта налога.")
        return
    total = sum(i['amount'] for i in data)
    bot.reply_to(message, f"🧾 Налог к уплате (5%): ${total*0.05:.2f}")

@bot.message_handler(commands=['newagent'])
def newagent(message):
    desc = message.text.replace('/newagent', '').strip()
    if not desc:
        bot.reply_to(message, "Опишите задачи: /newagent писать SEO-статьи")
        return
    agent = create_agent_from_description(desc)
    if message.chat.id not in custom_agents:
        custom_agents[message.chat.id] = []
    custom_agents[message.chat.id].append(agent)
    bot.reply_to(message, f"🆕 Создан агент:\nРоль: {agent['role']}\nПромпт: {agent['prompt']}")

@bot.message_handler(commands=['agents'])
def agents_list(message):
    base = ["🔍 Researcher", "📊 Analyst", "✍️ Copywriter", "📱 SMM Strategist", "🌐 Translator",
            "🗓️ Secretary", "🎨 Designer", "📋 Project Manager", "💰 Finance Assistant", "🧭 Coordinator"]
    extra = [f"🆕 {a['role']}" for a in custom_agents.get(message.chat.id, [])]
    bot.reply_to(message, "👥 **Текущие агенты:**\n" + "\n".join(f"- {a}" for a in base + extra), parse_mode="Markdown")

@bot.message_handler(commands=['monitor'])
def monitor_cmd(message):
    parts = message.text.split()
    if len(parts) < 2 or parts[1] not in ['on', 'off']:
        bot.reply_to(message, "Используйте: /monitor on или /monitor off")
        return
    chat_id = message.chat.id
    if parts[1] == 'on':
        monitoring_active[chat_id] = True
        bot.reply_to(message, "🔎 Автоматический мониторинг включён (каждые 10 минут).")
        threading.Thread(target=background_monitor, args=(chat_id,), daemon=True).start()
    else:
        monitoring_active[chat_id] = False
        bot.reply_to(message, "🔎 Мониторинг выключен.")

@bot.message_handler(commands=['ask'])
def ask_cmd(message):
    q = message.text.replace('/ask', '').strip()
    if not q:
        bot.reply_to(message, "Задайте вопрос после /ask")
    else:
        bot.reply_to(message, ask_ai(q))

if __name__ == '__main__':
    while True:
        try:
            bot.polling()
        except:
            time.sleep(5)
