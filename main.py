from flask import Flask, request
import vk_api
from vk_api.utils import get_random_id
from datetime import datetime, timedelta
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
        print(f"✅ Сообщение отправлено {user_id}: {text[:50]}...")
        return True
    except Exception as e:
        print(f"❌ Ошибка отправки {user_id}: {e}")
        return False

# ФУНКЦИЯ С ОТВЕТОМ (ВЫПОЛНЯЕТСЯ В ПОТОКЕ)
def delayed_response(user_id):
    print(f"⏰ [ТАЙМЕР] Запущен поток для пользователя {user_id}, жду 3 минуты...")
    time.sleep(180)  # Ждём 3 минуты (180 секунд)
    
    print(f"⏰ [ТАЙМЕР] Прошло 3 минуты для {user_id}, начинаю обработку...")
    
    user_id_str = str(user_id)
    if user_id_str not in user_states:
        print(f"❌ [ТАЙМЕР] Пользователь {user_id} не найден в хранилище")
        return
    
    state = user_states[user_id_str]
    
    # ЕСЛИ УЖЕ ОТВЕЧАЛИ 2 РАЗА - НЕ ОТВЕЧАЕМ
    if state["response_count"] >= 2:
        print(f"⚠️ [ТАЙМЕР] Пользователю {user_id} уже отправлено 2 ответа. Игнорируем.")
        state["is_waiting_for_response"] = False
        save_states(user_states)
        return
    
    # ПРОВЕРЯЕМ, ЕСТЬ ЛИ НЕОТВЕЧЕННЫЕ СООБЩЕНИЯ
    if state["pending_messages"] > 0:
        response_text = "Добрый день! На данный момент сотрудники заняты. Как только освободимся, дадим вам ответ."
        
        print(f"📤 [ТАЙМЕР] Отправка сообщения пользователю {user_id}...")
        success = send_message(user_id, response_text)
        
        if success:
            # УВЕЛИЧИВАЕМ СЧЁТЧИК ОТВЕТОВ
            state["response_count"] += 1
            # ОБНУЛЯЕМ СЧЁТЧИК НЕОТВЕЧЕННЫХ СООБЩЕНИЙ
            state["pending_messages"] = 0
            # СОХРАНЯЕМ ВРЕМЯ ПОСЛЕДНЕГО ОТВЕТА
            state["last_response_time"] = datetime.now().isoformat()
            
            print(f"📨 [ТАЙМЕР] Отправлен ответ пользователю {user_id} (ответ #{state['response_count']})")
    else:
        print(f"ℹ️ [ТАЙМЕР] У пользователя {user_id} нет ожидающих сообщений")
    
    # СБРАСЫВАЕМ ФЛАГ ОЖИДАНИЯ
    state["is_waiting_for_response"] = False
    save_states(user_states)
    print(f"🏁 [ТАЙМЕР] Завершил работу для {user_id}")

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
        
        print(f"💬 [НОВОЕ] Сообщение от {user_id}: {text}")
        
        user_id_str = str(user_id)
        
        # ИНИЦИАЛИЗАЦИЯ ДАННЫХ ПОЛЬЗОВАТЕЛЯ
        if user_id_str not in user_states:
            user_states[user_id_str] = {
                "response_count": 0,      # Сколько раз уже отвечали
                "pending_messages": 0,    # Сколько сообщений ожидают ответа
                "last_response_time": None,  # Время последнего ответа
                "is_waiting_for_response": False  # Ожидается ли ответ
            }
            print(f"📝 [НОВОЕ] Создан новый пользователь {user_id}")
        
        # УВЕЛИЧИВАЕМ СЧЁТЧИК НЕОТВЕЧЕННЫХ СООБЩЕНИЙ
        user_states[user_id_str]["pending_messages"] += 1
        print(f"📊 [НОВОЕ] pending_messages = {user_states[user_id_str]['pending_messages']}")
        
        # ЕСЛИ УЖЕ ОТВЕЧАЛИ 2 РАЗА - НИЧЕГО НЕ ДЕЛАЕМ
        if user_states[user_id_str]["response_count"] >= 2:
            print(f"🚫 [НОВОЕ] Пользователь {user_id} уже получил 2 ответа. Игнорирую.")
            save_states(user_states)
            return "ok"
        
        # ПРОВЕРЯЕМ, НЕТ ЛИ УЖЕ ЗАПУЩЕННОГО ПОТОКА
        if not user_states[user_id_str]["is_waiting_for_response"]:
            # ЗАПУСКАЕМ ПОТОК С ОЖИДАНИЕМ 3 МИНУТЫ
            thread = threading.Thread(target=delayed_response, args=(user_id,))
            thread.daemon = True
            thread.start()
            user_states[user_id_str]["is_waiting_for_response"] = True
            print(f"⏱️ [НОВОЕ] Запущен поток для {user_id}, ответ через 3 минуты")
        else:
            print(f"ℹ️ [НОВОЕ] Для {user_id} уже есть запущенный поток ожидания")
        
        save_states(user_states)
    
    return "ok"

# ЗАПУСК
if name == "__main__":
    port = int(os.environ.get('PORT', 10000))
    app.run(host="0.0.0.0", port=port)
