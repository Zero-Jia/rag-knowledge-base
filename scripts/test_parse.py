from app.services.document_parser import parse_document

text = parse_document("storage/uploads/1/1/test.pdf", "application/pdf")
print(text[:500])


