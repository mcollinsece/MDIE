import os
import sys
import boto3
import pydicom
import uuid
from datetime import datetime
from PIL import Image
import logging
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DicomConverter:
    def __init__(self):
        self.s3_client = boto3.client('s3')
        self.dynamodb = boto3.resource('dynamodb')
        self.input_bucket = os.environ['INPUT_BUCKET_NAME']
        self.input_key = os.environ['INPUT_KEY']
        self.output_bucket = os.environ['OUTPUT_BUCKET_NAME']
        self.table = self.dynamodb.Table(os.environ['DYNAMODB_TABLE_NAME'])
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
            # Create unique identifier using timestamp and UUID
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_id = str(uuid.uuid4())[:8]
            
            # Create unique output prefix
            base_name = os.path.splitext(self.input_key)[0]
            output_prefix = f"{base_name}/{timestamp}_{unique_id}/layers"
            
            for file_path in output_files:
                file_name = os.path.basename(file_path)
                output_key = f"{output_prefix}/{file_name}"
                
                logger.info(f"Uploading {file_name} to s3://{self.output_bucket}/{output_key}")
                self.s3_client.upload_file(
                    file_path,
                    self.output_bucket,
                    output_key
                )
            
            return output_prefix, unique_id, timestamp
            
        except ClientError as e:
            logger.error(f"Error uploading layers: {e}")
            raise


    def extract_dicom_metadata(self, ds):
        """Extract relevant DICOM metadata from dataset"""
        try:
            metadata = {
                # Patient information
                'PatientID': str(getattr(ds, 'PatientID', '')),
                'PatientName': str(getattr(ds, 'PatientName', '')),
                'PatientBirthDate': str(getattr(ds, 'PatientBirthDate', '')),
                
                # Study information
                'StudyInstanceUID': str(getattr(ds, 'StudyInstanceUID', '')),
                'StudyDate': str(getattr(ds, 'StudyDate', '')),
                'StudyTime': str(getattr(ds, 'StudyTime', '')),
                'StudyDescription': str(getattr(ds, 'StudyDescription', '')),
                
                # Series information
                'SeriesInstanceUID': str(getattr(ds, 'SeriesInstanceUID', '')),
                'SeriesNumber': str(getattr(ds, 'SeriesNumber', '')),
                'SeriesDescription': str(getattr(ds, 'SeriesDescription', '')),
                
                # Image information
                'SOPInstanceUID': str(getattr(ds, 'SOPInstanceUID', '')),
                'SOPClassUID': str(getattr(ds, 'SOPClassUID', '')),
                'Modality': str(getattr(ds, 'Modality', '')),
                
                # Technical parameters
                'Rows': str(getattr(ds, 'Rows', '')),
                'Columns': str(getattr(ds, 'Columns', '')),
                'PixelSpacing': str(getattr(ds, 'PixelSpacing', '')),
                'SliceThickness': str(getattr(ds, 'SliceThickness', '')),
            }
            
            # Remove empty values
            metadata = {k: v for k, v in metadata.items() if v}
            
            return metadata
            
        except Exception as e:
            logger.error(f"Error extracting DICOM metadata: {e}")
            raise
    
    def store_processing_data(self, unique_id, timestamp, output_prefix, layer_count, dicom_metadata):
        """Store processing information and DICOM metadata in DynamoDB"""
        try:
            item = {
                'id': unique_id,
                'timestamp': timestamp,
                'input_key': self.input_key,
                'input_bucket': self.input_bucket,
                'output_bucket': self.output_bucket,
                'output_prefix': output_prefix,
                'layer_count': layer_count,
                'processing_status': 'completed',
                
                # Add DICOM metadata
                'patient_id': dicom_metadata.get('PatientID'),
                'study_instance_uid': dicom_metadata.get('StudyInstanceUID'),
                'series_instance_uid': dicom_metadata.get('SeriesInstanceUID'),
                'sop_instance_uid': dicom_metadata.get('SOPInstanceUID'),
                'modality': dicom_metadata.get('Modality'),
                'study_date': dicom_metadata.get('StudyDate'),
                'series_number': dicom_metadata.get('SeriesNumber'),
                
                # Store complete metadata as a nested map
                'dicom_metadata': dicom_metadata
            }
            
            # Remove None values
            item = {k: v for k, v in item.items() if v is not None}
            
            self.table.put_item(Item=item)
            logger.info(f"Successfully stored processing data and DICOM metadata in DynamoDB for id: {unique_id}")
            
        except ClientError as e:
            logger.error(f"Error storing data in DynamoDB: {e}")
            raise
    
    def process(self):
        """Main processing function"""
        try:
            self.download_dicom()
            
            # Read DICOM file and extract metadata
            ds = pydicom.dcmread(self.local_input)
            dicom_metadata = self.extract_dicom_metadata(ds)
            
            output_files = self.convert_to_layers()
            output_prefix, unique_id, timestamp = self.upload_layers(output_files)
            
            # Store processing information and DICOM metadata in DynamoDB
            self.store_processing_data(
                unique_id=unique_id,
                timestamp=timestamp,
                output_prefix=output_prefix,
                layer_count=len(output_files),
                dicom_metadata=dicom_metadata
            )
            
            return {
                "OutputPrefix": output_prefix,
                "LayerCount": len(output_files),
                "UniqueId": unique_id,
                "Timestamp": timestamp,
                "StudyInstanceUID": dicom_metadata.get('StudyInstanceUID'),
                "SeriesInstanceUID": dicom_metadata.get('SeriesInstanceUID')
            }
            
        except Exception as e:
            logger.error(f"Processing failed: {e}")
            sys.exit(1)

if __name__ == "__main__":
    print(os.environ)
    converter = DicomConverter()
    result = converter.process()
    logger.info(f"Processing complete: {result}")

