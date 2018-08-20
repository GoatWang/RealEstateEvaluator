import os
import requests
import json
from math import sin, cos, sqrt, atan2, radians
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
from pymongo import MongoClient
import xgboost
from RealEstateEvaluator import settings

client = MongoClient()
db = client['RealEstate']

from RealEstateEvaluator import settings

def geoencode(address):
    g_api_key = settings.GOOGLEMAPAPIKEY
    url = 'https://maps.googleapis.com/maps/api/geocode/json?address=' + address + '&key=' + g_api_key + '&language=zh-TW'
    res = requests.get(url)
    res = json.loads(res.text)

    status = res['status']
    if status == "OK":
        result = res['results'][0]
        geometry = result['geometry']
        lng = geometry['location']['lng']
        lat = geometry['location']['lat']
        return (lng, lat)
    else:
        return None

def cal_distance(point1, point2):
    R = 6373.0
    lat1 = radians(point1[1])
    lon1 = radians(point1[0])
    lat2 = radians(point2[1])
    lon2 = radians(point2[0])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    distance = R * c
    return distance * 1000

def get_nearest_tarin_station_and_distance(lng, lat):
    assert pd.notnull(lng), "lng should not be null"
    query_loc =[lng, lat]
    query = { "loc" :{ "$near" : query_loc}} 
    collection = db.TrainStation
    station = collection.find_one(query)
    station_loc = station['loc']
    return {"name":station['station_name'], "distance":cal_distance(query_loc, station_loc)}

def find_county(lng, lat):
    assert pd.notnull(lng), "lng should not be null"
    collection = db.CountyCoverage
    point = [lng, lat]
    query = { "loc" :
                { "$geoIntersects" :
                { "$geometry" :
                    { "type" : "Point" ,
                    "coordinates" : point
            } } } } 
    county = collection.find_one(query)['name']
    return county

def find_village(lng, lat):
    assert pd.notnull(lng), "lng should not be null"
    collection = db.VillageCoverage
    point = [lng, lat]
    query = { "loc" :
                { "$geoIntersects" :
                { "$geometry" :
                    { "type" : "Point" ,
                    "coordinates" : point
            } } } } 
    village = collection.find_one(query)['VILLNAME']
    return village

def find_bus_stations_in_100m(lng, lat, meters):
    assert pd.notnull(lng), "lng should not be null"
    collection = db.BusStation
    point = [lng, lat]
    query = { "loc" :
         { "$near" :
           { "$geometry" :
              { "type" : "Point" ,
                "coordinates" : point} ,
             "$maxDistance" : meters
      } } }
    bus_stations = [c for c in collection.find(query)]
    return bus_stations

def find_nearest_n_points(lng, lat, n):
    collection = db.RealEstate
    assert pd.notnull(lng), "lng should not be null"
    point = [lng, lat]
    current_date = datetime.now()
    query = {
        "$and":[
            {'date':{"$gt":datetime(year=current_date.year-1911, month=current_date.month, day=current_date.day)-timedelta(500)}},
            { "loc" :
                    { "$near" :
                    { "$geometry" :
                        { "type" : "Point" ,
                        "coordinates" : point} ,
                } } }
        ]
    }
    cursor = collection.find(query).limit(n)
    df_nearest_points = pd.DataFrame([c for c in cursor])
    df_nearest_points['coordinates'] = df_nearest_points['loc'].apply(lambda x:x['coordinates'])
    avg_price = np.average(df_nearest_points['price'].values)
    df_nearest_points['dists'] = df_nearest_points['coordinates'].apply(lambda x: cal_distance(point, x))
    df_nearest_points['date'] = df_nearest_points['date'].apply(lambda x:str(x.year) + "-" + str(x.month)  + "-" + str(x.day))
    return {
        "nearest_points":df_nearest_points.to_dict(orient="records"),
        "avg_price":avg_price
    }

def find_avg_income(county, village):
    collection = db.AvgIncome
    avg_income = collection.find_one({'county':county, 'village':village})['income_avg']
    return avg_income

def find_low_use_electricity_rate(county, village):
    collection = db.LowUseElectricity
    low_use_electricity_rate = collection.find_one({'county':county, 'village':village})['low_use_electricity']
    return low_use_electricity_rate

def xgb_evaluate(params, total_area_m2):
    bst = xgboost.Booster({'nthread':1}) #init model
    bst.load_model(os.path.join(settings.BASE_DIR, "evaluator", "models", "bst_subtotal_log.pickle.dat")) # load data
    price = np.exp(bst.predict(xgboost.DMatrix(params))) / total_area_m2
    return price 


