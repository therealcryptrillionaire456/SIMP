#!/usr/bin/env python3
import PyPDF2
import sys
import json

def parse_pdf(pdf_path):
    """Parse PDF file and extract text content."""
    try:
        print(f"Opening PDF file: {pdf_path}")
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            num_pages = len(pdf_reader.pages)
            print(f"Number of pages: {num_pages}")
            
            # Extract metadata
            metadata = pdf_reader.metadata
            print(f"PDF Metadata: {metadata}")
            
            # Extract text from each page
            all_text = []
            for page_num in range(num_pages):
                page = pdf_reader.pages[page_num]
                text = page.extract_text()
                if text.strip():  # Only add non-empty pages
                    all_text.append({
                        'page': page_num + 1,
                        'text': text.strip()
                    })
            
            # Analyze content
            total_chars = sum(len(page['text']) for page in all_text)
            total_words = sum(len(page['text'].split()) for page in all_text)
            
            print(f"\n=== PDF Analysis Summary ===")
            print(f"Total pages with text: {len(all_text)}")
            print(f"Total characters: {total_chars}")
            print(f"Total words: {total_words}")
            
            # Show first few lines from first few pages to get sense of content
            print(f"\n=== Sample Content (first 3 pages) ===")
            for i in range(min(3, len(all_text))):
                page_data = all_text[i]
                preview = page_data['text'][:500] + "..." if len(page_data['text']) > 500 else page_data['text']
                print(f"\n--- Page {page_data['page']} ---")
                print(preview)
            
            # Try to identify structure
            print(f"\n=== Content Structure Analysis ===")
            lines_by_page = []
            for page_data in all_text[:5]:  # First 5 pages
                lines = page_data['text'].split('\n')
                lines_by_page.append({
                    'page': page_data['page'],
                    'line_count': len(lines),
                    'first_few_lines': lines[:5]
                })
            
            for page_info in lines_by_page:
                print(f"\nPage {page_info['page']}: {page_info['line_count']} lines")
                for i, line in enumerate(page_info['first_few_lines'][:3]):
                    print(f"  Line {i+1}: {line[:80]}..." if len(line) > 80 else f"  Line {i+1}: {line}")
            
            return {
                'metadata': metadata,
                'pages': all_text,
                'stats': {
                    'total_pages': num_pages,
                    'pages_with_text': len(all_text),
                    'total_chars': total_chars,
                    'total_words': total_words
                }
            }
            
    except Exception as e:
        print(f"Error parsing PDF: {e}")
        return None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python parse_pdf.py <pdf_file_path>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    result = parse_pdf(pdf_path)
    
    # Save full text to file for reference
    if result:
        output_file = "pdf_analysis.json"
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\nFull analysis saved to: {output_file}")