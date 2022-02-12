from lib2to3.pytree import convert
from random import random
from PIL import Image, ImageDraw, ImageFont
from randCol import getRandColor

files2021 = [
  {"fileDir" : "images/spines/slaughterhouse_five-9780812988529.png", "dimensions" : "5.3 x 0.6 x 8"},
  {"fileDir" : "images/spines/alice_knott-9780525535218.png", "dimensions" : "6.15x1.08x9.26"},
  {"fileDir" : "images/spines/dark_matter-9781101904220.png", "dimensions" : "6.35x1.2x9.5"},
  {"fileDir" : "images/spines/uzumaki-9781421561325.png", "dimensions" : "5.75 x 1.9 x 8.25"},
  {"fileDir" : "images/spines/pirate_cinema-9780765329080.png", "dimensions" : "5.81 x 1.29 x 8.7"},
  {"fileDir" : "images/spines/masseffect_revelation-9780345498168.jpg", "dimensions" : "4.14 x 0.83 x 6.84"},
  {"fileDir" : "images/spines/we_were_liars-9780385741279.png", "dimensions" : "5.5 x 0.84 x 8.25"},
  {"fileDir" : "images/spines/im_thinking_of_ending_things-9781501126949.jpeg", "dimensions" : "5.5 x 0.7 x 8.38"},
  {"fileDir" : "images/spines/rich_dad_poor_dad-9781612680170.png", "dimensions" : "6 x 1 x 8.75"},
  {"fileDir" : "images/spines/horus_rising-9781844162949.png", "dimensions" : "4.1 x 1 x 6.75"},
  #quantum garden
  {"title" : "Quantum Garden", "fileDir" : "", "dimensions" : ""},
  {"fileDir" : "images/spines/false_gods-9781844163700.png", "dimensions" : "4.19 x 1.1 x 6.75"},
  {"fileDir" : "images/spines/so_you_want_to_talk_about_race-9781580058827.png", "dimensions" : "5.8 x 0.9 x 8.45"},
  {"fileDir" : "images/spines/thousand_splendid_suns-9781594489501.png", "dimensions" : "6.32 x 1.26 x 9.29"},
  {"fileDir" : "images/spines/mysteries_of_the_first_instant-9781689226691.png", "dimensions" : "6 x 0.87 x 9"},
  #business ethics field guide
  {"title" : "Business Ethics Field Guide", "fileDir" : "", "dimensions" : ""},
  {"fileDir" : "images/spines/star_maker.png", "dimensions" : "6x1.4x8"},
  {"fileDir" : "images/spines/julius_caesar-9780812035735.png", "dimensions" : "5 x 0.6 x 7.25"},
  {"fileDir" : "images/spines/galaxy_in_flames-9781844163939.png", "dimensions" : "4.19 x 1.1 x 6.75"},
  {"fileDir" : "images/spines/dorian_gray.png", "dimensions" : "6 x 1.35 x 7.5"},
  {"fileDir" : "images/spines/spire.png", "dimensions" : "6 x 1.2 x 7"},
  {"fileDir" : "images/spines/sphere-9780062428868.png", "dimensions" : "1 x 5.2 x 7.9"},
  {"fileDir" : "images/spines/klee_wyck-9781553650270.png", "dimensions" : "5.5 x 0.95 x 8.25"},
  {"fileDir" : "images/spines/astrophysics_for_people_in_a_hurry-9780393609394.png", "dimensions" : "7.3 x 4.8 x 0.9"},
  #kazohinia
  {"title" : "Voyage to Kazohinia", "fileDir" : "", "dimensions" : ""},
  {"fileDir" : "images/spines/demon_slayer_one-9781974700523.png", "dimensions" : "5 x 0.7 x 7.5"},
  #if i did it
  {"title" : "If I Did It", "fileDir" : "", "dimensions" : ""},
  {"fileDir" : "images/spines/handmaids_tale-9780385490818.png", "dimensions" : "5.21 x 0.7 x 7.94"},
  {"fileDir" : "images/spines/i_am_watching_you-9781542046596.png", "dimensions" : "5.5 x 1 x 8.25"},
  {"fileDir" : "images/spines/flight_of_eisenstein-9781844164592.png", "dimensions" : "4.19 x 1 x 6.75"},
  {"fileDir" : "images/spines/macbeth-9781586638467.jpg", "dimensions" : "5.2 x 0.6 x 7.4"},
  {"fileDir" : "images/spines/sea_change-9781616963316.jpg", "dimensions" : "5 x .7 x 8"},
  {"fileDir" : "images/spines/innocence-9780553808032.png", "dimensions" : "6.4 x 1 x 9"},
  {"fileDir" : "images/spines/anthropocene_reviewed-9780525555216.png", "dimensions" : "5.8 x 1.09 x 8.55"},
  {"fileDir" : "images/spines/where_the_crawdads_sing-9780735219113.png", "dimensions" : "6.4 x 1.5 x 9.2"},
  {"fileDir" : "images/spines/annihilation-9780374104092.png", "dimensions" : "6.31 x 0.85 x 7.95"},
  {"fileDir" : "images/spines/merchant_of_venice-9780812035704.png", "dimensions" : "5 x 0.6 x 7.25"},
  {"fileDir" : "images/spines/valis-9780552118415.png", "dimensions" : "4.25 x 6.87 x .6"},
  {"fileDir" : "images/spines/tale_of_two_cities-9781774021705.jpg", "dimensions" : "8.75 x 4.88 x 1.38"},
  {"fileDir" : "images/spines/when_you_trap_a_tiger-9781524715700.jpg", "dimensions" : "5.88 x 0.99 x 8.56"},
  #red mars
  {"title" : "Red Mars", "fileDir" : "", "dimensions" : ""},
  {"fileDir" : "images/spines/symposium-9780143037538.jpg", "dimensions" : "4.36 x 0.34 x 7.11"},
  {"fileDir" : "images/spines/project_hail_mary-9780593135204.png", "dimensions" : "6.33 x 1.53 x 9.57"},
  {"fileDir" : "images/spines/a_light_in_the_attic-9780060513061.png", "dimensions" : "10.1 x 1.11 x 11.11"},
  {"fileDir" : "images/spines/masseffect_ascension-9780345498526.jpg", "dimensions" : "4.25 x 0.9 x 6.85"},
  {"fileDir" : "images/spines/doctor_faustus-9780199537068.jpg", "dimensions" : "7.5 x 1.4 x 5"},
  {"fileDir" : "images/spines/vacation_guide_to_the_solar_system-9780143129776.png", "dimensions" : "5.81 x 0.71 x 7.81"},
  {"fileDir" : "images/spines/old_man_and_the_sea-9780684830490.jpg", "dimensions" : "6.13 x 1 x 7"},
  {"fileDir" : "images/spines/immune-9780593241318.png", "dimensions" : "7.32 x 1.42 x 9.29"},
  {"fileDir" : "images/spines/flirtasaurus-9798654172310.png", "dimensions" : "5.5 x 0.65 x 8.5"},
  {"fileDir" : "images/spines/silence-9781250082275.png", "dimensions" : "5.44 x 0.72 x 8.25"},
  {"fileDir" : "images/spines/awakening-9780451524485.png", "dimensions" : "4.25 x 0.91 x 6.81"},
]

files2022 = [
  {"fileDir" : "images/spines/far_from_the_light_of_heaven-9780759557918.png", "dimensions" : "5.65x1.4x8.25"},
  {"fileDir" : "images/spines/bakemonogatari_one-9781942993889.png", "dimensions" : "5.49x0.64x7.5"},
  {"fileDir" : "images/spines/frankenstein-9781926444314.png", "dimensions" : "8.82x4.44x1.32"},
  {"fileDir" : "images/spines/man_with_no_shadow-9798638838638.png", "dimensions" : "6x0.53x9"},
  {"fileDir" : "images/spines/at_earths_core-9780809599783.jpeg", "dimensions" : "5x0.91x8"},
  {"fileDir" : "images/spines/demon_slayer_two-9781974700530.png", "dimensions" : "5x0.7x7.5"},
  {"fileDir" : "images/spines/ben_franklin-9781609425111.png", "dimensions" : "6x1.08x8"},
  {"fileDir" : "images/spines/pillars_of_the_earth-9780330450867.png", "dimensions" : "4.41x1.81x7.09"},
  {"fileDir" : "images/spines/sleeping_giants-9781101886717.png", "dimensions" : "5.5x0.7x8.3"},
  {"fileDir" : "images/spines/midnight_library-9780525559474.png", "dimensions" : "8.02x0.86x10.8"},
  {"fileDir" : "images/spines/my_man_jeeves-9781585678754.png", "dimensions" : "5.4 x 1.05 x 7.5"},
]

#dimension must be delimited with x.
def getBookHeightWidthLength(dimension):
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

def genBookHeightWidthLength():
  #h 6-9
  h = random() * (9 - 6) + 6
  #w .5-2
  w = random() * (2 - .5) + .5
  #l 5-6
  l = random() * (6 - 5) + 5
  return h,w,l

def getRandomFont(fontSize):
  fontList = [
    "fonts/LeagueGothic.ttf",
    "fonts/PlayfairDisplay.ttf",
    "fonts/SouthernAire.ttf",
    "fonts/Yellowtail.ttf",
  ]
  fontIndex = int(random() * (len(fontList)-1))
  return ImageFont.truetype(fontList[fontIndex], fontSize)

def convertInchesToPixels(inches):
  return int(inches * 47) #at some point, i'll make this a class, and each class can be instantiated with different bookshelf types. These types will have different pixel to inch ratios. but for now this is fine. my only image is a 1/20 ratio

shelfBackground = Image.open("./images/bookshelves/bookshelf1.jpg")
shelfLength = 1688
shelfBottoms = [676, 1328]
shelfBottomIndex = 0
# files2021 = files2021 + files2022

bookLeft = 75
for i, f in enumerate(files2021):
  h,w,l = 0,0,0
  if(f["dimensions"]):
    h,w,l = getBookHeightWidthLength(f["dimensions"])
  else:
    h,w,l = genBookHeightWidthLength()
  bookRight = bookLeft + convertInchesToPixels(w)
  if(bookRight > shelfLength):
    bookLeft = 75
    bookRight = bookLeft + convertInchesToPixels(w)
    shelfBottomIndex += 1
  bookTop = shelfBottoms[shelfBottomIndex] - convertInchesToPixels(h)
  if(f["fileDir"]): #use provided file
    spine = Image.open(f["fileDir"])
    spine = spine.resize((convertInchesToPixels(w), convertInchesToPixels(h)))
    shelfBackground.paste(spine, (bookLeft, bookTop))
  else: #draw our own cover rectangle
    newBook = Image.new("RGB", (convertInchesToPixels(h), convertInchesToPixels(w)), getRandColor(.7))
    imDraw = ImageDraw.Draw(newBook)
    imDraw.text((10, 0), f["title"], (255,255,255), font=getRandomFont(int(h*w)*4))
    newBook = newBook.rotate(270, expand=True)
    shelfBackground.paste(newBook, (bookLeft, bookTop))
  bookLeft = bookRight
shelfBackground.show()

# import base64
# from io import BytesIO
# buffered = BytesIO()
# image.save(buffered, format="JPEG")
# img_str = base64.b64encode(buffered.getvalue()