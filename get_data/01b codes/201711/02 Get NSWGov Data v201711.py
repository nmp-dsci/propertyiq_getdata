
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
dateid = str(20171104)
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
    ## stet 
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
    time.sleep(0.5)
    print("Time taken: --- %s seconds ---" % (time.time() - start))




#########
### Combine all the street level NSW GOV DATA

listing_directory = output_directory+'02a NSWGov Suburb Level'
suburbs_csv =  np.array(os.listdir(listing_directory))

new = True

# suburbs = suburbs_csv[0]
for suburbs in suburbs_csv:
    print(suburbs)
    
    try:
        suburbs_prices = pd.DataFrame(pd.read_csv(listing_directory + '/' + suburbs))
    except:
        print('no csv info')
        continue
            
    
    if new == True:
        suburbs_nswgov = suburbs_prices
        new = False
    else:
        suburbs_nswgov = suburbs_nswgov.append(suburbs_prices)

# save data frame
output_name = output_directory + '02e nswgov_suburbs_level_201607.csv'
suburbs_nswgov.to_csv(output_name)


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




a = suburb_split_df.apply(lambda x: suburb_split_df.columns[np.where(x)[0][0]] , axis = 1)


#########
### Combine all the street level NSW GOV DATA

listing_directory = output_directory+'02a NSWGov Street Level'

street_csv =  np.array(os.listdir(listing_directory))

new = True

# street = street_csv[0]
for street in street_csv:
    print(street)
    
    try:
        street_prices = pd.DataFrame(pd.read_csv(listing_directory + '/' + street))
    except:
        print('no csv info')
        continue
            
    
    if new == True:
        street_nswgov = street_prices
        new = False
    else:
        street_nswgov = street_nswgov.append(street_prices)

# save data frame
output_name = output_directory + '02e nswgov_street_level.csv'
street_nswgov.to_csv(output_name)


street_nswgov = pd.DataFrame(pd.read_csv(output_directory + '02e nswgov_street_level.csv'))


### Now attach the minimum property level
# 1. if strata = TRUE then need to find property number
# 2.    strata = FALSE then you have property number

multi_dwelling = street_nswgov['ADDRESS'].str.split('/')
street_nswgov['street_num'] = multi_dwelling.apply(lambda x: x[-1])

property_number = pd.DataFrame(pd.pivot_table(street_nswgov,values ='PROPERTY NUMBER', index = 'street_num',aggfunc=np.min  ))
property_number['street_num'] = property_number.index
property_number = property_number.rename(columns={'PROPERTY NUMBER': 'MIN PROPERTY NUMBER'})

street_nswgov = pd.merge(street_nswgov,property_number, on = 'street_num', how= 'left')

x= property_number['street_num'][1]
property_number['STRATA'] = property_number['street_num'].isin(street_nswgov['ADDRESS'])



#### get the property level information

urli = 'http://globe.six.nsw.gov.au/csv/current/property/#ROUNDED#/#PROPERTY_NUM#.csv'

#np.where(property_number['street_num'].str.contains('36 HIGH STREET, NORTH SYDNEY'))
#property_number.iloc[24646,]
# i = range(len(property_number))[1]
for i in range(len(property_number)):
    
    start = time.time()
    
    property_ix = property_number.ix[i]
    min_prop_num = property_ix['MIN PROPERTY NUMBER']
    
    print(property_ix['street_num'])
    
    addr = property_ix['street_num']
    addr = addr.replace(',', '')
    
    output_name = output_directory + '02b NSWGov Property Level/' + addr + '.csv'

    if os.path.exists(output_name):
        continue
       
    ## loop to find multi dwelling household
    n = 0
    while n <= 10 :
        print(n)
        
        try_prop_num = min_prop_num - n
        rounded = str(np.int(np.floor(min_prop_num/1000)*1000))
        while len(rounded) < 8:
            rounded = '0' + rounded
                
        try_url = urli.replace('#PROPERTY_NUM#', str(try_prop_num))
        try_url = try_url.replace('#ROUNDED#', rounded)
        
        try:
            html = urlopen(try_url).read()
        except urllib2.HTTPError:
            print('no html')
        else:
            n = 15
        
        n = n + 1
        
        # single dwelling fix
        if property_ix['STRATA'] == True:
            n = 15    
    
    if n >= 15:      
        text_file = open(output_name, "w")
        text_file.write(html)
        text_file.close()
        
    time.sleep(0.5)
    print("Time taken: --- %s seconds ---" % (time.time() - start))
    
    
    
#########
### Combine all the street level NSW GOV DATA
# increase with 15 year level       233376.0/ 221642-1
# takes 26,210 seconds .. 35 minutes
# takes 52632 (1.5 hrs) for 718,000 rows
listing_directory = output_directory+'02b NSWGov Property Level'

property_csv =  np.array(os.listdir(listing_directory))

start = time.time()

# prop = property_csv[0]
for prop in property_csv:
    print(prop)
    prop_sales = pd.read_csv(listing_directory + '/' + prop)
    prop_sales = pd.DataFrame(prop_sales)
    
    if prop == property_csv[0]:
        property_nswgov = prop_sales
    else:
        property_nswgov = property_nswgov.append(prop_sales)

print("Time taken: --- %s seconds ---" % (time.time() - start))

property_nswgov['SALE DATE'] = pd.to_datetime(property_nswgov['SALE DATE'], format="%d %B %Y")


# remove duplicates
property_nswgov['nswgov_index']= property_nswgov.apply(lambda x:
    'nswgov-' + str(x['PROPERTY NUMBER'] )+ "-" + x['SALE DATE'].strftime("%d %b %Y"), 
        axis = 1)

nswgov_dups = property_nswgov['nswgov_index'].value_counts()

property_nswgov.loc[property_nswgov['nswgov_index'] == 'nswgov-3859274-24 Jul 2013',]

### time taken 
start = time.time()

# x = nswgov_dups.index[1]
first_obs = pd.Series(nswgov_dups.index).apply(lambda x:
        np.where(property_nswgov['nswgov_index'] == x)[0][0])

print("Time taken: --- %s seconds ---" % (time.time() - start))

# Check things worked
len(np.unique(property_nswgov['nswgov_index']))
len(property_nswgov['nswgov_index'].iloc[first_obs ])


property_nswgov = property_nswgov.iloc[first_obs , ]
property_nswgov.index = property_nswgov['nswgov_index']





# save data frame
output_name = output_directory + '02f nswgov_property_level.csv'
property_nswgov.to_csv(output_name)


#### amalgamation of different geo scraping level




## Get property info
property_nswgov = pd.read_csv(output_directory + '02f nswgov_property_level.csv')
property_nswgov = pd.DataFrame(property_nswgov)
property_nswgov['update'] = 0
property_nswgov['SALE DATE'] = pd.to_datetime(property_nswgov['SALE DATE'], format="%Y-%m")

suburbs_nswgov = pd.DataFrame(pd.read_csv(output_directory + '02e nswgov_suburbs_level_201607.csv'))
suburbs_nswgov['update'] = 1
suburbs_nswgov['SALE DATE'] = pd.to_datetime(suburbs_nswgov['SALE DATE'], format="%d %B %Y")

### Append suburb run
property_nswgov = property_nswgov.append(suburbs_nswgov)

# x= property_nswgov['ADDRESS'].iloc[1]
property_nswgov['POSTCODE'] = property_nswgov['ADDRESS'].apply(lambda x: 
        x.split(" ")[len(x.split(" "))-1])

## check, should all be 4
property_nswgov['POSTCODE'].str.len().value_counts()
property_nswgov = property_nswgov.loc[property_nswgov['POSTCODE'].str.len() == 4,]

## Get Suburb
property_nswgov['SUBURB'] = property_nswgov['ADDRESS'].str.split(',',expand = True)[1]
property_nswgov['SUBURB'] = property_nswgov['SUBURB'].str.split("NSW",expand=  True)[0]
property_nswgov['SUBURB'] = property_nswgov['SUBURB'].str.strip()

### Find dups
print(property_nswgov.shape)            # 201607: 1,592,681

property_nswgov = property_nswgov.sort(['SALE DATE','PROPERTY NUMBER'])

property_nswgov['dup_flag'] = np.where(
    np.append(np.array([1]),np.diff(property_nswgov['PROPERTY NUMBER'])) <> 0,
    0,1)

property_nswgov['dup_flag'].value_counts()

property_nswgov = property_nswgov.loc[property_nswgov['dup_flag'] == 0, ]

print(property_nswgov.shape)            # 201607: 1,313,549


output_name = output_directory + '02f nswgov_property_level_201607.csv'
property_nswgov.to_csv(output_name)


### CREATE THE MERGE FILE

nswgov_df  = property_nswgov

nswgov_df['hhd_id'] = nswgov_df['PROPERTY NUMBER']
nswgov_df['sale_date'] = nswgov_df['SALE DATE']
nswgov_df['source'] = 'nswgov'
nswgov_df['state'] = 'nsw'

### GET ADDRESS
find_number = nswgov_df['ADDRESS'].str.split(" ",expand = True)

## this needs to be zero, i.e. no numbers in 2nd split
(find_number[1].str.len() - find_number[1].str.replace('0-9',"").str.len()).value_counts()

nswgov_df['addr'] = find_number[0]
nswgov_df['addr'] = nswgov_df['addr'].str.replace("[^A-Za-z0-9]", "-")

### GET STREET
find_street = nswgov_df['ADDRESS'].str.split(",", expand = True)
find_street = find_street[0].str.split(" ",expand = True)

#x= find_street[[1,2,3,4,5]].iloc[1]
find_street = find_street[[1,2,3,4,5]].apply(lambda x: "-".join(x[pd.notnull(x)]), axis = 1)
nswgov_df['street'] = find_street

nswgov_df = nswgov_df.rename(columns = {'POSTCODE':'postcode','SUBURB':'suburb',
                                        'SALE DATE':'sale_date'})

nswgov_df = nswgov_df[['addr','hhd_id','postcode','sale_date','source','state','street','suburb']]


output_name = output_directory + '02h nswgov_property_info_201607.csv'
nswgov_df.to_csv(output_name)



# nswgov_df = pd.read_csv(output_name)

nswgov_df['sale_date'].iloc[:,1].apply(lambda x: x.year).value_counts()
nswgov_df['sale_date'].iloc[:,1].apply(lambda x: x[:4]).value_counts()








