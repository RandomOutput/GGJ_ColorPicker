import math
from PIL import Image
#from wand.image import Image
#from wand.color import Color

def getMainColor(im):
	colors = dict()
	maxColor = (0,0,0)
	maxCount = 0
	max3 = []

	try:
		pix = list(im.getdata())
	except:
		raise

	for pixel in pix:
		if pixel in colors:
			colors[pixel] += 1
		else:
			colors[pixel] = 1

	for color in colors:
		minVal = min(color[0], color[1], color[2])
		maxVal = max(color[0], color[1], color[2])
		average = (color[0] + color[1] + color[2]) / 3.0

		if len(max3) < 3:
			max3.append((color, colors[color]))
			max3 = sorted(max3, key=lambda colorCount: colorCount[1])
		elif average > 50 and maxVal - minVal > 50 and colors[color] > max3[0][1]:
			max3[0] = ((color, colors[color]))
			max3 = sorted(max3, key=lambda colorCount: colorCount[1])

	top3Average = (round((max3[0][0][0]+max3[1][0][0]+max3[2][0][0])/3.0),round((max3[0][0][1]+max3[1][0][1]+max3[2][0][1])/3.0),round((max3[0][0][2]+max3[1][0][2]+max3[2][0][2])/3.0))

	return top3Average

def getColorDiff(image1, image2):
	try:
		vector = (abs(getMainColor(image1)[0] - getMainColor(image2)[0]), abs(getMainColor(image1)[1] - getMainColor(image2)[1]), abs(getMainColor(image1)[2] - getMainColor(image2)[2]))
	except:
		raise
	return math.sqrt((vector[0]*vector[0])+(vector[1]*vector[1])+(vector[2]*vector[2]))
			
if __name__=="__main__":
	im1 = Image.open("img1.png")
	im2 = Image.open("img4.jpg")
	im3 = Image.open("img3.png")
	print getColorDiff(im1, im2)
	print getColorDiff(im1, im3)

