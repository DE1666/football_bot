import math
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

FOOTBALL_DATA_API_KEY = "656e325174784b68a41717703ee0b58f"
BOT_TOKEN = "8906894460:AAELYRJloheu02bcFaumNuGx6E9ngbgFDkU"
ADMIN_ID = 6071687483
CHANNEL_USERNAME = "@freebetvipi"
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# تخزين مؤقت داخل الذاكرة
vip_users = set()
referrals = {}
user_inviter = {}

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

def check_channel_subscription(user_id):
    try:
        url = f"{TELEGRAM_API}/getChatMember"
        res = requests.get(url, params={"chat_id": CHANNEL_USERNAME, "user_id": user_id}, timeout=5)
        if res.status_code == 200:
            data = res.json()
            status = data.get("result", {}).get("status", "")
            if status in ["creator", "administrator", "member"]:
                return True
    except Exception as e:
        print("Sub check error:", e)
        return True
    return False

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
                    "h_exp": 1.65, "a_exp": 1.25
                })
    except Exception as e:
        print("API Error:", e)
    return matches_list

def search_team_match(query_team):
    url = "https://api.football-data.org/v4/matches"
    headers = {"X-Auth-Token": FOOTBALL_DATA_API_KEY}
    try:
        res = requests.get(url, headers=headers, timeout=8)
        if res.status_code == 200:
            data = res.json()
            for m in data.get("matches", []):
                h_name = m.get("homeTeam", {}).get("name", "")
                a_name = m.get("awayTeam", {}).get("name", "")
                if query_team.lower() in h_name.lower() or query_team.lower() in a_name.lower():
                    return {
                        "league": m.get("competition", {}).get("name", "مباراة رسمية"),
                        "home": h_name, "away": a_name,
                        "h_exp": 1.55, "a_exp": 1.20
                    }
    except Exception as e:
        print("Search match error:", e)
    return None

def send_telegram_message(chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    requests.post(f"{TELEGRAM_API}/sendMessage", json=payload)

def send_subscription_required(chat_id):
    msg = (
        "⚠️ **عذراً، يجب عليك الاشتراك في القناة الرسمية أولاً لاستخدام البوت!**\n\n"
        "اشترك في القناة ثم اضغط على **تحقق من الاشتراك** ✅"
    )
    kb = {
        "inline_keyboard": [
            [{"text": "📢 رابط القناة الرسمية", "url": "https://t.me/freebetvipi"}],
            [{"text": "✅ تحقق من الاشتراك", "callback_data": "cmd_check_sub"}]
        ]
    }
    send_telegram_message(chat_id, msg, kb)

def send_stars_invoice(chat_id):
    payload = {
        "chat_id": chat_id,
        "title": "اشتراك VIP - بوت التوقعات",
        "description": "احصل على جميع توقعات ومباريات اليوم كاملة بدون قيود لمدة شهر كامل!",
        "payload": "vip_subscription_payload",
        "currency": "XTR",
        "prices": [{"label": "اشتراك شهر VIP", "amount": 50}]
    }
    requests.post(f"{TELEGRAM_API}/sendInvoice", json=payload)

def answer_pre_checkout_query(pre_checkout_query_id):
    payload = {"pre_checkout_query_id": pre_checkout_query_id, "ok": True}
    requests.post(f"{TELEGRAM_API}/answerPreCheckoutQuery", json=payload)

def get_main_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "📅 مباريات اليوم", "callback_data": "cmd_today"}, {"text": "⭐ اشتراك VIP (50 نجمة)", "callback_data": "cmd_vip"}],
            [{"text": "🎁 اشتراك VIP مجاني (رابط الدعوة)", "callback_data": "cmd_invite"}],
            [{"text": "❓ طريقة الاستخدام", "callback_data": "cmd_help"}]
        ]
    }

@app.route("/", methods=["POST", "GET"])
def webhook():
    if request.method == "POST":
        data = request.get_json()

        if "pre_checkout_query" in data:
            query_id = data["pre_checkout_query"]["id"]
            answer_pre_checkout_query(query_id)
            return jsonify({"status": "success"}), 200

        if "message" in data and "successful_payment" in data["message"]:
            chat_id = data["message"]["chat"]["id"]
            vip_users.add(chat_id)
            msg = "🎉 **تمت عملية الشراء بنجاح!**\n\nأصبحت الآن مشتركاً في **VIP** ⭐ ويمكنك رؤية كامل مباريات اليوم بدون قيود!"
            send_telegram_message(chat_id, msg, get_main_keyboard())
            return jsonify({"status": "success"}), 200

        if "message" in data:
            chat_id = data["message"]["chat"]["id"]
            text = data["message"].get("text", "").strip()

            # التحقق من الاشتراك بالقناة
            if not check_channel_subscription(chat_id) and chat_id != ADMIN_ID:
                send_subscription_required(chat_id)
                return jsonify({"status": "success"}), 200

            is_vip = chat_id in vip_users or chat_id == ADMIN_ID

            if text.startswith("/start"):
                parts = text.split()
                if len(parts) > 1:
                    inviter_id = parts[1]
                    try:
                        inviter_id = int(inviter_id)
                        if inviter_id != chat_id and chat_id not in user_inviter:
                            user_inviter[chat_id] = inviter_id
                            referrals[inviter_id] = referrals.get(inviter_id, 0) + 1
                            count = referrals[inviter_id]
                            send_telegram_message(inviter_id, f"🎉 **انضم شخص جديد عبر رابطك!**\nعددهم الحالي: `{count}/10` شخص.")
                            if count >= 10 and inviter_id not in vip_users:
                                vip_users.add(inviter_id)
                                send_telegram_message(inviter_id, "🥳 **مبروك! قمت بدعوة 10 أشخاص بنجاح.**\nتم تفعيل اشتراك **VIP** المجاني لمدة شهر!")
                    except ValueError:
                        pass

                msg = "مرحباً بك في **بوت التوقعات الرياضية السحابي** ⚽\n\nاضغط الأزرار بالأسفل لتصفح الخدمات:"
                send_telegram_message(chat_id, msg, get_main_keyboard())

            elif text.startswith("/admin") and chat_id == ADMIN_ID:
                msg = f"⚙️ **لوحة الأدمن الاحترافية:**\n\n• عدد مشتركين VIP: `{len(vip_users)}`\n• عدد المسجلين بالدعوات: `{len(user_inviter)}`\n\n🔧 **أوامر التحكم السريعة:**\n• `/addvip 123456` : لتفعيل VIP لشخص مجاناً\n• `/delvip 123456` : لإلغاء VIP عن شخص"
                send_telegram_message(chat_id, msg, get_main_keyboard())

            elif text.startswith("/addvip") and chat_id == ADMIN_ID:
                try:
                    target_id = int(text.split()[1])
                    vip_users.add(target_id)
                    msg = f"✅ تم تفعيل VIP للمستخدم: `{target_id}` بنجاح!"
                except:
                    msg = "❌ خطأ! اكتب الأمر هكذا: `/addvip 12345678`"
                send_telegram_message(chat_id, msg, get_main_keyboard())

            elif text.startswith("/delvip") and chat_id == ADMIN_ID:
                try:
                    target_id = int(text.split()[1])
                    vip_users.discard(target_id)
                    msg = f"🗑️ تم إلغاء VIP عن المستخدم: `{target_id}`"
                except:
                    msg = "❌ خطأ! اكتب الأمر هكذا: `/delvip 12345678`"
                send_telegram_message(chat_id, msg, get_main_keyboard())

            elif text == "/today":
                handle_today_matches(chat_id, is_vip=is_vip)

            # للبحث عن المباريات: يمنع التحليل الوهمي إذا بدأت الرسالة بـ /
            elif text and not text.startswith("/"):
                match_data = search_team_match(text)
                if match_data:
                    res = calculate_full_analysis(match_data["h_exp"], match_data["a_exp"])
                    msg = (
                        f"🔎 **تحليل مباراة رسمية:** [{match_data['league']}]\n"
                        f"⚽ **{match_data['home']} 🆚 {match_data['away']}**\n\n"
                        f"• 🏆 **النتيجة:** 🏠 {res['p_h']}% | 🤝 {res['p_d']}% | ✈️ {res['p_a']}%\n"
                        f"• ⏱️ **الشوط الأول:** 🏠 {res['ht_h']}% | 🤝 {res['ht_d']}% | ✈️ {res['ht_a']}%\n"
                        f"🎯 **النتائج الدقيقة:** {res['top_scores']}\n"
                        f"📊 **الأهداف:** {res['goals']} | **BTTS:** {res['btts']}\n"
                        f"🛡️ **الثقة:** {res['confidence']}"
                    )
                else:
                    msg = f"❌ لم نجد مباراة حقيقية مجدولة اليوم أو قريباً للفريق: `{text}`.\nيرجى التأكد من كتابة الاسم الصحيح للفريق بالإنجليزية."
                send_telegram_message(chat_id, msg, get_main_keyboard())

        elif "callback_query" in data:
            cb = data["callback_query"]
            chat_id = cb["message"]["chat"]["id"]
            cb_data = cb.get("data")

            if cb_data == "cmd_check_sub":
                if check_channel_subscription(chat_id) or chat_id == ADMIN_ID:
                    send_telegram_message(chat_id, "✅ تم التحقق! مرحباً بك في البوت.", get_main_keyboard())
                else:
                    send_subscription_required(chat_id)
                return jsonify({"status": "success"}), 200

            is_vip = chat_id in vip_users or chat_id == ADMIN_ID

            if cb_data == "cmd_today":
                handle_today_matches(chat_id, is_vip=is_vip)
            elif cb_data == "cmd_vip":
                send_stars_invoice(chat_id)
            elif cb_data == "cmd_invite":
                my_count = referrals.get(chat_id, 0)
                msg = (
                    f"🎁 **برنامج الدعوة للحصول على VIP مجاناً:**\n\n"
                    f"قم بنشر الرابط الخاص بك، وعند انضمام **10 أشخاص** سيتفعل معك حساب VIP لمدة شهر تلقائياً!\n\n"
                    f"🔗 **رابطك الخاص:**\n`https://t.me/bot8906894460_bot?start={chat_id}`\n\n"
                    f"👥 **عدد الذين دعوتهم:** `{my_count}/10` شخص"
                )
                send_telegram_message(chat_id, msg, get_main_keyboard())
            elif cb_data == "cmd_help":
                send_telegram_message(chat_id, "💡 اكتب اسم أي فريق بالإنجليزية (مثل Real Madrid أو Arsenal) للبحث عن مباراته الحقيقية وتحليلها!")
        return jsonify({"status": "success"}), 200
    return "Bot is running on Vercel Serverless!", 200

def handle_today_matches(chat_id, is_vip=False):
    matches = get_official_today_matches()
    if not matches:
        send_telegram_message(chat_id, "ℹ️ لا توجد مباريات مسجلة اليوم.")
        return
    limit = len(matches) if is_vip else 3
    header = "⭐ **تقرير VIP (جميع المباريات مفتوحة):**\n\n" if is_vip else "FREE **تقرير مجاني (أول 3 مباريات فقط):**\n\n"
    response = header
    for idx, m in enumerate(matches[:limit], 1):
        res = calculate_full_analysis(m["h_exp"], m["a_exp"])
        response += (
            f"**{idx}️⃣ [{m['league']}]**\n"
            f"⚽ **{m['home']} 🆚 {m['away']}**\n"
            f"• 🏆 **الاحتمالات:** 🏠 {res['p_h']}% | 🤝 {res['p_d']}% | ✈️ {res['p_a']}%\n"
            f"🎯 **الترجيح:** {res['pred']}\n------------------------------\n"
        )
    if not is_vip and len(matches) > 3:
        response += "\n🔒 باقي المباريات مغلقة! اشترك في VIP أو ادعُ 10 أصدقاء لفتحها مجاناً."
    send_telegram_message(chat_id, response, get_main_keyboard())

if __name__ == "__main__":
    app.run()
