from docling.document_converter import DocumentConverter

converter = DocumentConverter()
result = converter.convert("data/raw/IPCC_AR6_WGI_SPM-25-29.pdf")
print("Conversion completed successfully!")

print("TYPE DE RESULT")
print(type(result))

print("\nATTRIBUTS DE RESULT")
print(vars(result).keys())

print("\nTYPE DE DOCUMENT")
print(type(result.document))

print("\nATTRIBUTS DU DOCUMENT")
print(vars(result.document).keys())

print("\nNOMBRE DE PAGES")
print(len(result.document.pages))

for page_no, page in result.document.pages.items():
    print(page_no, page)

# Export Markdown
markdown = result.document.export_to_markdown()

with open("ipcc_report.md", "w", encoding="utf-8") as f:
    f.write(markdown)
