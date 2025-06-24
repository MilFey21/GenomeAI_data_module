#!/usr/bin/env python3
"""
GenomeAI Data Module Startup Script
Launches the frontend server with integrated backend processing
"""

import os
import sys
import logging
from pathlib import Path

# Add current directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

def setup_environment():
    """Setup required directories and environment"""
    
    # Create required directories
    directories = [
        'uploads',
        'data_storage',
        'data_storage/processing_records',
        'templates',
        'logs'
    ]
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"✓ Created directory: {directory}")
    
    # Set environment variables
    os.environ.setdefault('FLASK_APP', 'genomeai_frontend.py')
    os.environ.setdefault('FLASK_ENV', 'development')
    
    print("✓ Environment setup complete")

def check_dependencies():
    """Check if required dependencies are installed"""
    
    required_packages = [
        'flask',
        'werkzeug',
        'jinja2'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"✓ {package} is installed")
        except ImportError:
            missing_packages.append(package)
            print(f"✗ {package} is missing")
    
    if missing_packages:
        print("\nMissing dependencies found. Please install them using:")
        print("pip install -r requirements.txt")
        return False
    
    return True

def main():
    """Main startup function"""
    
    print("🧬 Starting GenomeAI Data Module...")
    print("=" * 50)
    
    # Setup environment
    setup_environment()
    
    # Check dependencies
    if not check_dependencies():
        print("\nPlease install missing dependencies before running.")
        sys.exit(1)
    
    print("\n" + "=" * 50)
    print("🚀 Starting GenomeAI Frontend Server")
    print("=" * 50)
    
    try:
        # Import and run the frontend
        from genomeai_frontend import app, logger
        
        logger.info("GenomeAI Data Module starting up...")
        
        print("\n📁 Upload Interface: http://localhost:5000")
        print("🔧 Supported formats: CSV, TSV, XLSX, VCF, FASTA, FASTQ, BED, GFF, GTF, SAM, BAM")
        print("📊 Maximum file size: 5 GB")
        print("🔒 Logging enabled: Check genomeai_frontend.log")
        print("\nPress Ctrl+C to stop the server")
        print("-" * 50)
        
        # Start the Flask app
        app.run(
            debug=True,
            host='0.0.0.0',
            port=5000,
            use_reloader=True,
            threaded=True
        )
        
    except KeyboardInterrupt:
        print("\n\n🛑 Server stopped by user")
        
    except Exception as e:
        print(f"\n❌ Error starting server: {e}")
        logger.exception("Error starting GenomeAI frontend server")
        sys.exit(1)

if __name__ == "__main__":
    main() 