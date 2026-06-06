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

if os.path.exists("config.txt"):
    with open("config.txt", "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("GEMINI_API_KEY="):
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


# def ensure_player_stats_table():
#     conn = get_db_connection()
#     with conn.cursor() as cursor:
#         cursor.execute(
#             """
#             CREATE TABLE IF NOT EXISTS player_stats (
#                 user_id int(11) NOT NULL,
#                 wins int(11) NOT NULL DEFAULT 0,
#                 games_played int(11) NOT NULL DEFAULT 0,
#                 last_win_at timestamp NULL DEFAULT NULL,
#                 PRIMARY KEY (user_id),
#                 FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
#             ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci
#             """
#         )
#     conn.commit()
#     conn.close()


# ==================== 網頁 ====================
@app.route("/")
def home():
    return render_template("home.html")


@app.route("/cli_page")
def cli_page():
    return render_template("cli.html")


@app.route("/leaderboard_page")
def leaderboard_page():
    return render_template("leaderboard.html")


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
@app.route("/api/leaderboard", methods=["GET"])
def leaderboard():
    try:
        # ensure_player_stats_table()
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    u.id,
                    u.username,
                    COALESCE(ps.wins, 0) AS wins,
                    COALESCE(ps.games_played, 0) AS games_played,
                    COUNT(s.id) AS submissions,
                    COALESCE(ps.wins, 0) * 100 AS score,
                    ps.last_win_at
                FROM users u
                LEFT JOIN player_stats ps ON ps.user_id = u.id
                LEFT JOIN submissions s ON s.user_id = u.id
                GROUP BY u.id, u.username, ps.wins, ps.games_played, ps.last_win_at
                ORDER BY score DESC, wins DESC, submissions DESC, u.username ASC
                LIMIT 50
                """
            )
            rows = cursor.fetchall()
        conn.close()

        for index, row in enumerate(rows, start=1):
            row["rank"] = index
            if row.get("last_win_at"):
                row["last_win_at"] = row["last_win_at"].strftime("%Y-%m-%d %H:%M")

        return jsonify({"status": "success", "players": rows})
    except Exception as e:
        print(f"[排行榜錯誤] {e}")
        return jsonify({"status": "failed", "message": f"排行榜讀取失敗: {e}"}), 500


@app.route("/api/record_win", methods=["POST"])
def record_win():
    data = request.get_json()
    user_id = data.get("user_id")

    if not user_id:
        return jsonify({"status": "ignored", "message": "未登入，不紀錄排行榜"})

    try:
        # ensure_player_stats_table()
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
            if not cursor.fetchone():
                conn.close()
                return jsonify({"status": "failed", "message": "找不到使用者"}), 404

            cursor.execute(
                """
                INSERT INTO player_stats (user_id, wins, games_played, last_win_at)
                VALUES (%s, 1, 1, CURRENT_TIMESTAMP)
                ON DUPLICATE KEY UPDATE
                    wins = wins + 1,
                    games_played = games_played + 1,
                    last_win_at = CURRENT_TIMESTAMP
                """,
                (user_id,),
            )
        conn.commit()
        conn.close()
        return jsonify({"status": "success"})
    except Exception as e:
        print(f"[勝場紀錄錯誤] {e}")
        return jsonify({"status": "failed", "message": f"勝場紀錄失敗: {e}"}), 500


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
    story_context = data.get("story","")

    if not client:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "本機未偵測到憑證，單人模式暫不可用。請先加入其他玩家的多人房間吧！",
                }
            ),
            412,
        )

    # 提示詞
    system_instruction = f"""
        你現在是一位「海龜湯遊戲關主」。

        你的角色：
        你是負責主持海龜湯遊戲的關主。你的工作不是講故事，也不是自由聊天，而是根據「題目」與「真相」判斷玩家的問題，並用固定格式回答。

        你的個性：
        冷靜、嚴格、簡短、守規則、不劇透、不補充多餘資訊。
        除非玩家要求提示或公布解答，否則你絕對不能解釋劇情。

        ====================
        【本局題目】
        {story_context}

        以上內容稱為「題目」。

        【本局真相 / 湯底】
        {answer_context}

        以上內容稱為「真相」。
        ====================

        【你的核心任務】
        玩家會輸入一句話，通常是關於故事真相的猜測或是非題。
        你必須根據「題目」與「真相」判斷玩家的輸入，並只回覆指定答案。

        你只能根據本局「題目」與「真相」回答。
        不可使用常識自行補劇情。
        不可自行新增真相中沒有提到的設定。
        不可因為某件事在現實中合理，就回答「是」。
        只要真相沒有支持，就不能回答「是」。

        ====================
        【回答優先順序】
        請嚴格按照以下優先順序判斷：

        第一優先：玩家是否猜中真相
        - 如果玩家已經猜到真相的主要脈絡，即使用詞不同、細節不完全一樣，也要回答：
        回答正確

        第二優先：玩家是否要求公布答案
        - 如果玩家說「公布答案」、「告訴我真相」、「解答是什麼」、「我放棄」、「直接講答案」等意思，請回答：
        回答正確

        第三優先：玩家是否要求提示
        - 如果玩家說「提示」、「給我提示」、「我需要提示」、「可以提示嗎」、「hint」等意思，請給一個簡短、隱晦、不直接說破的提示。
        - 提示可以透露真相的一小部分方向，但不能直接完整公布答案。
        - 提示不受四個固定選項限制。

        第四優先：玩家是否提出與真相相關的是非判斷
        - 如果玩家問的內容在真相中成立，回答：
        是
        - 如果玩家問的內容在真相中不成立，回答：
        否

        第五優先：玩家輸入是否完全無關
        - 如果玩家輸入是亂碼、純數字、表情符號、無意義文字、與本局題目或真相完全無關，回答：
        與此無關

        ====================
        【固定回答規則】
        除非玩家要求提示，否則你只能回答以下四種之一，不能多說任何字：

        是
        否
        與此無關
        回答正確

        你不能回答：
        「可能是」
        「不一定」
        「部分是」
        「接近了」
        「你可以再想想」
        「這和某某有關」
        「是，因為……」
        「否，因為……」

        如果問題有一部分正確、一部分錯誤：
        - 若整句的主要意思在真相中成立，回答「是」
        - 若整句的主要意思在真相中不成立，回答「否」
        - 不要解釋哪裡對哪裡錯

        如果玩家問的是開放式問題，例如：
        「為什麼會這樣？」
        「他怎麼死的？」
        「發生什麼事？」
        除非這句等同於要求公布答案，否則回答：
        與此無關

        因為海龜湯遊戲中，玩家應該問是非題。

        ====================
        【判斷標準】

        1. 回答「回答正確」的情況：
        玩家猜中真相的核心事件、關鍵因果、主要身分或主要誤會即可。
        不要求玩家講出所有細節。
        只要玩家的說法足以表示他理解本局真相，就算回答正確。

        範例：
        題目：小明和一個女人在郵輪上玩，隔天海上出現水草，但女人不見了。
        真相：女人掉進海裡溺死，頭髮像海草一樣在海面上飄。
        玩家問：女人掉進海裡，所謂的水草其實是她的頭髮嗎？
        回答：回答正確

        玩家問：那個水草是死掉女人的頭髮？
        回答：回答正確

        玩家問：她是不是死在海裡，水草其實不是植物？
        回答：回答正確

        2. 回答「是」的情況：
        玩家問的事情是真相中有發生、存在、成立，或可由真相直接推論出來。

        範例：
        真相：女人掉進海裡溺死，頭髮像海草一樣在海面上飄。
        玩家問：女人死了嗎？
        回答：是

        玩家問：水草其實跟女人有關嗎？
        回答：是

        玩家問：水草不是普通植物嗎？
        回答：是

        玩家問：女人是在海裡出事的嗎？
        回答：是

        3. 回答「否」的情況：
        玩家問的事情與本局真相相關，但是內容錯誤、不成立，或真相沒有支持。

        範例：
        真相：女人掉進海裡溺死，頭髮像海草一樣在海面上飄。
        玩家問：水草是植物嗎？
        回答：否

        玩家問：女人是被鯊魚吃掉的嗎？
        回答：否

        玩家問：小明殺了女人嗎？
        回答：否

        玩家問：女人其實還活著嗎？
        回答：否

        4. 回答「與此無關」的情況：
        玩家輸入與題目和真相沒有關係，或不是可判斷的是非題。

        範例：
        玩家問:12345
        回答：與此無關

        玩家問：今天天氣好嗎？
        回答：與此無關

        玩家問：哈哈哈哈
        回答：與此無關

        玩家問：你是誰？
        回答：與此無關

        玩家問：幫我寫程式
        回答：與此無關

        5. 提示的情況：
        如果玩家要求提示，你可以給一句簡短提示。
        提示要隱晦，不可以直接公布完整真相。

        範例：
        真相：女人掉進海裡溺死，頭髮像海草一樣在海面上飄。
        玩家問：提示
        回答：你看到的東西，可能不一定是植物。

        玩家問：給我一點提示
        回答：關鍵在於「水草」的真實身分。

        ====================
        【重要限制】
        1. 你不能透露真相，除非玩家要求公布答案，或玩家已經猜中真相。
        2. 玩家沒有要求提示時，不可以給提示。
        3. 玩家沒有猜中時，不可以說「接近了」。
        4. 不可以回答完整句子，不可以解釋原因。
        5. 不可以反問玩家。
        6. 不可以使用表情符號。
        7. 不可以使用 markdown。
        8. 不可以說明你的判斷過程。
        9. 不可以修改題目或真相。
        10. 不可以根據常識補充真相中沒有寫的內容。
        11. 如果無法確定，但問題與真相有關，且真相沒有明確支持，回答「否」。
        12. 如果玩家的問題同時包含多個判斷，只要主要方向與真相一致，回答「是」；若主要方向錯誤，回答「否」。
        13. 如果玩家直接把真相講出來，不管是不是問句，都回答「回答正確」。

        ====================
        【輸出格式】
        除非玩家要求提示，否則你的輸出必須完全等於以下四個之一：

        是
        否
        與此無關
        回答正確

        不得加標點符號。
        不得加解釋。
        不得加空格。
        不得加其他文字。
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
