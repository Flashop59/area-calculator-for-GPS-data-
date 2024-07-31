import streamlit as st
import pandas as pd
import numpy as np
from shapely.geometry import Polygon
from sklearn.cluster import DBSCAN
from scipy.spatial import ConvexHull
import folium
from folium import plugins
from streamlit_folium import st_folium
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

# Function to process the uploaded file and return the map and field areas
def process_file(file):
    try:
        # Load the CSV file
        gps_data = pd.read_csv(file)
        
        # Check the columns available
        if 'Timestamp' not in gps_data.columns:
            st.error("The CSV file does not contain a 'Timestamp' column.")
            return None, None
        
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
        if fields.empty:
            st.error("No fields detected. Please check your data.")
            return None, None
        
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

        # Extract start and end dates for each field
        field_dates = fields.groupby('field_id').agg(
            start_date=('Timestamp', 'min'),
            end_date=('Timestamp', 'max')
        )

        # Filter out fields with area less than 5 gunthas
        valid_fields = field_areas_gunthas[field_areas_gunthas >= 5].index
        field_areas_gunthas = field_areas_gunthas[valid_fields]
        field_times = field_times[valid_fields]
        field_dates = field_dates.loc[valid_fields]

        if field_dates.empty:
            st.error("No valid fields with sufficient area found.")
            return None, None

        # Identify red points (noise)
        noise_points = gps_data[gps_data['field_id'] == -1]

        # Calculate distances and times
        distances = []
        times = []

        # Calculate distance and time from red points to nearest field start
        for idx, red_point in noise_points.iterrows():
            nearest_field_start = fields.groupby('field_id').first().reset_index()
            distances_to_fields = [geodesic((red_point['lat'], red_point['lng']), (row['lat'], row['lng'])).meters
                                   for idx, row in nearest_field_start.iterrows()]
            times_to_fields = [(nearest_field_start.iloc[i]['start_date'] - red_point['Timestamp']).total_seconds() / 60.0
                               for i in range(len(nearest_field_start))]

            min_distance_index = np.argmin(distances_to_fields)
            distances.append(distances_to_fields[min_distance_index])
            times.append(times_to_fields[min_distance_index])

        # Append NaNs for the last field
        distances.append(np.nan)
        times.append(np.nan)

        # Include distance and time for reaching from the start to the first field
        if not fields.empty:
            first_field = fields.groupby('field_id').first().reset_index()
            start_point = gps_data.iloc[0]
            distances = [geodesic((start_point['lat'], start_point['lng']), (first_field.iloc[0]['lat'], first_field.iloc[0]['lng'])).meters] + distances
            times = [(first_field.iloc[0]['start_date'] - start_point['Timestamp']).total_seconds() / 60.0] + times

        # Calculate travel distance and time between fields
        field_ids = list(valid_fields)
        for i in range(len(field_ids) - 1):
            end_point = fields[fields['field_id'] == field_ids[i]][['lat', 'lng']].values[-1]
            start_point = fields[fields['field_id'] == field_ids[i + 1]][['lat', 'lng']].values[0]
            distance = geodesic(end_point, start_point).meters
            time = (field_dates.loc[field_ids[i + 1], 'start_date'] - field_dates.loc[field_ids[i], 'end_date']).total_seconds() / 60.0
            distances.append(distance)
            times.append(time)

        distances.append(np.nan)  # No travel distance for the last field
        times.append(np.nan)  # No travel time for the last field

        # Ensure lengths match
        total_points = len(valid_fields) + len(noise_points) + 1
        if len(distances) < total_points:
            distances.extend([np.nan] * (total_points - len(distances)))
        if len(times) < total_points:
            times.extend([np.nan] * (total_points - len(times)))

        # Combine area, time, dates, and travel metrics into a single DataFrame
        combined_df = pd.DataFrame({
            'Field ID': list(valid_fields) + ['Total'],
            'Area (Gunthas)': list(field_areas_gunthas.values) + [np.nan],
            'Time (Minutes)': list(field_times.values) + [np.nan],
            'Start Date': list(field_dates['start_date'].values) + [np.nan],
            'End Date': list(field_dates['end_date'].values) + [np.nan],
            'Travel Distance to Field (meters)': distances,
            'Travel Time to Field (minutes)': times
        })

        # Create a satellite map
        map_center = [gps_data['lat'].mean(), gps_data['lng'].mean()]
        m = folium.Map(location=map_center, zoom_start=12)
        
        # Add Mapbox satellite imagery
        mapbox_token = 'pk.eyJ1IjoiZmxhc2hvcDAwNyIsImEiOiJjbHo5NzkycmIwN2RxMmtzZHZvNWpjYmQ2In0.A_FZYl5zKjwSZpJuP_MHiA'
        folium.TileLayer(
            tiles='https://api.mapbox.com/styles/v1/mapbox/satellite-v9/tiles/256/{z}/{x}/{y}?access_token=' + mapbox_token,
            attr='Mapbox Satellite Imagery',
            name='Satellite',
            overlay=True,
            control=True
        ).add_to(m)
        
        # Add fullscreen control
        plugins.Fullscreen(position='topright').add_to(m)

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

    except Exception as e:
        st.error(f"An error occurred: {e}")
        return None, None

# Streamlit app
st.title("Field Area and Time Calculation from GPS Data")
st.write("Upload a CSV file with 'lat', 'lng', and 'Timestamp' columns to calculate field areas and visualize them on a satellite map.")

# Initialize session state variables
if 'uploaded_file' not in st.session_state:
    st.session_state.uploaded_file = None

if 'combined_df' not in st.session_state:
    st.session_state.combined_df = None

if 'folium_map' not in st.session_state:
    st.session_state.folium_map = None

uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

if uploaded_file is not None:
    st.session_state.uploaded_file = uploaded_file
    st.write("Processing file...")
    st.session_state.folium_map, st.session_state.combined_df = process_file(uploaded_file)

if st.session_state.folium_map is not None and st.session_state.combined_df is not None:
    st.write("Field Areas, Times, Dates, and Travel Metrics:", st.session_state.combined_df)
    st.write("Download the combined data as a CSV file:")
    
    # Provide download link
    csv = st.session_state.combined_df.to_csv(index=False)
    st.download_button(
        label="Download CSV",
        data=csv,
        file_name='field_areas_times_dates_and_travel_metrics.csv',
        mime='text/csv'
    )
    
    st_folium(st.session_state.folium_map, width=725, height=500)
