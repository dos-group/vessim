import requests
import time
import sys

URL = 'http://localhost:8080'
ID = 'XXX111000'
ENDPOINTS = {
            'solar'     :   '/api/solar_power',
            'grid'      :   '/api/grid_power',
            'carbon'    :   '/api/grid_carbon',
            'discharge' :   '/api/battery_discharge_rate',
            'charge'    :   '/api/battery_charge_level',
            'powercap'  :   '/api/container_powercap',
            'power'     :   '/api/container_power'
            }

GET_ENDPOINTS = [
                '/api/solar_power',
                '/api/grid_power',
                '/api/grid_carbon',
                '/api/battery_discharge_rate',
                '/api/battery_charge_level',
]   
#setter
#register container + set powercap 
def set_powercap(cap):
    form = {'container_id' : str(ID),
            'kW' : cap}
    response = requests.post(URL + '/api/container_powercap',data=form)
    return response

#set battery charge rate
def set_battery_charge_rate(rate):
    form = {'kW' : rate}
    respons = requests.post(URL + '/api/battery_charge_level',data=form)
    

#set battery_max_discharge
def set_battery_max_discharge(rate):
    form = {'kW' : rate}
    respons = requests.post(URL + '/api/battery_max_discharge',data=form)
   
   

#getter
def get_data(endpoint):
    response = requests.get(URL + endpoint)
    return response



#get stats evry minute and print out

def main(argv):
    if 'dumb' in argv:
        while True:
            for api in GET_ENDPOINTS:
                response = get_data(api)
                print(str(response.content) + '\n')
            time.sleep(10)
    else:
        set_battery_charge_rate(5)
        set_powercap(500.0)
        i = 0
        while True:
            for api in GET_ENDPOINTS:
                
                response = get_data(api)
                output = str(response.content)
                #output = + str(response.content).split(':')[1] +" "+ str(response.content).rsplit(":",1)[1]
                print(api.rsplit('/',1)[1] + " : " + output + '\n')
                if i == 5:
                    set_battery_charge_rate(10)
                    set_powercap(250)
                if i == 7:
                    set_battery_max_discharge(10)

            time.sleep(10)
            i = i+1

if __name__ == '__main__':
    main(sys.argv[1:])




