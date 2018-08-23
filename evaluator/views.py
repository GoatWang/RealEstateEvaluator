from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.template import loader
from django.views.decorators.csrf import csrf_exempt
from evaluator.utl import geoencode, find_county, find_village, get_nearest_tarin_station_and_distance, find_bus_stations_in_100m, find_nearest_n_points, find_avg_income, find_low_use_electricity_rate, xgb_evaluate
import pandas as pd
import numpy as np

def index(request):
    template = loader.get_template('evaluator/index_eng.html')
    context = {}
    return HttpResponse(template.render(context, request))

@csrf_exempt
def evaluate(request):
    if request.method == "POST":
        post_data = request.POST
        address = post_data['address']
        total_area_m2 = float(post_data['total_area_m2'])
        house_year = int(post_data['house_year'])
        usage = post_data['usage']
        building_type = post_data['building_type']
        building_material = post_data['building_material']
        having_origanizational_management = post_data['having_origanizational_management'] == 'true'
        having_compartment = post_data['having_compartment'] == 'true'
        haveing_addition = post_data['haveing_addition'] == 'true'

        lng, lat = geoencode(address)
        station_and_distance = get_nearest_tarin_station_and_distance(lng, lat)
        station = station_and_distance['name']
        station_distance = station_and_distance['distance']
        bus_stations = find_bus_stations_in_100m(lng, lat, 100)
        num_bus_stations = len(bus_stations)
        nearest_points_obj = find_nearest_n_points(lng, lat, 8)
        nearest_points = nearest_points_obj['nearest_points']
        avg_price = nearest_points_obj['avg_price']

        county = find_county(lng, lat).replace("臺北市", "")
        village = find_village(lng, lat)
        avg_income = find_avg_income(county, village)
        low_use_electricity_rate = find_low_use_electricity_rate(county, village)

        cols = ['total_area_m2', 'house_year', 'have_manager', 'current_division', 'have_added_building',
       'is_for_household', 'is_for_business', 'is_resirential_building', 'is_Huaxia',
       'is_apartment', 'is_business_office', 'is_store', 'is_suite',
       'is_through_sky', 'is_factory', 'is_made_of_brick', 'is_made_of_RC',
       'Dummy_Wenshan', 'Dummy_Zhongzheng', 'Dummy_Wanhua', 'Dummy_Datong', 'Dummy_Zhongshan', 'Dummy_Neihu',
       'Dummy_Songshan', 'Dummy_Xinyi', 'Dummy_Nangang', 'Dummy_Beitou', 'Dummy_Shilin',
       'income_avg', 'nearest_tarin_station_distance', 'num_of_bus_stations_in_100m', 'nearest_point_avg_price']
        params = pd.Series(index=cols, data=np.zeros(len(cols)))

        # other
        params['total_area_m2'] = total_area_m2
        params['house_year'] = house_year
        params['have_manager'] = having_origanizational_management
        params['current_division'] = having_compartment
        params['have_added_building'] = haveing_addition
        params['have_added_building'] = haveing_addition
        
        # usage
        params['is_for_household'] = 1 if usage == "For Living" else 0
        params['is_for_business'] = 1 if usage == "For Business" else 0

        # building type
        building_type_code = int(building_type.split(".")[0])
        building_type_code_mapping = {
            1:'is_resirential_building', 
            2:'is_Huaxia',
            3:'is_apartment', 
            4:'is_through_sky',
            5:'is_business_office',
            6:'is_store', 
            7:'is_suite',
            8:'is_factory', 
        }
        if building_type_code != 9:
            params[building_type_code_mapping.get(building_type_code)] = 1

        # material 
        params['is_made_of_RC'] = 1 if building_material == "RC (Reinforced Concrete)" else 0
        params['is_made_of_brick'] = 1 if building_material == "Brick" else 0

        # district dummy
        params['Dummy_Wenshan'] = 1 if "文山" in county else 0
        params['Dummy_Zhongzheng'] = 1 if "中正" in county else 0
        params['Dummy_Wanhua'] = 1 if "萬華" in county else 0
        params['Dummy_Datong'] = 1 if "大同" in county else 0
        params['Dummy_Zhongshan'] = 1 if "中山" in county else 0
        params['Dummy_Neihu'] = 1 if "內湖" in county else 0
        params['Dummy_Songshan'] = 1 if "松山" in county else 0
        params['Dummy_Xinyi'] = 1 if "信義" in county else 0
        params['Dummy_Nangang'] = 1 if "南港" in county else 0
        params['Dummy_Beitou'] = 1 if "北投" in county else 0
        params['Dummy_Shilin'] = 1 if "士林" in county else 0

        # other 
        params['income_avg'] = avg_income
        params['nearest_tarin_station_distance'] = station_distance
        params['num_of_bus_stations_in_100m'] = num_bus_stations
        params['nearest_point_avg_price'] = avg_price
        print(params)

        price = xgb_evaluate(list(params), total_area_m2)
        return JsonResponse({
            "price":int(price[0] / 0.3025),
            "station_distance":int(station_distance),
            "num_bus_stations":int(num_bus_stations),
            "avg_income":int(avg_income),
            "avg_price":int(avg_price / 0.3025)
        })