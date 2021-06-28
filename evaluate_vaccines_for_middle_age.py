#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jun 28 16:13:17 2021

"""
import pandas as pd
import datetime

min_age = 18
max_age = 65

#%%
# download from here https://vaers.hhs.gov/data/datasets.html?
data = pd.read_csv('2021VAERSDATA.csv', encoding = "ISO-8859-1")
symptoms = pd.read_csv('2021VAERSSYMPTOMS.csv', encoding = "ISO-8859-1")
vaccine = pd.read_csv('2021VAERSVAX.csv', encoding = "ISO-8859-1")

# in the US it's Pfizer/Biontech  and Moderna, which are both mRNA vaccines.  
# There will be no separation between these vaccines

#%%
# download from here  https://covidtracking.com/data/download
infections = pd.read_csv('national-history.csv', encoding = "ISO-8859-1")

infections['date'] = pd.to_datetime(infections['date'], 
                                 format='%Y-%m-%d', 
                                 errors='coerce').apply(lambda dt: dt.replace(day=1)).dt.date
relevant_infections = infections[  ( datetime.date(2021, 1,1) <= infections['date'] ) 
								 &( datetime.date(2022, 1,1) > infections['date'] ) ]

# no age differentiation, and this is only WHEN a test was done. This excludes all uncounted infections. 
fatality_rate = infections['death'][0]  / infections['positive'][0]

#%%
# https://data.cdc.gov/Vaccinations/COVID-19-Vaccinations-in-the-United-States-Jurisdi/unsk-b7fc
administrations = pd.read_csv('COVID-19_Vaccinations_in_the_United_States_Jurisdiction.csv', encoding = "ISO-8859-1")
administrations['date'] = pd.to_datetime(administrations['Date'], 
                                 format='%m/%d/%Y', 
                                 errors='coerce').apply(lambda dt: dt.replace(day=1)).dt.date
relevant_administrations = administrations[  ( datetime.date(2021, 1,1) <= administrations['date'] ) 
								 &( datetime.date(2022, 1,1) > administrations['date'] ) ]
relevant_administrations = relevant_administrations[relevant_administrations['MMWR_week'] == 26] 


# sum_administered = relevant_administrations[relevant_administrations['MMWR_week'] == 26] 
sum_administered = sum(relevant_administrations['Administered_Dose1_Recip_18Plus'] - relevant_administrations['Administered_Dose1_Recip_65Plus']  )
# there must be an error because this sum is higher than shown here: https://covid.cdc.gov/covid-data-tracker/#vaccinations

#%%
merged =  pd.merge(data, symptoms, on="VAERS_ID")
merged =  pd.merge(merged, vaccine, on="VAERS_ID")
#%%
filtered =  merged[  (min_age <= merged['AGE_YRS'] )  &   (merged['AGE_YRS'] <max_age)]

count_lived = (filtered[(merged['DIED'] != 'Y')].shape)[0]
count_died = (filtered[(merged['DIED'] == 'Y')].shape)[0]

vaccine_mortality_rate = count_died / sum_administered



#%%




