import os
import sys
import boto3
import pydicom
import numpy as np
from PIL import Image
import logging
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DicomConverter:
    def __init__(self):
        self.s3_client = boto3.client('s3')
        self.input_bucket = os.environ['INPUT_BUCKET_NAME']
        self.input_key = os.environ['INPUT_KEY']
        self.output_bucket = os.environ['OUTPUT_BUCKET_NAME']
        self.local_input = '/tmp/dicom_file'
        self.local_output = '/tmp/'

    def download_dicom(self):
        """Download DICOM file from S3"""
        try:
            logger.info(f"Downloading DICOM from s3://{self.input_bucket}/{self.input_key}")
            self.s3_client.download_file(
                self.input_bucket,
                self.input_key,
                self.local_input
            )
        except ClientError as e:
            logger.error(f"Error downloading DICOM: {e}")
            raise

    def convert_to_layers(self):
        """Convert DICOM to image layers"""
        try:
            # Read DICOM file
            ds = pydicom.dcmread(self.local_input)
            
            # Get pixel array
            pixel_array = ds.pixel_array
            
            # Process each layer
            output_files = []
            for i in range(pixel_array.shape[0]):
                # Convert to 8-bit image
                layer = pixel_array[i].astype(float)
                layer = ((layer - layer.min()) / (layer.max() - layer.min()) * 255).astype(np.uint8)
                
                # Create PIL Image
                img = Image.fromarray(layer)
                
                # Save layer
                output_path = f"{self.local_output}/layer_{i:04d}.png"
                img.save(output_path)
                output_files.append(output_path)
                
            return output_files
            
        except Exception as e:
            logger.error(f"Error converting DICOM: {e}")
            raise

    def upload_layers(self, output_files):
        """Upload converted layers to S3"""
        try:
            output_prefix = f"{os.path.splitext(self.input_key)[0]}/layers"
            
            for file_path in output_files:
                file_name = os.path.basename(file_path)
                output_key = f"{output_prefix}/{file_name}"
                
                logger.info(f"Uploading {file_name} to s3://{self.output_bucket}/{output_key}")
                self.s3_client.upload_file(
                    file_path,
                    self.output_bucket,
                    output_key
                )
            
            return output_prefix
            
        except ClientError as e:
            logger.error(f"Error uploading layers: {e}")
            raise

    def process(self):
        """Main processing function"""
        try:
            self.download_dicom()
            output_files = self.convert_to_layers()
            output_prefix = self.upload_layers(output_files)
            
            return {
                "OutputPrefix": output_prefix,
                "LayerCount": len(output_files)
            }
            
        except Exception as e:
            logger.error(f"Processing failed: {e}")
            sys.exit(1)

if __name__ == "__main__":
    print(os.environ)
    converter = DicomConverter()
    result = converter.process()
    logger.info(f"Processing complete: {result}")

