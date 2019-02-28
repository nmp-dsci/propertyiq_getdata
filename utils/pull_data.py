
import os
import pandas as pd


def get_hrefs(a):
    href_i = a.split('href="')[1]
    href_i = href_i.split('"')[0]
    return(href_i);\

def last_update(output_directory,dateid):
    ## set directory
    final_dir  = output_directory + '01e Master_DF'
    last_dateid = pd.Series(os.listdir(final_dir))
    last_dateid = last_dateid.str.extract('(\d{8})')
    last_dateid = last_dateid[last_dateid!=dateid]
    last_dateid = last_dateid.astype(float).max().astype(int).astype(str).iloc[0]
    print('last Data Scrape: %s' % (last_dateid))
    return last_dateid


def get_jobs(updatefile, output_directory,last_dateid,sourceid):
    if os.path.exists(updatefile):
        area_counts = pd.read_csv(updatefile)
    else:
        # pull the lasted final dataset for source to get max_dateid
        old_source_df = pd.read_csv(output_directory + '01e Master_DF' + '/'+ last_dateid+'_'+sourceid+'.csv')
        old_source_df['DateID'] = pd.to_datetime(old_source_df['dateID'])
        old_source_df['bedrooms'] = old_source_df['beds'].fillna(0).apply(lambda x: '5' if x > 4 else str(int(x)) )
        old_source_df['bedrooms'].value_counts()
        ####################
        ### Bring in master poa mapping
        poa_sub = pd.read_csv(output_directory+'00 POA_SUBURB.csv')
        oztam_map = pd.read_csv(output_directory+'99 oztam_mapping.csv')
        ## create POA mapping
        poa_sub_focus = pd.merge(poa_sub,oztam_map,on='postcode',how='inner')
        poa_sub_focus['suburb'] = poa_sub_focus['suburb'].str.lower().str.replace(' ','+')
        poa_sub_focus['dummy'] = 1
        ## beds mapping
        beds_df = old_source_df.groupby('bedrooms').size().reset_index().drop(0,axis=1)
        beds_df['dummy'] = 1
        ### full POA * SUBURB
        area_counts = pd.merge(poa_sub_focus,beds_df, on='dummy')
        area_counts['state'] = 'nsw'
        area_counts['postcode'] =area_counts['postcode'].astype(int).astype(str)
        area_counts['area_sydney'] = area_counts.apply(lambda x: '-'.join(x[['suburb','state','postcode']]),axis = 1)
        area_counts['complete'] = np.NaN
        #### Tag max date listing
        old_source_df = old_source_df.query('suburb==suburb&postcode==postcode')
        old_source_df['suburb'] = old_source_df['suburb'].str.lower().str.replace(' ','+')
        old_source_df['postcode'] = old_source_df['postcode'].astype(int).astype(str)
        poa_sub_dateID = old_source_df.groupby(['postcode','suburb','bedrooms'])['DateID'].max().reset_index()
        ## final
        area_counts = pd.merge(
                area_counts
            ,   poa_sub_dateID
            ,   on=['postcode','suburb','bedrooms']
            ,   how='left'
            )
    # 
    return area_counts
        
