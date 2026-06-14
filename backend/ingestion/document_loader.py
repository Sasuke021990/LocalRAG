"""
Document loader module for parsing various file formats.
This module handles reading and extracting text content from different document types.
"""

import os
import logging
from typing import Dict, Any, Optional
from pathlib import Path

# Import libraries for different file types
try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    logging.warning("PyPDF2 not available for PDF processing")

try:
    from docx import Document as DocxDocument
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    logging.warning("python-docx not available for DOCX processing")

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    logging.warning("pandas not available for CSV processing")

# Configure logging
logger = logging.getLogger(__name__)

class DocumentLoader:
    """
    A class to load and parse documents from various file formats.
    Supports PDF, DOCX, TXT, CSV, and other common document types.
    """
    
    def __init__(self):
        """Initialize the document loader with available parsers."""
        self.supported_formats = {
            '.pdf': self._load_pdf,
            '.txt': self._load_txt,
            '.docx': self._load_docx,
            '.csv': self._load_csv,
            '.md': self._load_txt,
            '.html': self._load_html,
            '.htm': self._load_html,
            '.json': self._load_json,
            '.xml': self._load_xml
        }
        
    def load_document(self, file_path: str) -> Dict[str, Any]:
        """
        Load and parse a document file.
        
        Args:
            file_path (str): Path to the document file
            
        Returns:
            Dict containing document content and metadata
            
        Raises:
            ValueError: If file format is not supported or file cannot be read
        """
        try:
            # Get file extension
            file_ext = os.path.splitext(file_path)[1].lower()
            
            # Check if we have a parser for this format
            if file_ext not in self.supported_formats:
                raise ValueError(f"Unsupported file format: {file_ext}")
            
            # Load the document using appropriate parser
            content = self.supported_formats[file_ext](file_path)
            
            return {
                "content": content,
                "metadata": {
                    "filename": os.path.basename(file_path),
                    "format": file_ext,
                    "size": os.path.getsize(file_path),
                    "loaded_at": self._get_current_timestamp()
                }
            }
            
        except Exception as e:
            logger.error(f"Error loading document {file_path}: {str(e)}")
            raise ValueError(f"Failed to load document: {str(e)}")
    
    def _load_pdf(self, file_path: str) -> str:
        """
        Load and extract text from a PDF file.
        
        Args:
            file_path (str): Path to the PDF file
            
        Returns:
            Extracted text content
        """
        if not PDF_AVAILABLE:
            raise ImportError("PyPDF2 is required for PDF processing")
            
        try:
            text_content = []
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text_content.append(page.extract_text())
            
            return '\n'.join(text_content)
            
        except Exception as e:
            raise ValueError(f"Error reading PDF file: {str(e)}")
    
    def _load_txt(self, file_path: str) -> str:
        """
        Load and read text from a TXT file.
        
        Args:
            file_path (str): Path to the TXT file
            
        Returns:
            Text content
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read()
        except UnicodeDecodeError:
            # Try different encodings if UTF-8 fails
            try:
                with open(file_path, 'r', encoding='latin-1') as file:
                    return file.read()
            except Exception as e:
                raise ValueError(f"Error reading TXT file with multiple encodings: {str(e)}")
        except Exception as e:
            raise ValueError(f"Error reading TXT file: {str(e)}")
    
    def _load_docx(self, file_path: str) -> str:
        """
        Load and extract text from a DOCX file.
        
        Args:
            file_path (str): Path to the DOCX file
            
        Returns:
            Extracted text content
        """
        if not DOCX_AVAILABLE:
            raise ImportError("python-docx is required for DOCX processing")
            
        try:
            doc = DocxDocument(file_path)
            paragraphs = [paragraph.text for paragraph in doc.paragraphs]
            return '\n'.join(paragraphs)
        except Exception as e:
            raise ValueError(f"Error reading DOCX file: {str(e)}")
    
    def _load_csv(self, file_path: str) -> str:
        """
        Load and extract text from a CSV file.
        
        Args:
            file_path (str): Path to the CSV file
            
        Returns:
            Text content with CSV data
        """
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas is required for CSV processing")
            
        try:
            # Read CSV file
            df = pd.read_csv(file_path)
            
            # Convert to string representation
            return df.to_string(index=False)
        except Exception as e:
            raise ValueError(f"Error reading CSV file: {str(e)}")
    
    def _load_html(self, file_path: str) -> str:
        """
        Load and extract text from an HTML file.
        
        Args:
            file_path (str): Path to the HTML file
            
        Returns:
            Extracted text content
        """
        try:
            from bs4 import BeautifulSoup
            
            with open(file_path, 'r', encoding='utf-8') as file:
                soup = BeautifulSoup(file, 'html.parser')
                
                # Remove script and style elements
                for script in soup(["script", "style"]):
                    script.decompose()
                
                # Get text and clean it up
                text = soup.get_text()
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                text = ' '.join(chunk for chunk in chunks if chunk)
                
                return text
        except ImportError:
            raise ImportError("beautifulsoup4 is required for HTML processing")
        except Exception as e:
            raise ValueError(f"Error reading HTML file: {str(e)}")
    
    def _load_json(self, file_path: str) -> str:
        """
        Load and extract text from a JSON file.
        
        Args:
            file_path (str): Path to the JSON file
            
        Returns:
            Text content with JSON data
        """
        try:
            import json
            
            with open(file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
                return str(data)  # Convert to string representation
        except Exception as e:
            raise ValueError(f"Error reading JSON file: {str(e)}")
    
    def _load_xml(self, file_path: str) -> str:
        """
        Load and extract text from an XML file.
        
        Args:
            file_path (str): Path to the XML file
            
        Returns:
            Extracted text content
        """
        try:
            from xml.etree import ElementTree as ET
            
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            # Extract all text from XML elements
            text_content = []
            for elem in root.iter():
                if elem.text:
                    text_content.append(elem.text.strip())
                if elem.tail:
                    text_content.append(elem.tail.strip())
            
            return '\n'.join(text_content)
        except Exception as e:
            raise ValueError(f"Error reading XML file: {str(e)}")
    
    def _get_current_timestamp(self) -> str:
        """
        Get current timestamp in ISO format.
        
        Returns:
            Current timestamp as string
        """
        from datetime import datetime
        return datetime.now().isoformat()