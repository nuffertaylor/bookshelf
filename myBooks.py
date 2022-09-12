#ignore this file
from colorthief import ColorThief
import feedparser
from aws_lambdas.dynamodb_dao import putBook
from s3_dao import upload_file
from get_books import scrape_books_from_shelf

files2021 = [
  {"fileDir" : "images/spines/slaughterhouse_five-9780440180296.png", "dimensions" : "5.3 x 0.6 x 8", "goodreadsID" : "168646"},
  {"fileDir" : "images/spines/alice_knott-9780525535218.png", "dimensions" : "6.15x1.08x9.26", "goodreadsID" : "50935234"},
  {"fileDir" : "images/spines/dark_matter-9781101904220.png", "dimensions" : "6.35x1.2x9.5", "goodreadsID" : "27833670"},
  {"fileDir" : "images/spines/uzumaki-9781421561325.png", "dimensions" : "5.75 x 1.9 x 8.25", "goodreadsID" : "17837762"},
  {"fileDir" : "images/spines/pirate_cinema-9780765329080.png", "dimensions" : "5.81 x 1.29 x 8.7", "goodreadsID" : "13539171"},
  {"fileDir" : "images/spines/masseffect_revelation-9780345498168.jpg", "dimensions" : "4.14 x 0.83 x 6.84", "goodreadsID" : "231599"},
  {"fileDir" : "images/spines/we_were_liars-9780385741279.png", "dimensions" : "5.5 x 0.84 x 8.25", "goodreadsID" : "16143347"},
  {"fileDir" : "images/spines/im_thinking_of_ending_things-9781501126949.jpeg", "dimensions" : "5.5 x 0.7 x 8.38", "goodreadsID" : "40605223"},
  {"fileDir" : "images/spines/rich_dad_poor_dad-9781612680170.png", "dimensions" : "6 x 1 x 8.75", "goodreadsID" : "69571"},
  {"fileDir" : "images/spines/horus_rising-9781844162949.png", "dimensions" : "4.1 x 1 x 6.75", "goodreadsID" : "625603"},
  {"title" : "Quantum Garden", "fileDir" : "images/spines/quantum_garden-9781781085714.png", "dimensions" : "5.06 x 1.1 x 7.81", "goodreadsID" : "43822104"},
  {"fileDir" : "images/spines/false_gods-9781844163700.png", "dimensions" : "4.19 x 1.1 x 6.75", "goodreadsID" : "381817"},
  {"fileDir" : "images/spines/so_you_want_to_talk_about_race-9781580058827.png", "dimensions" : "5.8 x 0.9 x 8.45", "goodreadsID" : "41717572"},
  {"fileDir" : "images/spines/thousand_splendid_suns-9781594489501.png", "dimensions" : "6.32 x 1.26 x 9.29", "goodreadsID" : "128029"},
  {"fileDir" : "images/spines/mysteries_of_the_first_instant-9781689226691.png", "dimensions" : "6 x 0.87 x 9", "goodreadsID" : "57584081"},
  {"title" : "Business Ethics Field Guide", "fileDir" : "images/spines/business_ethics_field_guide-9780991091034.JPG", "dimensions" : "7x.7x8.2", "goodreadsID" : "32320324"},
  {"fileDir" : "images/spines/star_maker.png", "dimensions" : "6x1.4x8", "goodreadsID" : "525304"},
  {"fileDir" : "images/spines/julius_caesar-9780812035735.png", "dimensions" : "5 x 0.6 x 7.25", "goodreadsID" : "758621"},
  {"fileDir" : "images/spines/galaxy_in_flames-9781844163939.png", "dimensions" : "4.19 x 1.1 x 6.75", "goodreadsID" : "815091"},
  {"fileDir" : "images/spines/dorian_gray.png", "dimensions" : "6 x 1.35 x 7.5", "goodreadsID" : "5297"},
  {"fileDir" : "images/spines/spire.png", "dimensions" : "6 x 1.2 x 7", "goodreadsID" : "1041865"},
  {"fileDir" : "images/spines/sphere-9780062428868.png", "dimensions" : "1 x 5.2 x 7.9", "goodreadsID" : "455373"},
  {"fileDir" : "images/spines/klee_wyck-9781553650270.png", "dimensions" : "5.5 x 0.95 x 8.25", "goodreadsID" : "149181"},
  {"fileDir" : "images/spines/astrophysics_for_people_in_a_hurry-9780393609394.png", "dimensions" : "7.3 x 4.8 x 0.9", "goodreadsID" : "32191710"},
  {"title" : "Voyage to Kazohinia", "fileDir" : "images/spines/voyage_to_kazohinia-9780982578124.png", "dimensions" : "5.5 x 0.76 x 8.4", "goodreadsID" : "13330442"},
  {"fileDir" : "images/spines/demon_slayer_one-9781974700523.png", "dimensions" : "5 x 0.7 x 7.5", "goodreadsID" : "36538793"},
  {"title" : "If I Did It", "fileDir" : "images/spines/if_i_did_it-9780825305887.jpg", "dimensions" : "5.5 x 0.89 x 8.2", "goodreadsID" : "1797248"},
  {"fileDir" : "images/spines/handmaids_tale-9780385490818.png", "dimensions" : "5.21 x 0.7 x 7.94", "goodreadsID" : "38447"},
  {"fileDir" : "images/spines/i_am_watching_you-9781542046596.png", "dimensions" : "5.5 x 1 x 8.25", "goodreadsID" : "34914739"},
  {"fileDir" : "images/spines/flight_of_eisenstein-9781844164592.png", "dimensions" : "4.19 x 1 x 6.75", "goodreadsID" : "80155"},
  {"fileDir" : "images/spines/macbeth-9781586638467.jpg", "dimensions" : "5.2 x 0.6 x 7.4", "goodreadsID" : "17247"},
  {"fileDir" : "images/spines/sea_change-9781616963316.jpg", "dimensions" : "5 x .7 x 8", "goodreadsID" : "51600140"},
  {"fileDir" : "images/spines/innocence-9780553808032.png", "dimensions" : "6.4 x 1 x 9", "goodreadsID" : "17797381"},
  {"fileDir" : "images/spines/anthropocene_reviewed-9780525555216.png", "dimensions" : "5.8 x 1.09 x 8.55", "goodreadsID" : "55145261"},
  {"fileDir" : "images/spines/where_the_crawdads_sing-9780735219113.png", "dimensions" : "6.4 x 1.5 x 9.2", "goodreadsID" : "36809135"},
  {"fileDir" : "images/spines/annihilation-9780374104092.png", "dimensions" : "6.31 x 0.85 x 7.95", "goodreadsID" : "17934530"},
  {"fileDir" : "images/spines/merchant_of_venice-9780812035704.png", "dimensions" : "5 x 0.6 x 7.25", "goodreadsID" : "24133"},
  {"fileDir" : "images/spines/valis-9780552118415.png", "dimensions" : "4.25 x 6.87 x .6", "goodreadsID" : "22608"},
  {"fileDir" : "images/spines/tale_of_two_cities-9781774021705.jpg", "dimensions" : "8.75 x 4.88 x 1.38", "goodreadsID" : "54620797"},
  {"fileDir" : "images/spines/when_you_trap_a_tiger-9781524715700.jpg", "dimensions" : "5.88 x 0.99 x 8.56", "goodreadsID" : "44901877"},
  {"title" : "Red Mars", "fileDir" : "images/spines/red_mars-9780553560732.png", "dimensions" : "9.1 x 6.3 x 1.7", "goodreadsID" : "77507"},
  {"fileDir" : "images/spines/symposium-9780143037538.jpg", "dimensions" : "4.36 x 0.34 x 7.11", "goodreadsID" : "96987"},
  {"fileDir" : "images/spines/project_hail_mary-9780593135204.png", "dimensions" : "6.33 x 1.53 x 9.57", "goodreadsID" : "54493401"},
  {"title" : "A Light in the Attic", "isbn" : "9780060513061", "fileDir" : "images/spines/a_light_in_the_attic-9780060513061.png", "dimensions" : "10.1 x 1.11 x 11.11", "genre" : "poetry", "pubDate" : "1981", "goodreadsID" : "30118"},
  {"fileDir" : "images/spines/masseffect_ascension-9780345498526.jpg", "dimensions" : "4.25 x 0.9 x 6.85", "goodreadsID" : "2729221"},
  {"fileDir" : "images/spines/doctor_faustus-9780199537068.jpg", "dimensions" : "7.5 x 1.4 x 5", "goodreadsID" : "3141122"},
  {"fileDir" : "images/spines/vacation_guide_to_the_solar_system-9780143129776.png", "dimensions" : "5.81 x 0.71 x 7.81", "goodreadsID" : "32968553"},
  {"fileDir" : "images/spines/old_man_and_the_sea-9780684830490.jpg", "dimensions" : "6.13 x 1 x 7", "goodreadsID" : "2165"},
  {"fileDir" : "images/spines/immune-9780593241318.png", "dimensions" : "7.32 x 1.42 x 9.29", "goodreadsID" : "57423646"},
  {"fileDir" : "images/spines/flirtasaurus-9798654172310.png", "dimensions" : "5.5 x 0.65 x 8.5", "goodreadsID" : "53939957"},
  {"fileDir" : "images/spines/silence-9781250082275.png", "dimensions" : "5.44 x 0.72 x 8.25", "goodreadsID" : "25663542"},
  {"fileDir" : "images/spines/awakening-9780451524485.png", "dimensions" : "4.25 x 0.91 x 6.81", "goodreadsID" : "856250"},
]

files2022 = [
  {"fileDir" : "images/spines/far_from_the_light_of_heaven-9780759557918.png", "dimensions" : "5.65x1.4x8.25", "goodreadsID" : "57007657"},
  {"fileDir" : "images/spines/bakemonogatari_one-9781942993889.png", "dimensions" : "5.49x0.64x7.5", "goodreadsID" : "29744032"},
  {"fileDir" : "images/spines/frankenstein-9781926444314.png", "dimensions" : "8.82x4.44x1.32", "goodreadsID" : "43170350"},
  {"fileDir" : "images/spines/man_with_no_shadow-9798638838638.png", "dimensions" : "6x0.53x9", "goodreadsID" : "53897456"},
  {"fileDir" : "images/spines/at_earths_core-9780809599783.jpeg", "dimensions" : "5x0.91x8", "goodreadsID" : "215950"},
  {"fileDir" : "images/spines/demon_slayer_two-9781974700530.png", "dimensions" : "5x0.7x7.5", "goodreadsID" : "38926432"},
  {"fileDir" : "images/spines/ben_franklin-9781609425111.png", "dimensions" : "6x1.08x8", "goodreadsID" : "52309"},
  {"fileDir" : "images/spines/pillars_of_the_earth-9780330450867.png", "dimensions" : "4.41x1.81x7.09", "goodreadsID" : "1254150"},
  {"fileDir" : "images/spines/sleeping_giants-9781101886717.png", "dimensions" : "5.5x0.7x8.3", "goodreadsID" : "25733990"},
  {"fileDir" : "images/spines/midnight_library-9780525559474.png", "dimensions" : "8.02x0.86x10.8", "goodreadsID" : "52578297"},
  {"fileDir" : "images/spines/my_man_jeeves-9781585678754.png", "dimensions" : "5.4 x 1.05 x 7.5", "goodreadsID" : "200572"},
  # {"title": "Zombie Fallout 2", "fileDir" : "", "dimensions" : ".8 x 5.5 x 8.5", "goodreadsID" : "15756383"},
]

def rgb_to_hex(rgb : tuple):
  return "#%02x%02x%02x" % rgb

def calcDomRGB(source):
  cf = ColorThief(source)
  dominant = cf.get_color(quality=1)
  return rgb_to_hex(dominant)

# for x in files2021:
#   if(len(x["fileDir"]) > 0):
#     res = calcMeanRGB(x["fileDir"])
#     print(res)

def check_digit_13(isbn):
  assert len(isbn) == 12
  sum = 0
  for i in range(len(isbn)):
    c = int(isbn[i])
    if i % 2: w = 3
    else: w = 1
    sum += w * c
  r = 10 - (sum % 10)
  if r == 10: return '0'
  else: return str(r)

def convertISBNtoISBN13(isbn):
  if(len(isbn) == 13): return isbn
  if(len(isbn) != 10 or not isbn.isdigit()): return None
  # assert len(isbn) == 10
  prefix = "978" + isbn[:-1]
  check = check_digit_13(prefix)
  return prefix + check

def removeDirPrefix(file):
  f = file.split('/')
  return f[len(f)-1]

def findMatchingData(grid, arr):
  for x in arr:
    if grid == x["goodreadsID"]:
      return x
  return False

def get_books_from_shelf(userid, shelfname, submitter = ""):
  rss_url = "https://www.goodreads.com/review/list_rss/" + userid + "?shelf=" + shelfname
  parsed_rss = feedparser.parse(rss_url)
  print(parsed_rss["entries"][1].keys())

  for i, entry in enumerate(parsed_rss["entries"]):
    title = entry["title"]
    grid = entry["book_id"]
    pubDate = entry["book_published"]
    author = entry["author_name"]
    isbn = entry["isbn"]
    isbn13 = convertISBNtoISBN13(isbn)
    addtl = findMatchingData(entry["book_id"], files2022)
    if(addtl):
      fileName = removeDirPrefix(addtl["fileDir"])
      dimensions = addtl["dimensions"]
      domColor = calcDomRGB(addtl["fileDir"])

    #   #aws functions
    #   upload_file(addtl["fileDir"])
      putBook(title, grid, pubDate, author, isbn, isbn13, fileName, dimensions, domColor, submitter=submitter)

def getBooksFromShelf(userid, shelfname):
  bookDetails = scrape_books_from_shelf(userid, shelfname)
  numFound = 0
  for i, book in enumerate(bookDetails):
    print(book)
    if(book["isbn13"] == "isbn not found"):
      pass
    res = findMatchingData(book["isbn13"], files2022)
    if(res):
      numFound += 1
      book["fileDir"] = res["fileDir"]
      book["dimensions"] = res["dimensions"]
      bookDetails[i] = book
    else:
      print("{" + book["isbn13"] + "}" +" is an invalid isbn for : " + book["book_title"])
  print(numFound)
  return bookDetails


(get_books_from_shelf("119763485", "2022", "jonas"))

# buildBookshelfFromGoodreadsShelf("119763485", "2021")

def create_filename(title, book_id, extension):
  t = ''.join(ch for ch in title if ch.isalnum())
  return t + "-" + book_id + "." + extension

def get_ext_from_b64(b64str):
  a = b64str.split(';')[0]
  b = a.split('/')[1]
  return b

# print(create_filename("this is a cool book! #3", "444414", "png"))
# print(get_ext_from_b64("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAgEAAAHbCAYAAABSq0m1AAB4f0lEQVR42uydd5hcxZX2u6cn55xzzjnnqJmRZjRCAZRzRjkHUEAIoQQCFJCEkJAEIuckokAgBAvGBAfw+rP3+7xe767D7np3nX2+e+7M2CDNSBOqbt97+z3P8/tj1/aou29VvedWnXqPxYJAIBAIBAKBQCAMG84KfgqRCskKeQqVCs0KXQqTFeYpLFfYpLBT4W6FYwrHFe5RuFNhq8JahSUKcxQmKYxRaFWoUShWyFJIUAjv+Tdd8PMjEAgEAjH8cFKIVqhWmKpwi8IDCs8onFd4T"))
