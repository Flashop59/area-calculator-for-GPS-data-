import streamlit as st
import pandas as pd
import numpy as np
from shapely.geometry import Polygon
from sklearn.cluster import DBSCAN
from scipy.spatial import ConvexHull
import folium
from streamlit_folium import st_folium
import io
from geopy.distance import geodesic

# Function to calculate the area of a field in square meters using convex hull
def calculate_convex_hull_area(points):
    if len(points) < 3:  # Not enough points to form a polygon
        return 0
    try:
        hull = ConvexHull(points)
        poly = Polygon(points[hull.vertices])
        return poly.area  # Area in square degrees
    except Exception:
        return 0

# Function to calculate geodesic distance
def calculate_distance(coord1, coord2):
    return geodesic(coord1, coord2).meters

# Function to process the uploaded file and return the map and field areas
def process_file(file):
    # Load the CSV file
    gps_data = pd.read_csv(file)

    # Check the columns available
    st.write("Available columns:", gps_data.columns.tolist())
    
    # Use the correct column names
    if 'Timestamp' not in gps_data.columns:
        st.error("The CSV file does not contain a 'Timestamp' column.")
        return None, None, None
    
    gps_data = gps_data[['lat', 'lng', 'Timestamp']]
    
    # Convert Timestamp column to datetime with correct format
    gps_data['Timestamp'] = pd.to_datetime(gps_data['Timestamp'], format='%d-%m-%Y %H.%M', errors='coerce', dayfirst=True)
    
    # Drop rows where conversion failed
    gps_data = gps_data.dropna(subset=['Timestamp'])
    
    # Cluster the GPS points to identify separate fields
    coords = gps_data[['lat', 'lng']].values
    db = DBSCAN(eps=0.00008, min_samples=11).fit(coords)
    labels = db.labels_

    # Add labels to the data
    gps_data['field_id'] = labels

    # Calculate the area for each field
    fields = gps_data[gps_data['field_id'] != -1]  # Exclude noise points
    field_areas = fields.groupby('field_id').apply(
        lambda df: calculate_convex_hull_area(df[['lat', 'lng']].values))

    # Convert the area from square degrees to square meters (approximation)
    field_areas_m2 = field_areas * 0.77 * (111000 ** 2)  # rough approximation

    # Convert the area from square meters to gunthas (1 guntha = 101.17 m^2)
    field_areas_gunthas = field_areas_m2 / 101.17

    # Calculate time metrics for each field
    field_times = fields.groupby('field_id').apply(
        lambda df: (df['Timestamp'].max() - df['Timestamp'].min()).total_seconds() / 60.0
    )
    
    # Filter out fields with area less than 5 gunthas
    valid_fields = field_areas_gunthas[field_areas_gunthas >= 5].index
    field_areas_gunthas = field_areas_gunthas[valid_fields]
    field_times = field_times[valid_fields]

    # Calculate traveling distances and times between fields
    field_transitions = gps_data[gps_data['field_id'].isin(valid_fields)]
    field_transitions = field_transitions.sort_values(by='Timestamp')

    travel_distances = []
    travel_times = []

    prev_row = None
    for idx, row in field_transitions.iterrows():
        if prev_row is not None and row['field_id'] != prev_row['field_id']:
            distance = calculate_distance((prev_row['lat'], prev_row['lng']), (row['lat'], row['lng']))
            time_diff = (row['Timestamp'] - prev_row['Timestamp']).total_seconds() / 60.0
            travel_distances.append(distance)
            travel_times.append(time_diff)
        prev_row = row

    # Combine area, time, and travel data into a single DataFrame
    combined_data = {
        'Field ID': field_areas_gunthas.index,
        'Area (Gunthas)': field_areas_gunthas.values,
        'Time (Minutes)': field_times.values,
        'Travel Distance (Meters)': travel_distances + [None]*(len(field_areas_gunthas) - len(travel_distances)),
        'Travel Time (Minutes)': travel_times + [None]*(len(field_times) - len(travel_times))
    }

    combined_df = pd.DataFrame(combined_data)
    
    # Create a satellite map
    map_center = [gps_data['lat'].mean(), gps_data['lng'].mean()]
    m = folium.Map(location=map_center, zoom_start=12, tiles='Stamen Terrain')

    # Plot the points on the map
    for idx, row in gps_data.iterrows():
        color = 'blue' if row['field_id'] in valid_fields else 'red'  # Blue for fields, red for noise
        folium.CircleMarker(
            location=(row['lat'], row['lng']),
            radius=2,
            color=color,
            fill=True,
            fill_color=color
        ).add_to(m)

    return m, combined_df

# Streamlit app
st.title("Field Area, Time, and Travel Calculation from GPS Data")
st.write("Upload a CSV file with 'lat', 'lng', and 'Timestamp' columns to calculate field areas, travel distances, and visualize them on a satellite map.")

uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

if uploaded_file is not None:
    st.write("Processing file...")
    folium_map, combined_df = process_file(uploaded_file)
    
    if folium_map is not None:
        st.write("Field Areas, Times, and Travel Data:", combined_df)
        st.write("Download the combined data as a CSV file:")
        
        # Provide download link
        csv = combined_df.to_csv(index=False)
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name='field_areas_times_and_travel.csv',
            mime='text/csv'
        )
        
        st_folium(folium_map, width=725, height=500)
    else:
        st.error("Failed to process the file.")
