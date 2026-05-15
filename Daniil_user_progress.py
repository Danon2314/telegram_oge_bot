import json
import asyncio
import html
import random
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
TEST_QUESTIONS_COUNT = 5


# функция сохранения в Firebase
def save_user_progress(user_id, score, last_passed_at):
    doc_ref = db.collection('users').document(str(user_id))

    # сохраняем или обновляем данные пользователя
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

def update_user_mode(user_id, mode):
    doc_ref = db.collection('users').document(str(user_id))
    if doc_ref.get().exists:
        doc_ref.update({'mode': mode})
    else:
        doc_ref.set({
            'mode': mode,
            'score': 0,
            'last_passed_at': 'Неизвестно'
        })


class QuizStates(StatesGroup):
    mode = State()
    current_task_index = State()
    score = State()
    waiting_for_answer = State()


def load_tasks():
    with open(JSON_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


tasks = load_tasks()


def get_main_menu():
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Тренировка", callback_data="start_training"))
    builder.add(InlineKeyboardButton(text="Тест", callback_data="start_test"))
    builder.add(InlineKeyboardButton(text="Кабинет", callback_data="profile"))
    builder.adjust(2, 1)
    return builder.as_markup()


@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    welcome_text = (
        "<b>Добро пожаловать в Главное меню!</b>\n\n"
        "Здесь вы можете выбрать нужный раздел, используя кнопки ниже."
    )
    await message.answer(
        text=welcome_text,
        reply_markup=get_main_menu(),
        parse_mode="HTML"
    )


@dp.callback_query(F.data == "profile")
async def show_profile(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    doc_ref = db.collection('users').document(str(user_id))
    doc = doc_ref.get()

    if doc.exists:
        user_data = doc.to_dict()
        score = user_data.get('score', 0)
        last_passed = user_data.get('last_passed_at', 'Неизвестно')

        text = (
            f"<b>Личный кабинет</b>\n\n"
            f"Дата последнего тестирования: {last_passed}\n"
            f"Решено правильно: {score} из {len(tasks)}"
        )
    else:
        text = "<b>Личный кабинет</b>\n\nВы еще не проходили ни одного теста."

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Назад в меню", callback_data="back_to_main"))

    await callback.message.edit_text(
        text=text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()


@dp.callback_query(F.data == "back_to_main")
async def back_to_main_menu(callback: types.CallbackQuery):
    welcome_text = (
        "<b>Добро пожаловать в Главное меню!</b>\n\n"
        "Здесь вы можете выбрать нужный раздел, используя кнопки ниже."
    )

    # Возвращаем исходный текст главного меню и клавиатуру
    await callback.message.edit_text(
        text=welcome_text,
        reply_markup=get_main_menu(),
        parse_mode="HTML"
    )
    await callback.answer()


@dp.callback_query(F.data.in_(["start_training", "start_test"]))
async def start_quiz(callback: types.CallbackQuery, state: FSMContext):
    mode = "test" if callback.data == "start_test" else "training"
    update_user_mode(callback.from_user.id, mode)
    start_idx = 0 if mode == "test" else random.randint(0, len(tasks) - 1)

    await state.update_data(current_task_index=start_idx, score=0, mode=mode)
    task = tasks[start_idx]

    safe_topic = html.escape(task.get('topic', ''))
    safe_text = html.escape(task.get('text', ''))

    mode_name = "ТЕСТ" if mode == "test" else "ТРЕНИРОВКА"
    question_text = f"<b>Режим: {mode_name}</b>\n\n<b>Тема:</b> {safe_topic}\n{safe_text}"

    if mode == "training":
        question_text += "\n\n<i>(Для выхода напиши /start)</i>"

    await callback.message.answer(question_text, parse_mode="HTML")
    await state.set_state(QuizStates.waiting_for_answer)
    await callback.answer()


@dp.message(QuizStates.waiting_for_answer)
async def handle_answer(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    idx = user_data.get('current_task_index', 0)
    score = user_data.get('score', 0)
    mode = user_data.get('mode', 'training')

    task = tasks[idx]
    user_answer = message.text.strip().lower()
    correct_answer = str(task['correct_answer']).strip().lower()

    is_correct = (user_answer == correct_answer)
    if is_correct:
        score += 1

    if mode == 'training':
        if is_correct:
            await message.answer("<b>Ответ верный!</b>", parse_mode="HTML")
        else:
            safe_explanation = html.escape(task.get('explanation', 'Нет объяснения.'))
            await message.answer(f"<b>Неверно.</b>\n\n{safe_explanation}", parse_mode="HTML")
    else:
        # Режим теста
        await message.answer("Ответ принят. Переходим к следующему вопросу ⏳")

    if mode == 'training':
        # Бесконечная тренировка
        new_idx = random.randint(0, len(tasks) - 1)
        await state.update_data(current_task_index=new_idx, score=score)

        next_task = tasks[new_idx]
        safe_next_text = html.escape(next_task.get('text', ''))
        await message.answer(f"<b>Следующее задание:</b>\n{safe_next_text}", parse_mode="HTML")

    else:
        # Режим теста
        new_idx = idx + 1
        if new_idx < TEST_QUESTIONS_COUNT and new_idx < len(tasks):
            await state.update_data(current_task_index=new_idx, score=score)

            next_task = tasks[new_idx]
            safe_next_text = html.escape(next_task.get('text', ''))
            await message.answer(f"<b>Вопрос {new_idx + 1} из {TEST_QUESTIONS_COUNT}:</b>\n{safe_next_text}",
                                 parse_mode="HTML")
        else:
            # Тест окончен
            total_questions = min(TEST_QUESTIONS_COUNT, len(tasks))
            percent = int((score / total_questions) * 100)

            result_text = (
                f"<b>Тест завершён!</b>\n\n"
                f"Твой результат: {score} из {total_questions} правильных ответов.\n"
                f"Успешность: {percent}%\n"
            )
            await message.answer(result_text, parse_mode="HTML")

            current_date = datetime.now().strftime("%d-%m-%Y %H:%M")
            user_id = message.from_user.id

            save_user_progress(user_id=user_id, score=score, last_passed_at=current_date)

            await state.clear()
            await message.answer("Выбери нужный раздел:", reply_markup=get_main_menu(), parse_mode="HTML")

async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот выключен")
