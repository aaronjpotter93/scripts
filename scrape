import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# URL of the page to scrape
url = "https://andrews.edu/~rwright/precal/notes/notes.php"

# Directory to save PDFs
output_dir = "pdfs"
os.makedirs(output_dir, exist_ok=True)

# Fetch the content from the URL
response = requests.get(url)
soup = BeautifulSoup(response.content, "html.parser")

# Find all links ending with .pdf
pdf_links = soup.find_all("a", href=lambda href: href and href.endswith(".pdf"))

for link in pdf_links:
    # Get the full URL
    pdf_url = urljoin(url, link.get("href"))
    # Get the PDF file name
    pdf_name = os.path.join(output_dir, os.path.basename(pdf_url))

    # Download the PDF
    print(f"Downloading {pdf_name}...")
    pdf_response = requests.get(pdf_url)
    with open(pdf_name, "wb") as pdf_file:
        pdf_file.write(pdf_response.content)

print("Download complete.")
