import pypdf

def extract_pdf():
    reader = pypdf.PdfReader("AI_Engineer_Assessment_ (1).pdf")
    print(f"Total pages: {len(reader.pages)}")
    with open("requirements_extracted.txt", "w", encoding="utf-8") as f:
        for idx, page in enumerate(reader.pages):
            text = page.extract_text()
            f.write(f"--- PAGE {idx + 1} ---\n")
            f.write(text)
            f.write("\n\n")
    print("Done! Extracted text written to requirements_extracted.txt")

if __name__ == "__main__":
    extract_pdf()
