
### IMPORT Libraries
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
from urllib2 import urlopen,HTTPError
import re
import time
import os
import multiprocessing as mp
import matplotlib.pyplot as plt
import time
import datetime
import math

from bs4.element import Tag

#dateid = time.strftime("%Y%m%d")
dateid = str(20171231)
print (dateid)


## set directory
output_directory = "/Users/macmac/Documents/Property/20151207 Scape Sydney/"
os.listdir(os.path.dirname(output_directory))

updatefile = output_directory + '01a Region href property/AUHOUSEPRICE_RENT_'+dateid + '.csv'


final_dir  = output_directory + '01c Property_DF'
last_dateid = pd.Series(os.listdir(final_dir))
last_dateid = last_dateid.str.extract('(\d{8})',expand=False)
last_dateid = last_dateid[last_dateid<> dateid]
last_dateid = last_dateid.astype(float).max().astype(int).astype(str)
print('last Data Scrape: %s' % (last_dateid))

scrape_area_dir =  output_directory + '01a Region href property/' + dateid +'_auhouseprice_rent'
if os.path.exists(scrape_area_dir) == False :
    os.mkdir(scrape_area_dir)

##
if os.path.exists(updatefile):
    area_counts = pd.read_csv(updatefile)
else:
    ####################
    ### Bring in master poa mapping
    poa_sub = pd.read_csv(output_directory+'00 POA_SUBURB.csv')
    oztam_map = pd.read_csv(output_directory+'99 oztam_mapping.csv')
    ## create POA mapping
    area_counts = pd.merge(poa_sub,oztam_map,on='postcode',how='inner')
    area_counts['suburb'] = area_counts['suburb'].str.lower().str.replace(' ','+')
    area_counts['dummy'] = 1
    ##
    area_counts['state'] = 'nsw'
    area_counts['postcode'] =area_counts['postcode'].astype(int).astype(str)
    area_counts['area_sydney'] = area_counts.apply(lambda x: '/'.join(x[['state','postcode','suburb']]),axis = 1)
    area_counts['complete'] = np.NaN
    area_counts['DateID'] = np.NaN
    #### Tag max date listing
    #poa_sub_dateID = old_domain_df.groupby(['postcode','suburb'])['DateID'].max().reset_index()
    #poa_sub_dateID['postcode'] = poa_sub_dateID['postcode'].astype(int).astype(str)
    #area_counts = pd.merge(
    #        area_counts
    #    ,   poa_sub_dateID
    #    ,   on=['postcode','suburb']
    #    ,   how='left'
    #    )

print(area_counts['complete'].value_counts(dropna=False))
#print(area_counts.query('DateID==DateID').shape)
#print(area_counts.query('DateID<>DateID').shape)


area_counts.query('suburb=="ourimbah"')

##
template_url = 'http://house.getsoldprice.com.au/rent/list/###AREA_SYDNEY###/#PAGE#'

## STEP 2 SET FunctionFOR HREF
def get_hrefs(a):
    href_i = a.split('href="')[1]
    href_i = href_i.split('"')[0]
    return(href_i);\


#### drivers
rows = len(area_counts['area_sydney'])
iters = 5
leni = len(area_counts)
len_iter = leni/iters

rows1 = range( len_iter * 1 - len_iter ,len_iter * 1)
rows2 = range( len_iter * 2 - len_iter ,len_iter * 2)
rows3 = range( len_iter * 3 - len_iter ,len_iter * 3)
rows4 = range( len_iter * 4 - len_iter ,len_iter * 4)
rows5 = np.setdiff1d(range(rows),  range( leni/iters * 5 - leni/5))


for row in rows1:           # row = rows1[0] row = 384
	region = area_counts['area_sydney'].iloc[row]
	curr_dateid = pd.to_datetime(area_counts['DateID'].iloc[row])
	print(region)
	if pd.isnull(area_counts['complete'].iloc[row]):
		#
		## STEP 1 IDENTIFY URL
		url_domain = template_url.replace("###AREA_SYDNEY###", region)
		#
		## STEP 3: INITIALISE VALUES
		uptodate = False;\
		page_no = np.array(1);\
		total_start = time.time();\
		#
		## get max page
        try:
            find_max_pages = urlopen(url_domain.replace("#PAGE#",str(1))).read()
        except HTTPError:
            continue
        soup = BeautifulSoup(find_max_pages)
		# find class, max page
        find_max = soup.findAll("div", { "class" : "page-header" })
        if len(find_max) == 0:
			print('couldnt find page max')
			#break
			max_page = 0
        else:
			find_max = find_max[0].text
			find_max = re.split('Proper',find_max,maxsplit=1)[0]
			max_page = pd.Series(find_max).str.split('[^0-9]',expand=True)
			max_page = max_page[max_page<>''].max().max()
			if max_page<> max_page:
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
					html = urlopen(domain_url).read();\
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
        area_counts['complete'].iloc[row] = 1
        area_counts.to_csv(updatefile,index=False)
#### END LOOP 












