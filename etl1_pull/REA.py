
### IMPORT Libraries
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup

import requests
from fake_useragent import UserAgent
ua = UserAgent()

from urllib.request import urlopen
from urllib.error import HTTPError
import re,time,os,sys
import multiprocessing as mp
import time,datetime,math

sys.path.append('/Users/macmac/Documents/GitHub/propertyiq_getdata')

from config import * 
from utils import * 

sourceid = 'REA'

scrape_area_dir =  output_directory + '01a Region href property/' + dateid  + '_'+sourceid
if os.path.exists(scrape_area_dir) == False :
    os.mkdir(scrape_area_dir)

### get the suburb file to run through
updatefile = output_directory + '01a Region href property/'+sourceid+'_'+dateid + '.csv'
last_dateid = last_update(output_directory,dateid)
area_counts = get_jobs(updatefile, output_directory,last_dateid,sourceid)

area_counts = area_counts.query('DateID==DateID') ## pretty certain now

print('has DateID (scraped before) else never scraped')
print(area_counts.query('DateID!=DateID').shape)

##
template_url = 'https://www.realestate.com.au/sold/with-###BEDS###-bedrooms-in-###SUBURB###%2c+###STATE###+###POSTCODE###/list-#PAGE#?maxBeds=###BEDS###&includeSurrounding=false&activeSort=solddate'


## set up random elements for HEADER and IP ADDRESS
counter = 1
random_cutoff = pd.Series([4,23,31,105,45,55,60,140,123,130])
counter_cutoff = random_cutoff.sample(1).iloc[0]
ua_reset = 50
ua_counter = ua_reset +1

print(area_counts.complete.value_counts(dropna=False))

## region = regions[1]
for row in area_counts.query('complete!=1').index.values:           # row = rows2[0]
	url_source = template_url.replace("###SUBURB###", area_counts.loc[row]['suburb'])
	url_source = url_source.replace("###STATE###", area_counts.loc[row]['state'])
	url_source = url_source.replace("###POSTCODE###", str(int(float(area_counts.loc[row]['postcode']))))
	url_source = url_source.replace("###BEDS###", str(int(float(area_counts.loc[row]['bedrooms']))))
	curr_dateid = pd.to_datetime(area_counts['DateID'].loc[row])
	region = '-'.join(area_counts[['suburb','state','postcode','bedrooms']].astype(str).loc[row])
	print(region)
	## 
	uptodate = False
	page_no = np.array(1)
	total_start = time.time()
	## header rotation
	if ua_counter > ua_reset: 
		ua_random = ua.random
		# renew_connection() # connection
		# session = get_tor_session() # reset session
		ua_counter = 0
		print('user-agent: {}'.format(ua_random))
		# print('IP-addres: {}'.format(session.get('http://httpbin.org/ip', headers={'User-Agent': ua.random }).text))
		# clear cookies
	else: 
		ua_counter += 1
	## get max page
	try:
		find_max_pages = requests.get(url_source.replace('#PAGE#','1'), headers={'User-Agent': ua_random }).text
		# find_max_pages = session.get(url_source.replace('#PAGE#','1'), headers={'User-Agent': ua_random }).text
		soup = BeautifulSoup(find_max_pages)
		find_max = soup.findAll("p", { "class" : "results-set-footer__heading" })
		find_max = pd.Series(find_max[0].string)
		find_max = pd.Series(find_max.str.split('[^0-9]')[0])
		max_page = (find_max[find_max.str.len() == find_max.str.len().max() ]).astype(int).max()
		max_page = max_page/20.0
		max_page = 50 if max_page > 50 else int(np.ceil(max_page))
		print("MAX PAGE IS: {:d}".format(max_page))
	except Exception as  e:
		print("ERROR: Can't find MAX page")
		print(e)
		continue
	#
	## STEP 4:  GET PAGES
	for page_no in range(1,max_page + 1):
		print("Iterating Through Page: %s" % page_no)
		if uptodate ==False:
			start = time.time()
			source_url = url_source.replace("#PAGE#",str(page_no))
			# create directory
			output_name = scrape_area_dir + '/' + region +'_p' +str(page_no) + '.txt'
			if os.path.exists(output_name)==False:
				print('Get Data')
				time.sleep(0.25)
				try :
					# html = session.get(source_url, headers={'User-Agent': ua_random }).text
					html = requests.get(source_url, headers={'User-Agent': ua_random }).text
				except :
					print('ERROR: pulling url')
					continue
				# Pull Dates
				date_pattern = '(\d{1,2} [A-z]{3} \d{4})'
				html_dates = pd.Series(re.findall(date_pattern, html))
				html_dates = pd.to_datetime(html_dates, format = '%d %b %Y',errors='coerce')
				print('TESTING new_min={dt:s} < old_max={ex:s} '.format(dt=str(html_dates.min()), ex=str(curr_dateid)))
				if html_dates.min() < curr_dateid:
					uptodate = True
				#
				text_file = open(output_name, "w")
				text_file.write(html)
				text_file.close()
				#
				print("Time taken: --- %s seconds ---" % (time.time() - start))
				time.sleep(np.max([5-(time.time() - start),0]))
				# session.cookies.clear()
	#
	print("Time taken: --- %s seconds ---" % (time.time() - total_start))
	area_counts['complete'].loc[row] = 1
	area_counts.to_csv(updatefile,index=False)

##### END LOOP
