from PIL import Image, ImageDraw, ImageFont
from ImageOpener.PILImageOpener import PILImageOpener
from ImageOpener.S3ImageOpener import S3ImageOpener
from randCol import getRandColor
from random import random, choice
import feedparser
import copy
from dynamodb_dao import getBookBatch, getBook
import math
import colorsys

class Bookshelf:
  def __init__(self, imageOpener, bookshelfFileName, shelfWidthInches, shelfWidthPixels, shelfBottoms, shelfLeft):
    self.imageOpener = imageOpener
    self.shelves = []
    self.bookshelfImage = imageOpener.open(bookshelfFileName) 
    self.curShelf = copy.deepcopy(self.bookshelfImage)
    self.inchPixelRatio = shelfWidthPixels / shelfWidthInches
    self.shelfLength = shelfWidthPixels
    self.shelfBottoms = shelfBottoms #because shelves can have variable height, the array shelfBottoms tells us the number of shelves and their respective height in pixels
    self.shelfBottomIndex = 0
    self.shelfLeft = shelfLeft #constant, representing left edge of shelf
    self.bookLeft = shelfLeft #represents the left edge of the next book to be placed
    self.bookList = []

  #dimension must be delimited with x.
  def getBookHeightWidthLength(self, dimension):
    ds = [(float(s)) for s in (dimension.replace(" ", "").split('x'))]
    #longest dimension is book height
    h = max(ds)
    #shortest is book width
    w = min(ds)
    #middle is book length
    l = None
    for d in ds:
      if d == h: continue
      elif d == w: continue
      else: l = d
          
    #maybe it's a square book, so its height and width are the same. Either way, we don't really use l. so just set it so it isn't null
    if(l is None): l=h

    #there could be a case where this is incorrect, but that's a wacky book.
    return float(h), float(w), float(l)

  def genBookHeightWidthLength(self):
    #h 6-9
    h = random() * (9 - 6) + 6
    #w .5-2
    w = random() * (2 - .5) + .5
    #l 5-6
    l = random() * (6 - 5) + 5
    return h,w,l

  def getRandomFont(self, fontSize):
    fontList = [
      "example/LeagueGothic.ttf",
    ]
    return ImageFont.truetype(choice(fontList), fontSize)

  def getTextDimensions(self, text_string, font):
    ascent, descent = font.getmetrics()

    text_width = font.getmask(text_string).getbbox()[2]
    text_height = font.getmask(text_string).getbbox()[3] + descent

    return (text_width, text_height)

  def convertInchesToPixels(self, inches):
    return int(inches * self.inchPixelRatio) #at some point, i'll make this a class, and each class can be instantiated with different bookshelf types. These types will have different pixel to inch ratios. but for now this is fine. my only image is a 1/20 ratio

  def fillShelf(self, bookList):
    self.bookList = self.bookList + bookList
    for f in bookList:
      h,w,l = 0,0,0
      if(f["dimensions"]):
        h,w,l = self.getBookHeightWidthLength(f["dimensions"])
      else:
        h,w,l = self.genBookHeightWidthLength()
      h = self.convertInchesToPixels(h)
      w = self.convertInchesToPixels(w)
      bookRight = self.bookLeft + w

      if(bookRight > self.shelfLength): #move to next row
        self.bookLeft = self.shelfLeft
        bookRight = self.bookLeft + w
        if(self.shelfBottomIndex + 1 < len(self.shelfBottoms)):
          self.shelfBottomIndex += 1
        else: #move to next bookshelf
          self.shelfBottomIndex = 0
          self.shelves.append(self.curShelf)
          self.curShelf = copy.deepcopy(self.bookshelfImage)

      bookTop = self.shelfBottoms[self.shelfBottomIndex] - h

      if(f["fileName"]): #use provided file
        spine = self.imageOpener.open(f["fileName"])
        spine = spine.resize((w, h))
        self.curShelf.paste(spine, (self.bookLeft, bookTop))

      else: #draw our own cover rectangle
        newBook = Image.new("RGB", (h, w), getRandColor(.7))
        imDraw = ImageDraw.Draw(newBook)
        
        #okay so this only sometimes works. I don't know the proper solution at the moment.
        fontSize = 1 #purposefully small so we can upscale to appropriate fontsize
        randFont = self.getRandomFont(fontSize)
        while(self.getTextDimensions(f["title"], randFont)[0]+30 < w or self.getTextDimensions(f["title"], randFont)[1]+30 < h):
          randFont = self.getRandomFont(int(fontSize))
          fontSize += 1
        
        imDraw.text((15, 0), f["title"], (255,255,255), font=randFont)
        newBook = newBook.rotate(270, expand=True)
        self.curShelf.paste(newBook, (self.bookLeft, bookTop))

      self.bookLeft = bookRight
    
  def reorderShelf(self, sortMethod):
    orderedList = sortMethod(self.bookList)
    self.bookList = []
    self.shelves = []
    self.curShelf = copy.deepcopy(self.bookshelfImage)
    self.shelfBottomIndex = 0
    self.bookLeft = self.shelfLeft
    self.fillShelf(orderedList)

  def getFullShelf(self):
    if(len(self.shelves) > 0):
      self.shelves.append(self.curShelf)
      prevShelf = self.shelves[0]
      for i in range(1, len(self.shelves)):
        nextShelf = self.shelves[i]
        tempImage = Image.new('RGB', (prevShelf.width + nextShelf.width, prevShelf.height))
        tempImage.paste(prevShelf, (0,0))
        tempImage.paste(nextShelf, (prevShelf.width, 0))
        prevShelf = tempImage
      return prevShelf

    else:
      return self.curShelf
    
  def showShelf(self):
    self.getFullShelf().show()

  def saveShelf(self, saveLocation):
    self.getFullShelf().save(saveLocation)

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

def get_books_from_shelf(userid, shelfname):
  rss_url = "https://www.goodreads.com/review/list_rss/" + userid + "?shelf=" + shelfname
  parsed_rss = feedparser.parse(rss_url)
  books = []
  for entry in parsed_rss["entries"]:
    book = {"book_id" : entry["book_id"], 
            "title" : entry["title"], 
            "pubDate" : entry["book_published"],
            "author" : entry["author_name"],
            "isbn" : entry["isbn"],
            "isbn13" : convertISBNtoISBN13(entry["isbn"])
            }
    books.append(book)
  return books

def orderBooksByShelfOrder(books, batch):
  res = []
  batchCopy = copy.deepcopy(batch)
  for book in books:
    for e in batchCopy:
      found = None
      if book["book_id"] == e["book_id"]:
        found = e
        break
    if(found == None):
      print("didn't find " + book["title"])
    else:
      batchCopy.remove(found)
      res.append(found)
  return res

def colorStep (r,g,b, repetitions=1):
  #https://www.alanzucconi.com/2015/09/30/colour-sorting/
  lum = math.sqrt( .241 * r + .691 * g + .068 * b )
  h, s, v = colorsys.rgb_to_hsv(r,g,b)
  h2 = int(h * repetitions)
  lum2 = int(lum * repetitions)
  v2 = int(v * repetitions)
  if h2 % 2 == 1:
    v2 = repetitions - v2
    lum = repetitions - lum
  return (h2, lum, v2)

def orderBooksByAuthor(batch):
  pass

def orderBooksByColor(batch):
  batch.sort(key=lambda b : colorStep(int(b["domColor"][1:3], base=16),int(b["domColor"][3:5], base=16),int(b["domColor"][5:7], base=16),8))
  return batch

def orderBooksByGenre(batch):
  pass

def orderBooksByHeight(batch):
  byHeight = lambda b : max([float(s) for s in (b["dimensions"].replace(" ", "").split('x'))])
  batch.sort(key=byHeight)
  return batch

def orderBooksByPubDate(batch):
  byDate = lambda b : int(b["pubDate"]) if len(b["pubDate"]) > 0 else 3000 #if there's no pubdate, just put it at the end of the list
  batch.sort(key=byDate)
  return batch

def orderBooksByTitle(batch):
  byDate = lambda b : b["title"]
  batch.sort(key=byDate)
  return batch

def whichBooksFound(bookList, foundBooks):
  #return a list, the edited bookList which only contains the books not found in foundBooks
  unfound = []
  for b in bookList:
    found = False
    for f in foundBooks:
      if(b["title"] == f["title"]):
        found = True
        break
    if(not found):
      unfound.append(b)
  return unfound

def buildBookshelfFromGoodreadsShelf(userid, shelfname, sortMethod = None):
  books = get_books_from_shelf(userid, shelfname)
  batch = getBookBatch(books)
  sortedBooks = orderBooksByShelfOrder(books, batch)
  if(sortMethod != None):
    sortedBooks = sortMethod(sortedBooks)
  print(sortedBooks)
  # bookshelf = Bookshelf(S3ImageOpener, "bookshelf1.jpg", 35.5, 1688, [676, 1328, 2008, 2708, 3542], 75)
  # bookshelf.fillShelf(sortedBooks)
  # bookshelf.showShelf()

#example building bookshelf
# buildBookshelfFromGoodreadsShelf("24821860", "read")
# buildBookshelfFromGoodreadsShelf("119763485", "2021", orderBooksByPubDate)

def example():
  bookshelf = Bookshelf(PILImageOpener, "example/bookshelf1.jpg", 35.5, 1688, [676, 1328, 2008, 2708, 3542], 75)
  exampleBooks = [
    {"title" : "Slaughterhouse-Five", "fileName" : "example/slaughterhouse_five-9780812988529.jpg", "dimensions" : "5.3 x 0.6 x 8"},
    {"title" : "Alice Knott", "fileName" : "example/alice_knott-9780525535218.jpg", "dimensions" : "6.15x1.08x9.26"},
    {"title" : "Dark Matter", "fileName" : "example/dark_matter-9781101904220.jpg", "dimensions" : "6.35x1.2x9.5"},
  ]
  repeatNTimes = 1
  for i in range(repeatNTimes):
    bookshelf.fillShelf(exampleBooks)
  bookshelf.showShelf()
  bookshelf.saveShelf("exampleShelf.png")

def exampleAWS():
  bookshelf = Bookshelf(S3ImageOpener, "bookshelf1.jpg", 35.5, 1688, [676, 1328, 2008, 2708, 3542], 75)
  exampleBooks = [
    {"title" : "Slaughterhouse-Five", "fileName" : "slaughterhouse_five-9780440180296.png", "dimensions" : "5.3 x 0.6 x 8"},
    {"title" : "Alice Knott", "fileName" : "alice_knott-9780525535218.png", "dimensions" : "6.15x1.08x9.26"},
    {"title" : "Dark Matter", "fileName" : "dark_matter-9781101904220.png", "dimensions" : "6.35x1.2x9.5"},
  ]
  bookshelf.fillShelf(exampleBooks)
  bookshelf.showShelf()
  bookshelf.saveShelf("exampleShelf.png")

# example()