
### IMPORT Libraries
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
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

print('has DateID (scraped before) else never scraped')
print(area_counts.query('DateID!=DateID').shape)

##
template_url = 'https://www.realestate.com.au/sold/with-###BEDS###-bedrooms-in-###SUBURB###%2c+###STATE###+###POSTCODE###/list-#PAGE#?maxBeds=###BEDS###&includeSurrounding=false&activeSort=solddate'



## region = regions[1]
for row in area_counts.query('complete!=1').index.values:           # row = rows2[0]
	url_source = template_url.replace("###SUBURB###", area_counts.loc[row]['suburb'])
	url_source = url_source.replace("###STATE###", area_counts.loc[row]['state'])
	url_source = url_source.replace("###POSTCODE###", str(int(area_counts.loc[row]['postcode'])))
	url_source = url_source.replace("###BEDS###", str(int(area_counts.loc[row]['bedrooms'])))
	curr_dateid = pd.to_datetime(area_counts['DateID'].loc[row])
	region = '-'.join(area_counts[['suburb','state','postcode','bedrooms']].astype(str).loc[row])
	print(region)
	if pd.isnull(area_counts['complete'].loc[row]):
		uptodate = False
		page_no = np.array(1)
		total_start = time.time()
		## get max page
		time.sleep(0.5)
		try:
			find_max_pages = urlopen(url_source.replace("#PAGE#",str(page_no))).read().decode('utf-8')
		except :
			continue
		soup = BeautifulSoup(find_max_pages)
		# find class, max page
		find_max = soup.findAll("p", { "class" : "results-set-footer__heading" })
		if len(find_max) == 0:
			print('couldnt find page max')
			#break
			max_page = 1
		else:
			find_max = pd.Series(find_max[0].string)
			find_max = pd.Series(find_max.str.split('[^0-9]')[0])
			max_page = (find_max[find_max.str.len() == find_max.str.len().max() ]).astype(int).max()
			max_page = max_page/20.0
			max_page = 50 if max_page > 50 else int(np.ceil(max_page))
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
					    html = urlopen(source_url).read().decode('utf-8')
					except :
					    continue
					# Pull Dates
					date_pattern = '(\d{1,2} [A-z]{3} \d{4})'
					html_dates = pd.Series(re.findall(date_pattern, html))
					html_dates = pd.to_datetime(html_dates, format = '%d %b %Y',errors='coerce')
					if html_dates.min() < curr_dateid:
						uptodate = True
					#
					#
					text_file = open(output_name, "w")
					text_file.write(html)
					text_file.close()
					#
					print("Time taken: --- %s seconds ---" % (time.time() - start))
		#
		print("Time taken: --- %s seconds ---" % (time.time() - total_start))
		area_counts['complete'].loc[row] = 1
		area_counts.to_csv(updatefile,index=False)

##### END LOOP
