
### IMPORT Libraries
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
from urllib2 import urlopen
import re
import time
import os
import multiprocessing as mp
import matplotlib.pyplot as plt
import time
import datetime
import math


#dateid = time.strftime("%Y%m%d")
dateid = str(20171104)
print (dateid)

## set directory
output_directory = "/Users/macmac/Documents/Property/20151207 Scape Sydney/"
os.listdir(os.path.dirname(output_directory))

final_dir  = output_directory + '01c Property_DF'
last_dateid = pd.Series(os.listdir(final_dir))
last_dateid = last_dateid.str.extract('(\d{8})',expand=False).astype(float).max().astype(int).astype(str)
print('last Data Scrape: %s' % (last_dateid))

scrape_area_dir =  output_directory + '01a Region href property/' + dateid  + '_realestate.com'
suburb_dir =  output_directory + '01b Suburb_Files/' + dateid +'_realestate.com'

#######################################################################
# Build Master

suburb_files = pd.DataFrame({'suburb':os.listdir(suburb_dir)})
suburb_files['size'] = suburb_files['suburb'].apply(lambda x: os.stat(suburb_dir+'/'+x).st_size)
# filters
suburb_files = suburb_files.query('suburb <> ".DS_Store"  and size > 100')


master_df = pd.DataFrame()
for suburb in suburb_files['suburb'].values:         # suburb = suburb_files.values[0]
    print(suburb)
    suburb_df = pd.read_csv(suburb_dir +'/'+ suburb)
    suburb_df['filename'] = suburb
    #suburb_df = suburb_df.query('details==details')
    master_df = pd.concat([master_df,suburb_df],axis=0,ignore_index=True)


# suburub and postcode
suburb_state = master_df['filename'].str.split('-nsw-',expand=True)
master_df['suburb'] = suburb_state[0]
master_df['postcode'] = suburb_state[1].str.extract('([0-9]{4}).csv').astype(int)


################
## Price
master_df['price'] = master_df['price_str'].str.replace('[$,]','')
master_df['price'] = master_df['price'].apply(lambda x: np.NaN if x == 'Contact agent' else x)

### fix for Range
find_range = master_df['price'].str.contains('Range').fillna(False)
range_str = master_df['price'][find_range].str.split(' ',expand=True).reset_index()
range_str = pd.melt(range_str, id_vars = 'index')
range_str = range_str[range_str['value'].isin(['','-']) ==False]
### create interger
range_str2 = range_str[range_str['value'].str.replace('[a-z ]','').str.len() == range_str['value'].str.len()]
range_str2['value'] = range_str2['value'].astype(int)

### Apply 
master_df['price'][find_range] = range_str2.groupby('index')['value'].median()
master_df['price'] = master_df['price'].astype(float)



pd.crosstab(
            master_df['price'].isnull()
        ,   master_df['price_img'] <> 'missing'
        )


#####################
## TO CSV
master_df.to_csv(final_dir  + '/'+dateid+'_realestate.csv',index=False)









