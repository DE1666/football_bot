import math
import requests
import datetime
from flask import Flask, request, jsonify

app = Flask(__name__)

FOOTBALL_DATA_API_KEY = "656e325174784b68a41717703ee0b58f"
BOT_TOKEN = "8906894460:AAELYRJloheu02bcFaumNuGx6E9ngbgFDkU"
ADMIN_ID = 6071687483
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

def poisson(k, mean):
    return (math.pow(mean, k) * math.exp(-mean)) / math.factorial(k)

def calculate_full_analysis(home_exp, away_exp):
    home_probs = [poisson(i, home_exp) for i in range(6)]
    away_probs = [poisson(i, away_exp) for i in range(6)]
    
    win_h = sum(home_probs[h] * sum(away_probs[:h]) for h in range(1, 6))
    draw = sum(home_probs[i] * away_probs[i] for i in range(6))
    win_a = sum(away_probs[a] * sum(home_probs[:a]) for a in range(1, 6))
    tot = win_h + draw + win_a
    p_h, p_d, p_a = round((win_h/tot)*100, 1), round((draw/tot)*100, 1), round((win_a/tot)*100, 1)

    ht_h_exp, ht_a_exp = home_exp * 0.45, away_exp * 0.45
    ht_h_probs = [poisson(i, ht_h_exp) for i in range(4)]
    ht_a_probs = [poisson(i, ht_a_exp) for i in range(4)]
    ht_win_h = sum(ht_h_probs[h] * sum(ht_a_probs[:h]) for h in range(1, 4))
    ht_draw = sum(ht_h_probs[i] * ht_a_probs[i] for i in range(4))
    ht_win_a = sum(ht_a_probs[a] * sum(ht_h_probs[:a]) for a in range(1, 4))
    ht_tot = ht_win_h + ht_draw + ht_win_a
    ht_p_h, ht_p_d, ht_p_a = round((ht_win_h/ht_tot)*100, 1), round((ht_draw/ht_tot)*100, 1), round((ht_win_a/ht_tot)*100, 1)

    scores = []
    for h in range(4):
        for a in range(4):
            prob = home_probs[h] * away_probs[a]
            scores.append((f"{h}-{a}", prob))
    scores.sort(key=lambda x: x[1], reverse=True)
    top_3_scores = [f"`{s[0]}` ({round(s[1]*100, 1)}%)" for s in scores[:3]]

    max_p = max(p_h, p_d, p_a)
    pred = "🏠 فوز الأرض" if max_p == p_h else ("✈️ فوز الضيف" if max_p == p_a else "🤝 تعادل")
    goals = "⚽ أكثر من 2.5 (Over)" if (home_exp + away_exp) >= 2.50 else "🔒 أقل من 2.5 (Under)"
    btts = "✅ نعم (BTTS)" if (home_exp >= 1.05 and away_exp >= 1.05) else "❌ لا"
    confidence = "🔥 عالية جداً" if max_p >= 52.0 else ("⚡ متوسطة" if max_p >= 42.0 else "⚠️ مخاطرة")

    return {
        "p_h": p_h, "p_d": p_d, "p_a": p_a, "pred": pred,
        "ht_h": ht_p_h, "ht_d": ht_p_d, "ht_a": ht_p_a,
        "top_scores": ", ".join(top_3_scores),
        "goals": goals, "btts": btts, "confidence": confidence
    }

def get_dynamic_exp(team_name):
    name = team_name.lower()
    if any(top in name for top in ["roma", "inter", "real", "bayern", "city", "arsenal", "barcelona"]):
        return 2.15
    elif any(mid in name for mid in ["torino", "como", "villarreal", "betis", "leeds"]):
        return 1.45
    else:
        return 1.05

def get_official_today_matches():
    url = "https://api.football-data.org/v4/matches"
    headers = {"X-Auth-Token": FOOTBALL_DATA_API_KEY}
    matches_list = []
    try:
        res = requests.get(url, headers=headers, timeout=8)
        if res.status_code == 200:
            data = res.json()
            matches = data.get("matches", [])
            for m in matches[:8]:
                competition = m.get("competition", {}).get("name", "مباراة رسمية")
                h_name = m.get("homeTeam", {}).get("name", "Team Home")
                a_name = m.get("awayTeam", {}).get("name", "Team Away")
                matches_list.append({
                    "league": competition, "home": h_name, "away": a_name,
                    "h_exp": get_dynamic_exp(h_name) * 1.15,
                    "a_exp": get_dynamic_exp(a_name)
                })
    except Exception as e:
        print("API Error:", e)
    return matches_list

def send_telegram_message(chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    requests.post(f"{TELEGRAM_API}/sendMessage", json=payload)

def get_main_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "📅 مباريات اليوم", "callback_data": "cmd_today"}, {"text": "⭐ اشتراك VIP", "callback_data": "cmd_vip"}],
            [{"text": "❓ طريقة الاستخدام", "callback_data": "cmd_help"}]
        ]
    }

@app.route("/", methods=["POST", "GET"])
def webhook():
    if request.method == "POST":
        data = request.get_json()
        if "message" in data:
            chat_id = data["message"]["chat"]["id"]
            text = data["message"].get("text", "").strip()
            if text == "/start":
                msg = "مرحباً بك في **بوت التوقعات الرياضية السحابي** ⚽\n\nاضغط الأزرار بالأسفل لتصفح الخدمات:"
                send_telegram_message(chat_id, msg, get_main_keyboard())
            elif text == "/today":
                handle_today_matches(chat_id, is_vip=False)
            elif text:
                h_exp = get_dynamic_exp(text) * 1.15
                res = calculate_full_analysis(h_exp, 1.25)
                msg = (
                    f"🔎 **تحليل مباراة:** {text.title()}\n\n"
                    f"• 🏆 **النتيجة:** 🏠 {res['p_h']}% | 🤝 {res['p_d']}% | ✈️ {res['p_a']}%\n"
                    f"• ⏱️ **الشوط الأول:** 🏠 {res['ht_h']}% | 🤝 {res['ht_d']}% | ✈️ {res['ht_a']}%\n"
                    f"🎯 **النتائج الدقيقة:** {res['top_scores']}\n"
                    f"📊 **الأهداف:** {res['goals']} | **BTTS:** {res['btts']}\n"
                    f"🛡️ **الثقة:** {res['confidence']}"
                )
                send_telegram_message(chat_id, msg, get_main_keyboard())

        elif "callback_query" in data:
            cb = data["callback_query"]
            chat_id = cb["message"]["chat"]["id"]
            cb_data = cb.get("data")
            if cb_data == "cmd_today":
                handle_today_matches(chat_id, is_vip=False)
            elif cb_data == "cmd_vip":
                send_telegram_message(chat_id, "⭐ للاشتراك في VIP يرجى التواصل مع الإدارة.")
            elif cb_data == "cmd_help":
                send_telegram_message(chat_id, "💡 اكتب اسم أي فريق مباشرة لتحليله فوراً!")
        return jsonify({"status": "success"}), 200
    return "Bot is running on Vercel Serverless!", 200

def handle_today_matches(chat_id, is_vip=False):
    matches = get_official_today_matches()
    if not matches:
        send_telegram_message(chat_id, "ℹ️ لا توجد مباريات مسجلة اليوم.")
        return
    limit = len(matches) if is_vip else 3
    response = "FREE **تقرير مجاني (أول 3 مباريات فقط):**\n\n"
    for idx, m in enumerate(matches[:limit], 1):
        res = calculate_full_analysis(m["h_exp"], m["a_exp"])
        response += (
            f"**{idx}️⃣ [{m['league']}]**\n"
            f"⚽ **{m['home']} 🆚 {m['away']}**\n"
            f"• 🏆 **الاحتمالات:** 🏠 {res['p_h']}% | 🤝 {res['p_d']}% | ✈️ {res['p_a']}%\n"
            f"🎯 **الترجيح:** {res['pred']}\n------------------------------\n"
        )
    if not is_vip and len(matches) > 3:
        response += "\n🔒 هناك مباريات أخرى مغلقة!"
    send_telegram_message(chat_id, response, get_main_keyboard())

if __name__ == "__main__":
    app.run()
