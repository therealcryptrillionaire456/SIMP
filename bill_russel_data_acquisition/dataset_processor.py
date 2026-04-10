#!/usr/bin/env python3
"""
Bill Russell Protocol - Dataset Processor

Processes security datasets for ML training:
1. Cleans and normalizes data
2. Extracts features for anomaly detection
3. Creates training/validation/test splits
4. Generates Sigma rule compatible outputs

Based on PDF analysis: "Massive context density - fed it more signal across more domains"
"""

import os
import sys
import json
import csv
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import logging
import hashlib
import pickle

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data" / "bill_russel_datasets"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
FEATURES_DIR = DATA_DIR / "features"
LOG_FILE = DATA_DIR / "processor.log"

# Ensure directories exist
for dir_path in [PROCESSED_DIR, FEATURES_DIR]:
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
class DatasetStats:
    """Statistics for a processed dataset."""
    name: str
    total_records: int
    features: int
    attack_types: List[str]
    benign_count: int
    malicious_count: int
    processing_time_seconds: float
    memory_usage_mb: float
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class FeatureSet:
    """Extracted feature set for ML training."""
    name: str
    features: List[str]
    feature_matrix: np.ndarray
    labels: np.ndarray
    label_names: List[str]
    sample_weights: Optional[np.ndarray] = None
    
    def save(self, output_dir: Path):
        """Save feature set to disk."""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save metadata
        metadata = {
            "name": self.name,
            "features": self.features,
            "label_names": self.label_names,
            "shape": self.feature_matrix.shape,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
        with open(output_dir / "metadata.json", 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Save numpy arrays
        np.save(output_dir / "features.npy", self.feature_matrix)
        np.save(output_dir / "labels.npy", self.labels)
        
        if self.sample_weights is not None:
            np.save(output_dir / "sample_weights.npy", self.sample_weights)
        
        log.info(f"Saved feature set '{self.name}' to {output_dir}")


# ---------------------------------------------------------------------------
# Dataset Processors
# ---------------------------------------------------------------------------

class DatasetProcessor:
    """Base class for dataset processors."""
    
    def __init__(self, dataset_id: str):
        self.dataset_id = dataset_id
        self.raw_dir = RAW_DIR / dataset_id
        self.processed_dir = PROCESSED_DIR / dataset_id
        self.features_dir = FEATURES_DIR / dataset_id
        self.stats = None
        
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.features_dir.mkdir(parents=True, exist_ok=True)
    
    def process(self) -> DatasetStats:
        """Process the dataset - to be implemented by subclasses."""
        raise NotImplementedError
    
    def extract_features(self) -> FeatureSet:
        """Extract features for ML training - to be implemented by subclasses."""
        raise NotImplementedError
    
    def _save_stats(self, stats: DatasetStats):
        """Save dataset statistics."""
        stats_file = self.processed_dir / "stats.json"
        with open(stats_file, 'w') as f:
            json.dump(stats.to_dict(), f, indent=2)
        
        self.stats = stats
        log.info(f"Saved statistics for {self.dataset_id}")


class UNSWNB15Processor(DatasetProcessor):
    """Processor for UNSW-NB15 dataset."""
    
    def __init__(self):
        super().__init__("unsw_nb15")
        self.attack_types = {
            'Normal': 'benign',
            'Analysis': 'attack',
            'Backdoor': 'attack',
            'DoS': 'attack',
            'Exploits': 'attack',
            'Fuzzers': 'attack',
            'Generic': 'attack',
            'Reconnaissance': 'attack',
            'Shellcode': 'attack',
            'Worms': 'attack'
        }
    
    def process(self) -> DatasetStats:
        """Process UNSW-NB15 dataset."""
        log.info(f"Processing UNSW-NB15 dataset from {self.raw_dir}")
        start_time = datetime.now()
        
        # Find CSV files
        csv_files = list(self.raw_dir.glob("*.csv"))
        if not csv_files:
            raise FileNotFoundError(f"No CSV files found in {self.raw_dir}")
        
        log.info(f"Found {len(csv_files)} CSV files")
        
        # Load and concatenate all CSV files
        dfs = []
        for csv_file in csv_files:
            log.info(f"Loading {csv_file.name}...")
            df = pd.read_csv(csv_file, low_memory=False)
            dfs.append(df)
        
        combined_df = pd.concat(dfs, ignore_index=True)
        
        # Basic cleaning
        log.info(f"Original shape: {combined_df.shape}")
        
        # Remove duplicates
        combined_df = combined_df.drop_duplicates()
        log.info(f"After removing duplicates: {combined_df.shape}")
        
        # Handle missing values
        missing_before = combined_df.isnull().sum().sum()
        combined_df = combined_df.fillna(0)
        missing_after = combined_df.isnull().sum().sum()
        log.info(f"Missing values: {missing_before} -> {missing_after}")
        
        # Save processed data
        processed_file = self.processed_dir / "unsw_nb15_processed.csv"
        combined_df.to_csv(processed_file, index=False)
        log.info(f"Saved processed data to {processed_file}")
        
        # Calculate statistics
        processing_time = (datetime.now() - start_time).total_seconds()
        memory_usage = combined_df.memory_usage(deep=True).sum() / (1024 * 1024)
        
        # Count attack types
        attack_counts = {}
        if 'attack_cat' in combined_df.columns:
            attack_counts = combined_df['attack_cat'].value_counts().to_dict()
        
        stats = DatasetStats(
            name="UNSW-NB15",
            total_records=len(combined_df),
            features=len(combined_df.columns),
            attack_types=list(attack_counts.keys()),
            benign_count=len(combined_df[combined_df['label'] == 0]) if 'label' in combined_df.columns else 0,
            malicious_count=len(combined_df[combined_df['label'] == 1]) if 'label' in combined_df.columns else 0,
            processing_time_seconds=processing_time,
            memory_usage_mb=memory_usage
        )
        
        self._save_stats(stats)
        return stats
    
    def extract_features(self) -> FeatureSet:
        """Extract features for anomaly detection."""
        log.info(f"Extracting features from UNSW-NB15")
        
        # Load processed data
        processed_file = self.processed_dir / "unsw_nb15_processed.csv"
        if not processed_file.exists():
            raise FileNotFoundError(f"Processed file not found: {processed_file}")
        
        df = pd.read_csv(processed_file, low_memory=False)
        
        # Select features (based on UNSW-NB15 documentation)
        # Basic network features
        basic_features = [
            'dur', 'proto', 'service', 'state', 'spkts', 'dpkts',
            'sbytes', 'dbytes', 'rate', 'sttl', 'dttl', 'sload', 'dload',
            'sloss', 'dloss', 'sinpkt', 'dinpkt', 'sjit', 'djit',
            'swin', 'stcpb', 'dtcpb', 'dwin', 'tcprtt', 'synack', 'ackdat'
        ]
        
        # Content features
        content_features = [
            'smean', 'dmean', 'trans_depth', 'response_body_len',
            'ct_srv_src', 'ct_state_ttl', 'ct_dst_ltm', 'ct_src_dport_ltm',
            'ct_dst_sport_ltm', 'ct_dst_src_ltm'
        ]
        
        # Time-based features
        time_features = [
            'is_ftp_login', 'ct_ftp_cmd', 'ct_flw_http_mthd', 'ct_src_ltm',
            'ct_srv_dst'
        ]
        
        # Additional engineered features
        additional_features = [
            'attack_cat', 'label'  # Labels
        ]
        
        all_features = basic_features + content_features + time_features
        
        # Check which features exist in the dataset
        available_features = [f for f in all_features if f in df.columns]
        log.info(f"Available features: {len(available_features)}/{len(all_features)}")
        
        # Prepare feature matrix
        X = df[available_features].copy()
        
        # Convert categorical features to numeric
        categorical_cols = X.select_dtypes(include=['object']).columns
        for col in categorical_cols:
            X[col] = pd.factorize(X[col])[0]
        
        # Handle any remaining NaN values
        X = X.fillna(0)
        
        # Get labels
        if 'label' in df.columns:
            y = df['label'].values
            label_names = ['benign', 'malicious']
        else:
            # Create synthetic labels for demonstration
            y = np.zeros(len(X))
            label_names = ['benign']
        
        # Create feature set
        feature_set = FeatureSet(
            name="unsw_nb15_features",
            features=available_features,
            feature_matrix=X.values,
            labels=y,
            label_names=label_names
        )
        
        # Save feature set
        feature_set.save(self.features_dir)
        
        log.info(f"Extracted {len(available_features)} features from {len(X)} samples")
        return feature_set


class KDDCup99Processor(DatasetProcessor):
    """Processor for KDD Cup 1999 dataset (backup option)."""
    
    def __init__(self):
        super().__init__("kdd_cup_99")
    
    def process(self) -> DatasetStats:
        """Process KDD Cup 1999 dataset."""
        log.info(f"Processing KDD Cup 1999 dataset")
        start_time = datetime.now()
        
        # Find data file
        data_files = list(self.raw_dir.glob("kddcup.data*"))
        if not data_files:
            raise FileNotFoundError(f"No KDD Cup data files found in {self.raw_dir}")
        
        data_file = data_files[0]
        
        # Load column names
        names_file = self.raw_dir / "kddcup.names"
        if names_file.exists():
            with open(names_file, 'r') as f:
                lines = f.readlines()
            
            # Parse column names (skip comments and empty lines)
            column_names = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith('|'):
                    column_names.append(line.split(':')[0])
            
            # Last column is the label
            column_names.append('label')
        else:
            # Use standard KDD Cup column names
            column_names = [
                'duration', 'protocol_type', 'service', 'flag', 'src_bytes',
                'dst_bytes', 'land', 'wrong_fragment', 'urgent', 'hot',
                'num_failed_logins', 'logged_in', 'num_compromised',
                'root_shell', 'su_attempted', 'num_root', 'num_file_creations',
                'num_shells', 'num_access_files', 'num_outbound_cmds',
                'is_host_login', 'is_guest_login', 'count', 'srv_count',
                'serror_rate', 'srv_serror_rate', 'rerror_rate',
                'srv_rerror_rate', 'same_srv_rate', 'diff_srv_rate',
                'srv_diff_host_rate', 'dst_host_count', 'dst_host_srv_count',
                'dst_host_same_srv_rate', 'dst_host_diff_srv_rate',
                'dst_host_same_src_port_rate', 'dst_host_srv_diff_host_rate',
                'dst_host_serror_rate', 'dst_host_srv_serror_rate',
                'dst_host_rerror_rate', 'dst_host_srv_rerror_rate', 'label'
            ]
        
        # Load data
        log.info(f"Loading {data_file.name}...")
        df = pd.read_csv(data_file, header=None, names=column_names, low_memory=False)
        
        log.info(f"Original shape: {df.shape}")
        
        # Basic cleaning
        df = df.drop_duplicates()
        log.info(f"After removing duplicates: {df.shape}")
        
        # Handle missing values
        df = df.fillna(0)
        
        # Save processed data
        processed_file = self.processed_dir / "kddcup_processed.csv"
        df.to_csv(processed_file, index=False)
        log.info(f"Saved processed data to {processed_file}")
        
        # Calculate statistics
        processing_time = (datetime.now() - start_time).total_seconds()
        memory_usage = df.memory_usage(deep=True).sum() / (1024 * 1024)
        
        # Count attack types
        attack_counts = df['label'].value_counts().to_dict()
        
        # Classify as benign/malicious
        benign_labels = ['normal']
        benign_count = sum(count for label, count in attack_counts.items() 
                          if label in benign_labels)
        malicious_count = len(df) - benign_count
        
        stats = DatasetStats(
            name="KDD Cup 1999",
            total_records=len(df),
            features=len(df.columns) - 1,  # Exclude label
            attack_types=list(attack_counts.keys()),
            benign_count=benign_count,
            malicious_count=malicious_count,
            processing_time_seconds=processing_time,
            memory_usage_mb=memory_usage
        )
        
        self._save_stats(stats)
        return stats
    
    def extract_features(self) -> FeatureSet:
        """Extract features from KDD Cup 1999."""
        log.info(f"Extracting features from KDD Cup 1999")
        
        # Load processed data
        processed_file = self.processed_dir / "kddcup_processed.csv"
        if not processed_file.exists():
            raise FileNotFoundError(f"Processed file not found: {processed_file}")
        
        df = pd.read_csv(processed_file, low_memory=False)
        
        # Select features (basic network features from KDD Cup)
        basic_features = [
            'duration', 'src_bytes', 'dst_bytes', 'wrong_fragment', 'urgent',
            'hot', 'num_failed_logins', 'logged_in', 'num_compromised',
            'root_shell', 'su_attempted', 'num_root', 'num_file_creations',
            'num_shells', 'num_access_files', 'num_outbound_cmds',
            'is_host_login', 'is_guest_login', 'count', 'srv_count',
            'serror_rate', 'srv_serror_rate', 'rerror_rate', 'srv_rerror_rate',
            'same_srv_rate', 'diff_srv_rate', 'srv_diff_host_rate',
            'dst_host_count', 'dst_host_srv_count', 'dst_host_same_srv_rate',
            'dst_host_diff_srv_rate', 'dst_host_same_src_port_rate',
            'dst_host_srv_diff_host_rate', 'dst_host_serror_rate',
            'dst_host_srv_serror_rate', 'dst_host_rerror_rate',
            'dst_host_srv_rerror_rate'
        ]
        
        # Categorical features (will be encoded)
        categorical_features = ['protocol_type', 'service', 'flag']
        
        # Check which features exist
        available_features = [f for f in basic_features + categorical_features 
                            if f in df.columns]
        log.info(f"Available features: {len(available_features)}")
        
        # Prepare feature matrix
        X = df[available_features].copy()
        
        # Convert categorical features
        categorical_cols = X.select_dtypes(include=['object']).columns
        for col in categorical_cols:
            X[col] = pd.factorize(X[col])[0]
        
        # Handle NaN values
        X = X.fillna(0)
        
        # Get labels (convert to binary: normal=0, attack=1)
        if 'label' in df.columns:
            y = df['label'].apply(lambda x: 0 if x == 'normal' else 1).values
            label_names = ['benign', 'malicious']
        else:
            y = np.zeros(len(X))
            label_names = ['benign']
        
        # Create feature set
        feature_set = FeatureSet(
            name="kddcup_features",
            features=available_features,
            feature_matrix=X.values,
            labels=y,
            label_names=label_names
        )
        
        # Save feature set
        feature_set.save(self.features_dir)
        
        log.info(f"Extracted {len(available_features)} features from {len(X)} samples")
        return feature_set


# ---------------------------------------------------------------------------
# Main Processor
# ---------------------------------------------------------------------------

class SecurityDatasetProcessor:
    """Main processor for all security datasets."""
    
    def __init__(self):
        self.processors = {
            "unsw_nb15": UNSWNB15Processor(),
            "kdd_cup_99": KDDCup99Processor(),
            # Add more processors as datasets become available
        }
        
        log.info(f"Security Dataset Processor initialized")
        log.info(f"Available processors: {list(self.processors.keys())}")
    
    def process_dataset(self, dataset_id: str) -> Optional[DatasetStats]:
        """Process a specific dataset."""
        if dataset_id not in self.processors:
            log.error(f"No processor available for dataset: {dataset_id}")
            return None
        
        processor = self.processors[dataset_id]
        
        try:
            log.info(f"Processing dataset: {dataset_id}")
            stats = processor.process()
            log.info(f"Successfully processed {dataset_id}: {stats.total_records} records")
            return stats
        except Exception as e:
            log.error(f"Error processing {dataset_id}: {e}")
            return None
    
    def extract_features(self, dataset_id: str) -> Optional[FeatureSet]:
        """Extract features from a processed dataset."""
        if dataset_id not in self.processors:
            log.error(f"No processor available for dataset: {dataset_id}")
            return None
        
        processor = self.processors[dataset_id]
        
        try:
            log.info(f"Extracting features from: {dataset_id}")
            feature_set = processor.extract_features()
            log.info(f"Successfully extracted features from {dataset_id}")
            return feature_set
        except Exception as e:
            log.error(f"Error extracting features from {dataset_id}: {e}")
            return None
    
    def process_all(self) -> Dict[str, DatasetStats]:
        """Process all available datasets."""
        results = {}
        
        log.info(f"Processing all datasets")
        
        for dataset_id, processor in self.processors.items():
            try:
                stats = self.process_dataset(dataset_id)
                if stats:
                    results[dataset_id] = stats
                    log.info(f"✓ {dataset_id}: Processed {stats.total_records} records")
                else:
                    log.warning(f"✗ {dataset_id}: Processing failed")
            except Exception as e:
                log.error(f"✗ {dataset_id}: Error - {e}")
        
        # Generate summary
        self._generate_summary(results)
        
        return results
    
    def extract_all_features(self) -> Dict[str, FeatureSet]:
        """Extract features from all processed datasets."""
        results = {}
        
        log.info(f"Extracting features from all datasets")
        
        for dataset_id in self.processors.keys():
            try:
                feature_set = self.extract_features(dataset_id)
                if feature_set:
                    results[dataset_id] = feature_set
                    log.info(f"✓ {dataset_id}: Extracted {len(feature_set.features)} features")
                else:
                    log.warning(f"✗ {dataset_id}: Feature extraction failed")
            except Exception as e:
                log.error(f"✗ {dataset_id}: Error - {e}")
        
        return results
    
    def _generate_summary(self, results: Dict[str, DatasetStats]):
        """Generate processing summary."""
        total_records = sum(stats.total_records for stats in results.values())
        total_features = sum(stats.features for stats in results.values())
        
        log.info("=" * 60)
        log.info("PROCESSING SUMMARY")
        log.info("=" * 60)
        log.info(f"Total datasets processed: {len(results)}")
        log.info(f"Total records: {total_records:,}")
        log.info(f"Total features extracted: {total_features}")
        log.info("=" * 60)
        
        # Save summary to file
        summary_file = DATA_DIR / "processing_summary.json"
        summary = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "total_datasets": len(results),
            "total_records": total_records,
            "total_features": total_features,
            "results": {k: stats.to_dict() for k, stats in results.items()}
        }
        
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        log.info(f"Summary saved to: {summary_file}")
    
    def get_status(self) -> Dict:
        """Get current processing status."""
        status = {
            "total_datasets": len(self.processors),
            "processed_datasets": 0,
            "features_extracted": 0,
            "total_records": 0
        }
        
        for dataset_id in self.processors.keys():
            processed_dir = PROCESSED_DIR / dataset_id
            features_dir = FEATURES_DIR / dataset_id
            
            if processed_dir.exists() and list(processed_dir.glob("*.csv")):
                status["processed_datasets"] += 1
            
            if features_dir.exists() and list(features_dir.glob("*.npy")):
                status["features_extracted"] += 1
        
        return status


# ---------------------------------------------------------------------------
# Command Line Interface
# ---------------------------------------------------------------------------

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Bill Russell Protocol - Dataset Processor"
    )
    parser.add_argument(
        "--dataset",
        choices=["unsw_nb15", "kdd_cup_99", "all"],
        default="all",
        help="Dataset to process (default: all)"
    )
    parser.add_argument(
        "--extract-features",
        action="store_true",
        help="Extract features after processing"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show processing status only"
    )
    
    args = parser.parse_args()
    
    # Initialize processor
    processor = SecurityDatasetProcessor()
    
    if args.status:
        status = processor.get_status()
        print("\n" + "=" * 60)
        print("BILL RUSSELL PROTOCOL - PROCESSING STATUS")
        print("=" * 60)
        print(f"Total datasets: {status['total_datasets']}")
        print(f"Datasets processed: {status['processed_datasets']}")
        print(f"Features extracted: {status['features_extracted']}")
        print("=" * 60)
        return
    
    # Process datasets
    if args.dataset == "all":
        results = processor.process_all()
        if args.extract_features:
            feature_results = processor.extract_all_features()
    else:
        results = {}
        stats = processor.process_dataset(args.dataset)
        if stats:
            results[args.dataset] = stats
        
        if args.extract_features:
            feature_set = processor.extract_features(args.dataset)
    
    # Print final status
    status = processor.get_status()
    print(f"\nFinal status: {status['processed_datasets']}/{status['total_datasets']} datasets processed")


if __name__ == "__main__":
    main()