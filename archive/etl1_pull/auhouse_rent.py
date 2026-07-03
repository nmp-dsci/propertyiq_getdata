
### IMPORT Libraries
import pandas as pd
import numpy as np
from urllib.request import urlopen
from urllib.error import HTTPError
import re,time,os,sys
import time,datetime,math

from bs4 import BeautifulSoup
from bs4.element import Tag

sys.path.append('/Users/macmac/Documents/GitHub/propertyiq_getdata')

from config import * 
from utils import * 

sourceid = 'auhouse_rent'

scrape_area_dir =  output_directory + '01a Region href property/' + dateid  + '_'+sourceid
if os.path.exists(scrape_area_dir) == False :
    os.mkdir(scrape_area_dir)

### get the suburb file to run through
updatefile = output_directory + '01a Region href property/'+sourceid+'_'+dateid + '.csv'
last_dateid = last_update(output_directory,dateid)

if os.path.exists(updatefile) :
	area_counts = pd.read_csv(updatefile)
else:
	area_counts = get_jobs(updatefile, output_directory,last_dateid,sourceid)

print(area_counts.query('DateID==DateID')['complete'].value_counts(dropna=False))


template_url = "https://house.getsoldprice.com.au/rent/list/##STATE##/##POA##/##SUBURB##/##PAGE##/?sort=date&bmin=##BEDS##&bmax=##BEDS##"
## requires: ##STATE##, ##POA##,##SUBURB##, ##BEDS##



# row = 6
for row in area_counts.query('complete!=complete & DateID==DateID').index.values:
	curr_dateid = pd.to_datetime(area_counts.DateID.fillna('2015-01-01').loc[row])
	region_beds = '{r}_b{b}'.format(r=area_counts.loc[row,'area_sydney'],b=area_counts.loc[row,'bedrooms'])
	## STEP 1 IDENTIFY URL
	url_domain = template_url.replace('##STATE##',area_counts.loc[row,'state']
		).replace('##STATE##',area_counts.loc[row,'state']
		).replace('##POA##',str(area_counts.loc[row,'postcode'])
		).replace('##SUBURB##',area_counts.loc[row,'suburb']
		).replace('##BEDS##',str(area_counts.loc[row,'bedrooms']))
	print('ITERATING: {}'.format(url_domain))
	## STEP 3: INITIALISE VALUES
	uptodate = False
	page_no = np.array(1)
	total_start = time.time()
	## get max page
	try:
		find_max_pages = urlopen(url_domain.replace("##PAGE##",str(1))).read().decode('utf-8')
	except :
		print("ERROR: Cant find URL")
		continue
	soup = BeautifulSoup(find_max_pages)
	# find class, max page
	find_max = [x.text for x in soup.findAll("div", { "class" : "page-header" })]
	try: 
		max_page = pd.Series(find_max).str.extract('Displaying \d+ to \d+ of (\d+)',expand=False).astype(float).max()
		max_page = int(np.ceil(max_page/12.0))
		print('FOUND: Max page is {}'.format(max_page))
	except:
		print("ERROR: Can't find MAX page")
		continue
	#max_page = 50 if max_page > 50 else int(np.ceil(max_page))
	## STEP 4:  GET PAGES
	for page_no in range(1,max_page + 1):       # page_no=1
		print("Iterating Through Page: %s" % page_no)
		if uptodate ==False:
			# create directory
			output_name = scrape_area_dir + '/' + region_beds.replace('/','_') +'_p' +str(page_no) + '.txt'
			if os.path.exists(output_name) == False:
				print('Get Data')
				start = time.time()
				domain_url = url_domain.replace("##PAGE##",str(page_no))
				#
				html = urlopen(domain_url).read().decode('utf-8')
				# Pull Dates
				date_pattern = '(\w{3} \d{4})'
				html_dates = pd.Series(re.findall(date_pattern, html))
				html_dates = '01 ' + html_dates
				html_dates = pd.to_datetime(html_dates, format = '%d %b %Y',errors='coerce')
				print('TESTING new_min={dt:s} < old_max={ex:s} '.format(dt=str(html_dates.min()), ex=str(curr_dateid)))
				if html_dates.min() < curr_dateid or page_no > 100:
					uptodate = True
				#
				text_file = open(output_name, "w")
				text_file.write(html)
				text_file.close()
				#
				print("Time taken: --- %s seconds ---" % (time.time() - start))
				time.sleep(np.max([7-(time.time() - start),0]))
	#
	print("Time taken: --- %s seconds ---" % (time.time() - total_start))
	area_counts['complete'].loc[row] = 1
	area_counts.to_csv(updatefile,index=False)
