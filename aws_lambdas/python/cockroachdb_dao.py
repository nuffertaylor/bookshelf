import psycopg2
import time

class CockroachDAO:
  def __init__(self, db_url):
    self.conn = psycopg2.connect(db_url, sslrootcert="./root.crt")

  def exec_statement(self, stmt, args=None):
    try:
      with self.conn.cursor() as cur:
        if(args != None):
          cur.execute(stmt, args)
        else:
          cur.execute(stmt)
        self.conn.commit()
        return True
    except Exception as ex:
      template = "An exception of type {0} occurred. Arguments:\n{1!r}"
      message = template.format(type(ex).__name__, ex.args)
      failed_sql = cur.mogrify(stmt, args)
      print(message)
      print("Failed query: \n" + failed_sql)
      return False

  def exec_statement_fetch(self, stmt, args=None):
    try:
      with self.conn.cursor() as cur:
        if(args != None):
          cur.execute(stmt, args)
        else:
          cur.execute(stmt)
        self.conn.commit()
        return cur.fetchall()
    except Exception as ex:
      template = "An exception of type {0} occurred. Arguments:\n{1!r}"
      message = template.format(type(ex).__name__, ex.args)
      failed_sql = cur.mogrify(stmt, args)
      print(message)
      print("Failed query: \n" + failed_sql)
      return False


  def create_bookshelf_users_table(self):
    create_bookshelf_users_sql = """
    CREATE TABLE IF NOT EXISTS bookshelf_users (
      username VARCHAR ( 50 ) PRIMARY KEY,
      hashedPassword VARCHAR ( 255 ) NOT NULL,
      email VARCHAR ( 255 ) UNIQUE NOT NULL,
      authtoken VARCHAR ( 100 ) NOT NULL,
      expiry INT NOT NULL,
      salt VARCHAR ( 100 ) NOT NULL,
      ip VARCHAR ( 24 ),
      banned BOOLEAN NOT NULL
    );
    """
    self.exec_statement(create_bookshelf_users_sql)

  def create_shelf_image_table(self):
    create_shelf_image_sql = """
    CREATE TABLE IF NOT EXISTS shelf_images (
      shelf_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      filename STRING UNIQUE NOT NULL,
      timestamp INT NOT NULL
    );
    """
    self.exec_statement(create_shelf_image_sql)

  def create_bookshelf_table(self):
    create_bookshelf_sql = """
    CREATE TABLE IF NOT EXISTS bookshelf (
      upload_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      book_id INT NOT NULL,
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
      authorGender STRING NULL,
      country STRING NULL,
      language STRING NULL
    );
    """
    self.exec_statement(create_bookshelf_sql)

  def add_book(self, book):
    sql = 'INSERT INTO bookshelf (book_id, title, author, dimensions, domColor, fileName, genre, isbn, isbn13, pubDate, submitter, rating) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'
    return self.exec_statement(sql, (book["book_id"], book["title"], book["authorName"], book["dimensions"], book["domColor"], book["fileName"], book["genre"], book["isbn"], book["isbn13"], book["pubDate"], book["username"], "0"))

  def get_book_by(self, key, value):
    sql = "SELECT * FROM bookshelf WHERE " + key + " = %s"
    return self.exec_statement_fetch(sql, (value,))

  def add_books(self, bookList):
    for book in bookList:
      #don't attempt to add books with duplicate filenames
      if(self.get_book_by("filename", book["fileName"])):
        continue
      self.add_book(book)

  def add_shelf_image(self, filename):
    sql = "INSERT INTO shelf_images (filename, timestamp) VALUES (%s, %s)"
    self.exec_statement(sql, (filename, str(int(time.time()))))

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
    #check their ip address and ban any other users with the same ip
    self.exec_statement(sql, (username,))

  def get_user_by(self, key, value):
    sql = "SELECT * FROM bookshelf_users WHERE " + key + " = %s"
    res = self.exec_statement_fetch(sql, (value,))
    if(not res): return False
    res = res[0]
    return {
      "username" : res[0],
      "hashedPassword" : res[1],
      "email" : res[2],
      "authtoken" : res[3],
      "expiry" : res[4],
      "salt" : res[5],
      "ip" : res[6],
      "banned" : res[7]
    }

  def get_user(self, username):
    return self.get_user_by("username", username)

  def update_user_authtoken(self, username, authtoken, expiry):
    sql = "UPDATE bookshelf_users SET authtoken = %s, expiry = %s WHERE username = %s"
    return self.exec_statement(sql, (authtoken, expiry, username))
  
  def get_banned_ips(self):
    sql = "SELECT ip FROM bookshelf_users WHERE banned = 'TRUE'"
    #execute the sql now
    #return the results
    pass

  def get_leaderboard(self):
    pass

  def flag_image(self, upload_id):
    pass

  def upvote_image(self, upload_id):
    pass

  def downvote_image(self, upload_id):
    pass

# aws lambda update-function-configuration --function-name lambda-function-name --environment "Variables={DATABASE_URL=url}"
