
####################
#
#   PURPOSE: GET NSW GOVERMENT DATA
#
#   DATE: 2015-12-20
#
#   STEPS
#       1.
#       2.
#       3.
#       4.
#       5.
#
#####################


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
dateid = str(20171231)
print (dateid)

## set directory
output_directory = "/Users/macmac/Documents/Property/20151207 Scape Sydney/"
os.listdir(os.path.dirname(output_directory))

final_dir  = output_directory + '01c Property_DF'
last_dateid = pd.Series(os.listdir(final_dir))
last_dateid = last_dateid[~last_dateid.str.contains(dateid)]
last_dateid = last_dateid.str.extract('(\d{8})',expand=False).astype(float).max().astype(int).astype(str)
print('last Data Scrape: %s' % (last_dateid))

suburb_dir =  output_directory + '01b Suburb_Files/' + dateid +'_nswgov'
if os.path.exists(suburb_dir) ==False:
    os.mkdir(suburb_dir)


### Get DATA
base_df = pd.read_csv(final_dir+'/'+ last_dateid+'_domain.csv')
# suburubs to pull data for
suburbs = base_df.groupby(['postcode','suburb']).size().reset_index()
suburbs['suburb'] = suburbs['suburb'].str.replace('-','%20').str.upper()

##### LOOP THROUGH NSW data POSTCODE LEVEL
nswgov_url = 'http://globe.six.nsw.gov.au/PropertySales/PropertySales.html?type=suburb&postcode=#POSTCODE#&suburb=#SUBURB#'
nswgov_url = 'http://maps.six.nsw.gov.au/csv/current/suburb/#SUBURB#_#POSTCODE#.csv'



## got 8059 but there will be blanks
for row in suburbs.index.values:       # row =  suburbs.index.values[0]
    start = time.time()
    print(row)
    # street_info = suburbs.index[4]
    ### Set the Street data to be insert into URL
    postcodei = suburbs['postcode'].loc[row]
    suburbi = suburbs['suburb'].loc[row]
    ## IF street data already exists next
    output_name = suburb_dir+'/'+ str(postcodei) + '-' + suburbi.replace("%20", "_")  + '.csv'
    if os.path.exists(output_name)==False:
        urli = nswgov_url.replace('#POSTCODE#',str(postcodei))
        urli = urli.replace('#SUBURB#',suburbi)
        ## pull URL 
        try:
            html = urlopen(urli).read()
        except :
            #time.sleep(0.5)
            continue
        text_file = open(output_name, "w")
        text_file.write(html)
        text_file.close()
        time.sleep(0.25)
        print("Time taken: --- %s seconds ---" % (time.time() - start))




#########
### Combine all the street level NSW GOV DATA

suburbs_csv =  np.array(os.listdir(suburb_dir))

new = True

# suburbs = suburbs_csv[0]
for suburbs in suburbs_csv:
    print(suburbs)
    
    try:
        suburbs_prices = pd.DataFrame(pd.read_csv(suburb_dir + '/' + suburbs))
    except:
        print('no csv info')
        continue
            
    
    if new == True:
        suburbs_nswgov = suburbs_prices
        new = False
    else:
        suburbs_nswgov = suburbs_nswgov.append(suburbs_prices)

# save data frame


suburbs_nswgov = pd.DataFrame(pd.read_csv(output_directory + '02e nswgov_suburbs_level_201607.csv'))





##### LOOP THROUGH NSW data STREET LEVEL
nswgov_url = 'http://globe.six.nsw.gov.au/csv/current/street/#SUBURB#_#POSTCODE#/#STREET#_#SUBURB#_#POSTCODE#.csv'

# all unique combinations
streets = domain_df.groupby(['postcode','suburb','street_v2']).count()
streets = pd.DataFrame(streets)


### how many streets in a suburb
streets.loc[streets.index.get_level_values('postcode')== 2126,]
streets.loc[streets.index.get_level_values('postcode')== 2126,].shape

streets.loc[streets.index.get_level_values('postcode')== 2060,]
streets.loc[streets.index.get_level_values('postcode')== 2060,].shape


streets.loc[(streets.index.get_level_values('postcode')== 2126) &\
            (streets.index.get_level_values('street_v2').str.contains('green')) ,]

    

# street_info = streets.index[0]

## got 8059 but there will be blanks
for street_info in streets.index:
    
    start = time.time()

    print(street_info)
    # street_info = streets.index[4]
    ### Set the Street data to be insert into URL
    postcodei = str(street_info[0])
    
    suburbi = street_info[1]
    suburbi = suburbi.replace("-",'%20').upper()
    
    streeti = street_info[2]
    streeti = streeti.replace("-",'%20').upper()
    
    ## IF street data already exists next
    output_name = output_directory + '02a NSWGov Street Level/'+ postcodei.replace("%20", "_") + '-' + suburbi.replace("%20", "_") + '-' + streeti.replace("%20", "_") + '.csv'
    if os.path.exists(output_name):
        continue
    
    urli = nswgov_url.replace('#POSTCODE#',postcodei)
    urli = urli.replace('#SUBURB#',suburbi)
    urli = urli.replace('#STREET#',streeti)
        
    try:
        html = urlopen(urli).read()
    except :
        #time.sleep(0.5)
        continue
    
    text_file = open(output_name, "w")
    text_file.write(html)
    text_file.close()
    
    time.sleep(0.5)
    print("Time taken: --- %s seconds ---" % (time.time() - start))








