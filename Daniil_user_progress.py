import json
import asyncio
import html
import firebase_admin
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from firebase_admin import firestore
from firebase_admin import credentials

cred = credentials.Certificate('firebase-adminsdk-key.json')
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)
db = firestore.client()

API_TOKEN = '8330013656:AAGZMNIYWpF_6Tfv13ZlgaflNNQvhW-WnmE'
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
JSON_FILE = 'oge_task_examples.json'


# Функция сохранения в Firebase
def save_user_progress(user_id, score, last_passed_at):
    doc_ref = db.collection('users').document(str(user_id))

    # Сохраняем или обновляем данные пользователя
    if not doc_ref.get().exists:
        doc_ref.set({
            'score': score,
            'last_passed_at': last_passed_at
        })
        print(f'Добавлен новый пользователь: {user_id}')
    else:
        doc_ref.update({
            'score': score,
            'last_passed_at': last_passed_at
        })
        print(f'Данные пользователя {user_id} обновлены')


class QuizStates(StatesGroup):
    current_task_index = State()
    score = State()
    waiting_for_answer = State()


def load_tasks():
    with open(JSON_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


tasks = load_tasks()


def get_main_menu():
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Перейти к заданиям", callback_data="exercise"))
    builder.add(InlineKeyboardButton(text="Кабинет", callback_data="profile"))
    return builder.as_markup()


@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    welcome_text = (
        "🔔 <b>Добро пожаловать в Главное меню!</b>\n\n"
        "Здесь вы можете выбрать нужный раздел, используя кнопки ниже."
    )
    await message.answer(
        text=welcome_text,
        reply_markup=get_main_menu(),
        parse_mode="HTML"
    )


@dp.callback_query(F.data == "exercise")
async def start_quiz(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(current_task_index=0, score=0)
    task = tasks[0]

    safe_topic = html.escape(task.get('topic', ''))
    safe_text = html.escape(task.get('text', ''))

    question_text = f"<b>Тема:</b> {safe_topic}\n\n{safe_text}"

    await callback.message.answer(question_text, parse_mode="HTML")
    await state.set_state(QuizStates.waiting_for_answer)
    await callback.answer()


@dp.message(QuizStates.waiting_for_answer)
async def handle_answer(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    idx = user_data.get('current_task_index', 0)
    score = user_data.get('score', 0)
    task = tasks[idx]

    user_answer = message.text.strip().lower()
    correct_answer = str(task['correct_answer']).strip().lower()

    if user_answer == correct_answer:
        await message.answer("✅ Ответ верный!")

        score += 1
        new_idx = idx + 1

        if new_idx < len(tasks):
            await state.update_data(current_task_index=new_idx, score=score)
            next_task = tasks[new_idx]

            safe_next_text = html.escape(next_task.get('text', ''))
            await message.answer(f"<b>Следующее задание:</b>\n\n{safe_next_text}", parse_mode="HTML")
        else:
            await message.answer("🎉 Ты решил все задачи из списка!")

            # отправка в firebase
            current_date = datetime.now().strftime("%d-%m-%Y %H:%M")
            user_id = message.from_user.id
            save_user_progress(user_id=user_id, score=score, last_passed_at=current_date)

            await state.clear()
            await message.answer(
                text="👇 Выберите нужный раздел:",
                reply_markup=get_main_menu(),
                parse_mode="HTML"
            )
    else:
        safe_explanation = html.escape(task.get('explanation', 'Нет объяснения.'))
        await message.answer(f"❌ Неверно.\n\n{safe_explanation}", parse_mode="HTML")

async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот выключен")
