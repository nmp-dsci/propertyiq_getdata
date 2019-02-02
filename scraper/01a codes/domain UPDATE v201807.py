
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
sourceid = 'domain'
dateid = str(20180722)
print (dateid)


## set directory
output_directory = "/Users/macmac/Documents/Property/20151207 Scape Sydney/"
os.listdir(os.path.dirname(output_directory))

updatefile = output_directory + '01a Region href property/'+sourceid+'_Back_F_'+dateid + '.csv'

final_dir  = output_directory + '01e Master_DF'
last_dateid = pd.Series(os.listdir(final_dir))
last_dateid = last_dateid.str.extract('(\d{8})',expand=False)
last_dateid = last_dateid[last_dateid<>dateid]
last_dateid = last_dateid.astype(float).max().astype(int).astype(str)
print('last Data Scrape: %s' % (last_dateid))

scrape_area_dir =  output_directory + '01a Region href property/' + dateid +'_'+sourceid
if os.path.exists(scrape_area_dir) == False :
    os.mkdir(scrape_area_dir)

### Get seed postcodes
old_domain_df = pd.read_csv(final_dir + '/'+ last_dateid+'_'+sourceid+'.csv')
old_domain_df['dateID'] = pd.to_datetime(old_domain_df['dateID'],format='%d %b %Y')

##  Create final area_counts
old_domain_df['bedrooms'] = old_domain_df['beds'].fillna(0).apply(lambda x: '5-any' if x > 4 else str(int(x)) )
old_domain_df.groupby('bedrooms').size()
##
if os.path.exists(updatefile):
    area_counts = pd.read_csv(updatefile)
else:
    ####################
    ### Bring in master poa mapping
    poa_sub = pd.read_csv(output_directory+'00 POA_SUBURB.csv')
    oztam_map = pd.read_csv(output_directory+'99 oztam_mapping.csv')
    ## create POA mapping
    poa_sub_focus = pd.merge(poa_sub,oztam_map,on='postcode',how='inner')
    poa_sub_focus['suburb'] = poa_sub_focus['suburb'].str.lower().str.replace(' ','-')
    poa_sub_focus['dummy'] = 1
    ##
    beds_df = old_domain_df.groupby('bedrooms').size().reset_index().drop(0,axis=1)
    beds_df['dummy'] = 1
    ### full POA * SUBURB
    area_counts = pd.merge(poa_sub_focus,beds_df, on='dummy')
    area_counts['state'] = 'nsw'
    area_counts['postcode'] =area_counts['postcode'].astype(int).astype(str)
    area_counts['area_sydney'] = area_counts.apply(lambda x: '-'.join(x[['suburb','state','postcode']]),axis = 1)
    area_counts['complete'] = np.NaN
    #### Tag max date listing
    old_domain_df['suburb'] = old_domain_df['suburb'].str.lower().str.replace(' ','-')
    old_domain_df['postcode'] = old_domain_df['postcode'].astype(int).astype(str)
    poa_sub_dateID = old_domain_df.groupby(['postcode','suburb','bedrooms'])['dateID'].max().reset_index()
    area_counts = pd.merge(
            area_counts
        ,   poa_sub_dateID
        ,   on=['postcode','suburb','bedrooms']
        ,   how='left'
        )
    #area_counts = area_counts.query('dateID==dateID')



print(area_counts['complete'].value_counts(dropna=False))
area_counts.query('dateID==dateID').shape
area_counts.query('dateID<>dateID').shape

##
#template_url = 'https://www.domain.com.au/sold-listings/kiribilli-nsw-2060/?bedrooms=2&sort=solddate-desc&page=1'
template_url = 'https://www.domain.com.au/sold-listings/###AREA_SYDNEY###/?bedrooms=###BEDS###&sort=solddate-desc&page=#PAGE#'

## STEP 2 SET FunctionFOR HREF
def get_hrefs(a):
    href_i = a.split('href="')[1]
    href_i = href_i.split('"')[0]
    return(href_i);\


#### drivers
rows = len(area_counts['area_sydney'])
iters = 1
leni = len(area_counts)
len_iter = leni/iters

## manual fixe
area_counts['area_sydney'] = area_counts['area_sydney'].str.replace('brightonlesands','brighton-le-sands')


area_counts.query('suburb == "pyrmont"').shape


for row in range(rows):           # row = rows1[0] row = 10
    region = area_counts['area_sydney'].iloc[row]
    bedrooms = area_counts['bedrooms'].iloc[row]
    curr_dateid = pd.to_datetime(area_counts['dateID'].iloc[row])
    print(region+ '-bedrooms_' + str(bedrooms))
    if pd.isnull(area_counts['complete'].iloc[row]):
        url_domain = template_url.replace("###AREA_SYDNEY###", region)
        url_domain = url_domain.replace("###BEDS###", bedrooms)
        ## STEP 3: INITIALISE VALUES
        uptodate = False;\
        page_no = np.array(1);\
        total_start = time.time();\
        ## get max page
        try:
            find_max_pages = urlopen(url_domain.replace("#PAGE#",str(1))).read()
        except HTTPError:
            continue
        soup = BeautifulSoup(find_max_pages)
        # find class, max page
        find_max = soup.findAll("h1", { "class" : "search-results__summary" })
        if len(find_max) == 0:
			print('couldnt find page max')
			#break
			max_page = 0
        else:
			find_max = find_max[0].text
			find_max = re.split('Proper',find_max,maxsplit=1)[0]
			max_page = pd.Series(find_max).str.split('[^0-9]',expand=True)
			max_page = max_page[max_page<>''].max().max()
			max_page = int(max_page)/20.0
			max_page = 50 if max_page > 50 else int(np.ceil(max_page))
		## STEP 4:  GET PAGES
        for page_no in range(1,max_page + 1):       # page_no=1
			print("Iterating Through Page: %s" % page_no)
			if uptodate ==False:
				# create directory
				output_name = scrape_area_dir + '/' + region+'_b'+bedrooms[0] +'_p' +str(page_no) + '.txt'
				if os.path.exists(output_name) == False:
					print('Get Data')
					start = time.time()
					domain_url = url_domain.replace("#PAGE#",str(page_no))
					#
					html = urlopen(domain_url).read();\
					# Pull Dates
					date_pattern = '(\d{1,2} \w{3} \d{4})'
					html_dates = pd.Series(re.findall(date_pattern, html))
					html_dates = pd.to_datetime(html_dates, format = '%d %b %Y')
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
