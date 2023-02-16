import argparse
from enum import Enum

import telebot

from database_handler import SQLiteDB


class Status(Enum):
    WAIT_FOR_SUBJECT_NAME = 1
    WAIT_FOR_UNIVERSITY_NAME = 2


class ReturnCode(Enum):
    DELETE_RESPONSE_REQUEST = 1
    DELETE_RESPONSE = 2


class CringeMeterBot:
    def __init__(self, api_token, sqlite_db_path, debug=False):
        self.db_path = sqlite_db_path
        self.bot_api = telebot.TeleBot(api_token, skip_pending=True)
        self.database = SQLiteDB(sqlite_db_path)
        self._initialize_handlers()
        if debug:
            self._add_demo_data()

    def _add_demo_data(self):
        university_ids = []
        subject_ids = []
        for university_name in ["ИТМО", "ЛЭТИ", "СПБГУ"]:
            self.database.append_university(university_name)
            university_ids.append(self.database.university2id(university_name))
        for subject_name in ["ArchNN", "BigData", "IRME"]:
            self.database.append_subject(subject_name)
            subject_ids.append(self.database.subject2id(subject_name))
        self.database.append_subject_to_university(university_ids[0], subject_ids[0])
        self.database.append_subject_to_university(university_ids[0], subject_ids[1])
        self.database.append_subject_to_university(university_ids[1], subject_ids[2])

    def _build_menu_markup(self):
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        select_subject_button = telebot.types.KeyboardButton("Выбрать предмет")
        current_subject_button = telebot.types.KeyboardButton("Выбранный предмет")
        markup.add(select_subject_button, current_subject_button)
        return markup

    def _show_command_menu(self, chat_id):
        commands = [
            telebot.types.BotCommand("/start", "Запустить или обновить бота"),
            telebot.types.BotCommand("/help", "Показать справку"),
            telebot.types.BotCommand("/change_university", "Сменить университет"),
            telebot.types.BotCommand("/current_university", "Показать выбранный университет"),
            telebot.types.BotCommand("/change_subject", "Сменить предмет"),
            telebot.types.BotCommand("/current_subject", "Показать выбранный предмет"),
        ]
        self.bot_api.set_my_commands(commands, telebot.types.BotCommandScopeChat(chat_id))

    def _initialize_handlers(self):
        # Callback query handlers. The handlers and processed in the declaration order.
        self.bot_api.callback_query_handler(func=lambda call: True)(self._callback_query_handler)
        # Message handlers. The handlers and processed in the declaration order.
        #   Command handlers
        self.bot_api.message_handler(commands=["start"])(self.on_start)
        self.bot_api.message_handler(commands=["help"])(self.on_help)
        self.bot_api.message_handler(commands=["change_university"])(self.on_change_university)
        self.bot_api.message_handler(commands=["current_university"])(self.on_get_current_university)
        self.bot_api.message_handler(commands=["change_subject"])(self.on_change_subject)
        self.bot_api.message_handler(commands=["current_subject"])(self.on_get_current_subject)
        self.bot_api.message_handler(commands=["kon_notify_users"])(self.notify_for_update)
        # #   Menu button handlers
        self.bot_api.message_handler(func=lambda msg: msg.text == "Выбрать предмет")(self.on_change_subject)
        self.bot_api.message_handler(func=lambda msg: msg.text == "Выбранный предмет")(self.on_get_current_subject)
        # #   Data handlers
        if_user_await = lambda msg: self.database.get_user_current_state(msg.chat.id)[-1] != 0
        self.bot_api.message_handler(func=if_user_await)(self._on_wait_new_entry_message)
        self.bot_api.message_handler(content_types=["text"])(self.on_get_score)

    def _delete_response_request_messages(self, chat_id, response_message_id, request_message_id=None):
        if request_message_id is not None:
            self.bot_api.delete_message(chat_id, request_message_id)
        self.bot_api.delete_message(chat_id, response_message_id)
        # self.user__state[chat_id].clear_awaiting()
        self.database.clear_user_awaiting(chat_id)

    # ___

    def _maybe_continue_on_start(self, message):
        chat_id = message.chat.id
        ready, _, _, _, _, _ = self.database.get_user_current_state(chat_id)
        if not ready:
            self.on_start(message, send_welcome=False)

    def _is_wait_for_university_promt(self, chat_id):
        _, _, _, _, _, wait_for = self.database.get_user_current_state(chat_id)
        return wait_for == Status.WAIT_FOR_UNIVERSITY_NAME.value

    def _is_wait_for_subject_promt(self, chat_id):
        _, _, _, _, _, wait_for = self.database.get_user_current_state(chat_id)
        return wait_for == Status.WAIT_FOR_SUBJECT_NAME.value

    def on_get_score(self, message):
        chat_id = message.chat.id
        _, university_id, subject_id, _, _, _ = self.database.get_user_current_state(chat_id)
        if university_id is None or subject_id is None:
            if university_id is None:
                text = "Выбери свой университет с помощью /select_university"
                self.bot_api.send_message(chat_id, text)
            if subject_id is None:
                text = "Выбери предмет с помощью /select_subject"
                self.bot_api.send_message(chat_id, text)
        else:
            try:
                score = int(message.text)
                if not 0 <= score <= 10:
                    text = "Шкала кринжа от 0 до 10."
                    self.bot_api.send_message(chat_id, text)
                else:
                    university_name = self.database.id2university(university_id)
                    subject_name = self.database.id2subject(subject_id)
                    date = message.date
                    self.database.append_score(chat_id, university_id, subject_id, score, date)
                    text = f"Записал {score} для {subject_name} в {university_name}"
                    self.bot_api.send_message(chat_id, text)
            except ValueError:
                text = "Жду от тебя текущий уровень кринжа по шкале от 0 до 10."
                self.bot_api.send_message(chat_id, text)

    def _handle_university_promt(self, chat_id, university_name):
        self.database.append_university(university_name)
        university_id = self.database.university2id(university_name)
        self.database.set_university_for_user(chat_id, university_id)
        text = f"Все последующие оценки будут записаны для {university_name}."
        self.bot_api.send_message(chat_id, text)
        return ReturnCode.DELETE_RESPONSE

    def _handle_subject_promt(self, chat_id, subject_name):
        self.database.append_subject(subject_name)
        subject_id = self.database.subject2id(subject_name)
        _, university_id, _, _, _, _ = self.database.get_user_current_state(chat_id)
        self.database.set_subject_for_user(chat_id, subject_id)
        self.database.append_subject_to_university(university_id, subject_id)
        text = f"Все последующие оценки будут записаны для {subject_name}."
        self.bot_api.send_message(chat_id, text)
        return ReturnCode.DELETE_RESPONSE

    def _on_wait_new_entry_message(self, message):
        chat_id = message.chat.id
        try:
            _ = int(message.text)
            maybe_typed_score = True
        except ValueError:
            maybe_typed_score = False
        if self._is_wait_for_university_promt(chat_id):
            if maybe_typed_score:
                text = "Думаю, ты хотел ввести уровень кринжа. Отмени или закончи текущий выбор университета."
                self.bot_api.send_message(chat_id, text)
                return
            return_code = self._handle_university_promt(chat_id, message.text)
        elif self._is_wait_for_subject_promt(chat_id):
            if maybe_typed_score:
                text = "Думаю, ты хотел ввести уровень кринжа. Отмени или закончи текущий выбор предмета."
                self.bot_api.send_message(chat_id, text)
                return
            return_code = self._handle_subject_promt(chat_id, message.text)
        else:
            return
        if return_code == ReturnCode.DELETE_RESPONSE:
            _, _, _, response_message_id, _, _ = self.database.get_user_current_state(chat_id)
            self._delete_response_request_messages(chat_id, response_message_id, None)
        else:
            raise ValueError(f"Invalid return code: {return_code}")
        self._maybe_continue_on_start(message)

    def _handle_university_selection(self, chat_id, university_id):
        if university_id != "None":
            self.database.set_university_for_user(chat_id, university_id)
            university_name = self.database.id2university(university_id)
            text = f"Все последующие оценки будут записаны для {university_name}."
            self.bot_api.send_message(chat_id, text)
            return ReturnCode.DELETE_RESPONSE
        else:
            return ReturnCode.DELETE_RESPONSE_REQUEST

    def _handle_subject_selection(self, chat_id, subject_id):
        if subject_id != "None":
            self.database.set_subject_for_user(chat_id, subject_id)
            subject_name = self.database.id2subject(subject_id)
            text = f"Все последующие оценки будут записаны для \"{subject_name}\"."
            self.bot_api.send_message(chat_id, text)
            return ReturnCode.DELETE_RESPONSE
        else:
            return ReturnCode.DELETE_RESPONSE_REQUEST

    def _maybe_cancel_previous_menu(self, chat_id):
        _, _, _, response_message_id, request_message_id, wait_for = self.database.get_user_current_state(chat_id)
        if wait_for == 1:
            self._delete_response_request_messages(chat_id, response_message_id, request_message_id)

    def _callback_query_handler(self, callback_query):
        chat_id = callback_query.message.chat.id
        split = callback_query.data.split(":")
        ask_to_select_subject = False
        if len(split) > 1 and split[0] == "university_id":
            return_code = self._handle_university_selection(chat_id, university_id=split[1])
            ask_to_select_subject = return_code == ReturnCode.DELETE_RESPONSE
        elif len(split) > 1 and split[0] == "subject_id":
            return_code = self._handle_subject_selection(chat_id, subject_id=split[1])
        else:
            return
        if return_code == ReturnCode.DELETE_RESPONSE:
            ready, _, _, response_message_id, _, _ = self.database.get_user_current_state(chat_id)
            self._delete_response_request_messages(chat_id, response_message_id, None)
            if ask_to_select_subject and ready:
                message = telebot.types.Message(
                    message_id=-1,
                    from_user=telebot.types.User(id=None, is_bot=None, first_name=None),
                    date=None,
                    chat=telebot.types.Chat(id=chat_id, type=None),
                    content_type=None,
                    options={},
                    json_string=None,
                )
                self._ask_to_select_subject(message=message, cancel_option=False)
        elif return_code == ReturnCode.DELETE_RESPONSE_REQUEST:
            _, _, _, response_message_id, request_message_id, _ = self.database.get_user_current_state(chat_id)
            self._delete_response_request_messages(
                chat_id,
                response_message_id,
                request_message_id,
            )
        else:
            raise ValueError(f"Invalid return code: {return_code}")
        self._maybe_continue_on_start(callback_query.message)

    def send_welcome(self, chat_id):
        welcome_message = "Привет!\n" \
                          "Я предлагаю тебе присоединиться к сбору статистики по уровню кринжа на парах.\n" \
                          "Это очень просто!"
        self.bot_api.send_message(chat_id, text=welcome_message)

    def _show_keyboard_menu(self, chat_id):
        text = "Я готов к использованию.\n" \
               "Нажми /help, чтобы увидеть справку."
        menu_markup = self._build_menu_markup()
        self.bot_api.send_message(chat_id, text=text, reply_markup=menu_markup)

    def _ask_to_select(
            self,
            message,
            response_message_text,
            id_name,
            callback_data_prefix,
            status,
            cancel_option=True,
    ):
        chat_id = message.chat.id
        markup = telebot.types.InlineKeyboardMarkup()
        if cancel_option:
            markup.add(telebot.types.InlineKeyboardButton("Отмена", callback_data=f"{callback_data_prefix}:None"))
        for id, name in id_name:
            callback_data = f"{callback_data_prefix}:{id}"
            markup.add(telebot.types.InlineKeyboardButton(name, callback_data=callback_data))
        response_message = self.bot_api.send_message(chat_id, response_message_text, reply_markup=markup)
        self.database.set_wait_for_user(chat_id, status.value)
        self.database.set_response_message_id_for_user(chat_id, response_message.id)
        self.database.set_request_message_id_for_user(chat_id, message.id)

    def _ask_to_select_university(self, message, cancel_option=True):
        university_id_name = self.database.get_all_universities()
        if len(university_id_name) == 0:
            response_message_text = "Напиши название своего университета."
        else:
            response_message_text = "Выбери свой университет из списка или напиши свой."
        self._ask_to_select(
            message,
            response_message_text,
            university_id_name,
            "university_id",
            Status.WAIT_FOR_UNIVERSITY_NAME,
            cancel_option,
        )

    def _ask_to_select_subject(self, message, cancel_option=True):
        chat_id = message.chat.id
        _, university_id, subject_id, _, _, _ = self.database.get_user_current_state(chat_id)
        subject_ids = [i[0] for i in self.database.get_university_subjects(university_id)]
        subject_names = [self.database.id2subject(i) for i in subject_ids]
        subject_id_name = list(zip(subject_ids, subject_names))
        if len(subject_id_name) == 0:
            response_message_text = "Напиши название предмета."
        else:
            response_message_text = "Выбери предмет из списка или напиши свой."
        self._ask_to_select(
            message,
            response_message_text,
            subject_id_name,
            "subject_id",
            Status.WAIT_FOR_SUBJECT_NAME,
            cancel_option,
        )

    # Command events
    def on_start(self, message, send_welcome=True):
        chat_id = message.chat.id
        self.database.append_user(chat_id)
        if send_welcome:
            self.send_welcome(chat_id)
        _, university_id, subject_id, _, _, _ = self.database.get_user_current_state(chat_id)
        if university_id is None:
            self._ask_to_select_university(message, cancel_option=False)  # Add decorator that calls `on_start` again
            return
        elif university_id is not None and send_welcome:
            university_name = self.database.id2university(university_id)
            self.bot_api.send_message(
                chat_id,
                text=f"У тебя выбран университет {university_name}",
            )
        if subject_id is None:
            self._ask_to_select_subject(message, cancel_option=False)  # Add decorator that calls `on_start` again
            return
        elif subject_id is not None and send_welcome:
            subject_name = self.database.id2subject(subject_id)
            self.bot_api.send_message(
                chat_id,
                text=f"У тебя выбран предмет {subject_name}",
            )
        if university_id is not None and subject_id is not None:
            self.database.set_ready_for_user(chat_id)
            self._show_keyboard_menu(chat_id)
            self._show_command_menu(chat_id)

    def on_help(self, message):
        chat_id = message.chat.id
        text = "Шкала оценивания: 0 - ноль кринжа, 10 - кринжевый кринж.\n" \
               "Ставить оценок можешь сколько угодно.\n\n" \
               "Список доступных команд ты можешь увидеть в меню.\n" \
               "Для смены предмета нажми кнопку \"Выбрать предмет\" или выбери этот пункт в меню.\n" \
               "Чтобы быстро узнать выбранный предмет нажми \"Выбранный предмет\" или выбери этот пункт в меню.\n\n" \
               "Все прочие сообщения, которые ты будешь писать в чате будут записаны как твоя оценка уровня кринжа."
        self.bot_api.send_message(chat_id, text)

    def on_change_university(self, message):
        chat_id = message.chat.id
        ready, _, _, _, _, _ = self.database.get_user_current_state(chat_id)
        if ready != 1:
            self.bot_api.send_message(chat_id, "Для начала закончи выбор университета и предмета.")
        else:
            self._maybe_cancel_previous_menu(message.chat.id)
            self._ask_to_select_university(message)

    def on_get_current_university(self, message):
        chat_id = message.chat.id
        ready, university_id, _, _, _, _ = self.database.get_user_current_state(chat_id)
        if ready != 1:
            self.bot_api.send_message(chat_id, "Для начала закончи выбор университета и предмета.")
        else:
            self._maybe_cancel_previous_menu(chat_id)
            university_name = self.database.id2university(university_id)
            self.bot_api.send_message(chat_id, f"Текущий выбор университета: {university_name}")

    def on_change_subject(self, message):
        chat_id = message.chat.id
        ready, _, _, _, _, _ = self.database.get_user_current_state(chat_id)
        if ready != 1:
            self.bot_api.send_message(chat_id, "Для начала закончи выбор университета и предмета.")
        else:
            self._maybe_cancel_previous_menu(message.chat.id)
            self._ask_to_select_subject(message)

    def on_get_current_subject(self, message):
        chat_id = message.chat.id
        ready, _, subject_id, _, _, _ = self.database.get_user_current_state(chat_id)
        if ready != 1:
            self.bot_api.send_message(chat_id, "Для начала закончи выбор университета и предмета.")
        else:
            self._maybe_cancel_previous_menu(chat_id)
            subject_name = self.database.id2subject(subject_id)
            self.bot_api.send_message(chat_id, f"Текущий выбор предмет: {subject_name}")

    def notify_for_update(self, message):
        text = "Привет! У меня вышло новое обновление и я стал более удобным!\n" \
               "Обязательно нажми команду /start, чтобы я обновился.\n" \
               "P.S. Поделись ссылкой на меня со знакомыми."
        for chat_id in self.database.get_all_users():
            try:
                chat_id = chat_id[0]
                self.bot_api.set_my_commands([], telebot.types.BotCommandScopeChat(chat_id))
                self.bot_api.send_message(chat_id, text, reply_markup=telebot.types.ReplyKeyboardRemove())
            except:
                with open("blacklist.txt", "a") as f:
                    f.writelines([str(chat_id), ])

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Course cringe meter telegram bot")
    parser.add_argument("-t", "--api_token")
    parser.add_argument("-p", "--sqlite_db")
    parser.add_argument("-d", "--debug", action="store_true")
    args = parser.parse_args()
    bot = CringeMeterBot(args.api_token, args.sqlite_db, args.debug)
    bot.bot_api.infinity_polling()
