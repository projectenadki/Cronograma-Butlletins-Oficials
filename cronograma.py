from bs4 import BeautifulSoup
import requests, traceback, os, csv
from time import sleep
from datetime import date
from collections import OrderedDict
from selenium import webdriver
import json
import matplotlib.pyplot as plt
import numpy as np
import matplotlib.dates as mdates
from datetime import datetime
import matplotlib.ticker as ticker
import argparse

ABREVIATURA = {
	'Nombramientos':'N',
	'Revocaciones':'R',
	'Ceses/Dimisiones':'C/D',
	'Anuncio de reducción de capita':'Reducción capita'
}

AÑOS = []

def duplicados(borme,template):
	i = 0
	while i < len(borme):
		if borme[i]['fecha'] == template['fecha'] and borme[i]['titulo'] == template['titulo']:
			return True,i
		i = i + 1
	return False,0

def html_parser(html):
	borme = []
	soup = BeautifulSoup(html, 'lxml')
	lista_eventos = soup.find_all(class_='cbp_tmtimeline')[0]
	eventos = lista_eventos.find_all('li', recursive=False)
	for evento in eventos:
		fecha = evento.find('time').get('datetime')
		if args.año:
			año = fecha.split('-')[0]
			if año not in AÑOS:
				continue
		acciones = evento.find_all(class_='event-content')
		for accion in acciones:
			titulo = accion.find('h3').text[:-1]
			try:
				detalle = accion.text
			except:
				detalle = ''
				pass
			template = {}
			template['fecha'] = fecha
			try:
				if args.abreviatura:
					template['titulo'] = ABREVIATURA[titulo]
				else:
					template['titulo'] = titulo
			except:
				template['titulo'] = titulo
				pass
			
			dup,i = duplicados(borme,template)
			if dup:
				borme[i]['detalle'].append(detalle)
			else:
				template['detalle'] = [detalle]
				borme.append(template)
	return borme
		

# Elimina el botón que carga directivos (optimización)
def borme_button(driver):
	result = []
	for button in driver:
		val = button.get_attribute('onclick')
		if 'moreEventos' in val:
			result.append(button)
	return result

def get_html():
	options = webdriver.ChromeOptions()
	options.add_argument('--ignore-certificate-errors')
	options.add_argument('--incognito')
	options.add_argument('--headless')
	driver = webdriver.Chrome('/usr/lib/chromium/chromedriver', options=options)
	driver.get(args.url)
	more_buttons = driver.find_elements_by_class_name('EventosFooter')
	more_buttons = borme_button(more_buttons)
	while len(more_buttons) > 0:
		if more_buttons[0].is_displayed():
			driver.execute_script('arguments[0].click();', more_buttons[0])
			sleep(1)
		more_buttons.pop(0)
		if len(more_buttons) == 0:
			more_buttons = more_buttons + driver.find_elements_by_class_name('EventosFooter')
			more_buttons = borme_button(more_buttons)

	return driver.page_source

def plot(borme,name):
	names = [n['titulo'] for n in borme]


	# Convert date strings (e.g. 2014-10-18) to datetime
	dates = [datetime.strptime(d['fecha'], "%Y-%m-%d") for d in borme]



	## DATA2
	# Choose some nice levels
	levels = np.tile([-15,15,-13,13,-11,11,-9,9,-7,7,-5, 5, -3, 3, -1, 1],	int(np.ceil(len(dates)/6)))[:len(dates)]

	# Create figure and plot a stem plot with the date
	fig, ax = plt.subplots(figsize=(15, 8), constrained_layout=True)
	ax.set(title=name)

	markerline, stemline, baseline = ax.stem(dates, levels,linefmt="C3-", basefmt="k-",use_line_collection=True) # C3=Rojo, C2=Verde, C1=Naranja, C0=azul
	plt.setp(markerline, mec="k", mfc="w", zorder=3)

	# Shift the markers to the baseline by replacing the y-data by zeros.
	markerline.set_ydata(np.zeros(len(dates)))

	# annotate lines
	vert = np.array(['top', 'bottom'])[(levels > 0).astype(int)]
	for d, l, r, va in zip(dates, levels, names, vert):
		ax.annotate(r, xy=(d, l), xytext=(-3, np.sign(l)*3),textcoords="offset points", va=va, ha="right")


	# format xaxis with 4 month intervals
	if args.ejex:
		ax.get_xaxis().set_major_locator(mdates.MonthLocator(interval=args.ejex))

	else:
		xticks = [mdates.date2num(z) for z in dates] # Transformar fecha en formato mdates
		xticks = list(dict.fromkeys(xticks)) # Eliminar fechas duplicadas
		ax.get_xaxis().set_major_locator(ticker.FixedLocator(xticks)) # Eje X serán las fechas de los eventos

	
	ax.get_xaxis().set_major_formatter(mdates.DateFormatter("%d-%m-%Y"))
	plt.setp(ax.get_xticklabels(), rotation=30, ha="right")

	# remove y axis and spines
	ax.get_yaxis().set_visible(False)
	for spine in ["left", "top", "right"]:
		ax.spines[spine].set_visible(False)

	ax.margins(y=0.1)

	#plt.show()

	filename = '{}.png'.format(name)
	plt.savefig(filename)

def años():
	global AÑOS

	if '-' in args.año:
		inicio = int(args.año.split('-')[0])
		fin = int(args.año.split('-')[1])

		for año in range(inicio, fin + 1): 
			AÑOS.append(str(año)) 
	else:
		AÑOS.append(args.año)

def store_file(borme):
	result = ''
	for evento in borme:
		result = result + evento['fecha'] + '\n'
		for d in evento['detalle']:
			result = result + d + '\n' + '\n'
		result = result + '\n--------------------------------\n'

	if args.nombre:
		filename = '{}.txt'.format(args.nombre)
	else:
		if args.año:
			year = args.año.replace('-','_')
		else:
			year = 'completo'
		filename = '{}_{}.txt'.format(args.url.split('/')[-2:-1][0],year)
	with open(filename, 'w') as f:
		f.write(result)
	return filename

if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('--url', help='URL de la empresa de www.empresia.es', required=True)
	parser.add_argument('-x', '--ejex', help='Intérvalo fechas X-Axis en meses', default=0, type=int)
	parser.add_argument('--año', help='Mostrar período. Ejemplo: 2015-2020', default='', type=str)
	parser.add_argument('-a', '--abreviatura', help='Abreviar etiquetas', default=False, action='store_true')
	parser.add_argument('-n','--nombre', help='Nombre fichero de salida', default='', type=str)
	args = parser.parse_args()


	años()

	html = get_html()
	borme = html_parser(html)
	filename = store_file(borme)
	plot(borme,filename.split('.')[0])

	
	