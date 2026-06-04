import os
import socket
import threading
import random
import pymysql
import json
import time
import hashlib
from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
from google import genai
from google.genai import types

app = Flask(__name__, template_folder="htmlfile", static_folder="font")
CORS(app)

HOST = "0.0.0.0"
PORT = 65432  # 後台 Socket

# 房間狀態
# 結構：{ "房號": { "messages": [], "story": "", "ans": "", "status": "waiting", "player_count": 0 } }
rooms = {}


# GEMINI API 配置

GEMINI_API_KEY = None

if os.path.exists("key.txt"):
    with open("key.txt", "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("API_KEY="):
                GEMINI_API_KEY = line.split("=")[1].strip()

client = None
if GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        print("成功配置 Gemini API！")
    except Exception as e:
        print(f"[異常] 無法配置 Gemini API: {e}")
else:
    print("[警告] 未找到有效的 Gemini API 金鑰。")


# ==================== 資料庫 ====================


# 【資料庫連線】
def get_db_connection():
    return pymysql.connect(
        host="127.0.0.1",
        user="root",
        password="",
        database="turtle_soup",
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


# 【隨機撈取題目】
def get_random_story():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT story, answer FROM game_stories ORDER BY RAND() LIMIT 1"
            )
            row = cursor.fetchone()
        conn.close()
        if row:
            return row["story"], row["answer"]
    except Exception as e:
        print(f"[資料庫異常] 無法撈取題目: {e}")
    return "暫無題目", "暫無答案"


# ==================== 密碼加密 ====================
def hash_password(password):
    """使用SHA256加密密碼"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, hashed_password):
    """驗證密碼"""
    return hash_password(password) == hashed_password


# ==================== 網頁 ====================
@app.route("/")
def home():
    return render_template("home.html")


@app.route("/cli_page")
def cli_page():
    return render_template("cli.html")


@app.route("/submit_page")
def submit_page():
    return render_template("submit.html")


@app.route("/login_page")
def login_page():
    return render_template("login.html")


@app.route("/register_page")
def register_page():
    return render_template("register.html")


# ==================== 功能 ====================


# === 認證 ===


# 【用户註冊】
@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json()
    username = data.get("username", "").strip()
    email = data.get("email", "").strip()
    password = data.get("password", "")

    # 驗證輸入
    if not username or not email or not password:
        return jsonify({"status": "failed", "message": "所有欄位都是必填的！"}), 400

    if len(username) < 3 or len(username) > 20:
        return jsonify({"status": "failed", "message": "帳號必須是3-20個字符"}), 400

    if len(password) < 6:
        return jsonify({"status": "failed", "message": "密碼至少需要6個字符"}), 400

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # 檢查帳號是否已存在
            cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
            if cursor.fetchone():
                return jsonify({"status": "failed", "message": "帳號已存在！"}), 400

            # 檢查郵箱是否已註冊
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cursor.fetchone():
                return jsonify({"status": "failed", "message": "郵箱已被註冊！"}), 400

            # 插入新用户
            hashed_password = hash_password(password)
            sql = "INSERT INTO users (username, email, password) VALUES (%s, %s, %s)"
            cursor.execute(sql, (username, email, hashed_password))
            conn.commit()
        conn.close()

        return jsonify({"status": "success", "message": "註冊成功！請登入。"})

    except Exception as e:
        print(f"[註冊異常] {e}")
        return jsonify({"status": "failed", "message": f"註冊失敗: {e}"}), 500


# 【用户登入】
@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"status": "failed", "message": "帳號和密碼不能為空！"}), 400

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, username, password FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()
        conn.close()

        if not user:
            return jsonify({"status": "failed", "message": "帳號不存在！"}), 401

        if not verify_password(password, user["password"]):
            return jsonify({"status": "failed", "message": "密碼錯誤！"}), 401

        # 登入成功，返回用户信息
        return jsonify({
            "status": "success",
            "message": "登入成功！",
            "user_id": user["id"],
            "username": user["username"]
        })

    except Exception as e:
        print(f"[登入異常] {e}")
        return jsonify({"status": "failed", "message": f"登入失敗: {e}"}), 500


# === 題目投稿 ===


# 【查重功能】
@app.route("/api/get_all_titles", methods=["GET"])
def get_all_titles():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT title, story FROM game_stories")
            rows = cursor.fetchall()
        conn.close()
        return jsonify(rows)
    except:
        return jsonify([])


# 【投稿功能】
@app.route("/api/submit", methods=["POST"])
def submit_story():
    data = request.get_json()
    title, story, answer = data.get("title"), data.get("story"), data.get("answer")
    user_id = data.get("user_id")  # 取得用户ID
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # 投稿記錄表，包含user_id
            sql = "INSERT INTO submissions (title, story, answer, user_id) VALUES (%s, %s, %s, %s)"
            cursor.execute(sql, (title, story, answer, user_id))
            # 題庫表
            sql2 = "INSERT INTO game_stories (title, story, answer) VALUES (%s, %s, %s)"
            cursor.execute(sql2, (title, story, answer))
        conn.commit()
        conn.close()
        return jsonify({"message": "投稿成功！已即時存入題庫！"})
    except Exception as e:
        return jsonify({"message": f"寫入失敗: {e}"}), 500


# === 遊戲房間 ===


# 【單人】
@app.route("/api/create_room", methods=["POST"])
def create_room():
    story, answer = get_random_story()
    return jsonify({"story": story, "answer": answer})


# 【建立房間】
@app.route("/api/create_specific_room", methods=["POST"])
def create_specific_room():
    data = request.get_json()
    room_id = data.get("room_id")
    story, answer = get_random_story()
    rooms[room_id] = {
        "messages": [f"房間 {room_id} 已成立。等待玩家加入..."],
        "story": story,
        "ans": answer,
        "status": "waiting",
        "player_count": 0,
    }
    print(f"[系統日誌] 關主成功開拓多人房間: {room_id}")
    return jsonify({"story": story, "answer": answer})


# 【加入房間】
@app.route("/api/connect_room", methods=["POST"])
def connect_room():
    data = request.get_json()
    room_id = data.get("room_id")
    player_id = data.get("player_id", "玩家")

    if room_id in rooms:
        rooms[room_id]["player_count"] += 1
        rooms[room_id]["messages"].append(f"【{player_id}】進入了房間。")
        print(
            f"[系統日誌] 房間 {room_id} 新增一位玩家，目前在線: {rooms[room_id]['player_count']} 人"
        )
        return jsonify({"status": "success"})
    return jsonify({"status": "failed", "message": "房間號碼不存在！"}), 404


# 【玩家/關主 獲取訊息面板狀態】
@app.route("/api/get_messages", methods=["GET"])
def get_messages():
    room_id = request.args.get("room_id")
    if room_id not in rooms:
        return jsonify({"status": "closed", "messages": [], "player_count": 0})
    return jsonify(
        {
            "status": rooms[room_id]["status"],
            "messages": rooms[room_id]["messages"],
            "player_count": rooms[room_id]["player_count"],
        }
    )


# === 遊戲開始後 ===


# 【開始遊戲】
@app.route("/api/start_game", methods=["POST"])
def start_game():
    data = request.get_json()
    room_id = data.get("room_id")
    if room_id in rooms:
        rooms[room_id]["status"] = "playing"
        rooms[room_id]["messages"].append(
            f"遊戲正式開始！【題目】：{rooms[room_id]['story']}"
        )
        return jsonify({"status": "success"})
    return jsonify({"message": "房間不存在"}), 400


# 【玩家提問】
@app.route("/api/send_msg", methods=["POST"])
def send_msg():
    data = request.get_json()
    room_id = data.get("room_id")
    msg = data.get("msg", "")
    if room_id in rooms:
        rooms[room_id]["messages"].append(msg)
        print(f"[房間 {room_id}] 收到提問: {msg}")
        return jsonify({"status": "success"})
    return jsonify({"message": "房間不存在"}), 400


# 【關主回覆】
@app.route("/api/reply", methods=["POST"])
def handle_reply():
    data = request.get_json()
    room_id = data.get("room_id")
    answer = data.get("reply", "")
    if room_id not in rooms:
        return jsonify({"message": "房間不存在"}), 400

    reply_msg = f"關主回覆：【{answer}】"
    rooms[room_id]["messages"].append(reply_msg)

    if "回答正確" in answer:
        truth = f"故事真相：{rooms[room_id]['ans']} 遊戲結束！"
        rooms[room_id]["messages"].append(truth)

    return jsonify({"message": "已廣播回覆"})


# 【關主提示】
@app.route("/api/send_hint", methods=["POST"])
def send_hint():
    data = request.get_json()
    room_id = data.get("room_id")
    hint_content = data.get("hint", "")[:30]
    if room_id in rooms:
        rooms[room_id]["messages"].append(f'關主提示："{hint_content}"')
        return jsonify({"status": "success"})
    return jsonify({"message": "房間不存在"}), 400


# 【下一題】
@app.route("/api/next_round", methods=["POST"])
def next_round():
    data = request.get_json()
    room_id = data.get("room_id")
    if room_id in rooms:
        story, answer = get_random_story()
        rooms[room_id]["story"] = story
        rooms[room_id]["ans"] = answer
        rooms[room_id]["status"] = "waiting"
        rooms[room_id]["messages"] = [
            f"關主已開啟新的一局！房號 {room_id}，等待遊戲開始..."
        ]
        return jsonify({"status": "success"})
    return jsonify({"message": "房間不存在"}), 400


# 【防手滑/關閉網頁銷毀房間】
@app.route("/api/close_room", methods=["POST"])
def close_room():
    if request.is_json:
        data = request.get_json()
    else:
        data = json.loads(request.data.decode("utf-8"))
    room_id = data.get("room_id")
    if room_id in rooms:
        print(f"[系統安全維護] 房間 {room_id} 已由關主端觸發銷毀程序。")
        rooms[room_id]["status"] = "closed"

        def delayed_delete():
            time.sleep(2)
            if room_id in rooms:
                del rooms[room_id]

        threading.Thread(target=delayed_delete, daemon=True).start()
    return jsonify({"status": "success"})


# 【單人模式】
@app.route("/api/ai_chat", methods=["POST"])
def ai_chat():
    data = request.get_json()
    player_msg = data.get("msg", "")  # 玩家問的問題
    answer_context = data.get("answer", "")  # 從資料庫撈出來的真相答案

    # 防呆：如果沒填 API Key 或初始化失敗，啟動原本的弱智型 if/else 備援方案
    if not client:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "本機未偵測到 AI 關主憑證（config.txt），單人模式暫不可用。請先加入其他玩家的多人房間吧！",
                }
            ),
            412,
        )

    # 提示詞
    system_instruction = f"""
    你現在是一位「海龜湯遊戲關主」。
    
    【本局真相（湯底）】：
    {answer_context}
    
    【你的絕對規則】：
    1. 玩家會對你提出一個關於故事真相的「是非題」。
    2. 你只能根據上方的【本局真相】進行邏輯推理，並嚴格從以下「四個固定選項」中選擇一個回答，絕對不能多說任何解釋：
       - 若玩家猜對了關鍵核心、或是要求公布解答，請回答：『回答正確』。
       - 若玩家問的問題在真相中是成立的、正確的，請回答：『是』
       - 若玩家問的問題在真相中是不成立的、錯誤的，請回答：『否』
       - 若玩家問的方向完全無關緊要，請回答：『與此無關』
    3. 除非玩家要求給予提示，否則除了這四個標準回覆，不要對玩家做任何劇情解釋！
    """

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"玩家提問：{player_msg}",
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.2,
            ),
        )

        ai_reply = response.text.strip()
        print(f"[AI關主思維] 玩家問: {player_msg} -> AI判定: {ai_reply}")

        if "回答正確" in ai_reply:
            ai_reply = f"回答正確！揭曉真相：{answer_context}"

        return jsonify({"reply": ai_reply})

    except Exception as e:
        print(f"[AI連線異常] 呼叫 Gemini 發生錯誤: {e}")
        return jsonify({"reply": "AI 關主開小差了，請再試一次！"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5678, debug=False, threaded=True)
