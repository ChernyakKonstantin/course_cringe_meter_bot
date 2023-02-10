"""Версия для разработки."""

import os
import sqlite3
from enum import Enum

import telebot


class Status(Enum):
    WAIT_FOR_SUBJECT_NAME = 1
    WAIT_FOR_UNIVERSITY_NAME = 2


class CringeMeterBot:
    def __init__(self):
        self.mode = "dev"
        self.db_path = "database_dev.db" if self.mode == "dev" else "database_prod.db"
        self.example_chart_path = "example_chart.jpg"
        self.telegram_bot = telebot.TeleBot(self.load_token())
        self.waitlist = {}
        self._initialize_database()
        self._initialize_handlers()

    def load_token(self):
        if self.mode == "dev":
            token_path = "dev_token.txt"
        else:
            token_path = "prod_token.txt"
        with open(token_path) as f:
            token = f.readlines()[0]
        return token

    def _initialize_database(self):
        if not os.path.exists(self.db_path):
            con = sqlite3.connect(self.db_path)
            cur = con.cursor()
            cur.execute(
                "CREATE TABLE user_activity ("
                "   id INTEGER PRIMARY KEY,"
                "   university_id INTEGER,"
                "   subject_id INTEGER"
                ")"
            )
            cur.execute(
                "CREATE TABLE subject ("
                "   id INTEGER PRIMARY KEY,"
                "   name TEXT NOT NULL UNIQUE"
                ")"
            )
            cur.execute(
                "CREATE TABLE university ("
                "   id INTEGER PRIMARY KEY,"
                "   name TEXT NOT NULL UNIQUE"
                ")"
            )
            cur.execute(
                "CREATE TABLE score ("
                "   id INTEGER PRIMARY KEY,"
                "   user_id INTEGER,"
                "   university_id INTEGER,"
                "   subject_id INTEGER,"
                "   score INTEGER NOT NULL,"
                "   date FLOAT,"
                "   FOREIGN KEY (user_id) REFERENCES user_activity(id),"
                "   FOREIGN KEY (university_id) REFERENCES university(id),"
                "   FOREIGN KEY (subject_id) REFERENCES subject(id)"
                ")"
            )
            con.commit()
            con.close()

    def _initialize_handlers(self):
        self.telegram_bot.message_handler(commands=["start"])(self.send_welcome)
        self.telegram_bot.message_handler(commands=["cancel"])(self.cancel)
        self.telegram_bot.message_handler(func=lambda message: message.text == "Выбрать университет")(
            self.select_university)
        self.telegram_bot.message_handler(func=lambda message: message.text == "Выбрать предмет")(self.select_subject)
        self.telegram_bot.message_handler(func=lambda message: message.text == "Оценивать")(self.start_scoring)
        self.telegram_bot.message_handler(func=lambda message: message.chat.id in self.waitlist.keys())(
            self.handle_waitlist)
        self.telegram_bot.message_handler(content_types=["text"])(self.get_score)

    def add_menu(self):
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        select_university_button = telebot.types.KeyboardButton("Выбрать университет")
        select_subject_button = telebot.types.KeyboardButton("Выбрать предмет")
        start_scoring_button = telebot.types.KeyboardButton("Оценить кринж")
        markup.add(select_university_button, select_subject_button, start_scoring_button)
        return markup

    def add_user_to_db(self, chat_id):
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        cur.execute(f"INSERT OR IGNORE INTO user_activity(id) VALUES ({chat_id})")
        con.commit()
        con.close()

    def send_welcome(self, message):
        chat_id = message.chat.id
        self.add_user_to_db(chat_id)
        welcome_message = "Привет!\n" \
                          "Я предлагаю тебе присоединиться к сбору статистики по уровню кринжа на парах.\n" \
                          "Шкала оценивания: 0 - минимальный кринж (база), 10 - кринжевый кринж.\n" \
                          "Ставить оценок можешь сколько угодно.\n" \
                          "Ожидаем вот такие графики курса кринжа на примере <университета>:"
        markup = self.add_menu()
        self.telegram_bot.send_photo(
            chat_id,
            caption=welcome_message,
            photo=open(self.example_chart_path, 'rb'),
            reply_markup=markup,
        )

    def start_scoring(self, message):
        chat_id = message.chat.id
        university_id, subject_id = self.get_user_current_state(chat_id)
        if university_id is not None and subject_id is not None:
            text = f"Всё готово. Теперь ты можешь оценивать уровень кринжа"
            self.telegram_bot.send_message(chat_id, text)
        else:
            if university_id is None:
                text = "Выбери свой университет."
                self.telegram_bot.send_message(chat_id, text)
            if subject_id is None:
                text = "Выбери предмет."
                self.telegram_bot.send_message(chat_id, text)

    def send_help(self, message):
        chat_id = message.chat.id
        text = "/help - справка\n" \
               "Шкала оценивания: 0 - минимальный кринж (база), 10 - кринжевый кринж."
        self.telegram_bot.send_message(chat_id, text)

    def select_subject(self, message):
        chat_id = message.chat.id
        self.waitlist[chat_id] = Status.WAIT_FOR_SUBJECT_NAME
        text = "Напиши мне название предмета, который ты оцениваешь." \
               " Для отмены действия напиши /cancel."
        self.telegram_bot.send_message(chat_id, text)

    def select_university(self, message):
        chat_id = message.chat.id
        self.waitlist[chat_id] = Status.WAIT_FOR_UNIVERSITY_NAME
        text = "Напиши мне название своего университета, что я не напутал рейтинг." \
               " Для отмены действия напиши /cancel."
        self.telegram_bot.send_message(chat_id, text)

    def handle_waitlist(self, message):
        chat_id = message.chat.id
        if self.waitlist[chat_id] == Status.WAIT_FOR_SUBJECT_NAME:
            self.get_subject_name(message)
        elif self.waitlist[chat_id] == Status.WAIT_FOR_UNIVERSITY_NAME:
            self.get_university_name(message)

    def add_subject_to_db(self, subject_name):
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        cur.execute(
            f"INSERT OR IGNORE"
            f" INTO subject(name)"
            f" VALUES (\"{subject_name}\")",
        )
        con.commit()
        con.close()

    def set_subject_for_user(self, chat_id, subject_name):
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        subject_id = cur.execute(
            f"SELECT id"
            f" FROM subject"
            f" WHERE name=\"{subject_name}\"",
        ).fetchone()[0]
        cur.execute(
            f"UPDATE user_activity"
            f" SET subject_id ={subject_id}"
            f" WHERE id={chat_id}",
        )
        con.commit()
        con.close()

    def get_subject_name(self, message):
        chat_id = message.chat.id
        subject_name = message.text
        self.add_subject_to_db(subject_name)
        self.set_subject_for_user(chat_id, subject_name)
        del (self.waitlist[chat_id])
        text = f"Все последующие оценки будут записаны для предмета \"{subject_name}\"."
        self.telegram_bot.send_message(chat_id, text)
        self.start_scoring(message)

    def add_university_to_db(self, university_name):
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        cur.execute(
            f"INSERT OR IGNORE"
            f" INTO university(name)"
            f" VALUES (\"{university_name}\")",
        )
        con.commit()
        con.close()

    def set_university_for_user(self, chat_id, university_name):
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        university_id = cur.execute(
            f"SELECT id"
            f" FROM university"
            f" WHERE name=\"{university_name}\"",
        ).fetchone()[0]
        cur.execute(
            f"UPDATE user_activity"
            f" SET university_id ={university_id}"
            f" WHERE id={chat_id}",
        )
        con.commit()
        con.close()

    def get_university_name(self, message):
        chat_id = message.chat.id
        university_name = message.text
        self.add_university_to_db(university_name)
        self.set_university_for_user(chat_id, university_name)
        del (self.waitlist[chat_id])
        text = f"Все последующие оценки будут записаны для \"{university_name}\"."
        self.telegram_bot.send_message(chat_id, text)
        university_id, subject_id = self.get_user_current_state(chat_id)
        if university_id is not None and subject_id is not None:
            text = f"Всё готово. Теперь ты можешь оценивать уровень кринжа.\n" \
                   f"Шкала оценивания: 0 - минимальный кринж (база), 10 - кринжевый кринж."
            self.telegram_bot.send_message(chat_id, text)
        else:
            if university_id is None:
                text = "Выбери свой университет"
                self.telegram_bot.send_message(chat_id, text)
            if subject_id is None:
                text = "Выбери предмет"
                self.telegram_bot.send_message(chat_id, text)

    def cancel(self, message):
        chat_id = message.chat.id
        try:
            del (self.waitlist[chat_id])
        except KeyError:
            pass

    def get_user_current_state(self, chat_id):
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        university_id, subject_id = cur.execute(
            f"SELECT university_id, subject_id"
            f" FROM user_activity"
            f" WHERE id={chat_id}"
        ).fetchone()
        con.close()
        return university_id, subject_id

    def id2university(self, university_id):
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        university_name = cur.execute(
            f"SELECT name"
            f" FROM university"
            f" WHERE id = {university_id}",
        ).fetchone()[0]
        con.close()
        return university_name

    def id2subject(self, subject_id):
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        subject_name = cur.execute(
            f"SELECT name"
            f" FROM subject"
            f" WHERE id = {subject_id}",
        ).fetchone()[0]
        con.close()
        return subject_name

    def get_score(self, message):
        chat_id = message.chat.id
        university_id, subject_id = self.get_user_current_state(chat_id)
        if university_id is None or subject_id is None:
            if university_id is None:
                text = "Выбери свой университет"
                self.telegram_bot.send_message(chat_id, text)
            if subject_id is None:
                text = "Выбери предмет"
                self.telegram_bot.send_message(chat_id, text)
        else:
            try:
                score = int(message.text)
                if not 0 <= score <= 10:
                    text = "Шкала кринжа от 0 до 10."
                    self.telegram_bot.send_message(chat_id, text)
                else:
                    university_id, subject_id = self.get_user_current_state(chat_id)
                    university_name = self.id2university(university_id)
                    subject_name = self.id2subject(subject_id)
                    date = message.date
                    con = sqlite3.connect(self.db_path)
                    cur = con.cursor()
                    cur.execute(
                        f"INSERT INTO"
                        f" score(user_id, university_id, subject_id, score, date)"
                        f" VALUES ({chat_id}, {university_id}, {subject_id}, {score}, \"{date}\")",
                    )
                    con.close()
                    text = f"Записал {score} для {subject_name} в {university_name}"
                    self.telegram_bot.send_message(chat_id, text)
            except ValueError:
                text = "Жду от тебя текущий уровень кринжа по шкале от 0 до 10."
                self.telegram_bot.send_message(chat_id, text)


if __name__ == "__main__":
    bot = CringeMeterBot()
    bot.telegram_bot.infinity_polling()
