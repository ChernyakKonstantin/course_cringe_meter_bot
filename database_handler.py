import os
import sqlite3
from typing import List, Any, Tuple

__all__ = ["SQLiteDB", ]


class SQLiteDB:
    def __init__(self, db_path):
        self.db_path = db_path
        self._initialize_database()

    # PRIVATE METHODS
    def _initialize_database(self) -> None:
        if not os.path.exists(self.db_path):
            con = sqlite3.connect(self.db_path)
            cur = con.cursor()
            cur.execute(
                "CREATE TABLE user_activity ("
                "   id INTEGER PRIMARY KEY,"
                "   ready INTEGER DEFAULT 0,"
                "   university_id INTEGER,"
                "   subject_id INTEGER,"
                "   response_message_id INTEGER,"
                "   request_message_id INTEGER,"
                "   wait_for INTEGER DEFAULT 0"
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
                "CREATE TABLE university_subject ("
                "   id INTEGER PRIMARY KEY,"
                "   university_id INTEGER NOT NULL,"
                "   subject_id INTEGER NOT NULL,"
                "   FOREIGN KEY (university_id) REFERENCES university(id),"
                "   FOREIGN KEY (subject_id) REFERENCES subject(id)"
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

    def _execute(self, sql_statement) -> List[Any]:
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        result = cur.execute(sql_statement).fetchall()
        con.commit()
        con.close()
        return result

    # ____PUBLIC_METHODS____

    def clear_user_awaiting(self, user_id):
        self.set_wait_for_user(user_id, 0)
        self.set_request_message_id_for_user(user_id, None)
        self.set_response_message_id_for_user(user_id, None)

    # ___GETTERS___
    def get_all_universities(self) -> List[Tuple[int, str]]:
        sql_statement = f"SELECT * from university"
        universities = self._execute(sql_statement)
        return universities

    def get_university_subjects(self, university_id: int = None) -> List[Tuple[int, str]]:
        sql_statement = f"SELECT subject_id" \
                        f" from university_subject" \
                        f" WHERE university_id={university_id}"
        subjects = self._execute(sql_statement)
        return subjects

    def get_user_current_state(self, user_id: int) -> Tuple:
        sql_statement = f"SELECT ready, university_id, subject_id, response_message_id, request_message_id, wait_for" \
                        f" FROM user_activity" \
                        f" WHERE id={user_id}"
        data = self._execute(sql_statement)[0]
        ready, university_id, subject_id, response_message_id, request_message_id, wait_for = data
        return ready, university_id, subject_id, response_message_id, request_message_id, wait_for

    # ___APPENDERS___
    def append_user(self, user_id: int) -> None:
        sql_statement = f"INSERT OR IGNORE INTO user_activity(id) VALUES ({user_id})"
        self._execute(sql_statement)

    def append_university(self, university_name: str) -> None:
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        cur.execute(
            f"INSERT OR IGNORE"
            f" INTO university(name)"
            f" VALUES (\"{university_name}\")",
        )
        con.commit()
        con.close()

    def append_subject(self, subject_name: str) -> None:
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        cur.execute(
            f"INSERT OR IGNORE"
            f" INTO subject(name)"
            f" VALUES (\"{subject_name}\")",
        )
        con.commit()
        con.close()

    def append_subject_to_university(self, university_id, subject_id):
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        cur.execute(
            f"INSERT OR IGNORE"
            f" INTO university_subject(university_id, subject_id)"
            f" VALUES ({university_id}, {subject_id})",
        )
        con.commit()
        con.close()

    def append_score(self, user_id: int, university_id: int, subject_id: int, score: int, date: int) -> None:
        sql_statement = f"INSERT INTO" \
                        f" score(user_id, university_id, subject_id, score, date)" \
                        f" VALUES ({user_id}, {university_id}, {subject_id}, {score}, \"{date}\")"
        self._execute(sql_statement)

    # ___SETTERS___
    def set_ready_for_user(self, user_id):
        sql_statement = f"UPDATE user_activity" \
                        f" SET ready ={1}" \
                        f" WHERE id={user_id}"
        self._execute(sql_statement)

    def set_wait_for_user(self, user_id, status):
        sql_statement = f"UPDATE user_activity" \
                        f" SET wait_for ={int(status)}" \
                        f" WHERE id={user_id}"
        self._execute(sql_statement)

    def set_request_message_id_for_user(self, user_id, request_message_id):
        if request_message_id is None:
            request_message_id = "NULL"
        sql_statement = f"UPDATE user_activity" \
                        f" SET request_message_id ={request_message_id}" \
                        f" WHERE id={user_id}"
        self._execute(sql_statement)

    def set_response_message_id_for_user(self, user_id, response_message_id):
        if response_message_id is None:
            response_message_id = "NULL"
        sql_statement = f"UPDATE user_activity" \
                        f" SET response_message_id ={response_message_id}" \
                        f" WHERE id={user_id}"
        self._execute(sql_statement)

    def set_university_for_user(self, user_id: int, university_id: int) -> None:
        sql_statement = f"UPDATE user_activity" \
                        f" SET university_id ={university_id}" \
                        f" WHERE id={user_id}"
        self._execute(sql_statement)

    def set_subject_for_user(self, user_id: int, subject_id: int) -> None:
        sql_statement = f"UPDATE user_activity" \
                        f" SET subject_id ={subject_id}" \
                        f" WHERE id={user_id}"
        self._execute(sql_statement)

    # ___CONVERTERS___
    def id2subject(self, subject_id: int) -> str:
        sql_statement = f"SELECT name" \
                        f" FROM subject" \
                        f" WHERE id = {subject_id}"
        subject_name = self._execute(sql_statement)[0][0]
        return subject_name

    def subject2id(self, subject_name: str) -> int:
        sql_statement = f"SELECT id" \
                        f" FROM subject" \
                        f" WHERE name = \"{subject_name}\""
        subject_id = self._execute(sql_statement)[0][0]
        return subject_id

    def id2university(self, university_id: int) -> str:
        sql_statement = f"SELECT name" \
                        f" FROM university" \
                        f" WHERE id = {university_id}"
        university_name = self._execute(sql_statement)[0][0]
        return university_name

    def university2id(self, university_name: str) -> int:
        sql_statement = f"SELECT id" \
                        f" FROM university" \
                        f" WHERE name = \"{university_name}\""
        subject_id = self._execute(sql_statement)[0][0]
        return subject_id
