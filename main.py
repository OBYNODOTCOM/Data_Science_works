import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import calendar
import folium
import time
import math
import branca.colormap as cm
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim

# --- CONFIGURATION -------------------------------------------------
DATA_FILE = 'walmart-sales-dataset-of-45stores.xlsx'   # Walmart sales data file
# ------------------------------------------------------------------

# Set page configuration
st.set_page_config(page_title="Tesco Sales Dashboard", layout="wide")
st.title("🛒 Tesco Sales Data Visualization")
st.markdown("This dashboard presents five different chart types using the Walmart dataset (stores replaced by English city names). If you see errors, ensure the Excel file is present in this folder and update the `DATA_FILE` variable.")

# ------------------------------------------------------------
# Load and prepare data (cached for performance)
# ------------------------------------------------------------
@st.cache_data
def load_data():
    try:
        df = pd.read_excel(DATA_FILE)
    except FileNotFoundError:
        st.error(f"Excel file '{DATA_FILE}' not found. Please add it to this folder and update the `DATA_FILE` variable.")
        st.stop()
    except Exception as e:
        st.error(f"Error loading Excel file: {e}")
        st.stop()
    # Convert Date column to datetime
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    # Ensure numeric columns are actually numbers
    numeric_cols = ['Weekly_Sales', 'Holiday_Flag', 'Temperature', 'Fuel_Price', 'CPI', 'Unemployment']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    # Drop rows where critical numeric data is missing (optional but safe)
    df = df.dropna(subset=numeric_cols)
    # Extract month name for categorical plot
    df['Month'] = df['Date'].dt.month_name()
    # Ensure Store column is string (city names)
    df['Store'] = df['Store'].astype(str)
    return df

df = load_data()

# Sidebar controls
st.sidebar.header("Controls")
cities = sorted(df['Store'].unique())
selected_city = st.sidebar.selectbox("Choose a city for the time‑series chart", cities)

# ------------------------------------------------------------
# 1. Comparing categorical values – average weekly sales per month
# ------------------------------------------------------------
st.header("1. Average Weekly Sales by Month")
st.markdown("This bar chart compares average weekly sales across all months (all stores combined).")

month_order = list(calendar.month_name)[1:]  # January to December
monthly_avg = df.groupby('Month')['Weekly_Sales'].mean().reindex(month_order)

fig1, ax1 = plt.subplots(figsize=(10,5))
monthly_avg.plot(kind='bar', color='skyblue', edgecolor='black', ax=ax1)
ax1.set_title('Average Weekly Sales by Month')
ax1.set_xlabel('Month')
ax1.set_ylabel('Average Weekly Sales ($)')
ax1.grid(axis='y', linestyle='--', alpha=0.7)
plt.xticks(rotation=45)
st.pyplot(fig1)

# ------------------------------------------------------------
# 2. Part‑of‑a‑whole – holiday vs non‑holiday sales
# ------------------------------------------------------------
st.header("2. Holiday vs Non‑Holiday Sales")
st.markdown("This pie chart shows the proportion of total sales occurring during holiday weeks (Holiday_Flag = 1) versus non‑holiday weeks.")

holiday_sales = df.groupby('Holiday_Flag')['Weekly_Sales'].sum()
labels = ['Non-Holiday (0)', 'Holiday (1)']

fig2, ax2 = plt.subplots(figsize=(6,6))
ax2.pie(holiday_sales, labels=labels, autopct='%1.1f%%', startangle=90,
        colors=['lightcoral', 'gold'], explode=(0, 0.1))
ax2.set_title('Total Sales: Holiday vs Non-Holiday Weeks')
ax2.axis('equal')
st.pyplot(fig2)

# ------------------------------------------------------------
# 3. Changes over time – sales and CPI for a selected city
# ------------------------------------------------------------
st.header("3. Sales and CPI Over Time")
st.markdown(f"Time series of weekly sales and Consumer Price Index (CPI) for **{selected_city}**.")

city_data = df[df['Store'] == selected_city].sort_values('Date')

fig3, ax3 = plt.subplots(figsize=(12,5))
color = 'tab:red'
ax3.set_xlabel('Date')
ax3.set_ylabel('Weekly Sales ($)', color=color)
ax3.plot(city_data['Date'], city_data['Weekly_Sales'], color=color, linewidth=1)
ax3.tick_params(axis='y', labelcolor=color)

ax3b = ax3.twinx()
color = 'tab:blue'
ax3b.set_ylabel('CPI', color=color)
ax3b.plot(city_data['Date'], city_data['CPI'], color=color, linewidth=1)
ax3b.tick_params(axis='y', labelcolor=color)

plt.title(f'{selected_city}: Weekly Sales and CPI Over Time')
fig3.tight_layout()
st.pyplot(fig3)

# ------------------------------------------------------------
# 4. Geo‑spatial proxy – fuel price vs total sales per city (interactive map)
# ------------------------------------------------------------
st.header("4. Fuel Price vs Total Sales by City (Map)")
st.markdown("An interactive map of England: bubble markers show total sales by city; color indicates average fuel price.")

city_agg = df.groupby('Store').agg({
    'Weekly_Sales': 'sum',
    'Fuel_Price': 'mean'
}).reset_index()

# Helper: cached geocoding for city names (uses Nominatim)
@st.cache_data
def geocode_cities(city_list):
    geolocator = Nominatim(user_agent="walmart_dashboard")
    coords = {}
    fallback = {
        'London': (51.5074, -0.1278),
        'Manchester': (53.4808, -2.2426),
        'Birmingham': (52.4862, -1.8904),
        'Liverpool': (53.4084, -2.9916),
        'Leeds': (53.8008, -1.5491),
        'Sheffield': (53.3811, -1.4701),
        'Bristol': (51.4545, -2.5879),
        'Newcastle': (54.9783, -1.6178),
        'Nottingham': (52.9548, -1.1581),
        'Southampton': (50.9097, -1.4044),
        'Leicester': (52.6369, -1.1398),
        'Portsmouth': (50.8198, -1.0870),
        'York': (53.9590, -1.0815),
        'Oxford': (51.7520, -1.2577),
        'Cambridge': (52.2053, 0.1218)
    }
    for city in city_list:
        try:
            loc = geolocator.geocode(f"{city}, England, UK", timeout=10)
            if loc:
                coords[city] = (loc.latitude, loc.longitude)
            elif city in fallback:
                coords[city] = fallback[city]
            else:
                coords[city] = None
        except Exception:
            coords[city] = fallback.get(city, None)
        time.sleep(1)  # be polite to Nominatim
    return coords

city_names = city_agg['Store'].tolist()
coords_map = geocode_cities(city_names)

# Map center roughly in England
map_center = [52.3555, -1.1743]
m = folium.Map(location=map_center, zoom_start=6, tiles='CartoDB positron')

# Color scale for fuel price
vmin = float(city_agg['Fuel_Price'].min())
vmax = float(city_agg['Fuel_Price'].max())
colormap = cm.LinearColormap(['green', 'yellow', 'red'], vmin=vmin, vmax=vmax)
colormap.caption = 'Average Fuel Price'
colormap.add_to(m)

for _, row in city_agg.iterrows():
    name = row['Store']
    loc = coords_map.get(name)
    if not loc:
        continue
    lat, lon = loc
    sales = float(row['Weekly_Sales'])
    fuel = float(row['Fuel_Price'])
    # scale marker radius (sqrt scaling for better visual range)
    radius = max(5, math.sqrt(sales) / 200)
    color = colormap(fuel)
    popup_html = f"<b>{name}</b><br>Total Sales: ${int(sales):,}<br>Avg Fuel Price: ${fuel:.2f}"
    folium.CircleMarker(location=(lat, lon), radius=radius,
                        color=color, fill=True, fill_color=color,
                        fill_opacity=0.7, popup=folium.Popup(popup_html, max_width=300)).add_to(m)

# Render the map in Streamlit
st_data = st_folium(m, width=900, height=500)

# ------------------------------------------------------------
# 5. Relationship – temperature vs weekly sales
# ------------------------------------------------------------
st.header("5. Temperature vs Weekly Sales")
st.markdown("Scatter plot with regression line showing the relationship between temperature and weekly sales across all records.")

fig5, ax5 = plt.subplots(figsize=(10,6))
sns.regplot(x='Temperature', y='Weekly_Sales', data=df,
            scatter_kws={'alpha':0.3}, line_kws={'color':'red'}, ax=ax5)
ax5.set_title('Relationship between Temperature and Weekly Sales')
ax5.set_xlabel('Temperature (°F)')
ax5.set_ylabel('Weekly Sales ($)')
ax5.grid(True, linestyle='--', alpha=0.5)
st.pyplot(fig5)

st.markdown("---")
st.markdown(f"**Data source:** Walmart sales dataset (file: `{DATA_FILE}`) with store numbers replaced by English city names. If you encounter errors, check that all required packages are installed and the Excel file is present.")
