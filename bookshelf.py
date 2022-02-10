from lib2to3.pytree import convert
from PIL import Image

files2021 = [
  {"fileDir" : "images/spines/slaughterhouse_five-9780812988529.png", "dimensions" : "5.3 x 0.6 x 8"},
  {"fileDir" : "images/spines/alice_knott-9780525535218.png", "dimensions" : "6.15x1.08x9.26"},
  {"fileDir" : "images/spines/dark_matter-9781101904220.png", "dimensions" : "6.35x1.2x9.5"},
  {"fileDir" : "images/spines/uzumaki-9781421561325.png", "dimensions" : "5.75 x 1.9 x 8.25"},
  {"fileDir" : "images/spines/pirate_cinema-9780765329080.png", "dimensions" : "5.81 x 1.29 x 8.7"},
  #mass effect revelation
  {"fileDir" : "images/spines/we_were_liars-9780385741279.png", "dimensions" : "5.5 x 0.84 x 8.25"},
  #thinking of ending things
  {"fileDir" : "images/spines/rich_dad_poor_dad-9781612680170.png", "dimensions" : "6 x 1 x 8.75"},
  {"fileDir" : "images/spines/horus_rising-9781844162949.png", "dimensions" : "4.1 x 1 x 6.75"},
  #quantum garden
  {"fileDir" : "images/spines/false_gods-9781844163700.png", "dimensions" : "4.19 x 1.1 x 6.75"},
  {"fileDir" : "images/spines/so_you_want_to_talk_about_race-9781580058827.png", "dimensions" : "5.8 x 0.9 x 8.45"},
  {"fileDir" : "images/spines/thousand_splendid_suns-9781594489501.png", "dimensions" : "6.32 x 1.26 x 9.29"},
  {"fileDir" : "images/spines/mysteries_of_the_first_instant-9781689226691.png", "dimensions" : "6 x 0.87 x 9"},
  #business ethics field guide
  {"fileDir" : "images/spines/star_maker.png", "dimensions" : "6x1.4x8"},
  #julius ceasar
  {"fileDir" : "images/spines/galaxy_in_flames-9781844163939.png", "dimensions" : "4.19 x 1.1 x 6.75"},
  {"fileDir" : "images/spines/dorian_gray.png", "dimensions" : "6 x 1.35 x 7.5"},
  {"fileDir" : "images/spines/spire.png", "dimensions" : "6 x 1.2 x 7"},
  {"fileDir" : "images/spines/sphere-9780062428868.png", "dimensions" : "1 x 5.2 x 7.9"},
  {"fileDir" : "images/spines/klee_wyck-9781553650270.png", "dimensions" : "5.5 x 0.95 x 8.25"},
  {"fileDir" : "images/spines/astrophysics_for_people_in_a_hurry-9780393609394.png", "dimensions" : "7.3 x 4.8 x 0.9"},
  #kazohinia
  {"fileDir" : "images/spines/demon_slayer_one-9781974700523.png", "dimensions" : "5 x 0.7 x 7.5"},
  #if i did it
  {"fileDir" : "images/spines/handmaids_tale-9780385490818.png", "dimensions" : "5.21 x 0.7 x 7.94"},
  {"fileDir" : "images/spines/i_am_watching_you-9781542046596.png", "dimensions" : "5.5 x 1 x 8.25"},
  {"fileDir" : "images/spines/flight_of_eisenstein-9781844164592.png", "dimensions" : "4.19 x 1 x 6.75"},
  #macbeth
  #sea change
  {"fileDir" : "images/spines/innocence-9780553808032.png", "dimensions" : "6.4 x 1 x 9"},
  #anthropocene reviewed
  {"fileDir" : "images/spines/where_the_crawdads_sing-9780735219113.png", "dimensions" : "6.4 x 1.5 x 9.2"},
  {"fileDir" : "images/spines/annihilation-9780374104092.png", "dimensions" : "6.31 x 0.85 x 7.95"},
  #merchant of venice
  {"fileDir" : "images/spines/valis-9780552118415.png", "dimensions" : "4.25 x 6.87 x .6"},
  #tale of two cities
  #trap tiger
  #red mars
  #symposium
  #project hail mary
  #a light in the attic
  #mass effect ascension
  #doctor faustus
  #vacation guide to solar system
  {"fileDir" : "images/spines/old_man_and_the_sea-9780684830490.jpg", "dimensions" : "6.13 x 1 x 7"},
  #immune
  #flirtisaurus
  #silence
  #the awakening
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

def convertInchesToPixels(inches):
  return int(inches * 47) #at some point, i'll make this a class, and each class can be instantiated with different bookshelf types. These types will have different pixel to inch ratios. but for now this is fine. my only image is a 1/20 ratio

shelfBackground = Image.open("./images/bookshelves/bookshelf1.jpg")
shelfLength = 1638 + 73
shelfBottoms = [676, 1328]
shelfBottomIndex = 0
#files2021 = files2021 + files2022

bookLeft = 75
for i, f in enumerate(files2021):
  h,w,l = getBookHeightWidthLength(f["dimensions"])
  bookRight = bookLeft + convertInchesToPixels(w)
  if(bookRight > shelfLength):
    bookLeft = 75
    bookRight = bookLeft + convertInchesToPixels(w)
    shelfBottomIndex += 1
  bookTop = shelfBottoms[shelfBottomIndex] - convertInchesToPixels(h)
  spine = Image.open(f["fileDir"])
  spine = spine.resize((convertInchesToPixels(w), convertInchesToPixels(h)))
  shelfBackground.paste(spine, (bookLeft, bookTop))
  bookLeft = bookRight
shelfBackground.show()