
import pandas as pd
import numpy as np
from urllib.request import urlopen
from urllib.error import HTTPError
import re,time,os,sys
import multiprocessing as mp
import time,datetime,math

from bs4 import BeautifulSoup
from bs4.element import Tag

sys.path.append('/Users/macmac/Documents/GitHub/propertyiq_getdata')

from config import * 
from utils import * 




template_url = 'https://www.domain.com.au/auction-results/sydney/'

srcid = 'domain_auction'

output_dir = f'../../data/propertyiq_getdata/{srcid}'

if os.path.exists(output_dir) == False: 
    os.mkdir(output_dir)


### get dt ragne 

latest_dt = datetime.datetime.now().strftime('%Y-%m-%d')
dt_df = pd.DataFrame({'dt':pd.date_range(start ='2023-01-01',end = latest_dt)})
dt_df['DoW'] = dt_df.dt.dt.strftime('%A')
dt_df = dt_df.query('DoW == "Saturday"')

## set jobs needed
dt_df['output_fn'] = dt_df.apply(lambda x: f'{output_dir}/{srcid}_{x["dt"]}.txt',axis=1)
dt_df['complete'] =dt_df['output_fn'].apply(lambda x: os.path.exists(x) )
dt_df['url'] = dt_df['dt'].apply(lambda x: f'{template_url}{x.strftime("%Y-%m-%d")}')
dt_df = dt_df.sort_values('dt',ascending=False)

###Get data 
jobdt = dt_df.query('complete==False').iloc[0]

html = urlopen(jobdt['url']).read().decode('utf-8')





for row in dict(.to_json(orient='records')):


find_max_pages = urlopen(url_domain.replace("#PAGE#",str(1))).read().decode('utf-8')


    region = area_counts['area_sydney'].loc[row]
    bedrooms = area_counts['bedrooms'].loc[row]
    curr_dateid = pd.to_datetime(area_counts['DateID'].loc[row])
    print(region+ '-bedrooms_' + str(bedrooms))
    #
    url_domain = template_url.replace("###AREA_SYDNEY###", region)
    url_domain = url_domain.replace("###BEDS###", bedrooms)
    ## STEP 3: INITIALISE VALUES
    uptodate = False;\
    page_no = np.array(1);\
    total_start = time.time();\
    ## get max page
    try:
        soup = BeautifulSoup(find_max_pages)
        find_max = [x.text for x in soup.findAll("h1")]
        max_page = pd.Series(find_max).str.extract('(\d+), {b} Bedroom'.format(b=bedrooms)).astype(float).max()
        max_page = int(max_page)/20.0
        max_page = 50 if max_page > 50 else int(np.ceil(max_page))
        print('MAX pages is: {}'.format(max_page))
    except :
        print("ERROR: Can't find MAX page")
        continue
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
                html = urlopen(domain_url).read().decode('utf-8')
                # Pull Dates
                date_pattern = '(\d{1,2} \w{3} \d{4})'
                html_dates = pd.Series(re.findall(date_pattern, html))
                html_dates = pd.to_datetime(html_dates, format = '%d %b %Y')
                print('TESTING new_min={dt:s} < old_max={ex:s} '.format(dt=str(html_dates.min()), ex=str(curr_dateid)))
                if html_dates.min() < curr_dateid:
                    uptodate = True
                #
                text_file = open(output_name, "w")
                text_file.write(html)
                text_file.close()
                print("Time taken: --- %s seconds ---" % (time.time() - start))
                time.sleep(np.max([10-(time.time() - start),0]))
    #
    print("Time taken: --- %s seconds ---" % (time.time() - total_start))
    area_counts['complete'].loc[row] = 1
    area_counts.to_csv(updatefile,index=False)
#### END LOOP
