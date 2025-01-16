import os
import subprocess
import glob
import boto3
import uuid
from datetime import datetime
import sys
sys.path.insert(0, '/opt/pydicom')
import json
import pydicom


sagemaker = boto3.client('sagemaker-runtime')
s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
dynamodb_table_name = os.environ.get('DYNAMODB_TABLE_NAME')
table = dynamodb.Table(dynamodb_table_name)

endpoint_name = os.environ.get('SAGEMAKER_ENDPOINT_NAME')
disable_sagemaker = os.environ.get('DISABLE_SAGEMAKER', 'false').lower() == 'true'
tmp_dir = os.environ.get('TMP_DIR')


def lambda_handler(event, context):
    print("Received event:", event)
    print("Received context:", context)

    input_bucket_name = event['Records'][0]['s3']['bucket']['name']
    file_key = event['Records'][0]['s3']['object']['key']
    output_bucket_name = os.environ.get('OUTPUT_BUCKET_NAME')
    if not output_bucket_name:
        print("Output bucket name not provided")
        return {
            'statusCode': 500,
            'body': 'Output bucket name not provided'
        }
    print(f"Destination bucket: {output_bucket_name}")

    # Need a uuid for tracking and uniqueness
    dest_folder_name = uuid.uuid4()

    # Download the DICOM file from S3
    dicom_file = os.path.join(tmp_dir, 'dicom_file.dcm')
    s3.download_file(input_bucket_name, file_key, dicom_file)

    # Convert the DICOM file to PNG using mogrify
    try:
        print(f"Processing {dicom_file}")
        subprocess.run(['mogrify', '-format', 'png', dicom_file], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error converting DICOM to PNG")
        return

    # What is the list of png files that were produced
    image_files = [os.path.join(tmp_dir, f) for f in os.listdir(tmp_dir) if f.endswith('.png')]
    num_png_files = len(image_files)

    print(f"Files in the {tmp_dir}: {os.listdir(tmp_dir)}")

    # Read DICOM metadata
    dicom_data = pydicom.dcmread(dicom_file)

    modality = 'Unknown' if not hasattr(dicom_data, 'Modality') else dicom_data.Modality
    patient_id = 'Unknown' if not hasattr(dicom_data, 'PatientID') else dicom_data.PatientID
    study_date = 'Unknown' if not hasattr(dicom_data, 'StudyDate') else dicom_data.StudyDate
    study_description = 'Unknown' if not hasattr(dicom_data, 'StudyDescription') else dicom_data.StudyDescription
    series_description = 'Unknown' if not hasattr(dicom_data, 'SeriesDescription') else dicom_data.SeriesDescription

    print(f"Modality: {modality}")
    print(f"Patient ID: {patient_id}")
    print(f"Study Date: {study_date}")
    print(f"Study Description: {study_description}")
    print(f"Series Description: {series_description}")

# call endpoint for each image file
    responses = []
    if not disable_sagemaker:
        print("Calling SageMaker endpoint")
        print(f"Endpoint name: {endpoint_name}")
        for image_file in image_files:
            with open(image_file, 'rb') as f:
                image_data = f.read()
            response = sagemaker.invoke_endpoint(
                EndpointName=endpoint_name,
                ContentType='application/x-image',
                Body=image_data
            )
            responses.append(response)
    else:
        print("SageMaker inference is disabled")
    

    # Store the UUID, number of PNG files, DICOM metadata, and object detection results in DynamoDB
    table.put_item(
        Item={
            'uuid': str(dest_folder_name),
            'num_png_files': num_png_files,
            'timestamp': str(datetime.now()),
            'modality': modality,
            'patient_id': patient_id,
            'study_date': study_date,
            'study_description': study_description,
            'series_description': series_description,
            'sagemaker_response': responses
        }
    )

    # Upload the PNG files to the output S3 bucket
    for image_file in image_files:
        png_key = os.path.join(str(dest_folder_name), os.path.basename(image_file))
        s3.upload_file(image_file, output_bucket_name, png_key)

    print(f"Successfully processed {file_key}")
