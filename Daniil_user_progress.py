# библиотека
import json
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import firebase_admin
from firebase_admin import firestore
from firebase_admin import credentials
cred = credentials.Certificate('firebase-adminsdk-key.json')
firebase_admin.initialize_app(cred)
db = firestore.client()
API_TOKEN = '8330013656:AAGZMNIYWpF_6Tfv13ZlgaflNNQvhW-WnmE'
JSON_FILE = 'oge_task_examples.json'
bot = Bot(token="8330013656:AAGZMNIYWpF_6Tfv13ZlgaflNNQvhW-WnmE")
dp = Dispatcher()


#переменные
user_id = 'User-id-test-2'
topic = 'Maths'
last_passed_at = '16-01-2026'
score = 24

def save_user_progress(user_id, topic, last_passed_at, score):
    doc_ref = db.collection('users').document(str(user_id))
    if not doc_ref.get().exists:
        doc_ref.set({
        'score': score,
        'topic': topic,
        'last_passed_at': last_passed_at,
    })
        print (f'Добавлен новый польователь: {user_id}')
    else:
        doc_ref.update({
            'score': score,
            'topic': topic,
            'last_passed_at': last_passed_at,
        })
        print('Данные пользователя обновлены')


def get_user_progress(user_id):
    doc_ref = db.collection('users').document(str(user_id))
    doc_in = doc_ref.get()
    if doc_in.exists:
        data = doc_in.to_dict()
        print(f'score: {data['score']}')
        print(f'topic: {data['topic']}')
        print(f'last_passed_at: {data['last_passed_at']}')
    else:
        print('Пользователь еще не выполнял задания')


save_user_progress(user_id, topic, last_passed_at, score)
get_user_progress(user_id)

#бот

class QuizStates(StatesGroup):
    waiting_for_answer = State()

def load_tasks():
    with open(JSON_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

tasks = load_tasks()
current_task = tasks[0]

@dp.message(Command("start"))
async def start_cmd(message: types.Message, state: FSMContext):
    # Отправляем текст задания из JSON
    question_text = (
        f"<b>Тема:</b> {current_task['topic']}\n\n"
        f"{current_task['text']}"
    )

    await message.answer(question_text, parse_mode="HTML")
    await state.set_state(QuizStates.waiting_for_answer)


@dp.message(QuizStates.waiting_for_answer)
async def handle_answer(message: types.Message, state: FSMContext):
    user_answer = message.text.strip().lower()
    correct_answer = current_task['correct_answer'].strip().lower()

    if user_answer == correct_answer:
        await message.answer("✅ Ответ верный!")
    else:
        await message.answer(f"❌ Ответ неверный.\n\n{current_task['explanation']}")

    await state.clear()


async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот выключен")



