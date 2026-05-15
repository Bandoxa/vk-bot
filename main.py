from flask import Flask, request
import vk_api
from vk_api.utils import get_random_id
import json
import os
import threading
import time

# ТОКЕН VK
TOKEN = "vk1.a.fytAHLvQ-ROFp2XtEZ6bo0QFUzcSJANaeO47wd-L47rkEYQ6ueaXyYFlNGEl9YUvh3BYkQsrq4Z_jXF_n2U5jNBsDhNDwdf21gqfMxfFT2Wbv88YEFsxZWTRUrSS_GwZle8vNCH8PqVDchoCA8i_FRr1DAAenIPXLtAo7-kdEexDaCvf6C6H_6UQ-aAqutGJJuQMwcAMNwB8zKG8UA_uUA"

# СТРОКА ПОДТВЕРЖДЕНИЯ
CONFIRMATION_TOKEN = "118abff8"

# ПОДКЛЮЧЕНИЕ VK API
vk_session = vk_api.VkApi(token=TOKEN)
vk = vk_session.get_api()

app = Flask(__name__)

# ФАЙЛ ДЛЯ ХРАНЕНИЯ СОСТОЯНИЯ ПОЛЬЗОВАТЕЛЕЙ
STATE_FILE = "user_states.json"

# ЗАГРУЗКА СОСТОЯНИЙ ИЗ ФАЙЛА
def load_states():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

# СОХРАНЕНИЕ СОСТОЯНИЙ В ФАЙЛ
def save_states(states):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(states, f, ensure_ascii=False, indent=2)

# ИНИЦИАЛИЗАЦИЯ
user_states = load_states()

# ОТПРАВКА СООБЩЕНИЯ
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

# ФУНКЦИЯ С ОТВЕТОМ (ВЫПОЛНЯЕТСЯ ЧЕРЕЗ 3 МИНУТЫ)
def delayed_response(user_id):
    print(f"⏰ [ТАЙМЕР] Прошло 3 минуты для {user_id}")
    
    user_id_str = str(user_id)
    if user_id_str not in user_states:
        return
    
    state = user_states[user_id_str]
    
    # ЕСЛИ УЖЕ ОТВЕЧАЛИ - НЕ ОТВЕЧАЕМ
    if state["has_replied"]:
        print(f"⚠️ Пользователю {user_id} уже отвечали. Игнорирую.")
        return
    
    # ЕСЛИ ЕСТЬ НЕОТВЕЧЕННОЕ СООБЩЕНИЕ - ОТВЕЧАЕМ
    if state["pending_messages"] > 0 and not state["has_replied"]:
        response_text = "Добрый день! На данный момент сотрудники заняты. Как только освободимся, дадим вам ответ."
        send_message(user_id, response_text)
        
        # ОТМЕЧАЕМ, ЧТО ОТВЕТИЛИ
        state["has_replied"] = True
        state["response_time"] = datetime.now().isoformat()
        state["is_waiting_for_response"] = False
        
        save_states(user_states)
        print(f"📨 Отправлен единственный ответ пользователю {user_id}")
    else:
        state["is_waiting_for_response"] = False
        save_states(user_states)

# ОБРАБОТКА ВХОДЯЩЕГО СООБЩЕНИЯ
@app.route("/", methods=["POST"])
def callback():
    data = request.json
    
    # ПРОВЕРКА VK (ПОДТВЕРЖДЕНИЕ СЕРВЕРА)
    if data["type"] == "confirmation":
        print("🔑 Возвращаю confirmation token")
        return CONFIRMATION_TOKEN
    
    # НОВОЕ СООБЩЕНИЕ
    if data["type"] == "message_new":
        message = data["object"]["message"]
        user_id = message["from_id"]
        text = message["text"]
        
        print(f"💬 Сообщение от {user_id}: {text}")
        
        user_id_str = str(user_id)
        
        # ИНИЦИАЛИЗАЦИЯ ДАННЫХ ПОЛЬЗОВАТЕЛЯ
        if user_id_str not in user_states:
            user_states[user_id_str] = {
                "has_replied": False,        # Отвечали ли уже пользователю
                "pending_messages": 0,       # Количество сообщений
                "response_time": None,       # Время ответа
                "is_waiting_for_response": False  # Ожидается ли ответ
            }
            print(f"📝 Создан новый пользователь {user_id}")
        
        # ЕСЛИ УЖЕ ОТВЕЧАЛИ - ИГНОРИРУЕМ ВСЕ СООБЩЕНИЯ
        if user_states[user_id_str]["has_replied"]:
            print(f"🚫 Пользователю {user_id} уже отвечали. Новое сообщение игнорирую.")
            return "ok"
        
        # УВЕЛИЧИВАЕМ СЧЁТЧИК НЕОТВЕЧЕННЫХ СООБЩЕНИЙ
        user_states[user_id_str]["pending_messages"] += 1
        print(f"📊 pending_messages = {user_states[user_id_str]['pending_messages']}")
        
        # ЕСЛИ НЕТ ЗАПЛАНИРОВАННОГО ОТВЕТА - ЗАПУСКАЕМ ТАЙМЕР
        if not user_states[user_id_str]["is_waiting_for_response"]:
            # ЗАПУСКАЕМ ПОТОК С ОЖИДАНИЕМ 3 МИНУТЫ
            thread = threading.Thread(target=delayed_response, args=(user_id,))
            thread.daemon = True
            thread.start()
            user_states[user_id_str]["is_waiting_for_response"] = True
            print(f"⏱️ Запущен таймер для {user_id}, ответ через 3 минуты")
        
        save_states(user_states)
    
    return "ok"

# ЗАПУСК
if name == "__main__":
    from datetime import datetime
    port = int(os.environ.get('PORT', 10000))
    app.run(host="0.0.0.0", port=port)
