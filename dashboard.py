import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import glob
import os
import upsldcscrap  # Import the new scraper
import availabilitywithoutselenium


# --- Configuration & Styling ---
st.set_page_config(layout="wide", page_title="Power Management Cell EPM")

# --- Download Latest Availability Report ---
with st.spinner('Checking for latest availability report...'):
    file_path, msg = availabilitywithoutselenium.download_report()
    if file_path:
        st.success(f"Latest report downloaded: {file_path}")
    else:
        st.error(f"Failed to download report: {msg}")

# Global Green/Black Theme with White Borders
st.markdown("""

    <style>
    /* Main Background */
    .stApp {
        background-color: #000000;
        color: #00FF00;
    }
    
    /* Text Coloring for all text elements */
    h1, h2, h3, h4, h5, h6, p, label, span, div {
        color: #00FF00 !important;
        font-family: 'Courier New', Courier, monospace; 
    }
    
    /* Metrics Styling */
    div[data-testid="stMetricValue"] {
        color: #00FF00 !important;
    }
    div[data-testid="stMetricLabel"] {
        color: #00FF00 !important;
    }
    
    /* Table Styling - Global override for dataframe container */
    div[data-testid="stDataFrame"] {
        background-color: #000000 !important;
        border: 1px solid #FFFFFF !important; /* White Border */
    }
    
    /* Input/Slider Styling */
    div[data-baseweb="slider"] {
        color: #00FF00;
    }
    
    /* Expander Styling */
    .streamlit-expanderHeader {
        color: #00FF00 !important;
        background-color: #000000 !important;
        border: 1px solid #FFFFFF !important;
    }
    
    </style>
    """, unsafe_allow_html=True)

# --- Availability Data Processing ---
def load_availability_data():
    today_str = datetime.now().strftime("%Y-%m-%d")
    expected_file = f"Availability_Report_{today_str}.csv"
    files = sorted(glob.glob("Availability_Report_*.csv"), reverse=True)
    
    if not files:
        return None
    
    file_path = expected_file if os.path.exists(expected_file) else files[0]
    
    try:
        df = pd.read_csv(file_path, on_bad_lines='skip')
        return df
    except Exception as e:
        st.error(f"Error reading availability file: {e}")
        return None

def process_data(df, selected_block):
    block_df = df[df['Time Block'] == selected_block].copy()
    
    # Ensure Volume/Prices are numeric
    block_df['Volume'] = pd.to_numeric(block_df['Volume'], errors='coerce').fillna(0)
    
    # --- FILTER: CONSIDER ONLY MERIT PLANTS ---
    # We filter the raw block data where Dispatch Type is 'Merit'.
    if 'Dispatch Type' in block_df.columns:
        block_df = block_df[block_df['Dispatch Type'] == 'Merit'].copy()
    
    # Pivot logic
    dc_df = block_df[block_df['Type'] == 'DC'][['Plant Name', 'Volume', 'VC_Price', 'Category']].copy()
    dc_df = dc_df.rename(columns={'Volume': 'DC'})
    dc_df = dc_df.set_index('Plant Name')
    
    sg_df = block_df[block_df['Type'] == 'SG'][['Plant Name', 'Volume']].copy()
    sg_df = sg_df.rename(columns={'Volume': 'SG'})
    sg_df = sg_df.set_index('Plant Name')
    
    combined = dc_df.join(sg_df, how='outer')
    combined['DC'] = combined['DC'].fillna(0)
    combined['SG'] = combined['SG'].fillna(0)
    
    # Filter: Remove DC = 0
    combined = combined[combined['DC'] > 0].copy()
    
    combined['DC-SG'] = combined['DC'] - combined['SG']
    
    combined = combined.reset_index()
    
    # Categorization
    def apply_category(row):
        plant = str(row['Plant Name']).lower()
        original_cat = str(row['Category']).lower() if 'Category' in row and pd.notna(row['Category']) else ""
        
        if 'khurja' in plant: return 'State'
        if 'nuppl' in plant: return 'State'
        
        if 'ipp' in original_cat: return 'State'
        if 'uprvunl' in original_cat: return 'State'
        if 'state' in original_cat: return 'State'
        
        if 'isgs' in original_cat: return 'Central'
        if 'gna' in original_cat: return 'Central'
        if 'central' in original_cat: return 'Central'
        
        return 'Central'

    combined['Category'] = combined.apply(apply_category, axis=1)
    
    # Sorting
    combined['VC_Price'] = pd.to_numeric(combined['VC_Price'], errors='coerce').fillna(0)
    combined = combined.sort_values(by='VC_Price', ascending=False)
    
    # Thermal Backing Logic
    # if SG < 0.98 * DC -> BACKED, else FULL
    def get_status(row):
        try:
            if float(row['SG']) < (0.98 * float(row['DC'])):
                return 'BACKED'
        except:
            pass
        return 'FULL'
    
    combined['THERMAL BACKING STATUS'] = combined.apply(get_status, axis=1)
    
    return combined

def calculate_backing_metrics(processed_df):
    stats = {}
    for cat in ['State', 'Central']:
        cat_df = processed_df[processed_df['Category'] == cat]
        
        # Cumulative Backing Quantum: Sum(DC - SG) for ALL plants in category (filtered by Merit globally)
        cumulative_backing = cat_df['DC-SG'].sum()
        stats[f'{cat}_Quantum'] = cumulative_backing
        
        # Identify Lowest VC Backed Plant
        backed_plants = cat_df[cat_df['THERMAL BACKING STATUS'] == 'BACKED']
        if not backed_plants.empty:
            # Sort by VC Price Ascending (Lowest VC)
            lowest_vc_plant = backed_plants.sort_values(by='VC_Price', ascending=True).iloc[0]
            stats[f'{cat}_Backing_Plant'] = lowest_vc_plant['Plant Name']
        else:
            stats[f'{cat}_Backing_Plant'] = "None"
            
    return stats

# --- Main App ---

st.title("Power Management Cell EPM")

# --- Load Data & Process First (For Backing Metrics) ---
df = load_availability_data()
selected_df = None
selected_block_name = ""
backing_stats = {'State_Backing_Plant': 'N/A', 'State_Quantum': 0, 'Central_Backing_Plant': 'N/A', 'Central_Quantum': 0}

if df is not None:
    unique_blocks = df['Time Block'].unique()
    try:
        unique_blocks = sorted(unique_blocks, key=lambda x: x.split('-')[0])
    except:
        pass
        
    if len(unique_blocks) > 0:
        selected_block_name = st.select_slider(
            "Select Time Block (HH:mm)",
            options=unique_blocks,
            value=unique_blocks[0]
        )
        
        selected_df = process_data(df, selected_block_name)
        backing_stats = calculate_backing_metrics(selected_df)
    else:
        st.error("No time blocks found in data file.")

# --- Top Section: Demand & Backing Overview ---
try:
    demand_data = upsldcscrap.get_ups_data()
except Exception as e:
    # st.error(f"Error loading demand logic: {e}")
    demand_data = None

if demand_data:
    st.markdown("### Grid Demand Overview")
    cols = st.columns(8)
    
    with cols[0]: st.metric("Demand", demand_data.get('DEMAND_MW', 'N/A'))
    with cols[1]: st.metric("Schedule", demand_data.get('SCHEDULE_MW', 'N/A'))
    with cols[2]: st.metric("Drawl", demand_data.get('DRAWL_MW', 'N/A'))
    with cols[3]: st.metric("OD/UD", demand_data.get('OD_UD', 'N/A'))
    
    with cols[4]: st.metric("State Backing", backing_stats.get('State_Backing_Plant', 'None'))
    with cols[5]: st.metric("State Quantum", f"{backing_stats.get('State_Quantum', 0):.0f}")
    with cols[6]: st.metric("Cntrl Backing", backing_stats.get('Central_Backing_Plant', 'None'))
    with cols[7]: st.metric("Cntrl Quantum", f"{backing_stats.get('Central_Quantum', 0):.0f}")

    st.markdown("---")
else:
    st.warning("Could not fetch live demand data from UPSLDC.")

# --- Table Section ---
if selected_df is not None:
    st.markdown(f"### Merit Order Stack | Time Block: `{selected_block_name}`")
    
    display_cols = ['Plant Name', 'DC', 'SG', 'DC-SG', 'VC_Price', 'Category', 'THERMAL BACKING STATUS']
    available_cols = [c for c in display_cols if c in selected_df.columns]
    
    def style_table(styler):
        styler.set_properties(**{
            'background-color': 'black',
            'color': '#00FF00',
            'border-color': 'white'
        })
        styler.set_table_styles([
            {'selector': 'th', 'props': [('background-color', 'black'), ('color', '#00FF00'), ('border', '1px solid white')]},
            {'selector': 'td', 'props': [('border', '1px solid white')]}
        ])
        styler.format({
            'DC': '{:.2f}',
            'SG': '{:.2f}',
            'DC-SG': '{:.2f}',
            'VC_Price': '{:.2f}'
        })
        return styler

    st.dataframe(
        selected_df[available_cols].style.pipe(style_table),
        column_config={
            "Plant Name": st.column_config.TextColumn("Plant Name", width="medium"),
        },
        use_container_width=True,
        height=1000,
        hide_index=True 
    )
elif df is None:
    st.error("Availability Report not found.")
