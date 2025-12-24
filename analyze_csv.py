import pandas as pd
import glob
import os

# Find the availability report file
files = glob.glob("Availability_Report_*.csv")
if not files:
    print("No Availability Report found.")
else:
    file_path = files[0]
    print(f"Reading {file_path}")
    try:
        df = pd.read_csv(file_path, on_bad_lines='skip') # Skip bad lines if any
        print("Columns:", df.columns.tolist())
        
        if 'Type' in df.columns:
            print("Unique Types:", df['Type'].unique())
        
        if 'Category' in df.columns:
            print("Unique Categories:", df['Category'].unique())
            
        if 'VC_Price' in df.columns:
            print("VC_Price sample:", df['VC_Price'].head())

        if 'Plant Name' in df.columns:
            print("Plant Name sample:", df['Plant Name'].head())

        # Check for SG
        if 'Type' in df.columns:
             sg_exists = 'SG' in df['Type'].unique()
             print("SG exists in Type:", sg_exists)

    except Exception as e:
        print(f"Error reading CSV: {e}")
