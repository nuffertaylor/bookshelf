from PIL import Image, ImageDraw, ImageFont
from randCol import getRandColor
from random import random, choice

class Bookshelf:
  def __init__(self, bookshelfImageDir, shelfWidthInches, shelfWidthPixels, shelfBottoms, shelfLeft):
    self.shelves = []
    self.bookshelfImageDir = bookshelfImageDir
    self.curShelf = Image.open(bookshelfImageDir)
    self.inchPixelRatio = shelfWidthPixels / shelfWidthInches
    self.shelfLength = shelfWidthPixels
    self.shelfBottoms = shelfBottoms #because shelves can have variable height, the array shelfBottoms tells us the number of shelves and their respective height in pixels
    self.shelfBottomIndex = 0
    self.shelfLeft = shelfLeft #constant, representing left edge of shelf
    self.bookLeft = shelfLeft #represents the left edge of the next book to be placed

  #dimension must be delimited with x.
  def getBookHeightWidthLength(self, dimension):
    dimension = dimension.lower()
    dimension = dimension.replace(" ", "")
    ds = dimension.split('x')
    #longest dimension is book height
    h = ds[0]
    for d in ds: 
      if(d > h): h = d

    #shortest is book width
    w = ds[0]
    for d in ds: 
      if(d < w): w = d
    #middle is book length
    l = None
    for d in ds:
      if d == h: continue
      elif d == w: continue
      else: l = d

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

  def fillBookshelf(self, bookList):
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
          self.curShelf = Image.open(self.bookshelfImageDir)

      bookTop = self.shelfBottoms[self.shelfBottomIndex] - h

      if(f["fileDir"]): #use provided file
        spine = Image.open(f["fileDir"])
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

def example():
  bookshelf = Bookshelf("example/bookshelf1.jpg", 35.5, 1688, [676, 1328, 2008, 2708, 3542], 75)
  exampleBooks = [
    {"title" : "Slaughterhouse-Five", "fileDir" : "example/slaughterhouse_five-9780812988529.jpg", "dimensions" : "5.3 x 0.6 x 8"},
    {"title" : "Alice Knott", "fileDir" : "example/alice_knott-9780525535218.jpg", "dimensions" : "6.15x1.08x9.26"},
    {"title" : "Dark Matter", "fileDir" : "example/dark_matter-9781101904220.jpg", "dimensions" : "6.35x1.2x9.5"},
  ]
  repeatNTimes = 1
  for i in range(repeatNTimes):
    bookshelf.fillBookshelf(exampleBooks)
  bookshelf.showShelf()
  bookshelf.saveShelf("exampleShelf.png")

example()