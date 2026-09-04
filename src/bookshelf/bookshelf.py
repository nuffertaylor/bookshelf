import pathlib
from PIL import Image, ImageDraw, ImageFont
from bookshelf.image_opener.pil_image_opener import PILImageOpener
from bookshelf.image_opener.s3_image_opener import S3ImageOpener
from bookshelf.rand_col import getRandColor
from random import random, choice
import feedparser
import copy
import math
import colorsys

_FONT_PATH = pathlib.Path(__file__).parent.parent.parent / "example" / "LeagueGothic.ttf"


class Bookshelf:
    def __init__(self, imageOpener, bookshelfFileName, shelfWidthInches, shelfWidthPixels, shelfBottoms, shelfLeft):
        self.imageOpener = imageOpener
        self.shelves = []
        self.bookshelfImage = imageOpener.open(bookshelfFileName)
        self.curShelf = copy.deepcopy(self.bookshelfImage)
        self.inchPixelRatio = shelfWidthPixels / shelfWidthInches
        self.shelfLength = shelfWidthPixels
        self.shelfBottoms = shelfBottoms
        self.shelfBottomIndex = 0
        self.shelfLeft = shelfLeft
        self.bookLeft = shelfLeft
        self.bookList = []

    def getBookHeightWidthLength(self, dimension):
        ds = [(float(s)) for s in (dimension.replace(" ", "").split('x'))]
        h = max(ds)
        w = min(ds)
        l = None
        for d in ds:
            if d == h:
                continue
            elif d == w:
                continue
            else:
                l = d
        if l is None:
            l = h
        return float(h), float(w), float(l)

    def genBookHeightWidthLength(self):
        h = random() * (9 - 6) + 6
        w = random() * (2 - .5) + .5
        l = random() * (6 - 5) + 5
        return h, w, l

    def getRandomFont(self, fontSize):
        fontList = [str(_FONT_PATH)]
        return ImageFont.truetype(choice(fontList), fontSize)

    def getTextDimensions(self, text_string, font):
        ascent, descent = font.getmetrics()
        text_width = font.getmask(text_string).getbbox()[2]
        text_height = font.getmask(text_string).getbbox()[3] + descent
        return (text_width, text_height)

    def convertInchesToPixels(self, inches):
        return int(inches * self.inchPixelRatio)

    def fillShelf(self, bookList):
        self.bookList = self.bookList + bookList
        for f in bookList:
            h, w, l = 0, 0, 0
            if f["dimensions"]:
                h, w, l = self.getBookHeightWidthLength(f["dimensions"])
            else:
                h, w, l = self.genBookHeightWidthLength()
            h = self.convertInchesToPixels(h)
            w = self.convertInchesToPixels(w)
            bookRight = self.bookLeft + w

            if bookRight > self.shelfLength:
                self.bookLeft = self.shelfLeft
                bookRight = self.bookLeft + w
                if self.shelfBottomIndex + 1 < len(self.shelfBottoms):
                    self.shelfBottomIndex += 1
                else:
                    self.shelfBottomIndex = 0
                    self.shelves.append(self.curShelf)
                    self.curShelf = copy.deepcopy(self.bookshelfImage)

            bookTop = self.shelfBottoms[self.shelfBottomIndex] - h

            if f["fileName"]:
                spine = self.imageOpener.open(f["fileName"])
                spine = spine.resize((w, h))
                self.curShelf.paste(spine, (self.bookLeft, bookTop))
            else:
                newBook = Image.new("RGB", (h, w), getRandColor(.7))
                imDraw = ImageDraw.Draw(newBook)

                fontSize = 1
                randFont = self.getRandomFont(fontSize)
                while self.getTextDimensions(f["title"], randFont)[0] + 30 < w or self.getTextDimensions(f["title"], randFont)[1] + 30 < h:
                    randFont = self.getRandomFont(int(fontSize))
                    fontSize += 1

                imDraw.text((15, 0), f["title"], (255, 255, 255), font=randFont)
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
        if len(self.shelves) > 0:
            self.shelves.append(self.curShelf)
            prevShelf = self.shelves[0]
            for i in range(1, len(self.shelves)):
                nextShelf = self.shelves[i]
                tempImage = Image.new('RGB', (prevShelf.width + nextShelf.width, prevShelf.height))
                tempImage.paste(prevShelf, (0, 0))
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
    total = 0
    for i in range(len(isbn)):
        c = int(isbn[i])
        w = 3 if i % 2 else 1
        total += w * c
    r = 10 - (total % 10)
    if r == 10:
        return '0'
    else:
        return str(r)


def convertISBNtoISBN13(isbn):
    if len(isbn) == 13:
        return isbn
    if len(isbn) != 10 or not isbn.isdigit():
        return None
    prefix = "978" + isbn[:-1]
    check = check_digit_13(prefix)
    return prefix + check


def colorStep(r, g, b, repetitions=1):
    lum = math.sqrt(.241 * r + .691 * g + .068 * b)
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
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
    batch.sort(key=lambda b: colorStep(int(b["domColor"][1:3], base=16), int(b["domColor"][3:5], base=16), int(b["domColor"][5:7], base=16), 8))
    return batch


def orderBooksByGenre(batch):
    pass


def orderBooksByHeight(batch):
    byHeight = lambda b: max([float(s) for s in (b["dimensions"].replace(" ", "").split('x'))])
    batch.sort(key=byHeight)
    return batch


def orderBooksByPubDate(batch):
    byDate = lambda b: int(b["pubDate"]) if len(b["pubDate"]) > 0 else 3000
    batch.sort(key=byDate)
    return batch


def orderBooksByTitle(batch):
    byDate = lambda b: b["title"]
    batch.sort(key=byDate)
    return batch


def whichBooksFound(bookList, foundBooks):
    unfound = []
    for b in bookList:
        found = False
        for f in foundBooks:
            if b["title"] == f["title"]:
                found = True
                break
        if not found:
            unfound.append(b)
    return unfound
