from sklearn.preprocessing import StandardScaler
import pickle
import pandas as pd

def standardise_data(train_data,test_data):
   scaler=StandardScaler()
   train_data_scaled=scaler.fit_transform(train_data)
   test_data_scaled=scaler.transform(test_data)
   test_data_scaled=pd.DataFrame(test_data_scaled,columns=['Map', 'NDVI', 'aspect', 'elevation',
       'max_water_accumulation', 'slope', 'soil_temperature',
       'today_expected_rain', 'today_rain_probability',
       'volumetric_soil_moisture', 'water_accumulation',
       'expected_accumulation', 'TWI'])
   train_data_scaled=pd.DataFrame(train_data_scaled,columns=['Map', 'NDVI', 'aspect', 'elevation',
       'max_water_accumulation', 'slope', 'soil_temperature',
       'today_expected_rain', 'today_rain_probability',
       'volumetric_soil_moisture', 'water_accumulation',
       'expected_accumulation', 'TWI'])
   with open("Scaler.pkl","wb") as file:
      pickle.dump(scaler,file)
   return (train_data_scaled,test_data_scaled)

    



