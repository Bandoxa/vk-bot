from flask import Flask, request
import vk_api
from vk_api.utils import get_random_id
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import json
import os

# ТОКЕН VK
TOKEN = "vk1.a.fytAHLvQ-ROFp2XtEZ6bo0QFUzcSJANaeO47wd-L47rkEYQ6ueaXyYFlNGEl9YUvh3BYkQsrq4Z_jXF_n2U5jNBsDhNDwdf21gqfMxfFT2Wbv88YEFsxZWTRUrSS_GwZle8vNCH8PqVDchoCA8i_FRr1DAAenIPXLtAo7-kdEexDaCvf6C6H_6UQ-aAqutGJJuQMwcAMNwB8zKG8UA_uUA"

# СТРОКА ПОДТВЕРЖДЕНИЯ
CONFIRMATION_TOKEN = "118abff8"

# ПОДКЛЮЧЕНИЕ VK API
vk_session = vk_api.VkApi(token=TOKEN)
vk = vk_session.get_api()

app = Flask(__name__)

# ПЛАНИРОВЩИК
scheduler = BackgroundScheduler()
scheduler.start()

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
    vk.messages.send(
        user_id=user_id,
        random_id=get_random_id(),
        message=text
    )

# ФУНКЦИЯ С ОТВЕТОМ (ВЫПОЛНЯЕТСЯ ЧЕРЕЗ 3 МИНУТЫ)
def delayed_response(user_id):
    # ПРОВЕРЯЕМ, НЕ БЫЛО ЛИ УЖЕ ОТПРАВЛЕНО
    user_id_str = str(user_id)
    if user_id_str in user_states:
        state = user_states[user_id_str]
        
        # ЕСЛИ УЖЕ ОТПРАВЛЯЛИ 2 РАЗА - НЕ ОТВЕЧАЕМ
        if state["response_count"] >= 2:
            print(f"Пользователю {user_id} уже отправлено 2 ответа. Игнорируем.")
            return
        
        # ПРОВЕРЯЕМ, НЕ БЫЛО ЛИ НОВЫХ СООБЩЕНИЙ ЗА ЭТО ВРЕМЯ
        # И ЕСТЬ ЛИ НЕОТВЕЧЕННЫЕ СООБЩЕНИЯ
        if state["pending_messages"] > 0:
            # ОТПРАВЛЯЕМ СТАНДАРТНЫЙ ОТВЕТ
            response_text = "Добрый день! На данный момент сотрудники заняты. Как только освободимся, дадим вам ответ."
            send_message(user_id, response_text)
            
            # УВЕЛИЧИВАЕМ СЧЁТЧИК ОТВЕТОВ
            state["response_count"] += 1
            # ОБНУЛЯЕМ СЧЁТЧИК НЕОТВЕЧЕННЫХ СООБЩЕНИЙ
            state["pending_messages"] = 0
            # СОХРАНЯЕМ ВРЕМЯ ПОСЛЕДНЕГО ОТВЕТА
            state["last_response_time"] = datetime.now().isoformat()
            
            save_states(user_states)
            print(f"Отправлен ответ пользователю {user_id} (ответ #{state['response_count']})")

# ОБРАБОТКА ВХОДЯЩЕГО СООБЩЕНИЯ
@app.route("/", methods=["POST"])
def callback():
    data = request.json
    
    # ПРОВЕРКА VK
    if data["type"] == "confirmation":
        return CONFIRMATION_TOKEN
    
    # НОВОЕ СООБЩЕНИЕ
    if data["type"] == "message_new":
        message = data["object"]["message"]
        user_id = message["from_id"]
        text = message["text"]
        
        print(f"Сообщение от {user_id}: {text}")
        
        user_id_str = str(user_id)
        
        # ИНИЦИАЛИЗАЦИЯ ДАННЫХ ПОЛЬЗОВАТЕЛЯ
        if user_id_str not in user_states:
            user_states[user_id_str] = {
                "response_count": 0,  # Сколько раз уже отвечали
                "pending_messages": 0, # Сколько сообщений ожидают ответа
                "last_response_time": None, # Время последнего ответа
                "is_waiting_for_response": False # Ожидается ли запланированный ответ
            }
        
        # УВЕЛИЧИВАЕМ СЧЁТЧИК НЕОТВЕЧЕННЫХ СООБЩЕНИЙ
        user_states[user_id_str]["pending_messages"] += 1
        
        # ЕСЛИ УЖЕ ОТВЕЧАЛИ 2 РАЗА - НИЧЕГО НЕ ДЕЛАЕМ
        if user_states[user_id_str]["response_count"] >= 2:
            print(f"Пользователь {user_id} уже получил 2 ответа. Новые сообщения игнорируются.")
            save_states(user_states)
            return "ok"
        
        # ПРОВЕРЯЕМ, НЕТ ЛИ УЖЕ ЗАПЛАНИРОВАННОГО ОТВЕТА
        if not user_states[user_id_str]["is_waiting_for_response"]:
            # ПЛАНИРУЕМ ОТВЕТ ЧЕРЕЗ 3 МИНУТЫ
            run_time = datetime.now() + timedelta(minutes=3)
            scheduler.add_job(
                delayed_response,
                trigger='date',
                run_date=run_time,
args=[user_id],
                id=f"response_{user_id}_{datetime.now().timestamp()}", # Уникальный ID
                replace_existing=False
            )
            user_states[user_id_str]["is_waiting_for_response"] = True
            print(f"Запланирован ответ для пользователя {user_id} через 3 минуты")
        
        save_states(user_states)
    
    return "ok"

# ДОБАВЛЯЕМ ВОЗМОЖНОСТЬ СБРОСА (ОПЦИОНАЛЬНО)
# Можно отправить секретное слово, чтобы сбросить счётчик
def reset_user_state(user_id):
    user_id_str = str(user_id)
    if user_id_str in user_states:
        user_states[user_id_str] = {
            "response_count": 0,
            "pending_messages": 0,
            "last_response_time": None,
            "is_waiting_for_response": False
        }
        save_states(user_states)
        print(f"Состояние пользователя {user_id} сброшено")
        send_message(user_id, "Ваши ожидания сброшены. Вы снова можете получить ответ через 3 минуты.")

# ЗАПУСК
if name == "__main__":
    app.run(host="0.0.0.0", port=5000)
