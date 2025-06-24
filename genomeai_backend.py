import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import hashlib
import magic
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('genomeai_backend.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class GenomeAIDataProcessor:
    """
    Backend processor for GenomeAI data module
    Handles file validation, storage, and ML pipeline integration
    """
    
    def __init__(self, storage_path: str = "data_storage"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
        
        # Supported file formats and their validation rules
        self.supported_formats = {
            'csv': {'extensions': ['.csv'], 'mime_types': ['text/csv'], 'delimiter': ','},
            'tsv': {'extensions': ['.tsv', '.txt'], 'mime_types': ['text/tab-separated-values', 'text/plain'], 'delimiter': '\t'},
            'xlsx': {'extensions': ['.xlsx'], 'mime_types': ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']},
            'vcf': {'extensions': ['.vcf'], 'mime_types': ['text/plain'], 'header_pattern': '##fileformat=VCF'},
            'fasta': {'extensions': ['.fasta', '.fa'], 'mime_types': ['text/plain'], 'header_pattern': '>'},
            'fastq': {'extensions': ['.fastq', '.fq'], 'mime_types': ['text/plain'], 'header_pattern': '@'},
            'bed': {'extensions': ['.bed'], 'mime_types': ['text/plain']},
            'gff': {'extensions': ['.gff', '.gff3'], 'mime_types': ['text/plain'], 'header_pattern': '##gff-version'},
            'gtf': {'extensions': ['.gtf'], 'mime_types': ['text/plain']},
            'sam': {'extensions': ['.sam'], 'mime_types': ['text/plain'], 'header_pattern': '@HD'},
            'bam': {'extensions': ['.bam'], 'mime_types': ['application/octet-stream']},
        }
        
        self.max_file_size = 5 * 1024 * 1024 * 1024  # 5 GB
        
    def validate_file_format(self, file_path: str) -> Tuple[bool, str, Optional[str]]:
        """
        Validate file format based on extension, MIME type, and content
        
        Args:
            file_path: Path to the file to validate
            
        Returns:
            Tuple of (is_valid, error_message, detected_format)
        """
        try:
            file_path = Path(file_path)
            
            # Check if file exists
            if not file_path.exists():
                return False, "File does not exist", None
                
            # Check file size
            file_size = file_path.stat().st_size
            if file_size > self.max_file_size:
                return False, f"File size ({file_size / (1024**3):.2f} GB) exceeds maximum allowed size (5 GB)", None
                
            # Check if file is empty
            if file_size == 0:
                return False, "File is empty", None
                
            # Get file extension
            extension = file_path.suffix.lower()
            
            # Find matching format
            detected_format = None
            for format_name, format_info in self.supported_formats.items():
                if extension in format_info['extensions']:
                    detected_format = format_name
                    break
                    
            if not detected_format:
                return False, f"Unsupported file extension: {extension}", None
                
            # Validate file content for specific formats
            content_valid, content_error = self._validate_file_content(file_path, detected_format)
            if not content_valid:
                return False, content_error, detected_format
                
            return True, "File validation successful", detected_format
            
        except Exception as e:
            logger.exception(f"Error validating file {file_path}")
            return False, f"Validation error: {str(e)}", None
            
    def _validate_file_content(self, file_path: Path, format_name: str) -> Tuple[bool, str]:
        """
        Validate file content based on format-specific rules
        """
        try:
            format_info = self.supported_formats[format_name]
            
            # For text-based formats, check header pattern if specified
            if 'header_pattern' in format_info:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    first_line = f.readline().strip()
                    if not first_line.startswith(format_info['header_pattern']):
                        return False, f"File does not contain expected {format_name.upper()} header pattern"
                        
            # Format-specific validations
            if format_name == 'csv':
                return self._validate_csv_content(file_path)
            elif format_name == 'tsv':
                return self._validate_tsv_content(file_path)
            elif format_name == 'vcf':
                return self._validate_vcf_content(file_path)
            elif format_name in ['fasta', 'fastq']:
                return self._validate_sequence_content(file_path, format_name)
                
            return True, "Content validation passed"
            
        except Exception as e:
            return False, f"Content validation error: {str(e)}"
            
    def _validate_csv_content(self, file_path: Path) -> Tuple[bool, str]:
        """Validate CSV file structure"""
        try:
            import csv
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                # Try to detect dialect
                sample = f.read(1024)
                f.seek(0)
                
                try:
                    dialect = csv.Sniffer().sniff(sample)
                    reader = csv.reader(f, dialect)
                    
                    # Check if we can read at least one row
                    first_row = next(reader, None)
                    if not first_row:
                        return False, "CSV file appears to be empty or malformed"
                        
                    return True, "CSV validation passed"
                except csv.Error as e:
                    return False, f"CSV format error: {str(e)}"
                    
        except Exception as e:
            return False, f"CSV validation error: {str(e)}"
            
    def _validate_tsv_content(self, file_path: Path) -> Tuple[bool, str]:
        """Validate TSV file structure"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                first_line = f.readline().strip()
                if not first_line:
                    return False, "TSV file appears to be empty"
                    
                # Check if line contains tabs
                if '\t' not in first_line:
                    return False, "TSV file does not contain tab separators"
                    
                return True, "TSV validation passed"
                
        except Exception as e:
            return False, f"TSV validation error: {str(e)}"
            
    def _validate_vcf_content(self, file_path: Path) -> Tuple[bool, str]:
        """Validate VCF file structure"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines_checked = 0
                found_header = False
                
                for line in f:
                    line = line.strip()
                    if line.startswith('##'):
                        continue
                    elif line.startswith('#CHROM'):
                        found_header = True
                        # Validate required columns
                        columns = line.split('\t')
                        required_cols = ['#CHROM', 'POS', 'ID', 'REF', 'ALT', 'QUAL', 'FILTER', 'INFO']
                        if not all(col in columns for col in required_cols):
                            return False, "VCF file missing required columns"
                        break
                    elif lines_checked > 100:  # Don't check too many lines
                        break
                    lines_checked += 1
                    
                if not found_header:
                    return False, "VCF file missing required header line (#CHROM...)"
                    
                return True, "VCF validation passed"
                
        except Exception as e:
            return False, f"VCF validation error: {str(e)}"
            
    def _validate_sequence_content(self, file_path: Path, format_name: str) -> Tuple[bool, str]:
        """Validate FASTA/FASTQ sequence files"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines_checked = 0
                sequence_count = 0
                
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                        
                    if format_name == 'fasta' and line.startswith('>'):
                        sequence_count += 1
                    elif format_name == 'fastq' and line.startswith('@'):
                        sequence_count += 1
                        
                    lines_checked += 1
                    if lines_checked > 1000:  # Check first 1000 lines
                        break
                        
                if sequence_count == 0:
                    return False, f"No {format_name.upper()} sequences found in file"
                    
                return True, f"{format_name.upper()} validation passed ({sequence_count} sequences found)"
                
        except Exception as e:
            return False, f"{format_name.upper()} validation error: {str(e)}"
            
    def process_uploaded_file(self, file_path: str, user_id: str, metadata: Dict = None) -> Dict:
        """
        Process an uploaded file and prepare it for ML pipeline
        
        Args:
            file_path: Path to the uploaded file
            user_id: ID of the user who uploaded the file
            metadata: Additional metadata about the file
            
        Returns:
            Dictionary with processing results
        """
        try:
            # Validate file
            is_valid, error_msg, detected_format = self.validate_file_format(file_path)
            
            if not is_valid:
                return {
                    'success': False,
                    'error': error_msg,
                    'file_path': file_path
                }
                
            # Generate file hash for integrity checking
            file_hash = self._calculate_file_hash(file_path)
            
            # Create processing record
            processing_record = {
                'user_id': user_id,
                'original_filename': Path(file_path).name,
                'file_path': file_path,
                'file_hash': file_hash,
                'file_format': detected_format,
                'file_size': Path(file_path).stat().st_size,
                'upload_timestamp': datetime.now().isoformat(),
                'processing_status': 'queued',
                'metadata': metadata or {}
            }
            
            # Save processing record
            record_id = self._save_processing_record(processing_record)
            
            # Queue for ML processing (mock implementation)
            self._queue_for_ml_processing(record_id, processing_record)
            
            return {
                'success': True,
                'record_id': record_id,
                'file_format': detected_format,
                'file_size': processing_record['file_size'],
                'processing_status': 'queued'
            }
            
        except Exception as e:
            logger.exception(f"Error processing uploaded file {file_path}")
            return {
                'success': False,
                'error': f"Processing error: {str(e)}",
                'file_path': file_path
            }
            
    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA-256 hash of file"""
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
        
    def _save_processing_record(self, record: Dict) -> str:
        """Save processing record to storage"""
        record_id = f"{record['user_id']}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        records_dir = self.storage_path / "processing_records"
        records_dir.mkdir(exist_ok=True)
        
        record_file = records_dir / f"{record_id}.json"
        with open(record_file, 'w') as f:
            json.dump(record, f, indent=2)
            
        return record_id
        
    def _queue_for_ml_processing(self, record_id: str, record: Dict):
        """Queue file for ML processing (mock implementation)"""
        # In a real implementation, this would:
        # 1. Add to processing queue (Redis, Celery, etc.)
        # 2. Trigger ML pipeline
        # 3. Update processing status
        
        logger.info(f"Queued file {record['original_filename']} for ML processing (Record ID: {record_id})")
        
        # Mock processing status update
        self._update_processing_status(record_id, 'processing')
        
    def _update_processing_status(self, record_id: str, status: str, results: Dict = None):
        """Update processing status for a record"""
        try:
            record_file = self.storage_path / "processing_records" / f"{record_id}.json"
            
            if record_file.exists():
                with open(record_file, 'r') as f:
                    record = json.load(f)
                    
                record['processing_status'] = status
                record['last_updated'] = datetime.now().isoformat()
                
                if results:
                    record['results'] = results
                    
                with open(record_file, 'w') as f:
                    json.dump(record, f, indent=2)
                    
                logger.info(f"Updated processing status for {record_id}: {status}")
                
        except Exception as e:
            logger.exception(f"Error updating processing status for {record_id}")
            
    def get_processing_status(self, record_id: str) -> Optional[Dict]:
        """Get processing status for a record"""
        try:
            record_file = self.storage_path / "processing_records" / f"{record_id}.json"
            
            if record_file.exists():
                with open(record_file, 'r') as f:
                    return json.load(f)
                    
        except Exception as e:
            logger.exception(f"Error getting processing status for {record_id}")
            
        return None
        
    def get_user_uploads(self, user_id: str) -> List[Dict]:
        """Get all uploads for a specific user"""
        try:
            records_dir = self.storage_path / "processing_records"
            user_records = []
            
            if records_dir.exists():
                for record_file in records_dir.glob("*.json"):
                    try:
                        with open(record_file, 'r') as f:
                            record = json.load(f)
                            if record.get('user_id') == user_id:
                                user_records.append(record)
                    except Exception as e:
                        logger.warning(f"Error reading record file {record_file}: {e}")
                        
            # Sort by upload timestamp (newest first)
            user_records.sort(key=lambda x: x.get('upload_timestamp', ''), reverse=True)
            return user_records
            
        except Exception as e:
            logger.exception(f"Error getting user uploads for {user_id}")
            return []

# Example usage and testing
if __name__ == "__main__":
    processor = GenomeAIDataProcessor()
    
    # Example validation
    test_file = "test_sample.csv"
    if Path(test_file).exists():
        is_valid, error_msg, format_type = processor.validate_file_format(test_file)
        print(f"File validation: {is_valid}, Format: {format_type}")
        if not is_valid:
            print(f"Error: {error_msg}")
            
        # Example processing
        if is_valid:
            result = processor.process_uploaded_file(test_file, "test_user")
            print(f"Processing result: {result}")
    else:
        print(f"Test file {test_file} not found")
        
    print("GenomeAI Backend Data Processor initialized successfully")
