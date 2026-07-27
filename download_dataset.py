import os
import urllib.request
import pandas as pd

url = "https://raw.githubusercontent.com/mahikkaaa/End_2_End_Data_Science_Project/master/udemy_courses.csv"
dest_dir = "dataset"
dest_path = os.path.join(dest_dir, "udemy_courses.csv")

os.makedirs(dest_dir, exist_ok=True)

try:
    print(f"Downloading dataset from: {url}")
    # Set user-agent header to avoid blocked downloads
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        data = response.read()
    with open(dest_path, 'wb') as f:
        f.write(data)
    
    # Verify shape
    df = pd.read_csv(dest_path)
    print(f"Successfully downloaded and saved dataset to: {dest_path}")
    print(f"Dataset shape: {df.shape}")
except Exception as e:
    print(f"Error downloading dataset: {e}")
