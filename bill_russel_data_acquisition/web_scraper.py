#!/usr/bin/env python3
"""
Bill Russell Protocol - Security Dataset Web Scraper

Scrapes free security datasets for threat detection training:
1. UNSW-NB15 - Anomaly detection baseline
2. CIC-DDoS 2019 - DDoS pattern recognition  
3. LANL Authentication Dataset - Long-term behavioral baseline
4. IoT-23 - Malicious vs benign traffic classification

Based on PDF analysis of Anthropic's Mythos capabilities:
- Massive context density (more signal across domains)
- Better reasoning chains (multi-step logic)
- Cross-domain pattern synthesis
"""

import os
import sys
import json
import time
import logging
import hashlib
import zipfile
import tarfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import urllib.request
import urllib.error
import urllib.parse
import concurrent.futures
import threading

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data" / "bill_russel_datasets"
DATASET_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
METADATA_FILE = DATA_DIR / "dataset_metadata.json"
LOG_FILE = DATA_DIR / "scraper.log"

# Ensure directories exist
for dir_path in [DATA_DIR, DATASET_DIR, PROCESSED_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class DatasetInfo:
    """Information about a security dataset."""
    name: str
    description: str
    urls: List[str]  # Multiple mirrors/sources
    file_type: str  # csv, pcap, json, etc.
    expected_size_mb: int
    expected_files: int
    license: str
    citation: str
    last_updated: str
    hash_algo: str = "sha256"
    expected_hash: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class DownloadResult:
    """Result of a dataset download."""
    dataset_name: str
    success: bool
    downloaded_files: List[str]
    total_size_mb: float
    download_time_seconds: float
    error_message: Optional[str] = None
    hash_verified: bool = False
    
    def to_dict(self) -> Dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Dataset Definitions (Based on Implementation Roadmap)
# ---------------------------------------------------------------------------

DATASETS = {
    "unsw_nb15": DatasetInfo(
        name="UNSW-NB15",
        description="Network traffic dataset for anomaly detection with 9 attack types",
        urls=[
            "https://www.unsw.adfa.edu.au/unsw-canberra-cyber/cybersecurity/ADFA-NB15-Datasets/UNSW-NB15_1.csv",
            "https://www.unsw.adfa.edu.au/unsw-canberra-cyber/cybersecurity/ADFA-NB15-Datasets/UNSW-NB15_2.csv",
            "https://www.unsw.adfa.edu.au/unsw-canberra-cyber/cybersecurity/ADFA-NB15-Datasets/UNSW-NB15_3.csv",
            "https://www.unsw.adfa.edu.au/unsw-canberra-cyber/cybersecurity/ADFA-NB15-Datasets/UNSW-NB15_4.csv",
        ],
        file_type="csv",
        expected_size_mb=250,
        expected_files=4,
        license="CC BY-NC-SA 4.0",
        citation="Moustafa, N., & Slay, J. (2015). UNSW-NB15: a comprehensive data set for network intrusion detection systems.",
        last_updated="2023-01-15"
    ),
    
    "cic_ddos_2019": DatasetInfo(
        name="CIC-DDoS 2019",
        description="DDoS attack dataset with 13 attack types and benign traffic",
        urls=[
            "https://www.unb.ca/cic/datasets/ddos-2019.html",  # Main page
            # Note: Actual download requires form submission, we'll implement alternative
        ],
        file_type="pcap/csv",
        expected_size_mb=5000,
        expected_files=50,
        license="Academic Use",
        citation="Sharafaldin, I., et al. (2019). Toward generating a new intrusion detection dataset and intrusion traffic characterization.",
        last_updated="2019-12-01"
    ),
    
    "lanl_authentication": DatasetInfo(
        name="LANL Authentication Dataset",
        description="58 days of authentication logs from Los Alamos National Lab",
        urls=[
            "https://csr.lanl.gov/data/cyber1/",  # Requires authentication
            # Alternative: Use processed version from academic sources
        ],
        file_type="csv",
        expected_size_mb=2000,
        expected_files=1,
        license="LANL Restricted",
        citation="Turcotte, M. J., et al. (2017). Unifying cybersecurity datasets for anomaly detection.",
        last_updated="2017-05-01"
    ),
    
    "iot_23": DatasetInfo(
        name="IoT-23",
        description="Network traffic from IoT devices, labeled as malicious/benign",
        urls=[
            "https://www.stratosphereips.org/datasets-iot23",
            # Actual files: https://mcfp.felk.cvut.cz/publicDatasets/IoT-23-Dataset/
        ],
        file_type="pcap",
        expected_size_mb=3000,
        expected_files=23,
        license="CC BY-NC-SA 4.0",
        citation="Garcia, S., et al. (2020). IoT-23: A labeled dataset with malicious and benign IoT network traffic.",
        last_updated="2020-01-15"
    ),
    
    # Alternative free datasets (backup options)
    "kdd_cup_99": DatasetInfo(
        name="KDD Cup 1999",
        description="Classic intrusion detection dataset (simulated military network)",
        urls=[
            "http://kdd.ics.uci.edu/databases/kddcup99/kddcup.data.gz",
            "http://kdd.ics.uci.edu/databases/kddcup99/kddcup.names"
        ],
        file_type="csv",
        expected_size_mb=150,
        expected_files=2,
        license="Public Domain",
        citation="Stolfo, S. J., et al. (1999). KDD Cup 1999 Data.",
        last_updated="1999-01-01"
    ),
    
    "nsl_kdd": DatasetInfo(
        name="NSL-KDD",
        description="Improved version of KDD Cup 1999 with reduced redundancy",
        urls=[
            "https://www.unb.ca/cic/datasets/nsl.html",
            # Files: KDDTrain+.txt, KDDTest+.txt, etc.
        ],
        file_type="csv",
        expected_size_mb=50,
        expected_files=4,
        license="Academic Use",
        citation="Tavallaee, M., et al. (2009). A detailed analysis of the KDD CUP 99 data set.",
        last_updated="2009-01-01"
    ),
}


# ---------------------------------------------------------------------------
# Web Scraper Core
# ---------------------------------------------------------------------------

class SecurityDatasetScraper:
    """Scrapes and downloads security datasets for Bill Russell Protocol."""
    
    def __init__(self, max_workers: int = 4, timeout: int = 300):
        self.max_workers = max_workers
        self.timeout = timeout
        self.download_stats = {}
        self.metadata = self._load_metadata()
        
        log.info(f"Security Dataset Scraper initialized")
        log.info(f"Target datasets: {list(DATASETS.keys())}")
        log.info(f"Data directory: {DATA_DIR}")
    
    def _load_metadata(self) -> Dict:
        """Load existing dataset metadata."""
        if METADATA_FILE.exists():
            try:
                with open(METADATA_FILE, 'r') as f:
                    return json.load(f)
            except Exception as e:
                log.error(f"Error loading metadata: {e}")
        return {"datasets": {}, "download_history": []}
    
    def _save_metadata(self):
        """Save dataset metadata."""
        try:
            with open(METADATA_FILE, 'w') as f:
                json.dump(self.metadata, f, indent=2)
        except Exception as e:
            log.error(f"Error saving metadata: {e}")
    
    def download_dataset(self, dataset_id: str, force: bool = False) -> DownloadResult:
        """Download a specific dataset."""
        if dataset_id not in DATASETS:
            return DownloadResult(
                dataset_name=dataset_id,
                success=False,
                downloaded_files=[],
                total_size_mb=0,
                download_time_seconds=0,
                error_message=f"Unknown dataset: {dataset_id}"
            )
        
        dataset = DATASETS[dataset_id]
        log.info(f"Downloading dataset: {dataset.name}")
        
        # Check if already downloaded
        dataset_dir = DATASET_DIR / dataset_id
        dataset_dir.mkdir(exist_ok=True)
        
        if not force and self._is_dataset_complete(dataset_id, dataset_dir):
            log.info(f"Dataset {dataset.name} already downloaded and verified")
            return DownloadResult(
                dataset_name=dataset.name,
                success=True,
                downloaded_files=list(str(f) for f in dataset_dir.iterdir()),
                total_size_mb=self._get_directory_size_mb(dataset_dir),
                download_time_seconds=0,
                hash_verified=True
            )
        
        start_time = time.time()
        downloaded_files = []
        total_size = 0
        
        try:
            # Try each URL until successful
            for url in dataset.urls:
                try:
                    log.info(f"Trying URL: {url}")
                    
                    if "unsw.adfa.edu.au" in url:
                        files = self._download_unsw_nb15(url, dataset_dir)
                    elif "kdd.ics.uci.edu" in url:
                        files = self._download_kdd_cup(url, dataset_dir)
                    else:
                        files = self._download_generic(url, dataset_dir)
                    
                    if files:
                        downloaded_files.extend(files)
                        total_size += sum(f.stat().st_size for f in files if f.exists())
                        break
                        
                except Exception as e:
                    log.warning(f"Failed to download from {url}: {e}")
                    continue
            
            download_time = time.time() - start_time
            
            if downloaded_files:
                # Verify download
                hash_verified = self._verify_dataset(dataset_id, dataset_dir)
                
                result = DownloadResult(
                    dataset_name=dataset.name,
                    success=True,
                    downloaded_files=[str(f) for f in downloaded_files],
                    total_size_mb=total_size / (1024 * 1024),
                    download_time_seconds=download_time,
                    hash_verified=hash_verified
                )
                
                log.info(f"Successfully downloaded {dataset.name}: {len(downloaded_files)} files, {result.total_size_mb:.2f} MB")
                
                # Update metadata
                self._update_dataset_metadata(dataset_id, result)
                
                return result
            else:
                raise Exception("All download attempts failed")
                
        except Exception as e:
            download_time = time.time() - start_time
            log.error(f"Failed to download {dataset.name}: {e}")
            
            return DownloadResult(
                dataset_name=dataset.name,
                success=False,
                downloaded_files=[],
                total_size_mb=0,
                download_time_seconds=download_time,
                error_message=str(e)
            )
    
    def _download_unsw_nb15(self, url: str, target_dir: Path) -> List[Path]:
        """Download UNSW-NB15 dataset (special handling needed)."""
        # UNSW-NB15 requires special handling due to website structure
        # For now, we'll implement a simplified version
        filename = url.split('/')[-1]
        target_file = target_dir / filename
        
        log.info(f"Downloading UNSW-NB15 file: {filename}")
        
        # Set headers to mimic browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        
        req = urllib.request.Request(url, headers=headers)
        
        with urllib.request.urlopen(req, timeout=self.timeout) as response:
            with open(target_file, 'wb') as f:
                # Read in chunks to handle large files
                chunk_size = 8192
                total_size = 0
                
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    total_size += len(chunk)
                    
                    # Log progress every 10MB
                    if total_size % (10 * 1024 * 1024) < chunk_size:
                        log.info(f"Downloaded {total_size / (1024 * 1024):.1f} MB...")
        
        log.info(f"Download complete: {target_file} ({total_size / (1024 * 1024):.1f} MB)")
        return [target_file]
    
    def _download_kdd_cup(self, url: str, target_dir: Path) -> List[Path]:
        """Download KDD Cup dataset."""
        filename = url.split('/')[-1]
        target_file = target_dir / filename
        
        log.info(f"Downloading KDD Cup file: {filename}")
        
        urllib.request.urlretrieve(url, target_file)
        
        # Extract if compressed
        if filename.endswith('.gz'):
            extracted_file = self._extract_gzip(target_file, target_dir)
            return [extracted_file]
        
        return [target_file]
    
    def _download_generic(self, url: str, target_dir: Path) -> List[Path]:
        """Generic download method."""
        filename = url.split('/')[-1]
        target_file = target_dir / filename
        
        log.info(f"Downloading generic file: {filename}")
        
        urllib.request.urlretrieve(url, target_file)
        return [target_file]
    
    def _extract_gzip(self, gzip_file: Path, target_dir: Path) -> Path:
        """Extract gzip file."""
        import gzip
        
        output_file = target_dir / gzip_file.stem  # Remove .gz extension
        
        log.info(f"Extracting {gzip_file} to {output_file}")
        
        with gzip.open(gzip_file, 'rb') as f_in:
            with open(output_file, 'wb') as f_out:
                f_out.write(f_in.read())
        
        return output_file
    
    def _is_dataset_complete(self, dataset_id: str, dataset_dir: Path) -> bool:
        """Check if dataset is already downloaded and complete."""
        if not dataset_dir.exists():
            return False
        
        # Check metadata
        if dataset_id in self.metadata.get("datasets", {}):
            dataset_meta = self.metadata["datasets"][dataset_id]
            if dataset_meta.get("status") == "complete":
                # Check files exist
                expected_files = dataset_meta.get("files", [])
                if all((dataset_dir / f).exists() for f in expected_files):
                    return True
        
        return False
    
    def _get_directory_size_mb(self, directory: Path) -> float:
        """Get directory size in MB."""
        total_size = 0
        for file_path in directory.rglob('*'):
            if file_path.is_file():
                total_size += file_path.stat().st_size
        return total_size / (1024 * 1024)
    
    def _verify_dataset(self, dataset_id: str, dataset_dir: Path) -> bool:
        """Verify dataset integrity (basic checks)."""
        # Check files exist and are not empty
        files = list(dataset_dir.iterdir())
        if not files:
            return False
        
        for file_path in files:
            if not file_path.exists() or file_path.stat().st_size == 0:
                return False
        
        # TODO: Implement hash verification when we have expected hashes
        return True
    
    def _update_dataset_metadata(self, dataset_id: str, result: DownloadResult):
        """Update metadata with download results."""
        if "datasets" not in self.metadata:
            self.metadata["datasets"] = {}
        
        self.metadata["datasets"][dataset_id] = {
            "name": result.dataset_name,
            "status": "complete" if result.success else "failed",
            "files": result.downloaded_files,
            "size_mb": result.total_size_mb,
            "download_time": result.download_time_seconds,
            "hash_verified": result.hash_verified,
            "last_updated": datetime.utcnow().isoformat() + "Z"
        }
        
        # Add to download history
        if "download_history" not in self.metadata:
            self.metadata["download_history"] = []
        
        self.metadata["download_history"].append({
            "dataset_id": dataset_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "result": result.to_dict()
        })
        
        self._save_metadata()
    
    def download_all(self, force: bool = False) -> Dict[str, DownloadResult]:
        """Download all datasets."""
        results = {}
        
        log.info(f"Starting download of all datasets (force={force})")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all download tasks
            future_to_dataset = {
                executor.submit(self.download_dataset, dataset_id, force): dataset_id
                for dataset_id in DATASETS.keys()
            }
            
            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_dataset):
                dataset_id = future_to_dataset[future]
                try:
                    result = future.result(timeout=self.timeout)
                    results[dataset_id] = result
                    
                    if result.success:
                        log.info(f"✓ {dataset_id}: Success ({result.total_size_mb:.1f} MB)")
                    else:
                        log.warning(f"✗ {dataset_id}: Failed - {result.error_message}")
                        
                except Exception as e:
                    log.error(f"✗ {dataset_id}: Error - {e}")
                    results[dataset_id] = DownloadResult(
                        dataset_name=dataset_id,
                        success=False,
                        downloaded_files=[],
                        total_size_mb=0,
                        download_time_seconds=0,
                        error_message=str(e)
                    )
        
        # Generate summary
        self._generate_summary(results)
        
        return results
    
    def _generate_summary(self, results: Dict[str, DownloadResult]):
        """Generate download summary."""
        successful = sum(1 for r in results.values() if r.success)
        total_size = sum(r.total_size_mb for r in results.values() if r.success)
        
        log.info("=" * 60)
        log.info("DOWNLOAD SUMMARY")
        log.info("=" * 60)
        log.info(f"Total datasets: {len(results)}")
        log.info(f"Successful: {successful}")
        log.info(f"Failed: {len(results) - successful}")
        log.info(f"Total size: {total_size:.1f} MB")
        log.info("=" * 60)
        
        # Save summary to file
        summary_file = DATA_DIR / "download_summary.json"
        summary = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "total_datasets": len(results),
            "successful": successful,
            "total_size_mb": total_size,
            "results": {k: r.to_dict() for k, r in results.items()}
        }
        
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        log.info(f"Summary saved to: {summary_file}")
    
    def get_status(self) -> Dict:
        """Get current scraper status."""
        status = {
            "total_datasets": len(DATASETS),
            "downloaded_datasets": 0,
            "total_size_mb": 0,
            "last_updated": None
        }
        
        for dataset_id in DATASETS.keys():
            dataset_dir = DATASET_DIR / dataset_id
            if dataset_dir.exists() and list(dataset_dir.iterdir()):
                status["downloaded_datasets"] += 1
                status["total_size_mb"] += self._get_directory_size_mb(dataset_dir)
        
        # Get last update from metadata
        if self.metadata.get("download_history"):
            last_update = self.metadata["download_history"][-1]["timestamp"]
            status["last_updated"] = last_update
        
        return status


# ---------------------------------------------------------------------------
# Command Line Interface
# ---------------------------------------------------------------------------

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Bill Russell Protocol - Security Dataset Scraper"
    )
    parser.add_argument(
        "--dataset",
        choices=list(DATASETS.keys()) + ["all"],
        default="all",
        help="Dataset to download (default: all)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-download even if already exists"
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=4,
        help="Maximum concurrent downloads (default: 4)"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Download timeout in seconds (default: 300)"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show download status only"
    )
    
    args = parser.parse_args()
    
    # Initialize scraper
    scraper = SecurityDatasetScraper(
        max_workers=args.max_workers,
        timeout=args.timeout
    )
    
    if args.status:
        status = scraper.get_status()
        print("\n" + "=" * 60)
        print("BILL RUSSELL PROTOCOL - DATASET STATUS")
        print("=" * 60)
        print(f"Total datasets available: {status['total_datasets']}")
        print(f"Datasets downloaded: {status['downloaded_datasets']}")
        print(f"Total size: {status['total_size_mb']:.1f} MB")
        if status['last_updated']:
            print(f"Last updated: {status['last_updated']}")
        print("=" * 60)
        return
    
    # Download datasets
    if args.dataset == "all":
        results = scraper.download_all(force=args.force)
    else:
        result = scraper.download_dataset(args.dataset, force=args.force)
        results = {args.dataset: result}
    
    # Print final status
    status = scraper.get_status()
    print(f"\nFinal status: {status['downloaded_datasets']}/{status['total_datasets']} datasets downloaded")


if __name__ == "__main__":
    main()