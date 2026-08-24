#!/bin/bash

# Step 1: Download the ZIP file
curl -L https://github.com/entsoe/relicapgrid/archive/refs/heads/cgmes-3.0_ncp-2.4_tc-1.1.zip -o relicapgrid.zip || { echo "Failed to download ZIP file"; exit 1; }

# Step 2: Unzip the file
unzip relicapgrid.zip || { echo "Failed to unzip file"; exit 1; }

# Step 3: Navigate into the extracted directory (using wildcard to match the folder name)
cd relicapgrid-cgmes*/Instance || { echo "Failed to enter the 'Instance' directory"; exit 1; }

# Step 4: Run 'make zip' in the 'Instance' directory
make zip || { echo "Failed to execute 'make zip'"; exit 1; }

# Step 5: Clean up the repository
curl -X POST --data-urlencode "update@drop.ru" https://cim.ontotext.com/graphdb/repositories/relicapgrid/statements || { echo "Failed to remove all data from /cim.ontotext.com/graphdb repository"; exit 1; }

# Step 6: Upload data to the repository
curl -X POST --header 'Content-Type: application/zip' --data-binary @./relicapgrid-CGM-trig.zip https://cim.ontotext.com/graphdb/repositories/relicapgrid/statements || { echo "Failed to upload zip file to /cim.ontotext.com/graphdb repository"; exit 1; }

echo "Data refreshed successfully!"
