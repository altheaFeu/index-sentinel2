"""
SentinelHub Image Download Script

This script authenticates and configures access to the SentinelHub API using OAuth credentials from a specified text file.
It sets the necessary parameters and saves the configuration for future use.
It then downloads Sentinel 2 data for the specified study area.

Make sure to create a text file ("parameters.txt") with the following content:
- Your SentinelHub instance ID
- Your OAuth client ID
- Your OAuth client secret

Usage:
1. Run the script.
2. If OAuth client ID and client secret are not already configured, the script will prompt you
    to enter them.
3. The script will save the configuration for future use.

For more information, visit: https://www.sentinel-hub.com/develop/api/overview/
To get the bounding box for your project area: http://bboxfinder.com/#0.000000,0.000000,0.000000,0.000000
"""

# Import necessary modules
from sentinelhub import (
    SHConfig,
    SentinelHubCatalog,
    CRS,
    BBox,
    DataCollection,
    MimeType,
    MosaickingOrder,
    SentinelHubRequest,
    bbox_to_dimensions,
)

import logging
from http.client import HTTPConnection  # HTTP communication

# Debug level for HTTP connections
HTTPConnection.debuglevel = 1

# Configure logging for debugging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s:%(name)s:%(threadName)s:%(message)s'
)

# Redirect all warnings
logging.captureWarnings(True)
requests_log = logging.getLogger("requests.packages.urllib3")
requests_log.setLevel(logging.DEBUG)
requests_log.propagate = True

import matplotlib.pyplot as plt
import numpy as np

import os, sys, pprint, datetime

# Authentication and configuration function
def authenticate(file):
    """
    Authenticate and configure access to the SentinelHub API using OAuth credentials.

    Args:
        path_txt (str): Path to the text file containing OAuth credentials.

    Returns:
        SHConfig: The SHConfig object configured for API access.
    """

    # Read credentials from the text file
    parameters = {
        'instance_id': file.readline().strip(),
        'client_id': file.readline().strip(),
        'client_secret': file.readline().strip()
    }

    print(pprint.pformat(parameters))

    # Configure the SHConfig object
    config = SHConfig()
    config.instance_id = parameters['instance_id']
    config.sh_client_id = parameters['client_id']
    config.sh_client_secret = parameters['client_secret']
    config.save()

    # Alternatively, manual configuration in the terminal:
    ## 'sentinelhub.config --show'
    ## 'sentinelhub.config --instance_id <your instance id>'
    ## 'sentinelhub.config --sh_client_id <your client id> --sh_client_secret <your client secret>'

    if not config.sh_client_id or not config.sh_client_secret:
        print("ATTENTION! To use SentinelHub API, you need to provide an OAuth client ID and client secret.")
        config.instance_id = input("OAuth instance ID: ")
        config.sh_client_id = input("OAuth client ID: ")
        config.sh_client_secret = input("OAuth client secret: ")

    return config

# Function to get information from the SentinelHub catalog
def get_catalog_info(config):
    catalog = SentinelHubCatalog(config=config)
    print(pprint.pformat(catalog.get_info()))

# Function to search for Sentinel 2 data
def search_data(bbox, time_interval, config):
    catalog = SentinelHubCatalog(config=config)
    search_iterator = catalog.search(
        DataCollection.SENTINEL2_L2A,
        bbox=bbox,
        time=time_interval,
        filter="eo:cloud_cover < 2",
        fields={"include": ["id", "properties.datetime", "properties.eo:cloud_cover"], "exclude": []},
    )

    result_search = list(search_iterator)
    return result_search

# Function to download data
def download_data(config, path, id, bbox, new_date):
    """
    Downloads Sentinel 2 data for a specified location and date.

    Args:
        config (SHConfig): The SHConfig object configured for API access.
        path (str): The path to the root directory where the data will be saved.
        id (str): The unique identifier for the downloaded data.
        bbox (BBox): The bounding box specifying the geographical area of interest.
        new_date (str): The date for which the data is to be downloaded in the format "YYYY-MM-DD".

    Returns:
        None
    """
    
    # Create folders for data storage
    if not os.path.exists(os.path.join(path, "data")):
        os.mkdir(os.path.join(path, "data"))

    if not os.path.exists(os.path.join(os.path.join(path, "data"), id)):
        os.mkdir(os.path.join(os.path.join(path, "data"), id))

    data_folder = os.path.join(os.path.join(path, "data"), id)

    # Calculate image size in pixels
    size = bbox_to_dimensions(bbox, resolution=10)
    print(f"The 60-meter resolution image has a size of {size} pixels")

    # Evaluation script to obtain specific bands
    evalscript_all_bands = """
        //VERSION=3
        function setup() {
            return {
                input: [{
                    bands: ["B02","B03","B04"],
                    units: "DN"
                }],
                output: {
                    bands: 3,
                    sampleType: "INT16"
                }
            };
        }

        function evaluatePixel(sample) {
            return [sample.B02,
                    sample.B03,
                    sample.B04];
        }
    """

    # Request Sentinel 2 data
    request_all_bands = SentinelHubRequest(
        data_folder=data_folder,
        evalscript=evalscript_all_bands,
        input_data=[
            SentinelHubRequest.input_data(
                data_collection=DataCollection.SENTINEL2_L2A,
                time_interval=(new_date, new_date),
                maxcc=0.2,
                mosaicking_order=MosaickingOrder.LEAST_CC,
            )
        ],
        responses=[SentinelHubRequest.output_response("default", MimeType.TIFF)],
        bbox=bbox,
        size=size,
        config=config,
    )

    # Download data
    request_all_bands.get_data(save_data=True)

    print(
        "An output folder has been created, and a TIFF file with 13 bands has been created with the following format:\n"
    )

    for folder, _, filenames in os.walk(request_all_bands.data_folder):
        for filename in filenames:
            print(os.path.join(folder, filename))

if __name__ == "__main__":
    # Specify the location of the configuration file
    path = your_path
    path_txt = os.path.join(path, "parameters.txt")

    try:
        file = open(path_txt, "r+")
        config = authenticate(file)
    except Exception as e:
        print(e)
        sys.exit()

    get_catalog_info(config)

    # Define the study area (Bbox should be of the form [x_min, y_min, x_max, y_max])
    coordinates = [x_min, y_min, x_max, y_max]
    bbox = BBox((coordinates[0], coordinates[1], coordinates[2], coordinates[3]), crs=CRS.WGS84)
    # Choose the time interval for image download
    time_interval = "first-date", "second-date"

    # Search for data
    result_search = search_data(bbox, time_interval, config)
    print("Total number of results: ", len(result_search))

    for id, result in enumerate(result_search):
        print(result)
        keep_it = input("Do you want to keep it? (yes/no/exit) ")
        if keep_it == "yes" or keep_it == "y" or keep_it == "oui" or keep_it == "o":
            id = result['id']
            new_date = result['properties']['datetime'][0:10]
            download_data(config, path, id, bbox, new_date)

        if keep_it == "exit" or keep_it == "e":
            sys.exit()
