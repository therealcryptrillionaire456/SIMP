#!/usr/bin/env python3
import PyPDF2
import re
import json
from collections import defaultdict

def analyze_pdf_structure(pdf_path):
    """Analyze PDF structure and extract key sections."""
    with open(pdf_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        
        # Extract all text
        all_text = []
        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            text = page.extract_text()
            if text.strip():
                all_text.append({
                    'page': page_num + 1,
                    'text': text
                })
        
        # Combine all text for analysis
        full_text = "\n".join([page['text'] for page in all_text])
        
        # Look for section headers (patterns like "1. ", "1.1 ", "2. ", etc.)
        section_pattern = r'\n(\d+(?:\.\d+)*\s+[A-Z][^\n]+)'
        sections = re.findall(section_pattern, full_text)
        
        # Look for table of contents patterns
        toc_pattern = r'(\d+(?:\.\d+)*\s+[^\n]+\s+\d+)'
        toc_entries = re.findall(toc_pattern, full_text[:5000])  # First few pages
        
        # Extract key findings patterns
        findings_patterns = [
            r'Key findings[^\n]*',
            r'Summary of findings[^\n]*',
            r'Conclusion[^\n]*',
            r'Overall risk[^\n]*',
            r'Capability[^\n]*',
            r'Limitation[^\n]*'
        ]
        
        findings = []
        for pattern in findings_patterns:
            matches = re.findall(pattern, full_text, re.IGNORECASE)
            findings.extend(matches)
        
        # Extract risk assessments
        risk_patterns = [
            r'Risk assessment[^\n]*',
            r'Threat model[^\n]*',
            r'CB-[12][^\n]*',
            r'Autonomy threat[^\n]*',
            r'RSP[^\n]*'
        ]
        
        risks = []
        for pattern in risk_patterns:
            matches = re.findall(pattern, full_text, re.IGNORECASE)
            risks.extend(matches)
        
        # Extract evaluation results
        eval_patterns = [
            r'evaluation[^\n]*results[^\n]*',
            r'score[^\n]*',
            r'performance[^\n]*',
            r'benchmark[^\n]*',
            r'threshold[^\n]*'
        ]
        
        evaluations = []
        for pattern in eval_patterns:
            matches = re.findall(pattern, full_text, re.IGNORECASE)
            evaluations.extend(matches)
        
        # Get document metadata
        metadata = pdf_reader.metadata
        
        # Analyze document structure
        structure = {
            'total_pages': len(pdf_reader.pages),
            'pages_with_text': len(all_text),
            'estimated_sections': len(sections),
            'toc_entries_found': len(toc_entries),
            'key_findings_count': len(findings),
            'risk_assessments_count': len(risks),
            'evaluations_count': len(evaluations)
        }
        
        # Sample content from different parts
        sample_content = {
            'beginning': full_text[:2000],
            'middle': full_text[len(full_text)//2:len(full_text)//2 + 2000],
            'end': full_text[-2000:]
        }
        
        # Extract model name and version
        model_name_match = re.search(r'Claude\s+([^\s]+)', full_text[:1000])
        model_name = model_name_match.group(0) if model_name_match else "Unknown"
        
        # Extract date
        date_match = re.search(r'April\s+\d+,\s+2026', full_text[:1000])
        date = date_match.group(0) if date_match else "Unknown"
        
        return {
            'metadata': metadata,
            'structure': structure,
            'model_info': {
                'name': model_name,
                'date': date
            },
            'sections_sample': sections[:20],  # First 20 sections
            'toc_sample': toc_entries[:10],    # First 10 TOC entries
            'key_findings_sample': findings[:10],
            'risk_assessments_sample': risks[:10],
            'evaluations_sample': evaluations[:10],
            'content_samples': sample_content
        }

def generate_report(analysis):
    """Generate a comprehensive report from analysis."""
    report = []
    
    report.append("=" * 80)
    report.append("CLAUDE MYTHOS PREVIEW SYSTEM CARD ANALYSIS")
    report.append("=" * 80)
    report.append("")
    
    # Document info
    report.append("DOCUMENT INFORMATION")
    report.append("-" * 40)
    report.append(f"Model: {analysis['model_info']['name']}")
    report.append(f"Date: {analysis['model_info']['date']}")
    report.append(f"Total pages: {analysis['structure']['total_pages']}")
    report.append(f"Pages with text: {analysis['structure']['pages_with_text']}")
    report.append("")
    
    # Metadata
    report.append("PDF METADATA")
    report.append("-" * 40)
    for key, value in analysis['metadata'].items():
        report.append(f"{key}: {value}")
    report.append("")
    
    # Structure
    report.append("DOCUMENT STRUCTURE")
    report.append("-" * 40)
    report.append(f"Estimated sections: {analysis['structure']['estimated_sections']}")
    report.append(f"TOC entries found: {analysis['structure']['toc_entries_found']}")
    report.append(f"Key findings: {analysis['structure']['key_findings_count']}")
    report.append(f"Risk assessments: {analysis['structure']['risk_assessments_count']}")
    report.append(f"Evaluations: {analysis['structure']['evaluations_count']}")
    report.append("")
    
    # Sections
    report.append("MAIN SECTIONS (sample)")
    report.append("-" * 40)
    for i, section in enumerate(analysis['sections_sample'][:15], 1):
        report.append(f"{i}. {section}")
    report.append("")
    
    # Key findings
    report.append("KEY FINDINGS (sample)")
    report.append("-" * 40)
    for i, finding in enumerate(analysis['key_findings_sample'], 1):
        report.append(f"{i}. {finding}")
    report.append("")
    
    # Risk assessments
    report.append("RISK ASSESSMENTS (sample)")
    report.append("-" * 40)
    for i, risk in enumerate(analysis['risk_assessments_sample'], 1):
        report.append(f"{i}. {risk}")
    report.append("")
    
    # Evaluations
    report.append("EVALUATIONS (sample)")
    report.append("-" * 40)
    for i, eval_item in enumerate(analysis['evaluations_sample'], 1):
        report.append(f"{i}. {eval_item}")
    report.append("")
    
    # Content samples
    report.append("DOCUMENT CONTENT SAMPLES")
    report.append("=" * 80)
    
    report.append("\nBEGINNING OF DOCUMENT:")
    report.append("-" * 40)
    report.append(analysis['content_samples']['beginning'][:1000])
    
    report.append("\n\nMIDDLE OF DOCUMENT:")
    report.append("-" * 40)
    report.append(analysis['content_samples']['middle'][:1000])
    
    report.append("\n\nEND OF DOCUMENT:")
    report.append("-" * 40)
    report.append(analysis['content_samples']['end'][:1000])
    
    return "\n".join(report)

if __name__ == "__main__":
    pdf_path = "/Users/kaseymarcelle/Documents/claude system card txt.pdf"
    
    print("Analyzing PDF structure...")
    analysis = analyze_pdf_structure(pdf_path)
    
    print("Generating report...")
    report = generate_report(analysis)
    
    # Save report
    with open("claude_system_card_report.txt", "w") as f:
        f.write(report)
    
    print(f"Report saved to: claude_system_card_report.txt")
    
    # Also save JSON for programmatic access
    with open("claude_system_card_analysis.json", "w") as f:
        json.dump(analysis, f, indent=2, default=str)
    
    print(f"Analysis saved to: claude_system_card_analysis.json")