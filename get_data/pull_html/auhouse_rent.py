
### IMPORT Libraries
import pandas as pd
import numpy as np
from urllib.request import urlopen
from urllib.error import HTTPError
import re,time,os
import time,datetime,math

from bs4 import BeautifulSoup
from bs4.element import Tag

from config import * 
from utils import * 

sourceid = 'auhouse_rent'

scrape_area_dir =  output_directory + '01a Region href property/' + dateid  + '_'+sourceid
if os.path.exists(scrape_area_dir) == False :
    os.mkdir(scrape_area_dir)

### get the suburb file to run through
updatefile = output_directory + '01a Region href property/'+sourceid+'_'+dateid + '.csv'

last_dateid = last_update(output_directory,dateid)

area_counts = get_jobs(updatefile, output_directory,last_dateid,sourceid)


print(area_counts['complete'].value_counts(dropna=False))

##
template_url = 'http://house.getsoldprice.com.au/rent/list/###AREA_SYDNEY###/#PAGE#'

# row = 0
for row in area_counts.query('complete!=complete').index.values:
	region = area_counts['area_sydney'].loc[row]
	curr_dateid = pd.to_datetime(area_counts['DateID'].loc[row])
	print(region)
	## STEP 1 IDENTIFY URL
	url_domain = template_url.replace("###AREA_SYDNEY###", region)
	## STEP 3: INITIALISE VALUES
	uptodate = False
	page_no = np.array(1)
	total_start = time.time()
	## get max page
	try:
		find_max_pages = urlopen(url_domain.replace("#PAGE#",str(1))).read().decode('utf-8')
	except :
		continue
	soup = BeautifulSoup(find_max_pages)
	# find class, max page
	find_max = soup.findAll("div", { "class" : "page-header" })
	if len(find_max) == 0:
		print('couldnt find page max')
		max_page = 0
	else:
		find_max = find_max[0].text
		find_max = re.split('Proper',find_max,maxsplit=1)[0]
		max_page = pd.Series(find_max).str.split('[^0-9]',expand=True)
		max_page = max_page[max_page!=''].max().max()
		if max_page!= max_page:
			max_page = 1
			uptodate == True
		else :
			max_page = int(np.ceil(max_page/12.0))
		#max_page = 50 if max_page > 50 else int(np.ceil(max_page))
	## STEP 4:  GET PAGES
	for page_no in range(1,max_page + 1):       # page_no=1
		print("Iterating Through Page: %s" % page_no)
		if uptodate ==False:
			# create directory
			output_name = scrape_area_dir + '/' + region.replace('/','_') +'_p' +str(page_no) + '.txt'
			if os.path.exists(output_name) == False:
				print('Get Data')
				start = time.time()
				domain_url = url_domain.replace("#PAGE#",str(page_no))
				#
				html = urlopen(domain_url).read().decode('utf-8')
				# Pull Dates
				date_pattern = '(\w{3} \d{4})'
				html_dates = pd.Series(re.findall(date_pattern, html))
				html_dates = '01 ' + html_dates
				html_dates = pd.to_datetime(html_dates, format = '%d %b %Y',errors='coerce')
				if html_dates.min() < curr_dateid:
					uptodate = True
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
