#!/bin/bash

GDBURL="https://cim.ontotext.com/graphdb/"
GDBUSER=""
GDBPASS=""


# Step 1: Download the ZIP file
curl -L https://github.com/entsoe/relicapgrid/archive/refs/heads/cgmes-3.0_ncp-2.4_tc-1.1.zip -o relicapgrid.zip || { echo "Failed to download ZIP file"; exit 1; }

# Step 2: Unzip the file
unzip relicapgrid.zip || { echo "Failed to unzip file"; exit 1; }

# Step 3: Navigate into the extracted directory (using wildcard to match the folder name)
cd relicapgrid-cgmes*/Instance || { echo "Failed to enter the 'Instance' directory"; exit 1; }

# Step 4: Run 'make zip' in the 'Instance' directory
make zip || { echo "Failed to execute 'make zip'"; exit 1; }

# Step 5: Authenticate and extract the authorization token
GDB_AUTH_HEADER="X-GraphDB-Password: $GDBPASS" 
GDB_AUTH_URL="$GDBURL""rest/login/admin"
auth_header=$(curl "$GDB_AUTH_URL" -X POST -H "$GDB_AUTH_HEADER" -I | grep "authorization:")
token=${auth_header#*: }
AUTH_HEADER="Authorization: Bearer $token"

# Step 5: Clean up the repository
curl  --http1.1 -H "$AUTH_HEADER" -X POST --data-urlencode "update@/drop.ru" "$GDBURL""repositories/relicapgrid/statements" || { echo "Failed to remove all data from $GDBURL repository"; exit 1; }

# Step 6: Upload data to the repository
curl  --http1.1 -H "$AUTH_HEADER" -X POST --header 'Content-Type: application/zip' --data-binary @relicapgrid-CGM-trig.zip "$GDBURL""repositories/relicapgrid/statements" || { echo "Failed to upload zip file to $GDBURL repository"; exit 1; }

echo "Data refreshed successfully!"
