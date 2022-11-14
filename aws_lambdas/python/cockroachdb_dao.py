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
      owner STRING NULL
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
      timestamp INT NULL
    );
    """
    self.exec_statement(create_bookshelf_sql)

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
      timestamp INT
    );
    """
    self.exec_statement(create_shelf_bgs_table_sql)

  #TODO: test
  def add_shelf_bg(self, submitter, filename, width_inches, width_pixels, shelf_bottoms, shelf_left):
    self.create_shelf_bgs_table()
    sql = """
      INSERT INTO shelf_bgs
      (submitter, filename, width_inches, width_pixels, shelf_bottoms, shelf_left, timestamp)
      VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    return self.exec_statement(sql, (submitter, filename, width_inches, width_pixels, shelf_bottoms, shelf_left, str(int(time.time()))))

  def get_all_shelf_bgs(self):
    sql = "SELECT * FROM shelf_bgs"
    return self.exec_statement_fetch(sql)

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
    if(not visitor_tuple): return False
    visitor_tuple = visitor_tuple[0]
    return {
      "visitor_id" : visitor_tuple[0],
      "ip" : visitor_tuple[1],
      "os" : visitor_tuple[2],
      "browser" : visitor_tuple[3],
      "timestamp" : visitor_tuple[4],
      "num_visits" : visitor_tuple[5]
    }

  def update_visit_count(self, visitor_id, prev_visits):
    sql = "UPDATE visitors SET num_visits = %s, timestamp = %s WHERE visitor_id = %s"
    return self.exec_statement(sql, (str(prev_visits + 1), str(int(time.time())), visitor_id))

  def add_book(self, book):
    sql = """
          INSERT INTO bookshelf 
          (book_id, title, author, dimensions, fileName, genre, isbn, isbn13, pubDate, submitter, domColor, rating, timestamp) 
          VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
          RETURNING upload_id
          """
    res = self.exec_statement_fetch(sql, (book["book_id"], book["title"], book["authorName"], book["dimensions"], book["fileName"], book["genre"], book["isbn"], book["isbn13"], book["pubDate"], book["username"], book["domColor"], "0", str(int(time.time()))))
    u_id = res[0]
    if(type(u_id) == list): u_id = u_id[0]
    return {"upload_id" : u_id}

  def get_book_by(self, key, value):
    sql = "SELECT * FROM bookshelf WHERE " + key + " = %s"
    res_list = self.exec_statement_fetch(sql, (value,))
    if(len(res_list) > 0): 
      book_tuple = res_list[0] #only concerned with the first result. write get_bookS for multiple
      return self.format_book_tuple(book_tuple)
    return False

  def has_username_uploaded_book(self, username, book_id):
    sql = "SELECT * FROM bookshelf WHERE submitter = %s AND book_id = %s"
    res = self.exec_statement_fetch(sql, (username, book_id))
    if(len(res) > 0): return self.format_book_tuple(res[0])
    return False

  def get_book_batch(self, book_batch):
    sql = "SELECT * FROM bookshelf WHERE book_id IN ("
    percentS = ""
    for i in range(len(book_batch)):
      percentS += "%s"
      if(i != len(book_batch)-1): percentS += ", "
    sql += percentS + ") OR title IN (" + percentS + ")"

    book_ids_and_titles = []
    for b in book_batch:
      book_ids_and_titles.append(b["book_id"])
    for b in book_batch:
      book_ids_and_titles.append(b["title"])
    res = self.exec_statement_fetch(sql, tuple(book_ids_and_titles))
    book_list = []
    for r in res:
      book_list.append(self.format_book_tuple(r))
    return book_list

  def update_book_file_name(self, upload_id, fileName):
    sql = "UPDATE bookshelf SET fileName = %s WHERE upload_id = %s"
    return self.exec_statement(sql, (fileName, upload_id))
  
  def delete_book(self, upload_id):
    sql = "DELETE FROM bookshelf WHERE upload_id = %s"
    return self.exec_statement(sql, (upload_id,)) 

  def format_book_tuple(self, book_tuple):
    return {
      "upload_id" : book_tuple[0],
      "book_id" : book_tuple[1],
      "title" : book_tuple[2],
      "author" : book_tuple[3],
      "dimensions" : book_tuple[4],
      "domColor" : book_tuple[5],
      "fileName" : book_tuple[6],
      "genre" : book_tuple[7],
      "isbn" : book_tuple[8],
      "isbn13" : book_tuple[9],
      "pubDate" : book_tuple[10],
      "submitter" : book_tuple[11],
      "rating" : book_tuple[12],
      "flagged" : book_tuple[13]
    }

  def format_shelf_image_tuple(self, shelf_image_tuple):
    return {
      "shelf_id" : shelf_image_tuple[0],
      "filename" : shelf_image_tuple[1],
      "timestamp" : shelf_image_tuple[2],
      "owner" : shelf_image_tuple[3]
    }

  def format_shelf_image_tuple_list(self, si_list):
    if(type(si_list) is not list): return False
    si = []
    for r in si_list:
      si.append(self.format_shelf_image_tuple(r))
    return si

  def add_books(self, bookList):
    for book in bookList:
      #don't attempt to add books with duplicate filenames
      if(self.get_book_by("filename", book["fileName"])):
        continue
      self.add_book(book)

  #todo: dynamic function that updates all changed values in a book object.
  def update_book(self, book):
    if("upload_id" not in book.keys()): return False
    return False

  def update_book_col(self, upload_id, col, value):
    sql = "UPDATE bookshelf set " + col + " = %s WHERE upload_id = %s"
    return self.exec_statement(sql, (value, upload_id))

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

  def update_user_col(self, username, col, val):
    sql = "UPDATE bookshelf_users SET " + col + " = %s WHERE username = %s"
    return self.exec_statement(sql, (val, username))

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
      "banned" : res[7],
      "goodreads_id" : res[8]
    }

  def get_user(self, username):
    return self.get_user_by("username", username)

  def update_user_authtoken(self, username, authtoken, expiry):
    sql = "UPDATE bookshelf_users SET authtoken = %s, expiry = %s WHERE username = %s"
    if(self.exec_statement(sql, (authtoken, expiry, username))):
      return self.get_user(username)
    return False

  def validate_username_authtoken(self, username, authtoken):
    user = self.get_user(username)
    if(not user): 
      return False
    if(authtoken != user["authtoken"]):
      return False
    if(int(time.time()) > int(user["expiry"])):
      return False
    return True
  
  def get_banned_ips(self):
    sql = "SELECT ip FROM bookshelf_users WHERE banned = 'TRUE'"
    #execute the sql now
    #return the results
    pass

  def get_leaderboard(self):
    sql = """
    SELECT submitter, COUNT(*) as count 
    FROM bookshelf 
    GROUP BY submitter 
    ORDER BY count DESC;
    """
    results = self.exec_statement_fetch(sql)
    leaderboard = []
    for r in results:
      leaderboard.append({"username" : r[0], "spines" : r[1]})
    return leaderboard

  def get_books_by_submitter(self, submitter):
    sql = "select * from bookshelf where submitter = %s"
    res = self.exec_statement_fetch(sql, (submitter,))
    if(not res): return False
    books = []
    for r in res:
      books.append(self.format_book_tuple(r))
    return books

  def set_shelf_image_owner(self, filename, username):
    sql = "UPDATE shelf_images SET owner = %s where filename = %s"
    return self.exec_statement(sql, (username, filename))

  def get_shelf_images_by_owner(self, owner):
    sql = "SELECT * FROM shelf_images WHERE OWNER = %s"
    res = self.exec_statement_fetch(sql, (owner,))
    return self.format_shelf_image_tuple_list(res)

  #longevity corresponds to the number of days the shelf image is allowed to exist on the server. default is one day
  def get_shelf_images_to_delete(self, longevity=1):
    allowedTimestamp = int(time.time()) - (longevity * 60 * 60 * 24)
    sql = """SELECT * FROM shelf_images
              WHERE timestamp < %s::integer
              AND owner IS NULL
    """
    res = self.exec_statement_fetch(sql, (allowedTimestamp,))
    return self.format_shelf_image_tuple_list(res)

  def delete_shelf_image(self, shelf_id):
    sql = "DELETE FROM shelf_images WHERE shelf_id = %s"
    return self.exec_statement(sql, (shelf_id,))

  def flag_image(self, upload_id):
    pass

  def upvote_image(self, upload_id):
    pass

  def downvote_image(self, upload_id):
    pass

# aws lambda update-function-configuration --function-name lambda-function-name --environment "Variables={DATABASE_URL=url}"
