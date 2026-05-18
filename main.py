from flask import Flask, request
import vk_api
from vk_api.utils import get_random_id

import json
import os
import threading
import time
import random

from datetime import datetime

# =========================================
# ТОКЕН VK
# =========================================

TOKEN = "vk1.a.fytAHLvQ-ROFp2XtEZ6bo0QFUzcSJANaeO47wd-L47rkEYQ6ueaXyYFlNGEl9YUvh3BYkQsrq4Z_jXF_n2U5jNBsDhNDwdf21gqfMxfFT2Wbv88YEFsxZWTRUrSS_GwZle8vNCH8PqVDchoCA8i_FRr1DAAenIPXLtAo7-kdEexDaCvf6C6H_6UQ-aAqutGJJuQMwcAMNwB8zKG8UA_uUA"


# =========================================
# CONFIRMATION TOKEN
# =========================================

CONFIRMATION_TOKEN = "118abff8"

# =========================================
# ПОДКЛЮЧЕНИЕ VK API
# =========================================

vk_session = vk_api.VkApi(token=TOKEN)

vk = vk_session.get_api()

# =========================================
# FLASK
# =========================================

app = Flask(__name__)

# =========================================
# ФАЙЛ СОСТОЯНИЙ
# =========================================

STATE_FILE = "user_states.json"

# =========================================
# ЗАГРУЗКА СОСТОЯНИЙ
# =========================================

def load_states():

    if os.path.exists(STATE_FILE):

        with open(STATE_FILE, "r", encoding="utf-8") as f:

            return json.load(f)

    return {}

# =========================================
# СОХРАНЕНИЕ СОСТОЯНИЙ
# =========================================

def save_states(states):

    with open(STATE_FILE, "w", encoding="utf-8") as f:

        json.dump(
            states,
            f,
            ensure_ascii=False,
            indent=2
        )

# =========================================
# ИНИЦИАЛИЗАЦИЯ
# =========================================

user_states = load_states()

# =========================================
# ОТПРАВКА СООБЩЕНИЯ
# =========================================

def send_message(user_id, text):

    try:

        vk.messages.send(
            user_id=user_id,
            random_id=get_random_id(),
            message=text
        )

        print(f"✅ Сообщение отправлено {user_id}")

        return True

    except Exception as e:

        print(f"❌ Ошибка отправки {user_id}: {e}")

        return False

# =========================================
# ФУНКЦИЯ ОТЛОЖЕННОГО ОТВЕТА
# =========================================

def delayed_response(user_id):

    # СЛУЧАЙНАЯ ЗАДЕРЖКА 15-20 МИНУТ
    delay_seconds = random.randint(900, 1200)

    delay_minutes = round(delay_seconds / 60, 1)

    print(f"⏳ Жду {delay_minutes} минут для {user_id}")

    # ОЖИДАНИЕ
    time.sleep(delay_seconds)

    print(f"⏰ Время ответа пришло для {user_id}")

    user_id_str = str(user_id)

    if user_id_str not in user_states:

        return

    state = user_states[user_id_str]

    # ЕСЛИ УЖЕ ОТВЕТИЛИ
    if state["has_replied"]:

        print(f"⚠️ Пользователю {user_id} уже отвечали")

        return

    # ЕСЛИ ЕСТЬ НЕОТВЕЧЕННЫЕ СООБЩЕНИЯ
    if state["pending_messages"] > 0:

        response_text = (
            "Добрый день! "
            "На данный момент сотрудники заняты. "
            "Как только освободимся, дадим вам ответ 🙂"
        )

        send_message(user_id, response_text)

        # ОТМЕЧАЕМ ОТВЕТ
        state["has_replied"] = True

        state["response_time"] = datetime.now().isoformat()

        state["is_waiting_for_response"] = False

        save_states(user_states)

        print(f"📨 Ответ отправлен пользователю {user_id}")

    else:

        state["is_waiting_for_response"] = False

        save_states(user_states)

# =========================================
# CALLBACK VK
# =========================================

@app.route("/", methods=["POST"])
def callback():

    data = request.json

    # =====================================
    # ПОДТВЕРЖДЕНИЕ VK
    # =====================================

    if data["type"] == "confirmation":

        print("🔑 VK confirmation")

        return CONFIRMATION_TOKEN

    # =====================================
    # НОВОЕ СООБЩЕНИЕ
    # =====================================

    if data["type"] == "message_new":

        message = data["object"]["message"]

        user_id = message["from_id"]

        text =age["text"]

        print(f"💬 Сообщение от {user_id}: {text}")

        user_id_str = str(user_id)

        # =================================
        # НОВЫЙ ПОЛЬЗОВАТЕЛЬ
        # =================================

        if user_id_str not in user_states:

            user_states[user_id_str] = {

                "has_replied": False,

                "pending_messages": 0,

                "response_time": None,

                "is_waiting_for_response": False
            }

            print(f"📝 Создан пользователь {user_id}")

        # =================================
        # ЕСЛИ УЖЕ ОТВЕЧАЛИ
        # =================================

        if user_states[user_id_str]["has_replied"]:

            print(f"🚫 Уже отвечали {user_id}")

            return "ok"

        # =================================
        # УВЕЛИЧИВАЕМ СЧЁТЧИК
        # =================================

        user_states[user_id_str]["pending_messages"] += 1

        print(
            f"📊 pending_messages = "
            f"{user_states[user_id_str]['pending_messages']}"
        )

        # =================================
        # ЗАПУСК ТАЙМЕРА
        # =================================

        if not user_states[user_id_str]["is_waiting_for_response"]:

            thread = threading.Thread(
                target=delayed_response,
                args=(user_id,)
            )

            thread.daemon = True

            thread.start()

            user_states[user_id_str]["is_waiting_for_response"] = True

            print(
                f"⏱️ Таймер запущен "
                f"для {user_id}"
            )

        save_states(user_states)

    return "ok"

# =========================================
# ЗАПУСК
# =========================================

if __name__ == "__main__":

    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port)
