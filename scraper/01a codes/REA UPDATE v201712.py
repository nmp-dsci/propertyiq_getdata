
### IMPORT Libraries
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
from urllib2 import urlopen,HTTPError
from httplib import IncompleteRead
import re
import time
import os
import multiprocessing as mp
import matplotlib.pyplot as plt
import time
import datetime
import math


#dateid = time.strftime("%Y%m%d")
dateid = str(20171231)
print (dateid)

## set directory
output_directory = "/Users/macmac/Documents/Property/20151207 Scape Sydney/"
os.listdir(os.path.dirname(output_directory))

final_dir  = output_directory + '01c Property_DF'
last_dateid = pd.Series(os.listdir(final_dir))
last_dateid = last_dateid.str.extract('(\d{8})',expand=False)
last_dateid = last_dateid[last_dateid<>dateid]
last_dateid = last_dateid.astype(float).max().astype(int).astype(str)
print('last Data Scrape: %s' % (last_dateid))

scrape_area_dir =  output_directory + '01a Region href property/' + dateid  + '_realestate.com'
if os.path.exists(scrape_area_dir) == False :
    os.mkdir(scrape_area_dir)


### Get seed postcodes
old_domain_df = pd.read_csv(final_dir + '/'+ last_dateid+'_realestate.csv')
old_domain_df['DateID'] = old_domain_df['sale_date'].str.extract('(\d{2} \w{3} \d{4})',expand=False)
old_domain_df['DateID'] = pd.to_datetime(old_domain_df['DateID'],format='%d %b %Y')

old_domain_df['bedrooms'] = old_domain_df['beds'].fillna(0).apply(lambda x: '5' if x > 4 else str(int(x)) )
old_domain_df['bedrooms'].value_counts()

### get the suburb file to run through
updatefile = output_directory + '01a Region href property/realestate_Back_F_'+dateid + '.csv'


if os.path.exists(updatefile):
    area_counts = pd.read_csv(updatefile)
else:
    ####################
    ### Bring in master poa mapping
    poa_sub = pd.read_csv(output_directory+'00 POA_SUBURB.csv')
    oztam_map = pd.read_csv(output_directory+'99 oztam_mapping.csv')
    ## create POA mapping
    poa_sub_focus = pd.merge(poa_sub,oztam_map,on='postcode',how='inner')
    poa_sub_focus['suburb'] = poa_sub_focus['suburb'].str.lower().str.replace(' ','+')
    poa_sub_focus['dummy'] = 1
    ## beds mapping
    beds_df = old_domain_df.groupby('bedrooms').size().reset_index().drop(0,axis=1)
    beds_df['dummy'] = 1
    ### full POA * SUBURB
    area_counts = pd.merge(poa_sub_focus,beds_df, on='dummy')
    area_counts['state'] = 'nsw'
    area_counts['postcode'] =area_counts['postcode'].astype(int).astype(str)
    area_counts['area_sydney'] = area_counts.apply(lambda x: '-'.join(x[['suburb','state','postcode']]),axis = 1)
    area_counts['complete'] = np.NaN
    #### Tag max date listing
    poa_sub_dateID = old_domain_df.groupby(['postcode','suburb'])['DateID'].max().reset_index()
    poa_sub_dateID['postcode'] = poa_sub_dateID['postcode'].astype(int).astype(str)
    ## final
    area_counts = pd.merge(
            area_counts
        ,   poa_sub_dateID
        ,   on=['postcode','suburb']
        ,   how='left'
        )

print('has DateID (scraped before) else never scraped')
print(area_counts.query('DateID==DateID').shape)
print(area_counts.query('DateID<>DateID').shape)

##
template_url = 'https://www.realestate.com.au/sold/with-###BEDS###-bedrooms-in-###SUBURB###%2c+###STATE###+###POSTCODE###/list-#PAGE#?maxBeds=###BEDS###&includeSurrounding=false&activeSort=solddate'


## STEP 2 SET FunctionFOR HREF
def get_hrefs(a):
    href_i = a.split('href="')[1]
    href_i = href_i.split('"')[0]
    return(href_i);\


#### drivers
rows = len(area_counts['suburb'])
iters = 5
leni = len(area_counts)
len_iter = leni/iters

rows1 = range( len_iter * 1 - len_iter ,len_iter * 1)
rows2 = range( len_iter * 2 - len_iter ,len_iter * 2)
rows3 = range( len_iter * 3 - len_iter ,len_iter * 3)
rows4 = range( len_iter * 4 - len_iter ,len_iter * 4)
rows5 = np.setdiff1d(range(rows),  range( leni/iters * 5 - leni/5))


###SUBURB###
###STATE###
###POSTCODE###
#PAGE#
#
## region = regions[1]
for row in range(rows):           # row = rows2[0]
    ## STEP 1 IDENTIFY URL
    url_domain = template_url.replace("###SUBURB###", area_counts.iloc[row]['suburb'])
    url_domain = url_domain.replace("###STATE###", area_counts.iloc[row]['state'])
    url_domain = url_domain.replace("###POSTCODE###", str(int(area_counts.iloc[row]['postcode'])))
    url_domain = url_domain.replace("###BEDS###", str(int(area_counts.iloc[row]['bedrooms'])))
    curr_dateid = pd.to_datetime(area_counts['DateID'].iloc[row])
    #
    region = '-'.join(area_counts[['suburb','state','postcode','bedrooms']].astype(str).iloc[row])
    print(region)
    if pd.isnull(area_counts['complete'].iloc[row]):
		## STEP 3: INITIALISE VALUES
		uptodate = False;\
		page_no = np.array(1);\
		total_start = time.time();\
		## get max page
		time.sleep(0.5)
		try:
			find_max_pages = urlopen(url_domain.replace("#PAGE#",str(page_no))).read()
		except HTTPError:
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
				domain_url = url_domain.replace("#PAGE#",str(page_no))
				# create directory
				output_name = scrape_area_dir + '/' + region +'_p' +str(page_no) + '.txt'
				if os.path.exists(output_name)==False:
					print('Get Data')  
					time.sleep(0.25) 
					try :
					    html = urlopen(domain_url).read()
					except IncompleteRead:
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
		area_counts['complete'].iloc[row] = 1
		area_counts.to_csv(updatefile,index=False)

##### END LOOP 








