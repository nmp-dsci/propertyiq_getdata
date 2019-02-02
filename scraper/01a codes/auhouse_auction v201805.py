
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


dateid = time.strftime("%Y%m%d")
print (dateid)

## set directory
output_directory = "/Users/macmac/Documents/Property/20151207 Scape Sydney/"
os.listdir(os.path.dirname(output_directory))

sourceid = 'auhouse_auction'
versionID = '1'

scrape_area_dir = output_directory + '01a Region href property/'+ sourceid +'_v' + versionID
if os.path.exists(scrape_area_dir) == False:
    os.mkdir(scrape_area_dir)

updatefile = output_directory + '01a Region href property/'+sourceid+'_'+dateid + '.csv'

### Build driver of urls to scrape which is saturday of results
start_yyyymmdd = pd.to_datetime('2015-01-01')
end_yyyymmdd = pd.to_datetime('today')

if os.path.exists(updatefile):
    url_master = pd.read_csv(updatefile)
else:
    url_master = pd.DataFrame({'dateID':pd.date_range(start_yyyymmdd,end_yyyymmdd)})
    url_master['DoW'] = url_master.dateID.dt.strftime('%a')
    url_master = url_master.query('DoW == "Sat"')
    url_master['dateID'] = url_master['dateID'].astype(str)
    url_master['state'] = 'NSW'
    url_master['complete'] = np.NaN
    url_master.to_csv(updatefile, index=False)
##
template_url = 'https://www.auhouseprices.com/auction/results/###STATE###/###DATEID###/###PAGEID###'

## STEP 2 SET FunctionFOR HREF
def get_hrefs(a):
    href_i = a.split('href="')[1]
    href_i = href_i.split('"')[0]
    return(href_i);\


#### drivers
rows = url_master.shape[0]
summary_df = pd.DataFrame()

for row in range(rows):           # row = range(rows)[0] # row = 0
    dateID = url_master['dateID'].iloc[row]
    state = url_master['state'].iloc[row]
    print('Pulling---'+ state + '---' + dateID )
    ## STEP 1 IDENTIFY URL
    url_domain = template_url.replace("###STATE###", state)
    url_domain = url_domain.replace("###DATEID###", dateID)
    ## STEP 3: INITIALISE VALUES
    uptodate = False
    page_no = np.array(1)
    total_start = time.time()
    find_max_pages = urlopen(url_domain.replace("###PAGEID###",str(1))).read()
    soup = BeautifulSoup(find_max_pages)
    ## FIND MAX
    find_max = soup.findAll("li", { "class" : "active" })
    find_max = pd.Series(find_max)
    find_max = find_max.apply(lambda x: x.text)
    find_max = find_max[find_max.str.contains('\d+ to \d+ of \d+')]
    if len(find_max) == 0:
        print('couldnt find page max')
        #break
        max_page = 0
    else:
        listing_n = find_max.str.extract('\d+ to (\d+) of \d+',expand=False).astype(float).iloc[0]
        total_n = find_max.str.extract('\d+ to \d+ of (\d+)',expand=False).astype(float).iloc[0]
        max_page = int(np.ceil(total_n/listing_n))
	## STEP 4:  GET PAGES
    for page_no in range(1,max_page + 1):       # page_no=1
        print("Iterating Through Page: %d" % page_no)
        # create directory
        output_name = scrape_area_dir + '/' + state+'_'+dateID+ '_p'+str(page_no)+ '.txt'
        if os.path.exists(output_name) == False:
            print('Get Data')
            start = time.time()
            domain_url = url_domain.replace("###PAGEID###",str(page_no))
            html = urlopen(domain_url).read();\
            #
            text_file = open(output_name, "w")
            text_file.write(html)
            text_file.close()
            print("Time taken: --- %s seconds ---" % (time.time() - start))
		#
    print("Time taken: --- %s seconds ---" % (time.time() - total_start))
    url_master['complete'].iloc[row] = 1
    url_master.to_csv(updatefile,index=False)
#### END LOOP
