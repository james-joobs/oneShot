#!/usr/bin/env python3

import os
import argparse
from photo_curator import PhotoCurator

def main():
    parser = argparse.ArgumentParser(description='Travel Photo Curation System')
    parser.add_argument('--data_folder', type=str, default='../data/', 
                      help='Path to folder containing images')
    parser.add_argument('--similarity_threshold', type=float, default=0.85,
                      help='Similarity threshold for duplicate detection (0.0-1.0)')
    parser.add_argument('--save_model', type=str, default=None,
                      help='Path to save model for TFLite conversion')
    
    args = parser.parse_args()
    
    data_folder = os.path.abspath(args.data_folder)
    
    if not os.path.exists(data_folder):
        print(f"Error: Data folder '{data_folder}' not found!")
        return
    
    print("Starting Travel Photo Curation System")
    print(f"Data folder: {data_folder}")
    print(f"Similarity threshold: {args.similarity_threshold}")
    
    curator = PhotoCurator(similarity_threshold=args.similarity_threshold)
    
    results = curator.process_photos(data_folder)
    
    if "error" in results:
        print(f"Error: {results['error']}")
        return
    
    curator.print_summary(results)
    
    if args.save_model:
        curator.save_model_for_tflite(args.save_model)

if __name__ == "__main__":
    main()