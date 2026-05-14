from flask import Flask, request
import vk_api
from vk_api.utils import get_random_id
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import json
import os

TOKEN = "vk1.a.fytAHLvQ-ROFp2XtEZ6bo0QFUzcSJANaeO47wd-L47rkEYQ6ueaXyYFlNGEl9YUvh3BYkQsrq4Z_jXF_n2U5jNBsDhNDwdf21gqfMxfFT2Wbv88YEFsxZWTRUrSS_GwZle8vNCH8PqVDchoCA8i_FRr1DAAenIPXLtAo7-kdEexDaCvf6C6H_6UQ-aAqutGJJuQMwcAMNwB8zKG8UA_uUA"
CONFIRMATION_TOKEN = "118abff8"

vk_session = vk_api.VkApi(token=TOKEN)
vk = vk_session.get_api()

app = Flask(__name__)

scheduler = BackgroundScheduler()
scheduler.start()

STATE_FILE = "user_states.json"

def load_states():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_states(states):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(states, f, ensure_ascii=False, indent=2)

user_states = load_states()

def send_message(user_id, text):
    try:
        vk.messages.send(
            user_id=user_id,
            random_id=get_random_id(),
            message=text
        )
        print(f"Сообщение отправлено {user_id}")
    except Exception as e:
        print(f"Ошибка отправки: {e}")

def delayed_response(user_id):
    user_id_str = str(user_id)
    if user_id_str in user_states:
        state = user_states[user_id_str]
        
        if state["response_count"] >= 2:
            print(f"Пользователю {user_id} уже отправлено 2 ответа")
            return
        
        if state["pending_messages"] > 0:
            response_text = "Добрый день! На данный момент сотрудники заняты. Как только освободимся, дадим вам ответ."
            send_message(user_id, response_text)
            
            state["response_count"] += 1
            state["pending_messages"] = 0
            state["last_response_time"] = datetime.now().isoformat()
            state["is_waiting_for_response"] = False
            
            save_states(user_states)
            print(f"Отправлен ответ пользователю {user_id}")

@app.route("/", methods=["POST"])
def callback():
    data = request.json
    
    if data["type"] == "confirmation":
        return CONFIRMATION_TOKEN
    
    if data["type"] == "message_new":
        message = data["object"]["message"]
        user_id = message["from_id"]
        text = message["text"]
        
        print(f"Сообщение от {user_id}: {text}")
        
        user_id_str = str(user_id)
        
        if user_id_str not in user_states:
            user_states[user_id_str] = {
                "response_count": 0,
                "pending_messages": 0,
                "last_response_time": None,
                "is_waiting_for_response": False
            }
        
        user_states[user_id_str]["pending_messages"] += 1
        
        if user_states[user_id_str]["response_count"] >= 2:
            print(f"Пользователь {user_id} уже получил 2 ответа")
            save_states(user_states)
            return "ok"
        
        if not user_states[user_id_str]["is_waiting_for_response"]:
            run_time = datetime.now() + timedelta(minutes=3)
            scheduler.add_job(
                delayed_response,
                trigger='date',
                run_date=run_time,
                args=[user_id],
                id=f"response_{user_id}_{datetime.now().timestamp()}",
                replace_existing=False
            )
            user_states[user_id_str]["is_waiting_for_response"] = True
            print(f"Запланирован ответ для {user_id} через 3 минуты")
        
        save_states(user_states)
    
    return "ok"

if __name__ == "__main__":
    import os
    port = int(os.environ.get('PORT', 10000))
    app.run(host="0.0.0.0", port=port)
