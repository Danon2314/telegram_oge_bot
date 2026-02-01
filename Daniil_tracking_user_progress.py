# библиотека
import firebase_admin
from firebase_admin import firestore
from firebase_admin import credentials
cred = credentials.Certificate('firebase-adminsdk-key.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

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




