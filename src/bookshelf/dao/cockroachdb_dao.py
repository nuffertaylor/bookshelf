import os
import psycopg2
import time
import uuid
from contextlib import contextmanager, suppress


class CockroachDAO:
    def __init__(self, db_url):
        if os.getenv("SKIP_SSL_CERT"):
            self.conn = psycopg2.connect(db_url)
        else:
            import boto3
            import tempfile
            secret_arn = os.getenv("CERT_SECRET_ARN")
            sm = boto3.client("secretsmanager")
            cert_content = sm.get_secret_value(SecretId=secret_arn)["SecretString"]
            with tempfile.NamedTemporaryFile(mode="w", suffix=".crt", delete=False) as f:
                f.write(cert_content)
                cert_path = f.name
            self.conn = psycopg2.connect(db_url, sslrootcert=cert_path)

    def __del__(self):
        self.disconnect()

    def disconnect(self):
        self.conn.close()

    def exec_statement(self, stmt, args=None):
        try:
            with self.conn.cursor() as cur:
                if args is not None:
                    cur.execute(stmt, args)
                else:
                    cur.execute(stmt)
                self.conn.commit()
                return True
        except Exception as ex:
            template = "An exception of type {0} occurred. Arguments:\n{1!r}"
            message = template.format(type(ex).__name__, ex.args)
            print(message)
            self._rollback()
            return False

    def exec_statement_fetch(self, stmt, args=None):
        try:
            with self.conn.cursor() as cur:
                if args is not None:
                    cur.execute(stmt, args)
                else:
                    cur.execute(stmt)
                self.conn.commit()
                if cur.pgresult_ptr is not None:
                    return cur.fetchall()
                return False
        except Exception as ex:
            template = "An exception of type {0} occurred. Arguments:\n{1!r}"
            message = template.format(type(ex).__name__, ex.args)
            print(message)
            self._rollback()
            return False

    def _rollback(self):
        with suppress(Exception):
            self.conn.rollback()

    @contextmanager
    def transaction(self):
        """A real transaction: `with db.transaction() as cur:`. Commits once on a clean exit, rolls
        back on any exception (which is re-raised). Unlike exec_statement it never commits
        intermediate statements and never swallows errors, so SELECT ... FOR UPDATE row locks are
        held until the block ends."""
        cur = self.conn.cursor()
        try:
            yield cur
            self.conn.commit()
        except BaseException:
            self._rollback()
            raise
        finally:
            cur.close()

    def validate_uuid(self, uuid_to_test):
        try:
            uuid.UUID(uuid_to_test)
            return True
        except Exception:
            return False

    def create_bookshelf_users_table(self):
        create_bookshelf_users_sql = """
        CREATE TABLE IF NOT EXISTS bookshelf_users (
          username VARCHAR ( 50 ) PRIMARY KEY,
          hashedPassword VARCHAR ( 255 ) NULL,
          email VARCHAR ( 255 ) UNIQUE NULL,
          authtoken VARCHAR ( 100 ) NOT NULL,
          expiry INT NOT NULL,
          salt VARCHAR ( 100 ) NULL,
          ip VARCHAR ( 24 ),
          banned BOOLEAN NOT NULL,
          goodreads_id STRING
        );
        """
        self.exec_statement(create_bookshelf_users_sql)

    def create_shelf_image_table(self):
        create_shelf_image_sql = """
        CREATE TABLE IF NOT EXISTS shelf_images (
          shelf_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          filename STRING UNIQUE NOT NULL,
          timestamp INT NOT NULL,
          owner STRING NULL,
          bookshelf_name STRING NULL,
          gr_shelf_name STRING NULL,
          gr_user_id STRING NULL
        );
        """
        self.exec_statement(create_shelf_image_sql)

    def create_bookshelf_table(self):
        create_bookshelf_sql = """
        CREATE TABLE IF NOT EXISTS bookshelf (
          upload_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          book_id INT NULL,
          title STRING NOT NULL,
          author STRING NULL,
          dimensions STRING NOT NULL,
          domColor STRING NULL,
          fileName STRING UNIQUE NOT NULL,
          genre STRING NULL,
          isbn STRING NULL,
          isbn13 STRING NULL,
          pubDate STRING NULL,
          submitter STRING NOT NULL,
          rating INT NULL,
          flagged BOOLEAN NULL,
          timestamp INT NULL,
          hardcover_book_id INT NULL
        );
        """
        self.exec_statement(create_bookshelf_sql)
        self.exec_statement("CREATE INDEX IF NOT EXISTS bookshelf_hardcover_book_id_idx ON bookshelf (hardcover_book_id)")

    def create_visitor_table(self):
        create_visitor_table_sql = """
        CREATE TABLE IF NOT EXISTS visitors (
          visitor_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          ip STRING,
          os STRING,
          browser STRING,
          timestamp INT,
          num_visits INT
        );
        """
        self.exec_statement(create_visitor_table_sql)

    def create_shelf_bgs_table(self):
        create_shelf_bgs_table_sql = """
        CREATE TABLE IF NOT EXISTS shelf_bgs (
          bg_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          submitter STRING NOT NULL,
          filename STRING UNIQUE NOT NULL,
          width_inches INT NOT NULL,
          width_pixels INT NOT NULL,
          shelf_bottoms INT[],
          shelf_left INT,
          timestamp INT,
          title STRING
        );
        """
        self.exec_statement(create_shelf_bgs_table_sql)

    def create_unfound_to_upload_table(self):
        create_bookshelf_sql = """
        CREATE TABLE IF NOT EXISTS unfound_to_upload (
          upload_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          book_id INT NULL,
          title STRING NOT NULL,
          author STRING NULL,
          isbn STRING NULL,
          isbn13 STRING NULL,
          pubDate STRING NULL,
          owner STRING NOT NULL,
          uploaded BOOLEAN NULL,
          timestamp INT NULL,
          hardcover_book_id INT NULL
        );
        """
        self.exec_statement(create_bookshelf_sql)

    def create_hardcover_connections_table(self):
        sql = """
        CREATE TABLE IF NOT EXISTS hardcover_connections (
          username           STRING PRIMARY KEY REFERENCES bookshelf_users(username),
          hardcover_id       BIGINT UNIQUE NOT NULL,
          hardcover_username STRING NOT NULL,
          access_token_enc   STRING NOT NULL,
          refresh_token_enc  STRING NOT NULL,
          access_expires_at  INT NOT NULL,
          scopes             STRING NOT NULL,
          needs_reauth       BOOLEAN NOT NULL DEFAULT false,
          created_at         INT NOT NULL,
          updated_at         INT NOT NULL
        );
        """
        self.exec_statement(sql)

    def create_oauth_states_table(self):
        sql = """
        CREATE TABLE IF NOT EXISTS oauth_states (
          state         STRING PRIMARY KEY,
          code_verifier STRING NOT NULL,
          mode          STRING NOT NULL,
          username      STRING NULL,
          created_at    INT NOT NULL,
          expires_at    INT NOT NULL,
          used          BOOLEAN NOT NULL DEFAULT false
        );
        """
        self.exec_statement(sql)

    def format_shelf_bg_tuple(self, x):
        return {
            "bg_id": x[0],
            "submitter": x[1],
            "filename": x[2],
            "width_inches": x[3],
            "width_pixels": x[4],
            "shelf_bottoms": x[5],
            "shelf_left": x[6],
            "timestamp": x[7],
            "title": x[8],
        }

    def add_shelf_bg(self, submitter, filename, width_inches, width_pixels, shelf_bottoms, shelf_left, title):
        self.create_shelf_bgs_table()
        sql = """
          INSERT INTO shelf_bgs
          (submitter, filename, width_inches, width_pixels, shelf_bottoms, shelf_left, timestamp, title)
          VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        return self.exec_statement(sql, (submitter, filename, width_inches, width_pixels, shelf_bottoms, shelf_left, str(int(time.time())), title))

    def get_all_shelf_bgs(self):
        sql = "SELECT * FROM shelf_bgs"
        res = self.exec_statement_fetch(sql)
        if not res:
            return False
        return [self.format_shelf_bg_tuple(x) for x in res]

    def get_shelf_bg_by_bg_id(self, bg_id):
        if not self.validate_uuid(bg_id):
            return False
        sql = "SELECT * FROM shelf_bgs WHERE bg_id = %s"
        res = self.exec_statement_fetch(sql, (bg_id,))
        if not res:
            return False
        if len(res) > 0:
            return self.format_shelf_bg_tuple(res[0])
        return False

    def get_shelf_bg_by_filename(self, filename):
        sql = "SELECT * FROM shelf_bgs WHERE filename = %s"
        res = self.exec_statement_fetch(sql, (filename,))
        if not res:
            return False
        if len(res) > 0:
            return self.format_shelf_bg_tuple(res[0])
        return False

    def add_visitor(self, visitor):
        sql = """
          INSERT INTO visitors
          (ip, os, browser, timestamp, num_visits)
          VALUES (%s, %s, %s, %s, 1)
        """
        return self.exec_statement(sql, (visitor["ip"], visitor["os"], visitor["browser"], str(int(time.time()))))

    def get_visitor_by_ip(self, ip):
        sql = "SELECT * FROM visitors WHERE ip = %s"
        visitor_tuple = self.exec_statement_fetch(sql, (ip,))
        if not visitor_tuple:
            return False
        visitor_tuple = visitor_tuple[0]
        return {
            "visitor_id": visitor_tuple[0],
            "ip": visitor_tuple[1],
            "os": visitor_tuple[2],
            "browser": visitor_tuple[3],
            "timestamp": visitor_tuple[4],
            "num_visits": visitor_tuple[5],
        }

    def update_visit_count(self, visitor_id, prev_visits):
        if not self.validate_uuid(visitor_id):
            return False
        sql = "UPDATE visitors SET num_visits = %s, timestamp = %s WHERE visitor_id = %s"
        return self.exec_statement(sql, (str(prev_visits + 1), str(int(time.time())), visitor_id))

    @staticmethod
    def _id_or_none(value):
        """Normalise an id from a request (int, numeric string, '' or None) to int or None."""
        if value is None or value == "":
            return None
        return int(value)

    def add_book(self, book):
        book_id = self._id_or_none(book.get("book_id"))
        hardcover_book_id = self._id_or_none(book.get("hardcover_book_id"))
        sql = """
              INSERT INTO bookshelf
              (book_id, title, author, dimensions, fileName, genre, isbn, isbn13, pubDate, submitter, domColor, rating, timestamp, hardcover_book_id)
              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
              RETURNING upload_id
              """
        res = self.exec_statement_fetch(sql, (book_id, book["title"], book["authorName"], book["dimensions"], book["fileName"], book["genre"], book["isbn"], book["isbn13"], book["pubDate"], book["username"], book["domColor"], "0", str(int(time.time())), hardcover_book_id))
        u_id = res[0]
        if type(u_id) == list:
            u_id = u_id[0]
        self.mark_unfound_as_uploaded(book_id, hardcover_book_id)
        return {"upload_id": u_id}

    def add_unfound_to_upload(self, book, username):
        self.create_unfound_to_upload_table()
        sql = """
              INSERT INTO unfound_to_upload
              (book_id, title, author, isbn, isbn13, pubDate, owner, uploaded, timestamp, hardcover_book_id)
              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
              RETURNING upload_id
              """
        res = self.exec_statement_fetch(sql, (self._id_or_none(book.get("book_id")), book["title"], book["author"], book["isbn"], book["isbn13"], book["pubDate"], username, False, str(int(time.time())), self._id_or_none(book.get("hardcover_book_id"))))
        u_id = res[0]
        if type(u_id) == list:
            u_id = u_id[0]
        return {"upload_id": u_id}

    def get_book_by(self, key, value):
        if key == "upload_id" and not self.validate_uuid(value):
            return False
        sql = "SELECT * FROM bookshelf WHERE " + key + " = %s"
        res_list = self.exec_statement_fetch(sql, (value,))
        if len(res_list) > 0:
            return self.format_book_tuple(res_list[0])
        return False

    @staticmethod
    def _id_match_clause(book_id, hardcover_book_id):
        """('(book_id = %s OR hardcover_book_id = %s)', params) using whichever ids are present,
        or (None, []) when neither is."""
        clauses = []
        params = []
        if book_id is not None:
            clauses.append("book_id = %s")
            params.append(book_id)
        if hardcover_book_id is not None:
            clauses.append("hardcover_book_id = %s")
            params.append(hardcover_book_id)
        if not clauses:
            return None, []
        return "(" + " OR ".join(clauses) + ")", params

    def get_book_by_ids(self, book_id=None, hardcover_book_id=None):
        """First bookshelf row matching either id (whichever is present), else False."""
        clause, params = self._id_match_clause(self._id_or_none(book_id), self._id_or_none(hardcover_book_id))
        if clause is None:
            return False
        res = self.exec_statement_fetch("SELECT * FROM bookshelf WHERE " + clause + " LIMIT 1", tuple(params))
        if res:
            return self.format_book_tuple(res[0])
        return False

    def has_username_uploaded_book(self, username, book_id=None, hardcover_book_id=None):
        clause, params = self._id_match_clause(self._id_or_none(book_id), self._id_or_none(hardcover_book_id))
        if clause is None:
            return False
        sql = "SELECT * FROM bookshelf WHERE submitter = %s AND " + clause
        res = self.exec_statement_fetch(sql, (username, *params))
        if res and len(res) > 0:
            return self.format_book_tuple(res[0])
        return False

    def has_user_saved_unfound(self, username, book_id=None, hardcover_book_id=None):
        clause, params = self._id_match_clause(self._id_or_none(book_id), self._id_or_none(hardcover_book_id))
        if clause is None:
            return False
        sql = "SELECT * FROM unfound_to_upload WHERE owner = %s AND " + clause
        res = self.exec_statement_fetch(sql, (username, *params))
        return bool(res)

    def get_book_batch(self, book_batch):
        percentS = ", ".join(["%s"] * len(book_batch))
        sql = "SELECT * FROM bookshelf WHERE book_id IN (" + percentS + ") OR title IN (" + percentS + ")"

        params = [b.get("book_id") for b in book_batch] + [b["title"] for b in book_batch]
        hardcover_ids = [b["hardcover_book_id"] for b in book_batch if b.get("hardcover_book_id") is not None]
        if hardcover_ids:
            sql += " OR hardcover_book_id IN (" + ", ".join(["%s"] * len(hardcover_ids)) + ")"
            params.extend(hardcover_ids)
        res = self.exec_statement_fetch(sql, tuple(params))
        return [self.format_book_tuple(r) for r in res]

    def get_spines_by_title_author(self, title, author):
        sql = """
          SELECT * FROM bookshelf
          WHERE LOWER(TRIM(title)) = LOWER(TRIM(%s))
          AND LOWER(TRIM(author)) = LOWER(TRIM(%s))
        """
        res = self.exec_statement_fetch(sql, (title, author))
        if not res:
            return []
        return [self.format_book_tuple(r) for r in res]

    def get_spines_batch_by_title_author(self, book_list):
        if not book_list or len(book_list) == 0:
            return []

        title_author_conditions = []
        params = []
        book_ids = []
        hardcover_ids = []
        for book in book_list:
            title_author_conditions.append("(LOWER(TRIM(title)) = LOWER(TRIM(%s)) AND LOWER(TRIM(author)) = LOWER(TRIM(%s)))")
            params.append(book["title"])
            params.append(book["author"])
            if book.get("book_id"):
                book_ids.append(book["book_id"])
            if book.get("hardcover_book_id") is not None:
                hardcover_ids.append(book["hardcover_book_id"])

        sql = "SELECT * FROM bookshelf WHERE " + " OR ".join(title_author_conditions)
        if book_ids:
            placeholders = ", ".join(["%s"] * len(book_ids))
            sql += f" OR book_id IN ({placeholders})"
            params.extend(book_ids)
        if hardcover_ids:
            placeholders = ", ".join(["%s"] * len(hardcover_ids))
            sql += f" OR hardcover_book_id IN ({placeholders})"
            params.extend(hardcover_ids)

        res = self.exec_statement_fetch(sql, tuple(params))
        if not res:
            return []
        return [self.format_book_tuple(r) for r in res]

    def update_book_file_name(self, upload_id, fileName):
        if not self.validate_uuid(upload_id):
            return False
        sql = "UPDATE bookshelf SET fileName = %s WHERE upload_id = %s"
        return self.exec_statement(sql, (fileName, upload_id))

    def delete_book(self, upload_id):
        if not self.validate_uuid(upload_id):
            return False
        sql = "DELETE FROM bookshelf WHERE upload_id = %s"
        return self.exec_statement(sql, (upload_id,))

    def format_book_tuple(self, book_tuple):
        return {
            "upload_id": book_tuple[0],
            "book_id": book_tuple[1],
            "title": book_tuple[2],
            "author": book_tuple[3],
            "dimensions": book_tuple[4],
            "domColor": book_tuple[5],
            "fileName": book_tuple[6],
            "genre": book_tuple[7],
            "isbn": book_tuple[8],
            "isbn13": book_tuple[9],
            "pubDate": book_tuple[10],
            "submitter": book_tuple[11],
            "rating": book_tuple[12],
            "flagged": book_tuple[13],
            # index 14 is `timestamp` (not exposed); hardcover_book_id was appended last
            "hardcover_book_id": book_tuple[15] if len(book_tuple) > 15 else None,
        }

    def format_unfound_to_upload_tuple(self, book_tuple):
        return {
            "upload_id": book_tuple[0],
            "book_id": book_tuple[1],
            "title": book_tuple[2],
            "author": book_tuple[3],
            "isbn": book_tuple[4],
            "isbn13": book_tuple[5],
            "pubDate": book_tuple[6],
            "owner": book_tuple[7],
            "uploaded": book_tuple[8],
            "timestamp": book_tuple[9],
            "hardcover_book_id": book_tuple[10] if len(book_tuple) > 10 else None,
        }

    def format_shelf_image_tuple(self, shelf_image_tuple):
        return {
            "shelf_id": shelf_image_tuple[0],
            "filename": shelf_image_tuple[1],
            "timestamp": shelf_image_tuple[2],
            "owner": shelf_image_tuple[3],
            "bookshelf_name": shelf_image_tuple[4],
            "gr_shelf_name": shelf_image_tuple[5],
            "gr_user_id": shelf_image_tuple[6],
        }

    def format_shelf_image_tuple_list(self, si_list):
        if type(si_list) is not list:
            return False
        return [self.format_shelf_image_tuple(r) for r in si_list]

    def format_unfound_to_upload_tuple_list(self, book_list):
        if type(book_list) is not list:
            return False
        return [self.format_unfound_to_upload_tuple(r) for r in book_list]

    def add_books(self, bookList):
        for book in bookList:
            if self.get_book_by("filename", book["fileName"]):
                continue
            self.add_book(book)

    def add_unfound_to_uploads(self, bookList, username):
        for book in bookList:
            book_id = book.get("book_id")
            hardcover_book_id = book.get("hardcover_book_id")
            if self._id_or_none(book_id) is None and self._id_or_none(hardcover_book_id) is None:
                continue
            if self.has_user_saved_unfound(username, book_id, hardcover_book_id) or self.get_book_by_ids(book_id, hardcover_book_id):
                continue
            self.add_unfound_to_upload(book, username)

    def update_book(self, book):
        if "upload_id" not in book.keys():
            return False
        if not self.validate_uuid(book["upload_id"]):
            return False
        return False

    def update_book_col(self, upload_id, col, value):
        if not self.validate_uuid(upload_id):
            return False
        sql = "UPDATE bookshelf set " + col + " = %s WHERE upload_id = %s"
        return self.exec_statement(sql, (value, upload_id))

    def add_shelf_image_and_owner(self, filename, owner, bookshelf_name):
        sql = "INSERT INTO shelf_images (filename, timestamp, owner, bookshelf_name) VALUES (%s, %s, %s, %s)"
        self.exec_statement(sql, (filename, str(int(time.time())), owner, bookshelf_name))
        return True

    def add_shelf_image(self, filename, gr_shelf_name, gr_user_id):
        sql = "INSERT INTO shelf_images (filename, timestamp, gr_shelf_name, gr_user_id) VALUES (%s, %s, %s, %s)"
        self.exec_statement(sql, (filename, str(int(time.time())), gr_shelf_name, gr_user_id))

    def add_shelf_images(self, filenameList):
        for filename in filenameList:
            self.add_shelf_image(filename)

    def add_user(self, user):
        sql = "INSERT INTO bookshelf_users (username, hashedPassword, email, authtoken, expiry, salt, ip, banned) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
        return self.exec_statement(sql, (user["username"], user["hashedPassword"], user["email"], user["authtoken"], user["expiry"], user["salt"], user["ip"], "FALSE"))

    def add_users(self, userList):
        for user in userList:
            self.add_user(user)

    def ban_user(self, username):
        sql = "UPDATE bookshelf_users SET banned = 'TRUE' WHERE username = %s"
        self.exec_statement(sql, (username,))

    def update_user_col(self, username, col, val):
        sql = "UPDATE bookshelf_users SET " + col + " = %s WHERE username = %s"
        return self.exec_statement(sql, (val, username))

    def get_user_by(self, key, value):
        sql = "SELECT * FROM bookshelf_users WHERE " + key + " = %s"
        res = self.exec_statement_fetch(sql, (value,))
        if not res:
            return False
        res = res[0]
        return {
            "username": res[0],
            "hashedPassword": res[1],
            "email": res[2],
            "authtoken": res[3],
            "expiry": res[4],
            "salt": res[5],
            "ip": res[6],
            "banned": res[7],
            "goodreads_id": res[8],
        }

    def get_user(self, username):
        return self.get_user_by("username", username)

    def update_user_authtoken(self, username, authtoken, expiry):
        sql = "UPDATE bookshelf_users SET authtoken = %s, expiry = %s WHERE username = %s"
        if self.exec_statement(sql, (authtoken, expiry, username)):
            return self.get_user(username)
        return False

    def validate_username_authtoken(self, username, authtoken):
        user = self.get_user(username)
        if not user:
            return False
        if authtoken != user["authtoken"]:
            return False
        if int(time.time()) > int(user["expiry"]):
            return False
        return not user["banned"]

    # ---- Hardcover OAuth accounts -------------------------------------------------------------

    def username_taken(self, username):
        """Case-insensitive check (get_user is an exact match). Raises on a DB error rather than
        reporting a name as free."""
        res = self.exec_statement_fetch("SELECT 1 FROM bookshelf_users WHERE LOWER(username) = LOWER(%s) LIMIT 1", (username,))
        if res is False:
            raise RuntimeError("database error while checking username")
        return len(res) > 0

    def email_taken(self, email):
        res = self.exec_statement_fetch("SELECT 1 FROM bookshelf_users WHERE LOWER(email) = LOWER(%s) LIMIT 1", (email,))
        if res is False:
            raise RuntimeError("database error while checking email")
        return len(res) > 0

    def create_oauth_user(self, username, email, authtoken, expiry):
        """Insert a password-less account. Returns False (not an exception) on any failure,
        e.g. a concurrent insert of the same username."""
        sql = """
          INSERT INTO bookshelf_users (username, hashedPassword, email, authtoken, expiry, salt, ip, banned)
          VALUES (%s, NULL, %s, %s, %s, NULL, NULL, FALSE)
        """
        return self.exec_statement(sql, (username, email, authtoken, expiry))

    def delete_user(self, username):
        """Used only to undo a half-created OAuth account."""
        return self.exec_statement("DELETE FROM bookshelf_users WHERE username = %s", (username,))

    @staticmethod
    def _format_connection(row):
        return {
            "username": row[0],
            "hardcover_id": row[1],
            "hardcover_username": row[2],
            "access_token_enc": row[3],
            "refresh_token_enc": row[4],
            "access_expires_at": row[5],
            "scopes": row[6],
            "needs_reauth": row[7],
        }

    _CONNECTION_COLS = ("username, hardcover_id, hardcover_username, access_token_enc, refresh_token_enc, "
                        "access_expires_at, scopes, needs_reauth")

    def get_hardcover_connection(self, username):
        res = self.exec_statement_fetch(
            "SELECT " + self._CONNECTION_COLS + " FROM hardcover_connections WHERE username = %s", (username,))
        if not res:
            return False
        return self._format_connection(res[0])

    def get_user_by_hardcover_id(self, hardcover_id):
        """The bookshelf user linked to this Hardcover user id, or False. The id is the identity key;
        never look accounts up by username or email."""
        res = self.exec_statement_fetch("SELECT username FROM hardcover_connections WHERE hardcover_id = %s", (hardcover_id,))
        if not res:
            return False
        return self.get_user(res[0][0])

    def upsert_hardcover_connection(self, username, hardcover_id, hardcover_username, access_token_enc,
                                    refresh_token_enc, access_expires_at, scopes):
        """Insert or replace this account's connection (clears needs_reauth). Returns False if the
        hardcover_id belongs to a different account (UNIQUE violation) or on any DB error."""
        now = int(time.time())
        sql = """
          INSERT INTO hardcover_connections
          (username, hardcover_id, hardcover_username, access_token_enc, refresh_token_enc,
           access_expires_at, scopes, needs_reauth, created_at, updated_at)
          VALUES (%s, %s, %s, %s, %s, %s, %s, false, %s, %s)
          ON CONFLICT (username) DO UPDATE SET
            hardcover_id = EXCLUDED.hardcover_id,
            hardcover_username = EXCLUDED.hardcover_username,
            access_token_enc = EXCLUDED.access_token_enc,
            refresh_token_enc = EXCLUDED.refresh_token_enc,
            access_expires_at = EXCLUDED.access_expires_at,
            scopes = EXCLUDED.scopes,
            needs_reauth = false,
            updated_at = EXCLUDED.updated_at
        """
        return self.exec_statement(sql, (username, hardcover_id, hardcover_username, access_token_enc,
                                         refresh_token_enc, access_expires_at, scopes, now, now))

    def mark_hardcover_needs_reauth(self, username):
        return self.exec_statement(
            "UPDATE hardcover_connections SET needs_reauth = true, updated_at = %s WHERE username = %s",
            (int(time.time()), username))

    # Transaction-scoped helpers: take the cursor from `with db.transaction() as cur:`.

    def lock_hardcover_connection(self, cur, username):
        """SELECT ... FOR UPDATE; a concurrent caller blocks here until this transaction ends."""
        cur.execute("SELECT " + self._CONNECTION_COLS + " FROM hardcover_connections WHERE username = %s FOR UPDATE", (username,))
        row = cur.fetchone()
        return self._format_connection(row) if row else False

    def save_hardcover_tokens(self, cur, username, access_token_enc, refresh_token_enc, access_expires_at, scopes):
        cur.execute(
            """UPDATE hardcover_connections
               SET access_token_enc = %s, refresh_token_enc = %s, access_expires_at = %s, scopes = %s,
                   needs_reauth = false, updated_at = %s
               WHERE username = %s""",
            (access_token_enc, refresh_token_enc, access_expires_at, scopes, int(time.time()), username))

    def set_hardcover_needs_reauth(self, cur, username):
        cur.execute("UPDATE hardcover_connections SET needs_reauth = true, updated_at = %s WHERE username = %s",
                    (int(time.time()), username))

    # ---- OAuth state --------------------------------------------------------------------------

    def delete_expired_oauth_states(self, now):
        return self.exec_statement("DELETE FROM oauth_states WHERE expires_at < %s", (now,))

    def create_oauth_state(self, state, code_verifier, mode, username, created_at, expires_at):
        sql = """
          INSERT INTO oauth_states (state, code_verifier, mode, username, created_at, expires_at, used)
          VALUES (%s, %s, %s, %s, %s, %s, false)
        """
        return self.exec_statement(sql, (state, code_verifier, mode, username, created_at, expires_at))

    def consume_oauth_state(self, state, now):
        """Atomically mark a state used and return its row, or None if unknown, expired or already
        used. A single UPDATE ... RETURNING, so two concurrent callbacks cannot both win."""
        sql = """
          UPDATE oauth_states SET used = true
          WHERE state = %s AND used = false AND expires_at > %s
          RETURNING code_verifier, mode, username
        """
        res = self.exec_statement_fetch(sql, (state, now))
        if not res:
            return None
        return {"code_verifier": res[0][0], "mode": res[0][1], "username": res[0][2]}

    def get_leaderboard(self):
        sql = """
        SELECT submitter, COUNT(*) as count
        FROM bookshelf
        GROUP BY submitter
        ORDER BY count DESC;
        """
        results = self.exec_statement_fetch(sql)
        if not results:
            return []
        return [{"username": r[0], "spines": r[1]} for r in results]

    def get_books_by_submitter(self, submitter):
        sql = "select * from bookshelf where submitter = %s"
        res = self.exec_statement_fetch(sql, (submitter,))
        if not res:
            return False
        return [self.format_book_tuple(r) for r in res]

    def set_shelf_image_owner(self, filename, username, bookshelf_name):
        sql = "UPDATE shelf_images SET owner = %s, bookshelf_name = %s where filename = %s"
        return self.exec_statement(sql, (username, bookshelf_name, filename))

    def get_shelf_image_by_filename(self, filename):
        sql = "SELECT * FROM shelf_images WHERE filename = %s LIMIT 1"
        res = self.exec_statement_fetch(sql, (filename,))
        return self.format_shelf_image_tuple_list(res)[0]

    def get_shelf_images_by_owner(self, owner):
        sql = "SELECT * FROM shelf_images WHERE OWNER = %s"
        res = self.exec_statement_fetch(sql, (owner,))
        return self.format_shelf_image_tuple_list(res)

    def get_unfound_to_upload_by_owner(self, owner):
        sql = "SELECT * FROM unfound_to_upload WHERE owner = %s and uploaded = %s"
        res = self.exec_statement_fetch(sql, (owner, False))
        return self.format_unfound_to_upload_tuple_list(res)

    def mark_unfound_as_uploaded(self, book_id=None, hardcover_book_id=None):
        clause, params = self._id_match_clause(self._id_or_none(book_id), self._id_or_none(hardcover_book_id))
        if clause is None:
            return False
        sql = "UPDATE unfound_to_upload SET uploaded = %s WHERE " + clause
        return self.exec_statement(sql, (True, *params))

    def get_shelf_images_to_delete(self, longevity=1):
        allowedTimestamp = int(time.time()) - (longevity * 60 * 60 * 24)
        sql = """SELECT * FROM shelf_images
                  WHERE timestamp < %s::integer
                  AND owner IS NULL
        """
        res = self.exec_statement_fetch(sql, (allowedTimestamp,))
        return self.format_shelf_image_tuple_list(res)

    def delete_shelf_image(self, shelf_id):
        if not self.validate_uuid(shelf_id):
            return False
        sql = "DELETE FROM shelf_images WHERE shelf_id = %s"
        return self.exec_statement(sql, (shelf_id,))
