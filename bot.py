import os
import feedparser
import re
import asyncio
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler


BOT_TOKEN = os.getenv("BOT_TOKEN")


NEWS_FEEDS = {
    "BleepingComputer": "https://www.bleepingcomputer.com/feed/",
    "The Hacker News": "https://feeds.feedburner.com/TheHackersNews",
    "Dark Reading": "https://www.darkreading.com/rss.xml",
    "SecurityWeek": "https://feeds.feedburner.com/securityweek",
    "ET CISO India": "https://ciso.economictimes.indiatimes.com/rssfeeds/13357270.cms",
    "Krebs on Security": "https://krebsonsecurity.com/feed/",
    "Schneier on Security": "https://www.schneier.com/blog/atom.xml",
    "CyberScoop": "https://www.cyberscoop.com/feed/",
    "SANS ISC": "https://isc.sans.edu/rssfeed.xml",
    "Threatpost": "https://threatpost.com/feed/"
}


CVE_FEED = "https://nvd.nist.gov/feeds/xml/cve/misc/nvd-rss.xml"


sent_links = set()

stats = {
    "ransomware": 0,
    "malware": 0,
    "vulnerability": 0,
    "breach": 0
}


def clean_html(text):
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)


def simple_summary(text):

    text = clean_html(text)

    sentences = re.split(r'[.!?]', text)

    short = sentences[:4]

    summary = ". ".join(short)

    return summary[:450] + "..."


def detect_category(text):

    text = text.lower()

    if "ransomware" in text:
        stats["ransomware"] += 1
        return "💀 Ransomware"

    if "malware" in text:
        stats["malware"] += 1
        return "⚠️ Malware"

    if "vulnerability" in text or "cve" in text or "exploit" in text:
        stats["vulnerability"] += 1
        return "🐞 Vulnerability"

    if "breach" in text or "leak" in text:
        stats["breach"] += 1
        return "🔓 Data Breach"

    if "phishing" in text:
        return "🎣 Phishing"

    return "🔐 Cyber Security"


def breaking_alert(title):

    keywords = ["critical", "zero-day", "attack", "exploit"]

    title = title.lower()

    for k in keywords:
        if k in title:
            return True

    return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_chat.id

    if "users" not in context.application.bot_data:
        context.application.bot_data["users"] = set()

    context.application.bot_data["users"].add(user)

    await update.message.reply_text(
        "🚀 Cyber Threat Intelligence Bot Activated\n\nYou will now receive cyber security alerts.\n\nType /help to see commands."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = """
<b>Cyber Intelligence Bot Commands</b>

/start  - Activate alerts
/latest - Latest cyber news
/sources - News sources
/report - Daily cyber report
/help - Show commands
"""

    await update.message.reply_text(text, parse_mode="HTML")


async def sources(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = "<b>Cyber Intelligence Sources</b>\n\n"

    for s in NEWS_FEEDS.keys():
        text += f"• {s}\n"

    await update.message.reply_text(text, parse_mode="HTML")


async def latest(update: Update, context: ContextTypes.DEFAULT_TYPE):

    for source, url in NEWS_FEEDS.items():

        feed = feedparser.parse(url)

        for entry in feed.entries[:1]:

            summary = simple_summary(entry.summary)

            category = detect_category(entry.title + summary)

            message = f"""
<b>Latest Cyber News</b>

<b>Source:</b> {source}
<b>Category:</b> {category}

<b>Headline:</b>
{entry.title}

<b>Summary:</b>
{summary}
"""

            button = InlineKeyboardButton("Read Article", url=entry.link)
            keyboard = InlineKeyboardMarkup([[button]])

            await update.message.reply_text(
                message,
                parse_mode="HTML",
                reply_markup=keyboard
            )


async def daily_report(update: Update, context: ContextTypes.DEFAULT_TYPE):

    report = f"""
<b>Daily Cyber Threat Report</b>

Ransomware: {stats['ransomware']}
Malware: {stats['malware']}
Vulnerabilities: {stats['vulnerability']}
Data Breaches: {stats['breach']}

Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}
"""

    await update.message.reply_text(report, parse_mode="HTML")


async def send_news(app):

    for source, url in NEWS_FEEDS.items():

        feed = feedparser.parse(url)

        for entry in feed.entries[:3]:

            if entry.link not in sent_links:

                sent_links.add(entry.link)

                summary = simple_summary(entry.summary)

                category = detect_category(entry.title + summary)

                if breaking_alert(entry.title):
                    alert = "🚨 BREAKING CYBER ALERT"
                else:
                    alert = "🚨 Cyber Security Alert"

                message = f"""
<b>{alert}</b>

<b>Source:</b> {source}
<b>Category:</b> {category}

<b>Headline:</b>
{entry.title}

<b>Summary:</b>
{summary}
"""

                button = InlineKeyboardButton("Read Article", url=entry.link)
                keyboard = InlineKeyboardMarkup([[button]])

                for user in app.bot_data.get("users", []):

                    await app.bot.send_message(
                        chat_id=user,
                        text=message,
                        parse_mode="HTML",
                        reply_markup=keyboard
                    )


async def send_cve_alerts(app):

    feed = feedparser.parse(CVE_FEED)

    for entry in feed.entries[:3]:

        if entry.link not in sent_links:

            sent_links.add(entry.link)

            message = f"""
<b>NEW CVE ALERT</b>

<b>{entry.title}</b>

This vulnerability may affect software systems.
Security teams should review patches and updates.

More Details:
{entry.link}
"""

            for user in app.bot_data.get("users", []):

                await app.bot.send_message(
                    chat_id=user,
                    text=message,
                    parse_mode="HTML"
                )


def check_news(app):
    asyncio.run(send_news(app))


def check_cve(app):
    asyncio.run(send_cve_alerts(app))


def main():

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("latest", latest))
    app.add_handler(CommandHandler("sources", sources))
    app.add_handler(CommandHandler("report", daily_report))
    app.add_handler(CommandHandler("help", help_command))

    scheduler = BackgroundScheduler()

    scheduler.add_job(lambda: check_news(app), "interval", minutes=5)
    scheduler.add_job(lambda: check_cve(app), "interval", minutes=10)

    scheduler.start()

    print("Cyber Threat Intelligence Bot Running...")

    app.run_polling()


if __name__ == "__main__":
    main()
