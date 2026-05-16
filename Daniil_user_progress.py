import json
import asyncio
import html
import random
import firebase_admin
from datetime import datetime, timedelta
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


def ensure_user_doc(user_id):
    """Убедиться, что документ пользователя существует и содержит все нужные поля."""
    doc_ref = db.collection('users').document(str(user_id))
    doc = doc_ref.get()
    if not doc.exists:
        doc_ref.set({
            'total_attempts': 0,
            'correct_answers': 0,
            'topics_stats': {},  # topic -> {'attempts': int, 'correct': int}
            'streak_days': 0,
            'last_activity_date': None,
            'last_passed_at': 'Неизвестно',
            'mode': 'training'
        })
        return doc_ref.get()
    return doc


def update_user_stats(user_id, topic: str, correct: bool):
    """Обновляет статистику пользователя в Firestore после каждого ответа.

    - увеличивает total_attempts
    - увеличивает correct_answers, если correct
    - обновляет статистику по теме
    - обновляет серию (streak_days) по дате
    """
    doc_ref = db.collection('users').document(str(user_id))
    doc = ensure_user_doc(user_id)
    data = doc.to_dict()

    # счётчики
    total = data.get('total_attempts', 0) + 1
    correct_total = data.get('correct_answers', 0) + (1 if correct else 0)

    # статистика по теме
    topics = data.get('topics_stats', {}) or {}
    t = topic or 'Общее'
    if t not in topics:
        topics[t] = {'attempts': 0, 'correct': 0}
    topics[t]['attempts'] = topics[t].get('attempts', 0) + 1
    if correct:
        topics[t]['correct'] = topics[t].get('correct', 0) + 1

    # обновление серии (streak)
    today = datetime.now().date()
    last_date_str = data.get('last_activity_date')
    streak = data.get('streak_days', 0) or 0

    try:
        last_date = datetime.fromisoformat(last_date_str).date() if last_date_str and isinstance(last_date_str, str) else None
    except Exception:
        last_date = None

    if last_date is None:
        # первая активность
        streak = 1
    else:
        if last_date == today:
            # уже было занятие сегодня — не меняем серию
            pass
        elif last_date == (today - timedelta(days=1)):
            # продолжение серии
            streak = (streak or 0) + 1
        else:
            # пропуск — сбрасываем
            streak = 1

    # обновляем документ
    doc_ref.update({
        'total_attempts': total,
        'correct_answers': correct_total,
        'topics_stats': topics,
        'streak_days': streak,
        'last_activity_date': today.isoformat()
    })


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


def get_back_to_main_markup():
    """Возвращает inline-клавиатуру с одной кнопкой "Назад в меню"."""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Назад в меню", callback_data="back_to_main"))
    builder.adjust(1)
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
        total = user_data.get('total_attempts', 0) or 0
        correct = user_data.get('correct_answers', 0) or 0
        last_passed = user_data.get('last_passed_at', 'Неизвестно')
        streak = user_data.get('streak_days', 0) or 0
        last_activity = user_data.get('last_activity_date') or 'Неизвестно'

        percent = int((correct / total) * 100) if total > 0 else 0

        text_lines = [
            "<b>Личный кабинет</b>",
            "",
            f"Всего решено заданий: {total}",
            f"Правильных ответов: {correct} ({percent}%)",
            f"Текущая серия дней: {streak}",
            f"Последняя активность: {last_activity}",
            "",
            "<b>Статистика по темам:</b>"
        ]

        topics = user_data.get('topics_stats', {}) or {}
        if topics:
            for topic_name, stats in topics.items():
                at = stats.get('attempts', 0)
                cr = stats.get('correct', 0)
                p = int((cr / at) * 100) if at > 0 else 0
                text_lines.append(f"{html.escape(topic_name)} — {cr}/{at} ({p}%)")
        else:
            text_lines.append("Пока нет данных по темам.")

        text = "\n".join(text_lines)
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
    # убедимся, что документ пользователя инициализирован
    ensure_user_doc(callback.from_user.id)
    start_idx = 0 if mode == "test" else random.randint(0, len(tasks) - 1)

    await state.update_data(current_task_index=start_idx, score=0, mode=mode)
    task = tasks[start_idx]

    safe_topic = html.escape(task.get('topic', ''))
    safe_text = html.escape(task.get('text', ''))

    mode_name = "ТЕСТ" if mode == "test" else "ТРЕНИРОВКА"
    question_text = f"<b>Режим: {mode_name}</b>\n\n<b>Тема:</b> {safe_topic}\n{safe_text}"


    await callback.message.answer(question_text, parse_mode="HTML", reply_markup=get_back_to_main_markup())
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

    # обновляем статистику пользователя в БД
    topic = task.get('topic', 'Общее')
    try:
        update_user_stats(message.from_user.id, topic, is_correct)
    except Exception as e:
        # не даём падать боту, логируем ошибку
        print(f"Ошибка обновления статистики для пользователя {message.from_user.id}: {e}")

    if mode == 'training':
        if is_correct:
            await message.answer("<b>Ответ верный!</b>", parse_mode="HTML", reply_markup=get_back_to_main_markup())
        else:
            safe_explanation = html.escape(task.get('explanation', 'Нет объяснения.'))
            # при объяснении неправильного ответа не показываем кнопку "Назад в меню"
            await message.answer(f"<b>Неверно.</b>\n\n{safe_explanation}", parse_mode="HTML")
    else:
        # Режим теста
        await message.answer("Ответ принят. Переходим к следующему вопросу ⏳", reply_markup=get_back_to_main_markup())

    if mode == 'training':
        # Бесконечная тренировка
        new_idx = random.randint(0, len(tasks) - 1)
        await state.update_data(current_task_index=new_idx, score=score)

        next_task = tasks[new_idx]
        safe_next_text = html.escape(next_task.get('text', ''))
        await message.answer(f"<b>Следующее задание:</b>\n{safe_next_text}", parse_mode="HTML", reply_markup=get_back_to_main_markup())

    else:
        # Режим теста
        new_idx = idx + 1
        if new_idx < TEST_QUESTIONS_COUNT and new_idx < len(tasks):
            await state.update_data(current_task_index=new_idx, score=score)

            next_task = tasks[new_idx]
            safe_next_text = html.escape(next_task.get('text', ''))
            await message.answer(
                f"<b>Вопрос {new_idx + 1} из {TEST_QUESTIONS_COUNT}:</b>\n{safe_next_text}",
                parse_mode="HTML",
                reply_markup=get_back_to_main_markup()
            )
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
