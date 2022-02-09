from PIL import Image

files = [
"images/spines/far_from_the_light_of_heaven-9780759557918.png",
"images/spines/bakemonogatari_one-9781942993889.png",
"images/spines/frankenstein-9781926444314.png",
"images/spines/man_with_no_shadow-9798638838638.png",
"images/spines/at_earths_core-9780809599783.jpeg",
"images/spines/demon_slayer_two-9781974700530.png",
"images/spines/ben_franklin-9781609425111.png",
"images/spines/pillars_of_the_earth-9780330450867.png",
"images/spines/sleeping_giants-9781101886717.png",
"images/spines/midnight_library-9780525559474.png",
]

dimensions = [
"5.65x1.4x8.25",
"5.49x0.64x7.5",
"8.82x4.44x1.32",
"6x0.53x9",
"5x0.91x8",
"5x0.7x7.5",
"6x1.08x8",
"4.41x1.81x7.09",
"5.5x0.7x8.3",
"8.02x0.86x10.8",
]

#dimension must be delimited with x.
def getBookHeightWidthLength(dimension):
  dimension.lower()
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
shelfBottom = 700
bookLeft = 75
for i, f in enumerate(files):
  h,w,l = getBookHeightWidthLength(dimensions[i])
  bookTop = shelfBottom - convertInchesToPixels(h)
  bookRight = bookLeft + convertInchesToPixels(w)
  #box = (bookLeft, bookTop, bookRight, shelfBottom)
  spine = Image.open(f)
  spine = spine.resize((convertInchesToPixels(w), convertInchesToPixels(h)))
  shelfBackground.paste(spine, (bookLeft, bookTop))
  bookLeft = bookRight
shelfBackground.show()